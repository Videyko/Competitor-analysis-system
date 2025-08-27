#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Веб-інтерфейс для користувачів
FastAPI з HTML шаблонами
"""

import os
import sys
sys.path.append('/app')

from fastapi import FastAPI, HTTPException, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Optional
import requests
import json
import uuid
from datetime import datetime
import asyncio
from io import BytesIO
import pandas as pd

# Локальні імпорти
from shared.logger import setup_logger
from shared.database import db_manager
from shared.redis_client import web_redis, web_cache
from shared.utils import generate_task_id, parse_keywords_list, parse_urls_list, parse_emails_list
from error_handlers import add_error_handlers

# Налаштування логування
logger = setup_logger('web_service')

# Pydantic моделі
class SiteAnalysisConfig(BaseModel):
    id: str
    name: str
    sites: List[str]
    positive_keywords: List[str]
    negative_keywords: List[str]
    max_time_minutes: int
    max_links: int
    openai_api_key: Optional[str]
    email_recipients: List[str]
    created_at: datetime
    last_analysis: Optional[datetime] = None

class BatchAnalysisRequest(BaseModel):
    config_id: str
    send_email: bool = True
    custom_message: Optional[str] = None

# FastAPI застосунок
app = FastAPI(
    title="Competitor Analysis Web Interface",
    description="Веб-інтерфейс для аналізу конкурентів",
    version="1.0.0"
)

# Налаштування шаблонів та статичних файлів
try:
    templates = Jinja2Templates(directory="/app/templates")
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")
    logger.info("Шаблони та статичні файли налаштовано")
except Exception as e:
    logger.error(f"Помилка налаштування шаблонів: {e}")
    templates = None

# Глобальні змінні
analysis_configs = {}
batch_analysis_results = {}

# URLs мікросервісів
ANALYSIS_SERVICE_URL = os.getenv("ANALYSIS_SERVICE_URL", "http://analysis-service:8000")
EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL", "http://email-service:8001")

logger.info(f"Analysis Service URL: {ANALYSIS_SERVICE_URL}")
logger.info(f"Email Service URL: {EMAIL_SERVICE_URL}")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Головна сторінка"""
    if not templates:
        return HTMLResponse("""
        <html><body>
            <h1>Competitor Analysis System</h1>
            <p>Система запущена, але шаблони не завантажені</p>
            <ul>
                <li><a href="/api/docs">API Documentation</a></li>
                <li><a href="/health">Health Check</a></li>
            </ul>
        </body></html>
        """)
    
    try:
        return templates.TemplateResponse("home.html", {
            "request": request,
            "configs": list(analysis_configs.values())
        })
    except Exception as e:
        logger.error(f"Помилка рендерингу головної сторінки: {e}")
        return HTMLResponse(f"<h1>Error</h1><p>{str(e)}</p>")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Перевіряємо доступність мікросервісів
    analysis_status = "unknown"
    email_status = "unknown"
    
    try:
        response = requests.get(f"{ANALYSIS_SERVICE_URL}/health", timeout=5)
        analysis_status = "ok" if response.status_code == 200 else "error"
    except:
        analysis_status = "unreachable"
    
    try:
        response = requests.get(f"{EMAIL_SERVICE_URL}/health", timeout=5)
        email_status = "ok" if response.status_code == 200 else "error"
    except:
        email_status = "unreachable"
    
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "services": {
            "analysis": analysis_status,
            "email": email_status
        }
    }

@app.get("/config/new", response_class=HTMLResponse)
async def new_config_form(request: Request):
    """Форма створення нової конфігурації"""
    if not templates:
        return HTMLResponse("<h1>Templates not available</h1>")
    
    try:
        return templates.TemplateResponse("config_form.html", {
            "request": request,
            "config": None,
            "title": "Нова конфігурація"
        })
    except Exception as e:
        logger.error(f"Помилка рендерингу форми конфігурації: {e}")
        return HTMLResponse(f"<h1>Error</h1><p>{str(e)}</p>")

@app.get("/config/{config_id}", response_class=HTMLResponse)
async def edit_config_form(request: Request, config_id: str):
    """Форма редагування конфігурації"""
    if not templates:
        return HTMLResponse("<h1>Templates not available</h1>")
    
    if config_id not in analysis_configs:
        raise HTTPException(status_code=404, detail="Конфігурація не знайдена")
    
    try:
        return templates.TemplateResponse("config_form.html", {
            "request": request,
            "config": analysis_configs[config_id],
            "title": "Редагування конфігурації"
        })
    except Exception as e:
        logger.error(f"Помилка рендерингу форми редагування: {e}")
        return HTMLResponse(f"<h1>Error</h1><p>{str(e)}</p>")

