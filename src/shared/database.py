#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль роботи з базою даних PostgreSQL
"""

import os
import asyncio
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, JSON, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from datetime import datetime
import uuid

# Базова модель
Base = declarative_base()

class AnalysisConfig(Base):
    """Модель конфігурації аналізу"""
    __tablename__ = 'analysis_configs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    sites = Column(ARRAY(Text), nullable=False)
    positive_keywords = Column(ARRAY(Text), nullable=False)
    negative_keywords = Column(ARRAY(Text), default=[])
    max_time_minutes = Column(Integer, default=20)
    max_links = Column(Integer, default=300)
    openai_api_key = Column(Text)
    email_recipients = Column(ARRAY(Text), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_analysis = Column(DateTime)

class AnalysisResult(Base):
    """Модель результату аналізу"""
    __tablename__ = 'analysis_results'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id = Column(UUID(as_uuid=True))
    site_url = Column(Text, nullable=False)
    task_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), default='pending')
    pages_analyzed = Column(Integer, default=0)
    positive_matches = Column(JSON, default=[])
    negative_matches = Column(JSON, default=[])
    detailed_stats = Column(JSON, default={})
    ai_analysis = Column(Text)
    analysis_time = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class EmailTask(Base):
    """Модель email задачі"""
    __tablename__ = 'email_tasks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(255), unique=True, nullable=False)
    analysis_task_id = Column(String(255))
    recipients = Column(JSON, nullable=False)
    subject = Column(Text, nullable=False)
    status = Column(String(50), default='pending')
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class DatabaseManager:
    """Менеджер бази даних"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'postgresql://competitor_user:competitor_pass@localhost:5432/competitor_db'
        )
        self.engine = None
        self.SessionLocal = None
        self._initialize()
    
    def _initialize(self):
        """Ініціалізація з'єднання з БД"""
        self.engine = create_engine(
            self.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=300
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        """Створення таблиць"""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Отримання сесії БД"""
        return self.SessionLocal()
    
    def save_analysis_config(self, config_data: Dict[str, Any]) -> str:
        """Збереження конфігурації аналізу"""
        with self.get_session() as session:
            config = AnalysisConfig(**config_data)
            session.add(config)
            session.commit()
            return str(config.id)
    
    def get_analysis_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        """Отримання конфігурації аналізу"""
        with self.get_session() as session:
            config = session.query(AnalysisConfig).filter(
                AnalysisConfig.id == config_id
            ).first()
            
            if config:
                return {
                    'id': str(config.id),
                    'name': config.name,
                    'sites': config.sites,
                    'positive_keywords': config.positive_keywords,
                    'negative_keywords': config.negative_keywords,
                    'max_time_minutes': config.max_time_minutes,
                    'max_links': config.max_links,
                    'openai_api_key': config.openai_api_key,
                    'email_recipients': config.email_recipients,
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'last_analysis': config.last_analysis.isoformat() if config.last_analysis else None
                }
            return None
    
    def get_all_analysis_configs(self) -> List[Dict[str, Any]]:
        """Отримання всіх конфігурацій"""
        with self.get_session() as session:
            configs = session.query(AnalysisConfig).order_by(AnalysisConfig.created_at.desc()).all()
            
            return [
                {
                    'id': str(config.id),
                    'name': config.name,
                    'sites': config.sites,
                    'positive_keywords': config.positive_keywords,
                    'negative_keywords': config.negative_keywords,
                    'max_time_minutes': config.max_time_minutes,
                    'max_links': config.max_links,
                    'email_recipients': config.email_recipients,
                    'created_at': config.created_at.isoformat(),
                    'last_analysis': config.last_analysis.isoformat() if config.last_analysis else None
                }
                for config in configs
            ]
    
    def save_analysis_result(self, result_data: Dict[str, Any]) -> str:
        """Збереження результату аналізу"""
        with self.get_session() as session:
            result = AnalysisResult(**result_data)
            session.add(result)
            session.commit()
            return str(result.id)
    
    def get_analysis_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Отримання результату аналізу"""
        with self.get_session() as session:
            result = session.query(AnalysisResult).filter(
                AnalysisResult.task_id == task_id
            ).first()
            
            if result:
                return {
                    'id': str(result.id),
                    'config_id': str(result.config_id) if result.config_id else None,
                    'site_url': result.site_url,
                    'task_id': result.task_id,
                    'status': result.status,
                    'pages_analyzed': result.pages_analyzed,
                    'positive_matches': result.positive_matches,
                    'negative_matches': result.negative_matches,
                    'detailed_stats': result.detailed_stats,
                    'ai_analysis': result.ai_analysis,
                    'analysis_time': result.analysis_time,
                    'created_at': result.created_at.isoformat(),
                    'completed_at': result.completed_at.isoformat() if result.completed_at else None
                }
            return None
    
    def update_analysis_result(self, task_id: str, update_data: Dict[str, Any]):
        """Оновлення результату аналізу"""
        with self.get_session() as session:
            session.query(AnalysisResult).filter(
                AnalysisResult.task_id == task_id
            ).update(update_data)
            session.commit()
    
    def save_email_task(self, task_data: Dict[str, Any]) -> str:
        """Збереження email задачі"""
        with self.get_session() as session:
            task = EmailTask(**task_data)
            session.add(task)
            session.commit()
            return str(task.id)
    
    def get_email_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Отримання email задачі"""
        with self.get_session() as session:
            task = session.query(EmailTask).filter(
                EmailTask.task_id == task_id
            ).first()
            
            if task:
                return {
                    'id': str(task.id),
                    'task_id': task.task_id,
                    'analysis_task_id': task.analysis_task_id,
                    'recipients': task.recipients,
                    'subject': task.subject,
                    'status': task.status,
                    'sent_count': task.sent_count,
                    'failed_count': task.failed_count,
                    'created_at': task.created_at.isoformat(),
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None
                }
            return None
    
    def update_email_task(self, task_id: str, update_data: Dict[str, Any]):
        """Оновлення email задачі"""
        with self.get_session() as session:
            session.query(EmailTask).filter(
                EmailTask.task_id == task_id
            ).update(update_data)
            session.commit()
    
    def delete_analysis_config(self, config_id: str) -> bool:
        """Видалення конфігурації"""
        with self.get_session() as session:
            deleted = session.query(AnalysisConfig).filter(
                AnalysisConfig.id == config_id
            ).delete()
            session.commit()
            return deleted > 0
    
    def get_recent_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Отримання останніх результатів"""
        with self.get_session() as session:
            results = session.query(AnalysisResult).order_by(
                AnalysisResult.created_at.desc()
            ).limit(limit).all()
            
            return [
                {
                    'task_id': result.task_id,
                    'site_url': result.site_url,
                    'status': result.status,
                    'pages_analyzed': result.pages_analyzed,
                    'created_at': result.created_at.isoformat(),
                    'completed_at': result.completed_at.isoformat() if result.completed_at else None
                }
                for result in results
            ]

# Глобальний екземпляр менеджера БД
db_manager = DatabaseManager()