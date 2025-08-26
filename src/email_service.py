#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Мікросервіс для відправки звітів на електронну пошту
"""

import os
import sys
import time
sys.path.append('/app')

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Optional
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import jinja2
import aiofiles
import asyncio
import uuid
import requests
from io import BytesIO
import pandas as pd
from datetime import datetime

# Локальні імпорти
from shared.logger import setup_logger
from shared.redis_client import email_redis, email_cache
from shared.utils import generate_task_id

# Налаштування логування
logger = setup_logger('email_service')

# Pydantic моделі
class EmailSettings(BaseModel):
    smtp_server: str = Field(..., description="SMTP сервер")
    smtp_port: int = Field(default=587, description="SMTP порт")
    email: str = Field(..., description="Email відправника")
    password: str = Field(..., description="Пароль відправника")
    use_tls: bool = Field(default=True, description="Використовувати TLS")

class Recipient(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class EmailRequest(BaseModel):
    recipients: List[Recipient] = Field(..., description="Список отримувачів")
    subject: str = Field(..., description="Тема листа")
    analysis_task_id: str = Field(..., description="ID задачі аналізу")
    analysis_service_url: str = Field(default="http://analysis-service:8000", description="URL сервісу аналізу")
    custom_message: Optional[str] = Field(default=None, description="Додаткове повідомлення")
    include_attachments: bool = Field(default=True, description="Включити вкладення")

class EmailStatus(BaseModel):
    task_id: str
    status: str  # "pending", "sending", "sent", "failed"
    recipients_count: int
    sent_count: int
    failed_count: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class EmailService:
    def __init__(self, settings: EmailSettings):
        self.settings = settings
        self.jinja_env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
        
    async def get_analysis_result(self, task_id: str, service_url: str) -> Dict:
        """Отримує результат аналізу з основного сервісу"""
        try:
            # Додаємо retry логіку
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(f"{service_url}/result/{task_id}", timeout=30)
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 404:
                        raise HTTPException(status_code=404, detail="Результат аналізу не знайдено")
                    elif response.status_code == 202:
                        # Аналіз ще виконується
                        if attempt < max_retries - 1:
                            await asyncio.sleep(10)
                            continue
                        else:
                            raise HTTPException(status_code=202, detail="Аналіз ще не завершено")
                    else:
                        response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Спроба {attempt + 1} не вдалася: {e}")
                        await asyncio.sleep(5)
                        continue
                    raise
                    
        except Exception as e:
            logger.error(f"Помилка отримання результату аналізу: {e}")
            raise HTTPException(status_code=400, detail=f"Не вдалося отримати результат аналізу: {e}")
    
    def generate_html_report(self, analysis_result: Dict, custom_message: str = None) -> str:
        """Генерує HTML звіт"""
        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Звіт аналізу конкурентів</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; color: #333; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }
        .summary { background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .section { margin: 20px 0; }
        .positive { color: #27ae60; }
        .negative { color: #e74c3c; }
        .stats { display: flex; gap: 20px; flex-wrap: wrap; }
        .stat-card { background: #f8f9fa; padding: 15px; border-radius: 5px; min-width: 200px; }
        .keyword-list { background: #fff; border: 1px solid #ddd; border-radius: 5px; padding: 10px; margin: 10px 0; }
        .context { font-style: italic; color: #666; font-size: 0.9em; }
        .ai-analysis { background: #e8f5e8; padding: 15px; border-radius: 5px; border-left: 4px solid #27ae60; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .url { color: #3498db; text-decoration: none; }
        .url:hover { text-decoration: underline; }
        .card { background: #fff; border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin: 10px 0; }
        .card-header { background: #f8f9fa; padding: 10px; margin: -15px -15px 15px -15px; border-radius: 5px 5px 0 0; border-bottom: 1px solid #ddd; }
        .alert-warning { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; margin: 10px 0; }
        .alert-success { background: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; padding: 15px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Звіт аналізу конкурентів</h1>
        <p>Аналіз сайту: <strong>{{ analysis_result.site_url }}</strong></p>
        <p>Дата: {{ analysis_result.completed_at }}</p>
    </div>

    {% if custom_message %}
    <div class="section">
        <h2>📝 Додаткове повідомлення</h2>
        <p>{{ custom_message }}</p>
    </div>
    {% endif %}

    <div class="summary">
        <h2>📊 Загальна статистика</h2>
        <div class="stats">
            <div class="stat-card">
                <h3>Сторінок проаналізовано</h3>
                <p style="font-size: 2em; margin: 0;"><strong>{{ analysis_result.pages_analyzed }}</strong></p>
            </div>
            <div class="stat-card">
                <h3 class="positive">Позитивні збіги</h3>
                <p style="font-size: 2em; margin: 0;"><strong>{{ analysis_result.summary_stats.positive_keywords_found }}</strong></p>
            </div>
            <div class="stat-card">
                <h3 class="negative">Негативні збіги</h3>
                <p style="font-size: 2em; margin: 0;"><strong>{{ analysis_result.summary_stats.negative_keywords_found }}</strong></p>
            </div>
            <div class="stat-card">
                <h3>Час аналізу</h3>
                <p style="font-size: 2em; margin: 0;"><strong>{{ analysis_result.summary_stats.analysis_time_seconds }}с</strong></p>
            </div>
        </div>
        
        {% if analysis_result.detailed_stats and analysis_result.detailed_stats.summary %}
        <hr>
        <div class="stats">
            <div class="stat-card">
                <h4>Ключові слова:</h4>
                <p>
                    <span class="positive">✅ Знайдено: {{ analysis_result.detailed_stats.summary.found_keywords }}/{{ analysis_result.detailed_stats.summary.total_keywords }}</span><br>
                    <span class="negative">❌ Не знайдено: {{ analysis_result.detailed_stats.summary.not_found_keywords }}</span>
                </p>
            </div>
            <div class="stat-card">
                <h4>Негативні слова:</h4>
                <p>
                    <span class="negative">⚠️ Знайдено: {{ analysis_result.detailed_stats.summary.found_forbidden }}/{{ analysis_result.detailed_stats.summary.total_forbidden }}</span><br>
                    <span class="positive">✅ Не знайдено: {{ analysis_result.detailed_stats.summary.not_found_forbidden }}</span>
                </p>
            </div>
        </div>
        {% endif %}
    </div>

    {% if analysis_result.positive_matches %}
    <div class="section">
        <h2 class="positive">✅ Позитивні ключові слова</h2>
        
        {% if analysis_result.detailed_stats and analysis_result.detailed_stats.keyword_stats %}
        <div class="card">
            <div class="card-header">
                <h5>Детальна статистика по ключових словах</h5>
            </div>
            <div class="card-body">
                {% for keyword, stats in analysis_result.detailed_stats.keyword_stats.items() %}
                    {% if stats.total_mentions > 0 %}
                    <div style="margin-bottom: 20px;">
                        <h6 class="positive">🔍 "{{ keyword }}" - {{ stats.total_mentions }} згадок на {{ stats.pages_found|length }} сторінках</h6>
                        <ul>
                            {% for page in stats.pages_found %}
                            <li>
                                <a href="{{ page.url }}" class="url">{{ page.url }}</a> 
                                ({{ page.count }} разів)
                                <br><small class="context">{{ page.context }}</small>
                            </li>
                            {% endfor %}
                        </ul>
                    </div>
                    {% endif %}
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        <table>
            <thead>
                <tr>
                    <th>Ключове слово</th>
                    <th>URL</th>
                    <th>Кількість</th>
                    <th>Контекст</th>
                </tr>
            </thead>
            <tbody>
                {% for match in analysis_result.positive_matches %}
                <tr>
                    <td><strong>{{ match.keyword }}</strong></td>
                    <td><a href="{{ match.url }}" class="url">{{ match.url }}</a></td>
                    <td>{{ match.count }}</td>
                    <td class="context">{{ match.context }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}
    
    {% if analysis_result.detailed_stats and analysis_result.detailed_stats.not_found_keywords %}
    <div class="section">
        <h2 class="negative">❌ Не знайдені позитивні ключові слова</h2>
        <div class="alert-warning">
            <h6>Наступні ключові слова не були знайдені на сайті:</h6>
            <ul>
                {% for keyword in analysis_result.detailed_stats.not_found_keywords %}
                <li><strong>"{{ keyword }}"</strong></li>
                {% endfor %}
            </ul>
            <p><em>Рекомендується:</em></p>
            <ul>
                <li>Перевірити правильність написання ключових слів</li>
                <li>Розглянути синоніми або альтернативні варіанти</li>
                <li>Звернутися до партнера щодо відсутності згадок</li>
            </ul>
        </div>
    </div>
    {% endif %}

    {% if analysis_result.negative_matches %}
    <div class="section">
        <h2 class="negative">❌ Негативні ключові слова</h2>
        
        {% if analysis_result.detailed_stats and analysis_result.detailed_stats.forbidden_stats %}
        <div class="card" style="border-left: 4px solid #e74c3c;">
            <div class="card-header">
                <h5>Детальна статистика по негативних словах</h5>
            </div>
            <div class="card-body">
                {% for keyword, stats in analysis_result.detailed_stats.forbidden_stats.items() %}
                    {% if stats.total_mentions > 0 %}
                    <div style="margin-bottom: 20px;">
                        <h6 class="negative">⚠️ "{{ keyword }}" - {{ stats.total_mentions }} згадок на {{ stats.pages_found|length }} сторінках</h6>
                        <ul>
                            {% for page in stats.pages_found %}
                            <li>
                                <a href="{{ page.url }}" class="url">{{ page.url }}</a> 
                                ({{ page.count }} разів)
                                <br><small class="context">{{ page.context }}</small>
                            </li>
                            {% endfor %}
                        </ul>
                    </div>
                    {% endif %}
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        <table>
            <thead>
                <tr>
                    <th>Ключове слово</th>
                    <th>URL</th>
                    <th>Кількість</th>
                    <th>Контекст</th>
                </tr>
            </thead>
            <tbody>
                {% for match in analysis_result.negative_matches %}
                <tr>
                    <td><strong>{{ match.keyword }}</strong></td>
                    <td><a href="{{ match.url }}" class="url">{{ match.url }}</a></td>
                    <td>{{ match.count }}</td>
                    <td class="context">{{ match.context }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}
    
    {% if analysis_result.detailed_stats and analysis_result.detailed_stats.not_found_forbidden %}
    <div class="section">
        <h2 class="positive">✅ Хороша новина!</h2>
        <div class="alert-success">
            <h6>Наступні негативні ключові слова НЕ були знайдені на сайті:</h6>
            <ul>
                {% for keyword in analysis_result.detailed_stats.not_found_forbidden %}
                <li><strong>"{{ keyword }}"</strong></li>
                {% endfor %}
            </ul>
            <p><em>Це позитивний показник - партнер не згадує ваших конкурентів!</em></p>
        </div>
    </div>
    {% endif %}

    {% if analysis_result.ai_analysis %}
    <div class="section">
        <h2>🤖 ШІ Аналіз</h2>
        <div class="ai-analysis">
            <pre>{{ analysis_result.ai_analysis }}</pre>
        </div>
    </div>
    {% endif %}

    <div class="section">
        <h2>🔗 Корисні посилання</h2>
        <h3 class="positive">Сторінки з позитивними ключовими словами:</h3>
        <ul>
        {% for url in analysis_result.pages_with_positive %}
            <li><a href="{{ url }}" class="url">{{ url }}</a></li>
        {% endfor %}
        </ul>
        
        {% if analysis_result.pages_with_negative %}
        <h3 class="negative">Сторінки з негативними ключовими словами:</h3>
        <ul>
        {% for url in analysis_result.pages_with_negative %}
            <li><a href="{{ url }}" class="url">{{ url }}</a></li>
        {% endfor %}
        </ul>
        {% endif %}
    </div>

    <div class="section">
        <p><em>Звіт згенеровано автоматично системою аналізу конкурентів</em></p>
    </div>
</body>
</html>
        """
        
        jinja_template = self.jinja_env.from_string(template)
        return jinja_template.render(
            analysis_result=analysis_result,
            custom_message=custom_message
        )
    
    def create_excel_attachment(self, analysis_result: Dict) -> BytesIO:
        """Створює Excel файл з результатами"""
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Позитивні ключові слова
            if analysis_result.get('positive_matches'):
                positive_df = pd.DataFrame([
                    {
                        'Ключове слово': match['keyword'],
                        'URL': match['url'],
                        'Кількість': match['count'],
                        'Контекст': match['context']
                    }
                    for match in analysis_result['positive_matches']
                ])
                positive_df.to_excel(writer, sheet_name='Позитивні', index=False)
            
            # Негативні ключові слова
            if analysis_result.get('negative_matches'):
                negative_df = pd.DataFrame([
                    {
                        'Ключове слово': match['keyword'],
                        'URL': match['url'],
                        'Кількість': match['count'],
                        'Контекст': match['context']
                    }
                    for match in analysis_result['negative_matches']
                ])
                negative_df.to_excel(writer, sheet_name='Негативні', index=False)
            
            # Детальна статистика по ключових словах
            if analysis_result.get('detailed_stats') and analysis_result['detailed_stats'].get('keyword_stats'):
                keyword_stats_data = []
                for keyword, stats in analysis_result['detailed_stats']['keyword_stats'].items():
                    if stats['total_mentions'] > 0:
                        for page in stats['pages_found']:
                            keyword_stats_data.append({
                                'Ключове слово': keyword,
                                'Всього згадок': stats['total_mentions'],
                                'Сторінок знайдено': len(stats['pages_found']),
                                'URL': page['url'],
                                'Згадок на сторінці': page['count'],
                                'Контекст': page['context']
                            })
                
                if keyword_stats_data:
                    keyword_stats_df = pd.DataFrame(keyword_stats_data)
                    keyword_stats_df.to_excel(writer, sheet_name='Детальна статистика позитивних', index=False)
            
            # Детальна статистика по негативних словах
            if analysis_result.get('detailed_stats') and analysis_result['detailed_stats'].get('forbidden_stats'):
                forbidden_stats_data = []
                for keyword, stats in analysis_result['detailed_stats']['forbidden_stats'].items():
                    if stats['total_mentions'] > 0:
                        for page in stats['pages_found']:
                            forbidden_stats_data.append({
                                'Негативне слово': keyword,
                                'Всього згадок': stats['total_mentions'],
                                'Сторінок знайдено': len(stats['pages_found']),
                                'URL': page['url'],
                                'Згадок на сторінці': page['count'],
                                'Контекст': page['context']
                            })
                
                if forbidden_stats_data:
                    forbidden_stats_df = pd.DataFrame(forbidden_stats_data)
                    forbidden_stats_df.to_excel(writer, sheet_name='Детальна статистика негативних', index=False)
            
            # Не знайдені слова
            if analysis_result.get('detailed_stats'):
                not_found_data = []
                
                # Не знайдені позитивні слова
                if analysis_result['detailed_stats'].get('not_found_keywords'):
                    for keyword in analysis_result['detailed_stats']['not_found_keywords']:
                        not_found_data.append({
                            'Тип': 'Позитивне',
                            'Ключове слово': keyword,
                            'Статус': 'Не знайдено',
                            'Рекомендація': 'Перевірити написання або звернутися до партнера'
                        })
                
                # Не знайдені негативні слова
                if analysis_result['detailed_stats'].get('not_found_forbidden'):
                    for keyword in analysis_result['detailed_stats']['not_found_forbidden']:
                        not_found_data.append({
                            'Тип': 'Негативне',
                            'Ключове слово': keyword,
                            'Статус': 'Не знайдено',
                            'Рекомендація': 'Позитивний показник - конкурент не згадується'
                        })
                
                if not_found_data:
                    not_found_df = pd.DataFrame(not_found_data)
                    not_found_df.to_excel(writer, sheet_name='Не знайдені слова', index=False)
            
            # Загальна статистика
            stats_data = [
                ['Сайт', analysis_result['site_url']],
                ['Сторінок проаналізовано', analysis_result['pages_analyzed']],
                ['Позитивних збігів', analysis_result['summary_stats']['positive_keywords_found']],
                ['Негативних збігів', analysis_result['summary_stats']['negative_keywords_found']],
                ['Час аналізу (сек)', analysis_result['summary_stats']['analysis_time_seconds']],
                ['Дата аналізу', analysis_result['completed_at']]
            ]
            
            # Додаємо детальну статистику
            if analysis_result.get('detailed_stats') and analysis_result['detailed_stats'].get('summary'):
                summary = analysis_result['detailed_stats']['summary']
                stats_data.extend([
                    ['', ''],
                    ['=== ДЕТАЛЬНА СТАТИСТИКА ===', ''],
                    ['Всього позитивних слів', summary['total_keywords']],
                    ['Знайдено позитивних слів', summary['found_keywords']],
                    ['Не знайдено позитивних слів', summary['not_found_keywords']],
                    ['Всього негативних слів', summary['total_forbidden']],
                    ['Знайдено негативних слів', summary['found_forbidden']],
                    ['Не знайдено негативних слів', summary['not_found_forbidden']]
                ])
            
            stats_df = pd.DataFrame(stats_data, columns=['Параметр', 'Значення'])
            stats_df.to_excel(writer, sheet_name='Загальна статистика', index=False)
        
        output.seek(0)
        return output
    
    def send_email(self, recipient: Recipient, subject: str, html_content: str, 
                   attachments: List[tuple] = None) -> bool:
        """Відправляє email одному отримувачу"""
        try:
            # Створюємо повідомлення
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.settings.email
            message["To"] = recipient.email
            
            # Додаємо HTML контент
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)
            
            # Додаємо вкладення
            if attachments:
                for filename, content in attachments:
                    attachment = MIMEBase('application', 'octet-stream')
                    content.seek(0)  # Важливо: переміщуємо курсор на початок
                    attachment.set_payload(content.read())
                    encoders.encode_base64(attachment)
                    attachment.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {filename}'
                    )
                    message.attach(attachment)
            
            # Відправляємо email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.settings.smtp_server, self.settings.smtp_port) as server:
                if self.settings.use_tls:
                    server.starttls(context=context)
                server.login(self.settings.email, self.settings.password)
                server.send_message(message)
            
            logger.info(f"Email відправлено до {recipient.email}")
            return True
            
        except Exception as e:
            logger.error(f"Помилка відправки email до {recipient.email}: {e}")
            return False

