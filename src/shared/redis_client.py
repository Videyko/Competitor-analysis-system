#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis клієнт для кешування та черг
"""

import os
import json
import redis
from typing import Any, Optional, Dict, List
from datetime import timedelta

class RedisClient:
    """Клієнт для роботи з Redis"""
    
    def __init__(self, redis_url: str = None, db: int = 0):
        self.redis_url = redis_url or os.getenv(
            'REDIS_URL', 
            'redis://:defaultpassword@localhost:6379/0'
        )
        
        # Парсинг URL та зміна DB
        if redis_url and f"/{db}" not in redis_url:
            self.redis_url = f"{redis_url.rstrip('/')}/{db}"
        
        self.client = redis.from_url(self.redis_url, decode_responses=True)
        self._test_connection()
    
    def _test_connection(self):
        """Тестування з'єднання з Redis"""
        try:
            self.client.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"Не вдалося підключитися до Redis: {e}")
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Встановлення значення"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            
            if ttl:
                return self.client.setex(key, ttl, value)
            else:
                return self.client.set(key, value)
        except Exception as e:
            print(f"Помилка збереження в Redis: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Отримання значення"""
        try:
            value = self.client.get(key)
            if value is None:
                return None
            
            # Спроба парсингу як JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            print(f"Помилка отримання з Redis: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Видалення ключа"""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            print(f"Помилка видалення з Redis: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Перевірка існування ключа"""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            print(f"Помилка перевірки існування в Redis: {e}")
            return False
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Збільшення числового значення"""
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            print(f"Помилка інкрементування в Redis: {e}")
            return 0
    
    def expire(self, key: str, ttl: int) -> bool:
        """Встановлення TTL для ключа"""
        try:
            return self.client.expire(key, ttl)
        except Exception as e:
            print(f"Помилка встановлення TTL в Redis: {e}")
            return False
    
    def keys(self, pattern: str = "*") -> List[str]:
        """Отримання списку ключів за шаблоном"""
        try:
            return self.client.keys(pattern)
        except Exception as e:
            print(f"Помилка отримання ключів з Redis: {e}")
            return []
    
    def flush_db(self):
        """Очищення поточної бази даних"""
        try:
            return self.client.flushdb()
        except Exception as e:
            print(f"Помилка очищення Redis DB: {e}")
            return False
    
    # Методи для роботи з хешами
    def hset(self, name: str, key: str, value: Any) -> bool:
        """Встановлення значення в хеш"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            return bool(self.client.hset(name, key, value))
        except Exception as e:
            print(f"Помилка hset в Redis: {e}")
            return False
    
    def hget(self, name: str, key: str) -> Optional[Any]:
        """Отримання значення з хешу"""
        try:
            value = self.client.hget(name, key)
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            print(f"Помилка hget з Redis: {e}")
            return None
    
    def hgetall(self, name: str) -> Dict[str, Any]:
        """Отримання всіх значень з хешу"""
        try:
            data = self.client.hgetall(name)
            result = {}
            for key, value in data.items():
                try:
                    result[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[key] = value
            return result
        except Exception as e:
            print(f"Помилка hgetall з Redis: {e}")
            return {}
    
    def hdel(self, name: str, key: str) -> bool:
        """Видалення ключа з хешу"""
        try:
            return bool(self.client.hdel(name, key))
        except Exception as e:
            print(f"Помилка hdel в Redis: {e}")
            return False
    
    # Методи для роботи зі списками (черги)
    def lpush(self, name: str, value: Any) -> int:
        """Додавання елемента в початок списку"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            return self.client.lpush(name, value)
        except Exception as e:
            print(f"Помилка lpush в Redis: {e}")
            return 0
    
    def rpush(self, name: str, value: Any) -> int:
        """Додавання елемента в кінець списку"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            return self.client.rpush(name, value)
        except Exception as e:
            print(f"Помилка rpush в Redis: {e}")
            return 0
    
    def lpop(self, name: str) -> Optional[Any]:
        """Отримання та видалення елемента з початку списку"""
        try:
            value = self.client.lpop(name)
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            print(f"Помилка lpop з Redis: {e}")
            return None
    
    def rpop(self, name: str) -> Optional[Any]:
        """Отримання та видалення елемента з кінця списку"""
        try:
            value = self.client.rpop(name)
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            print(f"Помилка rpop з Redis: {e}")
            return None
    
    def llen(self, name: str) -> int:
        """Отримання довжини списку"""
        try:
            return self.client.llen(name)
        except Exception as e:
            print(f"Помилка llen з Redis: {e}")
            return 0
    
    # Кешування з автоматичним TTL
    def cache_set(self, key: str, value: Any, ttl_minutes: int = 60):
        """Кешування з TTL в хвилинах"""
        return self.set(key, value, ttl=ttl_minutes * 60)
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Отримання з кешу"""
        return self.get(key)
    
    # Методи для задач
    def add_task(self, queue_name: str, task_data: Dict[str, Any]) -> bool:
        """Додавання задачі в чергу"""
        task_data['timestamp'] = int(time.time())
        return bool(self.rpush(f"queue:{queue_name}", task_data))
    
    def get_task(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Отримання задачі з черги"""
        return self.lpop(f"queue:{queue_name}")
    
    def get_queue_size(self, queue_name: str) -> int:
        """Отримання розміру черги"""
        return self.llen(f"queue:{queue_name}")
    
    # Статистика
    def get_stats(self) -> Dict[str, Any]:
        """Отримання статистики Redis"""
        try:
            info = self.client.info()
            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', '0B'),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'uptime_in_seconds': info.get('uptime_in_seconds', 0)
            }
        except Exception as e:
            print(f"Помилка отримання статистики Redis: {e}")
            return {}

class CacheManager:
    """Менеджер кешування для різних типів даних"""
    
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
    
    def cache_analysis_result(self, task_id: str, result: Dict[str, Any], ttl_hours: int = 24):
        """Кешування результату аналізу"""
        return self.redis.cache_set(f"analysis_result:{task_id}", result, ttl_hours * 60)
    
    def get_cached_analysis_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Отримання кешованого результату аналізу"""
        return self.redis.cache_get(f"analysis_result:{task_id}")
    
    def cache_site_content(self, url: str, content: str, ttl_hours: int = 6):
        """Кешування контенту сайту"""
        # Хешування URL для безпечного ключа
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.redis.cache_set(f"site_content:{url_hash}", content, ttl_hours * 60)
    
    def get_cached_site_content(self, url: str) -> Optional[str]:
        """Отримання кешованого контенту сайту"""
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.redis.cache_get(f"site_content:{url_hash}")
    
    def cache_email_template(self, template_id: str, rendered_html: str, ttl_hours: int = 12):
        """Кешування відрендереного email шаблону"""
        return self.redis.cache_set(f"email_template:{template_id}", rendered_html, ttl_hours * 60)
    
    def get_cached_email_template(self, template_id: str) -> Optional[str]:
        """Отримання кешованого email шаблону"""
        return self.redis.cache_get(f"email_template:{template_id}")

# Глобальні екземпляри для різних сервісів
analysis_redis = RedisClient(db=0)  # База 0 для аналізу
email_redis = RedisClient(db=1)     # База 1 для email
web_redis = RedisClient(db=2)       # База 2 для веб-інтерфейсу

# Менеджери кешування
analysis_cache = CacheManager(analysis_redis)
email_cache = CacheManager(email_redis)
web_cache = CacheManager(web_redis)