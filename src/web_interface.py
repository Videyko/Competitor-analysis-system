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
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Optional
import requests
import json
import uuid
from datetime import datetime
import asyncio

# Локальні імпорти
from shared.logger import setup_logger
from shared.database import db_manager
from shared.redis_client import web_redis, web_cache
from shared.utils import generate_task_id, parse_keywords_list, parse_urls_list, parse_emails_list

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
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Глобальні змінні
analysis_configs = {}
batch_analysis_results = {}

# URLs мікросервісів
ANALYSIS_SERVICE_URL = os.getenv("ANALYSIS_SERVICE_URL", "http://analysis-service:8000")
EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL", "http://email-service:8001")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Головна сторінка"""
    return templates.TemplateResponse("home.html", {
        "request": request,
        "configs": list(analysis_configs.values())
    })

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/config/new", response_class=HTMLResponse)
async def new_config_form(request: Request):
    """Форма створення нової конфігурації"""
    return templates.TemplateResponse("config_form.html", {
        "request": request,
        "config": None,
        "title": "Нова конфігурація"
    })

@app.get("/config/{config_id}", response_class=HTMLResponse)
async def edit_config_form(request: Request, config_id: str):
    """Форма редагування конфігурації"""
    if config_id not in analysis_configs:
        raise HTTPException(status_code=404, detail="Конфігурація не знайдена")
    
    return templates.TemplateResponse("config_form.html", {
        "request": request,
        "config": analysis_configs[config_id],
        "title": "Редагування конфігурації"
    })

@app.post("/config/save")
async def save_config(
    name: str = Form(...),
    sites: str = Form(...),
    positive_keywords: str = Form(...),
    negative_keywords: str = Form(...),
    max_time_minutes: int = Form(20),
    max_links: int = Form(300),
    openai_api_key: str = Form(""),
    email_recipients: str = Form(...),
    config_id: str = Form(None)
):
    """Зберігає конфігурацію"""
    
    # Обробляємо дані з форми
    sites_list = parse_urls_list(sites)
    positive_list = parse_keywords_list(positive_keywords)
    negative_list = parse_keywords_list(negative_keywords)
    recipients_list = parse_emails_list(email_recipients)
    
    # Валідація
    if not sites_list:
        raise HTTPException(status_code=400, detail="Необхідно вказати хоча б один сайт")
    if not positive_list:
        raise HTTPException(status_code=400, detail="Необхідно вказати хоча б одне позитивне ключове слово")
    if not recipients_list:
        raise HTTPException(status_code=400, detail="Необхідно вказати хоча б одного отримувача")
    
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
    
    return RedirectResponse(url="/", status_code=303)