# FastAPI застосунок
app = FastAPI(
    title="Email Report Service",
    description="Мікросервіс для відправки звітів аналізу на електронну пошту",
    version="1.0.0"
)

# Налаштування email (можна винести в змінні оточення)
email_settings = EmailSettings(
    smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    smtp_port=int(os.getenv("SMTP_PORT", "587")),
    email=os.getenv("EMAIL_USER", "your-email@gmail.com"),
    password=os.getenv("EMAIL_PASSWORD", "your-app-password"),
    use_tls=True
)

# Глобальні змінні для відстеження статусу
email_tasks = {}
email_service = EmailService(email_settings)

@app.get("/")
async def root():
    """Головна сторінка"""
    return {
        "message": "Email Report Service",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/send-report")
async def send_report(request: EmailRequest, background_tasks: BackgroundTasks):
    """
    Відправляє звіт аналізу на email
    """
    task_id = generate_task_id()
    
    # Зберігаємо статус задачі
    email_tasks[task_id] = EmailStatus(
        task_id=task_id,
        status="pending",
        recipients_count=len(request.recipients),
        sent_count=0,
        failed_count=0,
        created_at=datetime.now()
    )
    
    # Запускаємо відправку в фоновому режимі
    background_tasks.add_task(
        perform_email_sending,
        task_id,
        request
    )
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": f"Відправка звіту запланована для {len(request.recipients)} отримувачів"
    }

