#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Мікросервіс для аналізу партнерських/конкурентних сайтів
REST API на базі FastAPI
"""

import os
import sys
sys.path.append('/app')

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Dict, Optional
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from openai import OpenAI
import re
from urllib.parse import urljoin, urlparse
import json
import time
from dataclasses import dataclass, asdict
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from collections import defaultdict
import uuid
from datetime import datetime

# Локальні імпорти
from shared.logger import setup_logger
from shared.database import db_manager
from shared.redis_client import analysis_redis, analysis_cache
from shared.utils import generate_task_id, clean_url, ProgressTracker

# Налаштування логування
logger = setup_logger('analysis_service')

# Pydantic моделі для API
class AnalysisRequest(BaseModel):
    site_url: HttpUrl = Field(..., description="URL сайту для аналізу")
    positive_keywords: List[str] = Field(..., description="Позитивні ключові слова")
    negative_keywords: List[str] = Field(..., description="Негативні ключові слова")
    max_time_minutes: int = Field(default=20, ge=1, le=60, description="Максимальний час аналізу (хв)")
    max_links: int = Field(default=300, ge=10, le=1000, description="Максимальна кількість посилань")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API ключ")

class AnalysisStatus(BaseModel):
    task_id: str
    status: str  # "pending", "running", "completed", "failed"
    progress: int  # 0-100
    message: str
    started_at: datetime
    completed_at: Optional[datetime] = None

class KeywordMatch(BaseModel):
    keyword: str
    url: str
    count: int
    context: str

class AnalysisResult(BaseModel):
    task_id: str
    site_url: str
    status: str
    pages_analyzed: int
    positive_matches: List[KeywordMatch]
    negative_matches: List[KeywordMatch]
    ai_analysis: Optional[str]
    analysis_time: float
    pages_with_positive: List[str]
    pages_with_negative: List[str]
    summary_stats: Dict[str, int]
    detailed_stats: Dict
    completed_at: datetime

@dataclass
class SimpleAnalysisResult:
    """Результат аналізу сайту"""
    site_url: str
    pages_analyzed: int
    keyword_table: pd.DataFrame
    forbidden_table: pd.DataFrame
    ai_analysis: str
    analysis_time: float
    pages_with_keywords: List[str]
    pages_with_forbidden: List[str]
    detailed_stats: Dict

class AsyncPartnerSiteAnalyzer:
    def __init__(self, openai_api_key: str = None, max_workers: int = 5):
        """
        Ініціалізація асинхронного аналізатора
        """
        self.openai_api_key = openai_api_key
        if openai_api_key:
            self.client = OpenAI(api_key=openai_api_key)
        else:
            self.client = None
            
        self.max_workers = max_workers
        self.lock = threading.Lock()
        
        # Налаштування сесії
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
    async def find_all_links(self, base_url: str, max_links: int = 300) -> set:
        """
        Асинхронно знаходить всі посилання на сайті
        """
        logger.info(f"🔍 Шукаємо посилання на {base_url}")
        
        domain = urlparse(base_url).netloc.replace('www.', '')
        found_links = set()
        links_to_check = {base_url}
        checked_links = set()
        
        # Додаємо варіанти головної сторінки
        variations = [
            f"https://{domain}",
            f"https://www.{domain}",
            f"http://{domain}",
            f"http://www.{domain}"
        ]
        links_to_check.update(variations)
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            while links_to_check and len(found_links) < max_links:
                current_url = links_to_check.pop()
                
                if current_url in checked_links:
                    continue
                    
                checked_links.add(current_url)
                
                try:
                    logger.info(f"📄 Сканую: {current_url}")
                    async with session.get(current_url, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            soup = BeautifulSoup(content, 'html.parser')
                            
                            # Знаходимо всі посилання
                            for link in soup.find_all('a', href=True):
                                href = link['href']
                                full_url = urljoin(current_url, href)
                                parsed_url = urlparse(full_url)
                                
                                # Перевіряємо чи посилання з того ж домену
                                if (parsed_url.netloc.endswith(domain) or 
                                    parsed_url.netloc == domain or
                                    parsed_url.netloc == f"www.{domain}"):
                                    
                                    # Фільтруємо небажані посилання
                                    if not any(skip in full_url.lower() for skip in 
                                             ['#', 'javascript:', 'mailto:', 'tel:', '.pdf', '.jpg', 
                                              '.png', '.gif', '.zip', '.rar', '.exe', '.doc', '.docx', 
                                              '.xls', '.xlsx', 'wp-admin', 'wp-content']):
                                        
                                        # Очищуємо URL
                                        clean_url_result = clean_url(full_url)
                                        
                                        if clean_url_result and clean_url_result not in found_links:
                                            found_links.add(clean_url_result)
                                            
                                            # Додаємо до перевірки важливі сторінки
                                            if any(keyword in clean_url_result.lower() for keyword in 
                                                  ['product', 'catalog', 'category', 'товар', 'каталог', 
                                                   'категор', 'новин', 'news', 'about', 'contact']):
                                                if clean_url_result not in checked_links:
                                                    links_to_check.add(clean_url_result)
                    
                    await asyncio.sleep(0.5)  # Пауза між запитами
                    
                except Exception as e:
                    logger.error(f"❌ Помилка при сканування {current_url}: {e}")
                    continue
        
        logger.info(f"✅ Знайдено {len(found_links)} унікальних посилань")
        return found_links
    
    async def scrape_page_content(self, session: aiohttp.ClientSession, url: str) -> tuple:
        """
        Асинхронно скрапить контент однієї сторінки
        """
        try:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    content = await response.text()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Видаляємо непотрібні елементи
                    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                        element.decompose()
                    
                    # Витягуємо текст
                    text_content = soup.get_text(separator=' ', strip=True)
                    text_content = re.sub(r'\s+', ' ', text_content)
                    
                    # Фільтруємо дуже короткі сторінки
                    if len(text_content) < 100:
                        return None, None
                    
                    logger.info(f"✅ Отримано: {url} ({len(text_content)} символів)")
                    return url, text_content
                    
        except Exception as e:
            logger.error(f"❌ Помилка {url}: {e}")
            
        return None, None
    
    async def scrape_all_pages(self, links: set, max_time_minutes: int = 20) -> dict:
        """
        Асинхронно скрапить всі сторінки
        """
        start_time = time.time()
        max_time_seconds = max_time_minutes * 60
        
        logger.info(f"📥 Завантажуємо контент з {len(links)} сторінок...")
        
        pages_content = {}
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = []
            for url in links:
                if time.time() - start_time > max_time_seconds:
                    break
                task = asyncio.create_task(self.scrape_page_content(session, url))
                tasks.append(task)
            
            completed = 0
            for task in asyncio.as_completed(tasks):
                if time.time() - start_time > max_time_seconds:
                    logger.info("⏰ Досягнуто ліміт часу!")
                    break
                
                url, content = await task
                if url and content:
                    pages_content[url] = content
                
                completed += 1
                if completed % 20 == 0:
                    logger.info(f"📊 Оброблено {completed}/{len(links)} сторінок")
        
        logger.info(f"✅ Завантажено контент з {len(pages_content)} сторінок")
        return pages_content
    
    def search_keywords_static(self, pages_content: dict, 
                              keywords: List[str], forbidden_words: List[str]) -> tuple:
        """
        Статичний пошук ключових слів з детальною статистикою
        """
        logger.info("🔍 Статичний пошук ключових слів...")
        
        keyword_data = []
        forbidden_data = []
        
        # Детальна статистика по ключових словах
        keyword_stats = {}
        found_keywords = set()
        
        # Пошук ключових слів
        for keyword in keywords:
            keyword_stats[keyword] = {
                'total_mentions': 0,
                'pages_found': [],
                'contexts': []
            }
            
            for url, content in pages_content.items():
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                matches = pattern.findall(content)
                
                if matches:
                    count = len(matches)
                    context = self._extract_context(content, keyword, 200)
                    found_keywords.add(keyword)
                    
                    # Оновлюємо статистику
                    keyword_stats[keyword]['total_mentions'] += count
                    keyword_stats[keyword]['pages_found'].append({
                        'url': url,
                        'count': count,
                        'context': context
                    })
                    keyword_stats[keyword]['contexts'].append(context)
                    
                    keyword_data.append({
                        'Ключове слово': keyword,
                        'URL': url,
                        'Кількість згадок': count,
                        'Контекст': context
                    })
        
        # Детальна статистика по забороненим словам
        forbidden_stats = {}
        found_forbidden = set()
        
        # Пошук заборонених слів
        for forbidden_word in forbidden_words:
            forbidden_stats[forbidden_word] = {
                'total_mentions': 0,
                'pages_found': [],
                'contexts': []
            }
            
            for url, content in pages_content.items():
                pattern = re.compile(re.escape(forbidden_word), re.IGNORECASE)
                matches = pattern.findall(content)
                
                if matches:
                    count = len(matches)
                    context = self._extract_context(content, forbidden_word, 200)
                    found_forbidden.add(forbidden_word)
                    
                    # Оновлюємо статистику
                    forbidden_stats[forbidden_word]['total_mentions'] += count
                    forbidden_stats[forbidden_word]['pages_found'].append({
                        'url': url,
                        'count': count,
                        'context': context
                    })
                    forbidden_stats[forbidden_word]['contexts'].append(context)
                    
                    forbidden_data.append({
                        'Заборонене слово': forbidden_word,
                        'URL': url,
                        'Кількість згадок': count,
                        'Контекст': context
                    })
        
        # Визначаємо незнайдені слова
        not_found_keywords = [kw for kw in keywords if kw not in found_keywords]
        not_found_forbidden = [fw for fw in forbidden_words if fw not in found_forbidden]
        
        keyword_df = pd.DataFrame(keyword_data)
        forbidden_df = pd.DataFrame(forbidden_data)
        
        logger.info(f"✅ Знайдено {len(keyword_df)} згадок ключових слів")
        logger.info(f"⚠️ Знайдено {len(forbidden_df)} згадок заборонених слів")
        logger.info(f"📊 Ключових слів знайдено: {len(found_keywords)}/{len(keywords)}")
        logger.info(f"📊 Заборонених слів знайдено: {len(found_forbidden)}/{len(forbidden_words)}")
        
        if not_found_keywords:
            logger.info(f"❌ Не знайдено ключових слів: {', '.join(not_found_keywords)}")
        if not_found_forbidden:
            logger.info(f"❌ Не знайдено заборонених слів: {', '.join(not_found_forbidden)}")
        
        # Додаємо детальну статистику до результату
        detailed_stats = {
            'keyword_stats': keyword_stats,
            'forbidden_stats': forbidden_stats,
            'not_found_keywords': not_found_keywords,
            'not_found_forbidden': not_found_forbidden,
            'summary': {
                'total_keywords': len(keywords),
                'found_keywords': len(found_keywords),
                'not_found_keywords': len(not_found_keywords),
                'total_forbidden': len(forbidden_words),
                'found_forbidden': len(found_forbidden),
                'not_found_forbidden': len(not_found_forbidden)
            }
        }
        
        return keyword_df, forbidden_df, detailed_stats
    
    def _extract_context(self, text: str, keyword: str, context_length: int = 200) -> str:
        """Витягує контекст навколо ключового слова"""
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        match = pattern.search(text)
        
        if match:
            start = max(0, match.start() - context_length)
            end = min(len(text), match.end() + context_length)
            context = text[start:end].strip()
            
            # Обмежуємо кількість слів
            words = context.split()
            if len(words) > 40:
                words = words[:40]
                context = ' '.join(words) + "..."
            
            return f"...{context}..."
        
        return ""
    
    def ai_analyze_relevant_pages(self, pages_content: dict, 
                                 keyword_df: pd.DataFrame, forbidden_df: pd.DataFrame) -> str:
        """
        ШІ аналіз тільки релевантних сторінок
        """
        if not self.client:
            return "ШІ аналіз недоступний (не вказано API ключ)"
        
        logger.info("🤖 ШІ аналіз релевантних сторінок...")
        
        # Знаходимо сторінки з ключовими словами
        pages_with_keywords = set()
        if not keyword_df.empty:
            pages_with_keywords = set(keyword_df['URL'].unique())
        
        pages_with_forbidden = set()
        if not forbidden_df.empty:
            pages_with_forbidden = set(forbidden_df['URL'].unique())
        
        relevant_pages = pages_with_keywords.union(pages_with_forbidden)
        
        if not relevant_pages:
            return "Не знайдено сторінок з ключовими або забороненими словами для аналізу"
        
        # Підготовка контенту для ШІ
        relevant_content = ""
        for url in list(relevant_pages)[:10]:
            if url in pages_content:
                content_preview = pages_content[url][:1500]
                relevant_content += f"\n--- СТОРІНКА: {url} ---\n{content_preview}\n"
        
        # Статистика
        keyword_stats = {}
        if not keyword_df.empty:
            keyword_stats = keyword_df.groupby('Ключове слово')['Кількість згадок'].sum().to_dict()
        
        forbidden_stats = {}
        if not forbidden_df.empty:
            forbidden_stats = forbidden_df.groupby('Заборонене слово')['Кількість згадок'].sum().to_dict()
        
        prompt = f"""
