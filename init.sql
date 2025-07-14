-- Ініціалізація бази даних
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Таблиця конфігурацій
CREATE TABLE IF NOT EXISTS analysis_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    sites TEXT[] NOT NULL,
    positive_keywords TEXT[] NOT NULL,
    negative_keywords TEXT[] DEFAULT '{}',
    max_time_minutes INTEGER DEFAULT 20,
    max_links INTEGER DEFAULT 300,
    openai_api_key TEXT,
    email_recipients TEXT[] NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_analysis TIMESTAMP
);

-- Таблиця результатів аналізу
CREATE TABLE IF NOT EXISTS analysis_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_id UUID REFERENCES analysis_configs(id) ON DELETE CASCADE,
    site_url TEXT NOT NULL,
    task_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    pages_analyzed INTEGER DEFAULT 0,
    positive_matches JSONB DEFAULT '[]',
    negative_matches JSONB DEFAULT '[]',
    detailed_stats JSONB DEFAULT '{}',
    ai_analysis TEXT,
    analysis_time FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Таблиця email задач
CREATE TABLE IF NOT EXISTS email_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id VARCHAR(255) UNIQUE NOT NULL,
    analysis_task_id VARCHAR(255) REFERENCES analysis_results(task_id),
    recipients JSONB NOT NULL,
    subject TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    sent_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Індекси для продуктивності
CREATE INDEX IF NOT EXISTS idx_analysis_configs_created_at ON analysis_configs(created_at);
CREATE INDEX IF NOT EXISTS idx_analysis_results_task_id ON analysis_results(task_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_status ON analysis_results(status);
CREATE INDEX IF NOT EXISTS idx_analysis_results_created_at ON analysis_results(created_at);
CREATE INDEX IF NOT EXISTS idx_email_tasks_status ON email_tasks(status);

-- Функція для оновлення updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Тригер для analysis_configs
CREATE TRIGGER update_analysis_configs_updated_at
    BEFORE UPDATE ON analysis_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();