@app.get("/config/{config_id}/analyze", response_class=HTMLResponse)
async def analyze_config_form(request: Request, config_id: str):
    """Форма запуску аналізу"""
    if config_id not in analysis_configs:
        raise HTTPException(status_code=404, detail="Конфігурація не знайдена")
    
    config = analysis_configs[config_id]
    
    return templates.TemplateResponse("analyze_form.html", {
        "request": request,
        "config": config
    })

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
    """Виконує пакетний аналіз"""
    try:
        batch_result = batch_analysis_results[batch_id]
        batch_result["status"] = "running"
        
        # Аналізуємо кожен сайт
        for site_url in config.sites:
            try:
                logger.info(f"Запускаємо аналіз для {site_url}")
                
                # Запускаємо аналіз через API
                response = requests.post(f"{ANALYSIS_SERVICE_URL}/analyze", json={
                    "site_url": site_url,
                    "positive_keywords": config.positive_keywords,
                    "negative_keywords": config.negative_keywords,
                    "max_time_minutes": config.max_time_minutes,
                    "max_links": config.max_links,
                    "openai_api_key": config.openai_api_key
                })
                
                if response.status_code == 200:
                    task_data = response.json()
                    batch_result["analysis_tasks"][site_url] = {
                        "task_id": task_data["task_id"],
                        "status": "pending",
                        "site_url": site_url
                    }
                    logger.info(f"Аналіз {site_url} запущено: {task_data['task_id']}")
                else:
                    logger.error(f"Помилка запуску аналізу для {site_url}: {response.text}")
                    batch_result["failed_sites"] += 1
                    batch_result["analysis_tasks"][site_url] = {
                        "task_id": None,
                        "status": "failed",
                        "site_url": site_url,
                        "error": response.text
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
        
        # Відправляємо email якщо потрібно
        if batch_result["send_email"]:
            await send_batch_email_report(batch_id, config)
        
        batch_result["status"] = "completed"
        config.last_analysis = datetime.now()
        
    except Exception as e:
        logger.error(f"Помилка пакетного аналізу {batch_id}: {e}")
        batch_analysis_results[batch_id]["status"] = "failed"
        batch_analysis_results[batch_id]["error"] = str(e)

async def monitor_batch_analysis(batch_id: str):
    """Моніторить виконання пакетного аналізу"""
    batch_result = batch_analysis_results[batch_id]
    
    while batch_result["completed_sites"] + batch_result["failed_sites"] < batch_result["total_sites"]:
        await asyncio.sleep(10)  # Перевіряємо кожні 10 секунд
        
        for site_url, task_info in batch_result["analysis_tasks"].items():
            if task_info["status"] == "pending" and task_info["task_id"]:
                try:
                    # Перевіряємо статус аналізу
                    response = requests.get(f"{ANALYSIS_SERVICE_URL}/status/{task_info['task_id']}")
                    if response.status_code == 200:
                        status_data = response.json()
                        if status_data["status"] == "completed":
                            task_info["status"] = "completed"
                            batch_result["completed_sites"] += 1
                            logger.info(f"Аналіз {site_url} завершено")
                        elif status_data["status"] == "failed":
                            task_info["status"] = "failed"
                            batch_result["failed_sites"] += 1
                            logger.error(f"Аналіз {site_url} провалився")
                except Exception as e:
                    logger.error(f"Помилка перевірки статусу {site_url}: {e}")

async def send_batch_email_report(batch_id: str, config: SiteAnalysisConfig):
    """Відправляє email звіт про пакетний аналіз"""
    try:
        batch_result = batch_analysis_results[batch_id]
        
        # Готуємо список отримувачів
        recipients = [{"email": email} for email in config.email_recipients]
        
        # Для кожного успішного аналізу відправляємо email
        for site_url, task_info in batch_result["analysis_tasks"].items():
            if task_info["status"] == "completed" and task_info["task_id"]:
                try:
                    response = requests.post(f"{EMAIL_SERVICE_URL}/send-report", json={
                        "recipients": recipients,
                        "subject": f"Звіт аналізу: {site_url}",
                        "analysis_task_id": task_info["task_id"],
                        "analysis_service_url": ANALYSIS_SERVICE_URL,
                        "custom_message": batch_result["custom_message"],
                        "include_attachments": True
                    })
                    
                    if response.status_code == 200:
                        logger.info(f"Email звіт для {site_url} відправлено")
                    else:
                        logger.error(f"Помилка відправки email для {site_url}: {response.text}")
                        
                except Exception as e:
                    logger.error(f"Помилка відправки email для {site_url}: {e}")
        
        batch_result["email_sent"] = True
        
    except Exception as e:
        logger.error(f"Помилка відправки пакетного email звіту: {e}")

@app.get("/batch/{batch_id}", response_class=HTMLResponse)
async def view_batch_analysis(request: Request, batch_id: str):
    """Переглядає статус пакетного аналізу"""
    if batch_id not in batch_analysis_results:
        raise HTTPException(status_code=404, detail="Пакетний аналіз не знайдений")
    
    batch_result = batch_analysis_results[batch_id]
    
    return templates.TemplateResponse("batch_analysis.html", {
        "request": request,
        "batch": batch_result
    })

@app.get("/batch/{batch_id}/status")
async def get_batch_status(batch_id: str):
    """API для отримання статусу пакетного аналізу"""
    if batch_id not in batch_analysis_results:
        raise HTTPException(status_code=404, detail="Пакетний аналіз не знайдений")
    
    return batch_analysis_results[batch_id]

@app.get("/results", response_class=HTMLResponse)
async def view_results(request: Request):
    """Переглядає всі результати аналізів"""
    return templates.TemplateResponse("results.html", {
        "request": request,
        "batches": list(batch_analysis_results.values())
    })

@app.delete("/config/{config_id}")
async def delete_config(config_id: str):
    """Видаляє конфігурацію"""
    if config_id not in analysis_configs:
        raise HTTPException(status_code=404, detail="Конфігурація не знайдена")
    
    del analysis_configs[config_id]
    return {"message": "Конфігурація видалена"}

@app.delete("/batch/{batch_id}")
async def delete_batch_analysis(batch_id: str):
    """Видаляє результати пакетного аналізу"""
    if batch_id not in batch_analysis_results:
        raise HTTPException(status_code=404, detail="Пакетний аналіз не знайдений")
    
    del batch_analysis_results[batch_id]
    return {"message": "Результати пакетного аналізу видалені"}

# Створюємо директорії для шаблонів та статичних файлів
import os
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