Проаналізуй присутність бренду на партнерському сайті:

СТАТИСТИКА:
- Всього проаналізовано сторінок: {len(pages_content)}
- Сторінок з ключовими словами: {len(pages_with_keywords)}
- Сторінок з забороненими словами: {len(pages_with_forbidden)}

ПОЗИТИВНІ КЛЮЧОВІ СЛОВА (кількість згадок):
{json.dumps(keyword_stats, ensure_ascii=False, indent=2)}

НЕГАТИВНІ КЛЮЧОВІ СЛОВА (кількість згадок):
{json.dumps(forbidden_stats, ensure_ascii=False, indent=2)}

КОНТЕНТ РЕЛЕВАНТНИХ СТОРІНОК:
{relevant_content}

Дай оцінку у JSON форматі:
{{
    "brand_promotion_score": число_від_0_до_100,
    "summary": "Короткий висновок про присутність бренду",
    "detailed_analysis": "Детальний аналіз якості присутності",
    "recommendations": "Рекомендації для покращення співпраці"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ти експерт з аналізу присутності брендів на партнерських сайтах."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Помилка ШІ аналізу: {e}")
            return f"Помилка ШІ аналізу: {e}"
    
    async def analyze_site(self, site_url: str, keywords: List[str], 
                          forbidden_words: List[str], max_time_minutes: int = 20,
                          max_links: int = 300) -> SimpleAnalysisResult:
        """
        Повний асинхронний аналіз сайту
        """
        start_time = time.time()
        
        logger.info(f"🚀 Починаємо аналіз сайту: {site_url}")
        
        # 1. Знаходимо всі посилання
        all_links = await self.find_all_links(site_url, max_links)
        
        # 2. Завантажуємо контент
        pages_content = await self.scrape_all_pages(all_links, max_time_minutes)
        
        if not pages_content:
            return SimpleAnalysisResult(
                site_url=site_url,
                pages_analyzed=0,
                keyword_table=pd.DataFrame(),
                forbidden_table=pd.DataFrame(),
                ai_analysis="Не вдалося отримати контент",
                analysis_time=time.time() - start_time,
                pages_with_keywords=[],
                pages_with_forbidden=[],
                detailed_stats={}
            )
        
        # 3. Статичний пошук ключових слів
        keyword_df, forbidden_df, detailed_stats = self.search_keywords_static(
            pages_content, keywords, forbidden_words
        )
        
        # 4. ШІ аналіз
        ai_analysis = self.ai_analyze_relevant_pages(pages_content, keyword_df, forbidden_df)
        
        # 5. Збираємо результат
        pages_with_keywords = list(keyword_df['URL'].unique()) if not keyword_df.empty else []
        pages_with_forbidden = list(forbidden_df['URL'].unique()) if not forbidden_df.empty else []
        
        return SimpleAnalysisResult(
            site_url=site_url,
            pages_analyzed=len(pages_content),
            keyword_table=keyword_df,
            forbidden_table=forbidden_df,
            ai_analysis=ai_analysis,
            analysis_time=time.time() - start_time,
            pages_with_keywords=pages_with_keywords,
            pages_with_forbidden=pages_with_forbidden,
            detailed_stats=detailed_stats
        )

# FastAPI застосунок
app = FastAPI(
    title="Competitor Analysis Service",
    description="Мікросервіс для аналізу конкурентних/партнерських сайтів",
    version="1.0.0"
)

# Глобальні змінні для зберігання результатів
analysis_tasks = {}
analysis_results = {}

@app.get("/")
async def root():
    """Головна сторінка"""
    return {
        "message": "Competitor Analysis Service",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/analyze", response_model=Dict[str, str])
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    Запускає аналіз сайту в фоновому режимі
    """
    task_id = generate_task_id()
    
    # Зберігаємо статус задачі
    analysis_tasks[task_id] = AnalysisStatus(
        task_id=task_id,
        status="pending",
        progress=0,
        message="Задача створена",
        started_at=datetime.now()
    )
    
    # Запускаємо аналіз в фоновому режимі
    background_tasks.add_task(
        perform_analysis,
        task_id,
        str(request.site_url),
        request.positive_keywords,
        request.negative_keywords,
        request.max_time_minutes,
        request.max_links,
        request.openai_api_key
    )
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Аналіз запущено. Використайте /status/{task_id} для перевірки статусу"
    }

async def perform_analysis(task_id: str, site_url: str, positive_keywords: List[str], 
                          negative_keywords: List[str], max_time_minutes: int, 
                          max_links: int, openai_api_key: str = None):
    """
    Виконує аналіз сайту
    """
    try:
        # Оновлюємо статус
        analysis_tasks[task_id].status = "running"
        analysis_tasks[task_id].progress = 10
        analysis_tasks[task_id].message = "Ініціалізація аналізатора..."
        
        # Створюємо аналізатор
        analyzer = AsyncPartnerSiteAnalyzer(openai_api_key)
        
        # Оновлюємо прогрес
        analysis_tasks[task_id].progress = 20
        analysis_tasks[task_id].message = "Пошук посилань..."
        
        # Виконуємо аналіз
        result = await analyzer.analyze_site(
            site_url=site_url,
            keywords=positive_keywords,
            forbidden_words=negative_keywords,
            max_time_minutes=max_time_minutes,
            max_links=max_links
        )
        
        # Оновлюємо прогрес
        analysis_tasks[task_id].progress = 90
        analysis_tasks[task_id].message = "Обробка результатів..."
        
        # Конвертуємо результат у зручний формат
        positive_matches = []
        if not result.keyword_table.empty:
            for _, row in result.keyword_table.iterrows():
                positive_matches.append(KeywordMatch(
                    keyword=row['Ключове слово'],
                    url=row['URL'],
                    count=row['Кількість згадок'],
                    context=row['Контекст']
                ))
        
        negative_matches = []
        if not result.forbidden_table.empty:
            for _, row in result.forbidden_table.iterrows():
                negative_matches.append(KeywordMatch(
                    keyword=row['Заборонене слово'],
                    url=row['URL'],
                    count=row['Кількість згадок'],
                    context=row['Контекст']
                ))
        
        # Статистика
        summary_stats = {
            "pages_analyzed": result.pages_analyzed,
            "positive_keywords_found": len(positive_matches),
            "negative_keywords_found": len(negative_matches),
            "pages_with_positive": len(result.pages_with_keywords),
            "pages_with_negative": len(result.pages_with_forbidden),
            "analysis_time_seconds": int(result.analysis_time)
        }
        
        # Зберігаємо результат
        analysis_results[task_id] = AnalysisResult(
            task_id=task_id,
            site_url=site_url,
            status="completed",
            pages_analyzed=result.pages_analyzed,
            positive_matches=positive_matches,
            negative_matches=negative_matches,
            ai_analysis=result.ai_analysis,
            analysis_time=result.analysis_time,
            pages_with_positive=result.pages_with_keywords,
            pages_with_negative=result.pages_with_forbidden,
            summary_stats=summary_stats,
            detailed_stats=result.detailed_stats,
            completed_at=datetime.now()
        )
        
        # Оновлюємо статус
        analysis_tasks[task_id].status = "completed"
        analysis_tasks[task_id].progress = 100
        analysis_tasks[task_id].message = "Аналіз завершено успішно"
        analysis_tasks[task_id].completed_at = datetime.now()
        
        logger.info(f"✅ Аналіз {task_id} завершено успішно")
        
    except Exception as e:
        logger.error(f"❌ Помилка при аналізі {task_id}: {e}")
        
        # Оновлюємо статус з помилкою
        analysis_tasks[task_id].status = "failed"
        analysis_tasks[task_id].progress = 0
        analysis_tasks[task_id].message = f"Помилка: {str(e)}"
        analysis_tasks[task_id].completed_at = datetime.now()

@app.get("/status/{task_id}", response_model=AnalysisStatus)
async def get_analysis_status(task_id: str):
    """
    Отримує статус аналізу
    """
    if task_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Задача не знайдена")
    
    return analysis_tasks[task_id]

@app.get("/result/{task_id}", response_model=AnalysisResult)
async def get_analysis_result(task_id: str):
    """
    Отримує результат аналізу
    """
    if task_id not in analysis_results:
        if task_id not in analysis_tasks:
            raise HTTPException(status_code=404, detail="Задача не знайдена")
        
        status = analysis_tasks[task_id].status
        if status == "pending" or status == "running":
            raise HTTPException(status_code=202, detail="Аналіз ще не завершено")
        elif status == "failed":
            raise HTTPException(status_code=500, detail="Аналіз завершився з помилкою")
    
    return analysis_results[task_id]

@app.get("/tasks")
async def get_all_tasks():
    """
    Отримує список всіх задач
    """
    return {
        "tasks": list(analysis_tasks.keys()),
        "total": len(analysis_tasks)
    }

@app.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """
    Видаляє задачу та її результати
    """
    deleted = False
    
    if task_id in analysis_tasks:
        del analysis_tasks[task_id]
        deleted = True
    
    if task_id in analysis_results:
        del analysis_results[task_id]
        deleted = True
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Задача не знайдена")
    
    return {"message": "Задача видалена"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)