@app.post("/config/save")
async def save_config(
    name: str = Form(...),
    sites: str = Form(...),
    positive_keywords: str = Form(...),
    negative_keywords: str = Form(""),
    max_time_minutes: int = Form(20),
    max_links: int = Form(300),
    openai_api_key: str = Form(""),
    email_recipients: str = Form(...),
    config_id: str = Form(None)
):
    """Зберігає конфігурацію"""
    
    try:
        # Обробляємо дані з форми
        sites_list = parse_urls_list(sites)
        positive_list = parse_keywords_list(positive_keywords)
        negative_list = parse_keywords_list(negative_keywords)
        recipients_list = parse_emails_list(email_recipients)
        
        logger.info(f"Обробка конфігурації: сайтів={len(sites_list)}, позитивних={len(positive_list)}, негативних={len(negative_list)}, отримувачів={len(recipients_list)}")
        
        # Валідація
        if not sites_list:
            raise HTTPException(status_code=400, detail="Необхідно вказати хоча б один валідний сайт")
        if not positive_list:
            raise HTTPException(status_code=400, detail="Необхідно вказати хоча б одне позитивне ключове слово")
        if not recipients_list:
            raise HTTPException(status_code=400, detail="Необхідно вказати хоча б одного валідного отримувача")
        
        # Створюємо або оновлюємо конфігурацію
        if config_id and config_id in analysis_configs:
            # Оновлення існуючої конфігурації
            config = analysis_configs[config_id]
            config.name = name
            config.sites = sites_list
            config.positive_keywords = positive_list
            config.negative_keywords = negative_list
            config.max_time_minutes = max_time_minutes
            config.max_links = max_links
            config.openai_api_key = openai_api_key if openai_api_key else None
            config.email_recipients = recipients_list
            logger.info(f"Оновлено конфігурацію: {config_id}")
        else:
            # Створення нової конфігурації
            config_id = str(uuid.uuid4())
            config = SiteAnalysisConfig(
                id=config_id,
                name=name,
                sites=sites_list,
                positive_keywords=positive_list,
                negative_keywords=negative_list,
                max_time_minutes=max_time_minutes,
                max_links=max_links,
                openai_api_key=openai_api_key if openai_api_key else None,
                email_recipients=recipients_list,
                created_at=datetime.now()
            )
            analysis_configs[config_id] = config
            logger.info(f"Створено нову конфігурацію: {config_id}")
        
        return RedirectResponse(url="/", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка збереження конфігурації: {e}")
        raise HTTPException(status_code=500, detail=f"Помилка збереження: {str(e)}")

@app.get("/config/{config_id}/analyze", response_class=HTMLResponse)
async def analyze_config_form(request: Request, config_id: str):
    """Форма запуску аналізу"""
    if not templates:
        return HTMLResponse("<h1>Templates not available</h1>")
    
    if config_id not in analysis_configs:
        raise HTTPException(status_code=404, detail="Конфігурація не знайдена")
    
    config = analysis_configs[config_id]
    
    try:
        return templates.TemplateResponse("analyze_form.html", {
            "request": request,
            "config": config
        })
    except Exception as e:
        logger.error(f"Помилка рендерингу форми аналізу: {e}")
        return HTMLResponse(f"<h1>Error</h1><p>{str(e)}</p>")

@app.post("/config/{config_id}/analyze")
async def start_batch_analysis(
    request: Request,
    config_id: str,
    background_tasks: BackgroundTasks,
    send_email: bool = Form(True),
    custom_message: str = Form("")
):
    """Запускає пакетний аналіз"""
    if config_id not in analysis_configs:
        raise HTTPException(status_code=404, detail="Конфігурація не знайдена")
    
    config = analysis_configs[config_id]
    batch_id = str(uuid.uuid4())
    
    logger.info(f"Запуск пакетного аналізу: {batch_id} для конфігурації {config.name}")
    
    # Зберігаємо інформацію про пакетний аналіз
    batch_analysis_results[batch_id] = {
        "id": batch_id,
        "config_id": config_id,
        "config_name": config.name,
        "status": "pending",
        "total_sites": len(config.sites),
        "completed_sites": 0,
        "failed_sites": 0,
        "analysis_tasks": {},
        "email_sent": False,
        "created_at": datetime.now(),
        "send_email": send_email,
        "custom_message": custom_message
    }
    
    # Запускаємо аналіз в фоновому режимі
    background_tasks.add_task(perform_batch_analysis, batch_id, config)
    
    return RedirectResponse(url=f"/batch/{batch_id}", status_code=303)

async def perform_batch_analysis(batch_id: str, config: SiteAnalysisConfig):
    """Виконує пакетний аналіз БЕЗ email відправки"""
    try:
        batch_result = batch_analysis_results[batch_id]
        batch_result["status"] = "running"
        
        logger.info(f"Починаємо пакетний аналіз {batch_id} для {len(config.sites)} сайтів")
        
        # Аналізуємо кожен сайт
        for i, site_url in enumerate(config.sites):
            try:
                logger.info(f"Запускаємо аналіз для {site_url} ({i+1}/{len(config.sites)})")
                
                # Запускаємо аналіз через API
                request_data = {
                    "site_url": site_url,
                    "positive_keywords": config.positive_keywords,
                    "negative_keywords": config.negative_keywords,
                    "max_time_minutes": config.max_time_minutes,
                    "max_links": config.max_links,
                    "openai_api_key": config.openai_api_key
                }
                
                response = requests.post(
                    f"{ANALYSIS_SERVICE_URL}/analyze", 
                    json=request_data,
                    timeout=60
                )
                
                if response.status_code == 200:
                    task_data = response.json()
                    batch_result["analysis_tasks"][site_url] = {
                        "task_id": task_data["task_id"],
                        "status": "pending",
                        "site_url": site_url
                    }
                    logger.info(f"Аналіз {site_url} запущено: {task_data['task_id']}")
                else:
                    logger.error(f"Помилка запуску аналізу для {site_url}: {response.status_code} - {response.text}")
                    batch_result["failed_sites"] += 1
                    batch_result["analysis_tasks"][site_url] = {
                        "task_id": None,
                        "status": "failed",
                        "site_url": site_url,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                
            except Exception as e:
                logger.error(f"Помилка при аналізі {site_url}: {e}")
                batch_result["failed_sites"] += 1
                batch_result["analysis_tasks"][site_url] = {
                    "task_id": None,
                    "status": "failed",
                    "site_url": site_url,
                    "error": str(e)
                }
        
        # Чекаємо завершення всіх аналізів
        await monitor_batch_analysis(batch_id)
        
        batch_result["status"] = "completed"
        config.last_analysis = datetime.now()
        
        logger.info(f"Пакетний аналіз {batch_id} завершено")
        
    except Exception as e:
        logger.error(f"Помилка пакетного аналізу {batch_id}: {e}")
        batch_analysis_results[batch_id]["status"] = "failed"
        batch_analysis_results[batch_id]["error"] = str(e)

async def monitor_batch_analysis(batch_id: str):
    """Моніторить виконання пакетного аналізу"""
    batch_result = batch_analysis_results[batch_id]
    max_wait_time = 3600  # Максимум 1 година очікування
    start_time = datetime.now()
    
    logger.info(f"Починаємо моніторинг аналізу {batch_id}")
    
    while batch_result["completed_sites"] + batch_result["failed_sites"] < batch_result["total_sites"]:
        # Перевіряємо час очікування
        elapsed_time = (datetime.now() - start_time).total_seconds()
        if elapsed_time > max_wait_time:
            logger.warning(f"Перевищено максимальний час очікування для {batch_id}")
            break
            
        await asyncio.sleep(15)  # Перевіряємо кожні 15 секунд
        
        for site_url, task_info in batch_result["analysis_tasks"].items():
            if task_info["status"] == "pending" and task_info["task_id"]:
                try:
                    # Перевіряємо статус аналізу
                    response = requests.get(
                        f"{ANALYSIS_SERVICE_URL}/status/{task_info['task_id']}",
                        timeout=30
                    )
                    if response.status_code == 200:
                        status_data = response.json()
                        if status_data["status"] == "completed":
                            task_info["status"] = "completed"
                            batch_result["completed_sites"] += 1
                            logger.info(f"Аналіз {site_url} завершено")
                        elif status_data["status"] == "failed":
                            task_info["status"] = "failed"
                            task_info["error"] = status_data.get("message", "Невідома помилка")
                            batch_result["failed_sites"] += 1
                            logger.error(f"Аналіз {site_url} провалився")
                except Exception as e:
                    logger.error(f"Помилка перевірки статусу {site_url}: {e}")

@app.get("/batch/{batch_id}", response_class=HTMLResponse)
async def view_batch_analysis(request: Request, batch_id: str):
    """Переглядає статус пакетного аналізу"""
    if not templates:
        return HTMLResponse("<h1>Templates not available</h1>")
    
    if batch_id not in batch_analysis_results:
        raise HTTPException(status_code=404, detail="Пакетний аналіз не знайдений")
    
    batch_result = batch_analysis_results[batch_id]
    
    try:
        return templates.TemplateResponse("batch_analysis.html", {
            "request": request,
            "batch": batch_result
        })
    except Exception as e:
        logger.error(f"Помилка рендерингу сторінки пакетного аналізу: {e}")
        return HTMLResponse(f"<h1>Error</h1><p>{str(e)}</p>")

# 🆕 НОВИЙ ENDPOINT - Детальний перегляд результатів пакету
@app.get("/batch/{batch_id}/results", response_class=HTMLResponse)
async def view_batch_results_detailed(request: Request, batch_id: str):
    """Детальний перегляд результатів пакетного аналізу"""
    if not templates:
        return HTMLResponse("<h1>Templates not available</h1>")
    
    if batch_id not in batch_analysis_results:
        raise HTTPException(status_code=404, detail="Пакетний аналіз не знайдений")
    
    batch_result = batch_analysis_results[batch_id]
    
    # Отримуємо детальні результати для кожного сайту
    detailed_results = {}
    for site_url, task_info in batch_result["analysis_tasks"].items():
        if task_info["status"] == "completed" and task_info["task_id"]:
            try:
                response = requests.get(f"{ANALYSIS_SERVICE_URL}/result/{task_info['task_id']}", timeout=30)
                if response.status_code == 200:
                    detailed_results[site_url] = response.json()
                else:
                    logger.warning(f"Не вдалося отримати результат для {site_url}: HTTP {response.status_code}")
            except Exception as e:
                logger.error(f"Помилка отримання результату для {site_url}: {e}")
    
    try:
        return templates.TemplateResponse("batch_results_detail.html", {
            "request": request,
            "batch": batch_result,
            "detailed_results": detailed_results
        })
    except Exception as e:
        logger.error(f"Помилка рендерингу детальних результатів: {e}")
        return HTMLResponse(f"<h1>Error</h1><p>{str(e)}</p>")

# 🆕 НОВИЙ ENDPOINT - Перегляд окремого результату
@app.get("/result/{task_id}", response_class=HTMLResponse)
async def view_single_result(request: Request, task_id: str):
    """Детальний перегляд окремого результату аналізу"""
    if not templates:
        return HTMLResponse("<h1>Templates not available</h1>")
    
    try:
        # Отримуємо результат з analysis service
        response = requests.get(f"{ANALYSIS_SERVICE_URL}/result/{task_id}", timeout=30)
        
        if response.status_code == 200:
            result_data = response.json()
            return templates.TemplateResponse("result_detail.html", {
                "request": request,
                "result": result_data
            })
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Результат не знайдено")
        elif response.status_code == 202:
            # Аналіз ще не завершено
            return templates.TemplateResponse("analysis_pending.html", {
                "request": request,
                "task_id": task_id
            })
        else:
            raise HTTPException(status_code=response.status_code, detail="Помилка отримання результату")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Помилка отримання результату {task_id}: {e}")
        raise HTTPException(status_code=503, detail="Сервіс аналізу недоступний")

# 🆕 НОВИЙ ENDPOINT - Завантаження окремого результату
@app.get("/result/{task_id}/download")
async def download_single_result(task_id: str):
    """Завантаження Excel файлу для окремого результату"""
    try:
        response = requests.get(f"{ANALYSIS_SERVICE_URL}/result/{task_id}", timeout=30)
        
        if response.status_code == 200:
            result_data = response.json()
            
            # Створюємо Excel файл
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Позитивні збіги
                if result_data.get('positive_matches'):
                    positive_df = pd.DataFrame([
                        {
                            'Ключове слово': match['keyword'],
                            'URL': match['url'],
                            'Кількість': match['count'],
                            'Контекст': match['context']
                        }
                        for match in result_data['positive_matches']
                    ])
                    positive_df.to_excel(writer, sheet_name='Позитивні збіги', index=False)
                
                # Негативні збіги
                if result_data.get('negative_matches'):
                    negative_df = pd.DataFrame([
                        {
                            'Ключове слово': match['keyword'],
                            'URL': match['url'],
                            'Кількість': match['count'],
                            'Контекст': match['context']
                        }
                        for match in result_data['negative_matches']
                    ])
                    negative_df.to_excel(writer, sheet_name='Негативні збіги', index=False)
                
                # Детальна статистика
                if result_data.get('detailed_stats'):
                    stats_data = []
                    
                    # Статистика по ключових словах
                    if result_data['detailed_stats'].get('keyword_stats'):
                        for keyword, stats in result_data['detailed_stats']['keyword_stats'].items():
                            if stats['total_mentions'] > 0:
                                for page in stats['pages_found']:
                                    stats_data.append({
                                        'Тип': 'Позитивне',
                                        'Ключове слово': keyword,
                                        'Всього згадок': stats['total_mentions'],
                                        'URL': page['url'],
                                        'Згадок на сторінці': page['count'],
                                        'Контекст': page['context']
                                    })
                    
                    # Статистика по негативних словах
                    if result_data['detailed_stats'].get('forbidden_stats'):
                        for keyword, stats in result_data['detailed_stats']['forbidden_stats'].items():
                            if stats['total_mentions'] > 0:
                                for page in stats['pages_found']:
                                    stats_data.append({
                                        'Тип': 'Негативне',
                                        'Ключове слово': keyword,
                                        'Всього згадок': stats['total_mentions'],
                                        'URL': page['url'],
                                        'Згадок на сторінці': page['count'],
                                        'Контекст': page['context']
                                    })
                    
                    if stats_data:
                        pd.DataFrame(stats_data).to_excel(writer, sheet_name='Детальна статистика', index=False)
                
                # Загальна статистика
                summary_data = [
                    ['Сайт', result_data['site_url']],
                    ['Сторінок проаналізовано', result_data['pages_analyzed']],
                    ['Позитивних збігів', len(result_data.get('positive_matches', []))],
                    ['Негативних збігів', len(result_data.get('negative_matches', []))],
                    ['Час аналізу (сек)', result_data['analysis_time']],
                    ['Дата завершення', result_data['completed_at']],
                    ['Task ID', task_id]
                ]
                
                stats_df = pd.DataFrame(summary_data, columns=['Параметр', 'Значення'])
                stats_df.to_excel(writer, sheet_name='Загальна інформація', index=False)
            
            output.seek(0)
            
            # Створюємо безпечне ім'я файлу
            site_name = result_data['site_url'].replace('https://', '').replace('http://', '').replace('/', '_').replace(':', '_')
            filename = f"analysis_{site_name}_{task_id[:8]}.xlsx"
            
            return StreamingResponse(
                BytesIO(output.read()),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            raise HTTPException(status_code=response.status_code, detail="Результат не знайдено")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Помилка завантаження результату {task_id}: {e}")
        raise HTTPException(status_code=503, detail="Сервіс аналізу недоступний")

@app.get("/batch/{batch_id}/download")
async def download_batch_results(batch_id: str):
    """Завантаження Excel файлу з результатами"""
    if batch_id not in batch_analysis_results:
        raise HTTPException(status_code=404, detail="Пакетний аналіз не знайдений")
    
    batch_result = batch_analysis_results[batch_id]
    
    # Створюємо Excel файл
    output = BytesIO()
    all_positive = []
    all_negative = []
    summary_data = []
    
    for site_url, task_info in batch_result["analysis_tasks"].items():
        if task_info["status"] == "completed" and task_info["task_id"]:
            try:
                response = requests.get(f"{ANALYSIS_SERVICE_URL}/result/{task_info['task_id']}", timeout=30)
                if response.status_code == 200:
                    result_data = response.json()
                    
                    # Позитивні збіги
                    for match in result_data.get('positive_matches', []):
                        all_positive.append({
                            'Сайт': site_url,
                            'Ключове слово': match['keyword'],
                            'URL': match['url'],
                            'Кількість': match['count'],
                            'Контекст': match['context']
                        })
                    
                    # Негативні збіги
                    for match in result_data.get('negative_matches', []):
                        all_negative.append({
                            'Сайт': site_url,
                            'Заборонене слово': match['keyword'],
                            'URL': match['url'],
                            'Кількість': match['count'],
                            'Контекст': match['context']
                        })
                    
                    # Загальна статистика
                    summary_data.append({
                        'Сайт': site_url,
                        'Сторінок проаналізовано': result_data['pages_analyzed'],
                        'Позитивних збігів': len(result_data.get('positive_matches', [])),
                        'Негативних збігів': len(result_data.get('negative_matches', [])),
                        'Час аналізу (сек)': result_data['analysis_time'],
                        'Завершено': result_data['completed_at']
                    })
                    
            except Exception as e:
                logger.error(f"Помилка обробки результату для {site_url}: {e}")
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if summary_data:
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Загальна статистика', index=False)
        if all_positive:
            pd.DataFrame(all_positive).to_excel(writer, sheet_name='Позитивні збіги', index=False)
        if all_negative:
            pd.DataFrame(all_negative).to_excel(writer, sheet_name='Негативні збіги', index=False)
    
    output.seek(0)
    
    return StreamingResponse(
        BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=batch_results_{batch_id[:8]}.xlsx"}
    )

@app.get("/batch/{batch_id}/status")
async def get_batch_status(batch_id: str):
    """API для отримання статусу пакетного аналізу"""
    if batch_id not in batch_analysis_results:
        raise HTTPException(status_code=404, detail="Пакетний аналіз не знайдений")
    
    return batch_analysis_results[batch_id]

@app.get("/results", response_class=HTMLResponse)
async def view_results(request: Request):
    """Переглядає всі результати аналізів"""
    if not templates:
        return HTMLResponse("<h1>Templates not available</h1>")
    
    try:
        return templates.TemplateResponse("results.html", {
            "request": request,
            "batches": list(batch_analysis_results.values())
        })
    except Exception as e:
        logger.error(f"Помилка рендерингу сторінки результатів: {e}")
        return HTMLResponse(f"<h1>Error</h1><p>{str(e)}</p>")

@app.delete("/config/{config_id}")
async def delete_config(config_id: str):
    """Видаляє конфігурацію"""
    if config_id not in analysis_configs:
        raise HTTPException(status_code=404, detail="Конфігурація не знайдена")
    
    del analysis_configs[config_id]
    logger.info(f"Видалено конфігурацію: {config_id}")
    return {"message": "Конфігурація видалена"}

@app.delete("/batch/{batch_id}")
async def delete_batch_analysis(batch_id: str):
    """Видаляє результати пакетного аналізу"""
    if batch_id not in batch_analysis_results:
        raise HTTPException(status_code=404, detail="Пакетний аналіз не знайдений")
    
    del batch_analysis_results[batch_id]
    logger.info(f"Видалено пакетний аналіз: {batch_id}")
    return {"message": "Результати пакетного аналізу видалені"}

# 🆕 НОВИЙ ENDPOINT - API статусу аналізу
@app.get("/api/analysis/status/{task_id}")
async def get_analysis_status(task_id: str):
    """Проксі для отримання статусу аналізу"""
    try:
        response = requests.get(f"{ANALYSIS_SERVICE_URL}/status/{task_id}", timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except requests.exceptions.RequestException as e:
        logger.error(f"Помилка отримання статусу аналізу {task_id}: {e}")
        raise HTTPException(status_code=503, detail="Сервіс аналізу недоступний")

# API endpoints для отримання статистики
@app.get("/api/configs")
async def get_configs():
    """Отримати всі конфігурації"""
    return list(analysis_configs.values())

@app.get("/api/batches")
async def get_batches():
    """Отримати всі пакетні аналізи"""
    return list(batch_analysis_results.values())

@app.get("/api/analysis/result/{task_id}")
async def get_analysis_result(task_id: str):
    """Проксі для отримання результату аналізу"""
    try:
        response = requests.get(f"{ANALYSIS_SERVICE_URL}/result/{task_id}", timeout=30)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 202:
            raise HTTPException(status_code=202, detail="Аналіз ще не завершено")
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Результат не знайдено")
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except requests.exceptions.RequestException as e:
        logger.error(f"Помилка отримання результату аналізу {task_id}: {e}")
        raise HTTPException(status_code=503, detail="Сервіс аналізу недоступний")

# Створюємо директорії для шаблонів та статичних файлів якщо вони не існують
try:
    os.makedirs("/app/templates", exist_ok=True)
    os.makedirs("/app/static", exist_ok=True)
    os.makedirs("/app/static/css", exist_ok=True)
    os.makedirs("/app/static/js", exist_ok=True)
    logger.info("Директорії створено")
except Exception as e:
    logger.warning(f"Не вдалося створити директорії: {e}")

# 🆕 ДОДАЄМО ERROR HANDLERS
try:
    add_error_handlers(app, templates)
    logger.info("Error handlers додано")
except Exception as e:
    logger.error(f"Помилка додавання error handlers: {e}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Запуск веб-сервера...")
    uvicorn.run(app, host="0.0.0.0", port=8002)