async def perform_email_sending(task_id: str, request: EmailRequest):
    """
    Виконує відправку email
    """
    try:
        # Оновлюємо статус
        email_tasks[task_id].status = "sending"
        
        # Отримуємо результат аналізу
        analysis_result = await email_service.get_analysis_result(
            request.analysis_task_id, 
            request.analysis_service_url
        )
        
        # Генеруємо HTML звіт
        html_content = email_service.generate_html_report(
            analysis_result, 
            request.custom_message
        )
        
        # Створюємо вкладення
        attachments = []
        if request.include_attachments:
            try:
                excel_file = email_service.create_excel_attachment(analysis_result)
                filename = f"analysis_report_{analysis_result['site_url'].replace('https://', '').replace('http://', '').replace('/', '_')}.xlsx"
                attachments.append((filename, excel_file))
            except Exception as e:
                logger.error(f"Помилка створення Excel вкладення: {e}")
        
        # Відправляємо email кожному отримувачу
        for recipient in request.recipients:
            success = email_service.send_email(
                recipient=recipient,
                subject=request.subject,
                html_content=html_content,
                attachments=attachments
            )
            
            if success:
                email_tasks[task_id].sent_count += 1
            else:
                email_tasks[task_id].failed_count += 1
        
        # Оновлюємо статус
        email_tasks[task_id].status = "sent"
        email_tasks[task_id].completed_at = datetime.now()
        
        logger.info(f"Відправку email {task_id} завершено")
        
    except Exception as e:
        logger.error(f"Помилка при відправці email {task_id}: {e}")
        
        email_tasks[task_id].status = "failed"
        email_tasks[task_id].error_message = str(e)
        email_tasks[task_id].completed_at = datetime.now()

@app.get("/status/{task_id}", response_model=EmailStatus)
async def get_email_status(task_id: str):
    """
    Отримує статус відправки email
    """
    if task_id not in email_tasks:
        raise HTTPException(status_code=404, detail="Email задача не знайдена")
    
    return email_tasks[task_id]

@app.get("/tasks")
async def get_all_email_tasks():
    """
    Отримує список всіх email задач
    """
    return {
        "tasks": list(email_tasks.keys()),
        "total": len(email_tasks)
    }

@app.delete("/task/{task_id}")
async def delete_email_task(task_id: str):
    """
    Видаляє email задачу
    """
    if task_id not in email_tasks:
        raise HTTPException(status_code=404, detail="Email задача не знайдена")
    
    del email_tasks[task_id]
    return {"message": "Email задача видалена"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
