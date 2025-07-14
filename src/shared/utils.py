#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утиліти загального призначення
"""

import os
import re
import hashlib
import secrets
import string
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
import uuid
import json

def generate_secure_key(length: int = 32) -> str:
    """Генерація безпечного ключа"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_task_id() -> str:
    """Генерація унікального ID задачі"""
    return str(uuid.uuid4())

def hash_string(text: str) -> str:
    """Хешування рядка MD5"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def clean_url(url: str) -> str:
    """Очищення URL від параметрів та фрагментів"""
    parsed = urlparse(url)
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean.rstrip('/')

def is_valid_url(url: str) -> bool:
    """Перевірка валідності URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def normalize_domain(url: str) -> str:
    """Нормалізація домену з URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Видалення www
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ""

def extract_domain(url: str) -> str:
    """Витягування домену з URL"""
    try:
        return urlparse(url).netloc
    except:
        return ""

def is_same_domain(url1: str, url2: str) -> bool:
    """Перевірка чи URL належать одному домену"""
    return normalize_domain(url1) == normalize_domain(url2)

def clean_text(text: str, max_length: int = None) -> str:
    """Очищення тексту"""
    if not text:
        return ""
    
    # Видалення зайвих пробілів
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Обмеження довжини
    if max_length and len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + "..."
    
    return text

def extract_keywords_from_text(text: str, min_length: int = 3) -> List[str]:
    """Витягування ключових слів з тексту"""
    # Простий алгоритм витягування слів
    words = re.findall(r'\b[а-яА-Яa-zA-Z]{' + str(min_length) + ',}\b', text)
    return list(set(word.lower() for word in words))

def format_file_size(size_bytes: int) -> str:
    """Форматування розміру файлу"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def format_duration(seconds: float) -> str:
    """Форматування тривалості в секундах"""
    if seconds < 60:
        return f"{seconds:.1f}с"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}хв"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}год"

def validate_email(email: str) -> bool:
    """Валідація email адреси"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def sanitize_filename(filename: str) -> str:
    """Санітизація імені файлу"""
    # Видалення небезпечних символів
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Обмеження довжини
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    return filename

def parse_keywords_list(keywords_text: str) -> List[str]:
    """Парсинг списку ключових слів з тексту"""
    if not keywords_text:
        return []
    
    # Розділення по новим рядкам та комах
    keywords = re.split(r'[,\n\r]+', keywords_text)
    
    # Очищення та фільтрація
    cleaned = []
    for keyword in keywords:
        keyword = keyword.strip()
        if keyword and len(keyword) > 1:
            cleaned.append(keyword)
    
    return cleaned

def parse_urls_list(urls_text: str) -> List[str]:
    """Парсинг списку URL з тексту"""
    if not urls_text:
        return []
    
    urls = re.split(r'[\n\r]+', urls_text)
    
    cleaned = []
    for url in urls:
        url = url.strip()
        if url and is_valid_url(url):
            cleaned.append(clean_url(url))
    
    return cleaned

def parse_emails_list(emails_text: str) -> List[str]:
    """Парсинг списку email адрес з тексту"""
    if not emails_text:
        return []
    
    emails = re.split(r'[,\n\r]+', emails_text)
    
    cleaned = []
    for email in emails:
        email = email.strip()
        if email and validate_email(email):
            cleaned.append(email)
    
    return cleaned

def create_pagination(total_items: int, page: int, per_page: int = 20) -> Dict[str, Any]:
    """Створення інформації для пагінації"""
    total_pages = (total_items + per_page - 1) // per_page
    
    return {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None
    }

def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """Безпечний парсинг JSON"""
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return default

def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """Безпечна серіалізація в JSON"""
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return default

def merge_dicts(*dicts) -> Dict[str, Any]:
    """Об'єднання словників"""
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result

def get_env_bool(env_var: str, default: bool = False) -> bool:
    """Отримання boolean значення зі змінної середовища"""
    value = os.getenv(env_var, "").lower()
    return value in ('true', '1', 'yes', 'on')

def get_env_int(env_var: str, default: int = 0) -> int:
    """Отримання int значення зі змінної середовища"""
    try:
        return int(os.getenv(env_var, default))
    except (ValueError, TypeError):
        return default

def get_env_list(env_var: str, separator: str = ',', default: List[str] = None) -> List[str]:
    """Отримання списку зі змінної середовища"""
    if default is None:
        default = []
    
    value = os.getenv(env_var, "")
    if not value:
        return default
    
    return [item.strip() for item in value.split(separator) if item.strip()]

def calculate_score(positive_matches: int, total_positive: int, 
                   negative_matches: int, total_negative: int) -> float:
    """Розрахунок score для якості присутності бренду"""
    if total_positive == 0:
        return 0.0
    
    # Базова оцінка покриття позитивних слів (0-70%)
    positive_coverage = (positive_matches / total_positive) * 70
    
    # Бонус за відсутність негативних слів (0-30%)
    if total_negative > 0:
        negative_penalty = (negative_matches / total_negative) * 30
        negative_bonus = 30 - negative_penalty
    else:
        negative_bonus = 30
    
    # Загальна оцінка
    total_score = positive_coverage + negative_bonus
    
    return min(100.0, max(0.0, total_score))

def create_context_snippet(text: str, keyword: str, context_length: int = 100) -> str:
    """Створення контекстного сніпету навколо ключового слова"""
    if not text or not keyword:
        return ""
    
    # Знаходження позиції ключового слова (регістронезалежно)
    lower_text = text.lower()
    lower_keyword = keyword.lower()
    
    start_pos = lower_text.find(lower_keyword)
    if start_pos == -1:
        return ""
    
    # Розрахунок меж контексту
    context_start = max(0, start_pos - context_length)
    context_end = min(len(text), start_pos + len(keyword) + context_length)
    
    # Витягування контексту
    context = text[context_start:context_end]
    
    # Додавання еліпсису
    if context_start > 0:
        context = "..." + context
    if context_end < len(text):
        context = context + "..."
    
    return context.strip()

def get_date_range(days_back: int = 7) -> Tuple[datetime, datetime]:
    """Отримання діапазону дат"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    return start_date, end_date

def format_datetime(dt: datetime, format_string: str = "%d.%m.%Y %H:%M") -> str:
    """Форматування дати та часу"""
    if not dt:
        return ""
    return dt.strftime(format_string)

def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Обрізання рядка до максимальної довжини"""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

class ProgressTracker:
    """Клас для відстеження прогресу"""
    
    def __init__(self, total_steps: int):
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = datetime.now()
    
    def update(self, step: int = None, message: str = ""):
        """Оновлення прогресу"""
        if step is not None:
            self.current_step = step
        else:
            self.current_step += 1
        
        self.current_step = min(self.current_step, self.total_steps)
    
    def get_progress(self) -> Dict[str, Any]:
        """Отримання інформації про прогрес"""
        progress_percent = (self.current_step / self.total_steps) * 100
        elapsed_time = datetime.now() - self.start_time
        
        if self.current_step > 0:
            estimated_total = elapsed_time * (self.total_steps / self.current_step)
            remaining_time = estimated_total - elapsed_time
        else:
            remaining_time = timedelta(0)
        
        return {
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'progress_percent': round(progress_percent, 1),
            'elapsed_time': str(elapsed_time).split('.')[0],
            'remaining_time': str(remaining_time).split('.')[0] if remaining_time.total_seconds() > 0 else "0:00:00"
        }