#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обробники помилок для веб-інтерфейсу
"""

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import logging
from typing import Union

logger = logging.getLogger(__name__)

class ErrorHandlers:
    def __init__(self, templates: Jinja2Templates):
        self.templates = templates
    
    async def handle_404(self, request: Request, exc: HTTPException) -> Union[HTMLResponse, JSONResponse]:
        """Обробка помилки 404"""
        
        # Якщо це API запит, повертаємо JSON
        if request.url.path.startswith('/api/'):
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Not Found",
                    "message": "Ресурс не знайдено",
                    "path": str(request.url.path),
                    "method": request.method
                }
            )
        
        # Для веб-запитів повертаємо HTML
        if self.templates:
            try:
                return self.templates.TemplateResponse("error_404.html", {
                    "request": request,
                    "error_message": "Сторінка не знайдена",
                    "requested_path": request.url.path
                }, status_code=404)
            except:
                pass
        
        # Fallback HTML
        return HTMLResponse(
            content="""
            <html>
            <head><title>404 - Сторінка не знайдена</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1>404 - Сторінка не знайдена</h1>
                <p>Запитувана сторінка не існує.</p>
                <a href="/">Повернутися на головну</a>
            </body>
            </html>
            """,
            status_code=404
        )
    
    async def handle_500(self, request: Request, exc: Exception) -> Union[HTMLResponse, JSONResponse]:
        """Обробка серверних помилок 500"""
        
        logger.error(f"Серверна помилка 500: {exc}", exc_info=True)
        
        # Якщо це API запит, повертаємо JSON
        if request.url.path.startswith('/api/'):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "Внутрішня помилка сервера",
                    "path": str(request.url.path),
                    "method": request.method
                }
            )
        
        # Для веб-запитів повертаємо HTML
        if self.templates:
            try:
                return self.templates.TemplateResponse("error_500.html", {
                    "request": request,
                    "error_message": "Внутрішня помилка сервера",
                    "error_details": str(exc) if logger.level == logging.DEBUG else None
                }, status_code=500)
            except:
                pass
        
        # Fallback HTML
        return HTMLResponse(
            content="""
            <html>
            <head><title>500 - Помилка сервера</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1>500 - Внутрішня помилка сервера</h1>
                <p>Виникла помилка при обробці запиту.</p>
                <a href="/">Повернутися на головну</a>
            </body>
            </html>
            """,
            status_code=500
        )
    
    async def handle_503(self, request: Request, exc: HTTPException) -> Union[HTMLResponse, JSONResponse]:
        """Обробка помилки 503 - Service Unavailable"""
        
        # Якщо це API запит, повертаємо JSON
        if request.url.path.startswith('/api/'):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service Unavailable",
                    "message": "Сервіс тимчасово недоступний",
                    "path": str(request.url.path),
                    "method": request.method,
                    "details": exc.detail if hasattr(exc, 'detail') else None
                }
            )
        
        # Для веб-запитів повертаємо HTML
        if self.templates:
            try:
                return self.templates.TemplateResponse("error_503.html", {
                    "request": request,
                    "error_message": "Сервіс тимчасово недоступний",
                    "service_name": self._extract_service_name(request.url.path)
                }, status_code=503)
            except:
                pass
        
        # Fallback HTML
        return HTMLResponse(
            content="""
            <html>
            <head><title>503 - Сервіс недоступний</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1>503 - Сервіс тимчасово недоступний</h1>
                <p>Сервіс аналізу тимчасово недоступний. Спробуйте пізніше.</p>
                <a href="/">Повернутися на головну</a>
            </body>
            </html>
            """,
            status_code=503
        )
    
    def _extract_service_name(self, path: str) -> str:
        """Визначає назву сервісу з шляху"""
        if '/api/analysis/' in path:
            return "Сервіс аналізу"
        elif '/api/email/' in path:
            return "Email сервіс"
        else:
            return "Веб-сервіс"

# Функції для додавання обробників до FastAPI застосунку
def add_error_handlers(app, templates: Jinja2Templates = None):
    """Додає обробники помилок до FastAPI застосунку"""
    
    error_handlers = ErrorHandlers(templates)
    
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        return await error_handlers.handle_404(request, exc)
    
    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception):
        return await error_handlers.handle_500(request, exc)
    
    @app.exception_handler(503)
    async def service_unavailable_handler(request: Request, exc: HTTPException):
        return await error_handlers.handle_503(request, exc)
    
    logger.info("Обробники помилок додано до застосунку")
