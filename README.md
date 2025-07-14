# 🔍 Система аналізу конкурентів

Повністю автоматизована система для моніторингу присутності вашого бренду на сайтах партнерів та виявлення згадок конкурентів.

## 🚀 Швидкий старт на DigitalOcean

### 1. Створення Droplet

**Мінімальні вимоги:**
- 2 CPU, 4GB RAM, 80GB SSD
- Ubuntu 22.04 LTS

**Рекомендовано:**
- 4 CPU, 8GB RAM, 160GB SSD

### 2. Встановлення залежностей

```bash
# Підключення до сервера
ssh root@your-server-ip

# Оновлення системи
apt update && apt upgrade -y

# Встановлення Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Встановлення Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### 3. Розгортання проекту

```bash
# Клонування репозиторію
git clone https://github.com/your-username/competitor-analysis.git
cd competitor-analysis

# Налаштування конфігурації
cp .env.example .env
nano .env  # Заповніть необхідні дані

# Запуск розгортання
chmod +x scripts/*.sh
./scripts/deploy.sh
```

### 4. Налаштування .env файлу

```bash
# Ваш домен
DOMAIN=your-domain.com

# Безпечні паролі
SECRET_KEY=your-very-secure-secret-key
POSTGRES_PASSWORD=secure-db-password
REDIS_PASSWORD=secure-redis-password

# Email налаштування
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-gmail-app-password

# OpenAI для ШІ аналізу (опціонально)
OPENAI_API_KEY=sk-your-openai-key
```

## 🎯 Функціональність

### ✅ Основні можливості

- **Автоматичний аналіз сайтів** - сканування всіх сторінок партнерів
- **Пошук ключових слів** - виявлення згадок вашого бренду
- **Моніторинг конкурентів** - контроль згадок конкуруючих брендів
- **Детальні звіти** - HTML email + Excel файли
- **ШІ аналіз** - інтелектуальна оцінка якості присутності
- **Веб-інтерфейс** - зручне управління без коду

### 📊 Детальна статистика

- Повний список сторінок для кожного ключового слова
- Кількість згадок на кожній сторінці
- Контекст кожної знахідки
- Список незнайдених слів з рекомендаціями

### 📧 Автоматичні звіти

- **HTML email** з детальною розбивкою
- **Excel файли** з 6 аркушами даних
- **Рекомендації** для покращення співпраці
- **Масова розсилка** на кілька адрес

## 🏗️ Архітектура

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Веб-інтерфейс │────│ Аналіз сервіс │────│ Email сервіс │
│   (8002)    │    │    (8000)   │    │    (8001)   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
              ┌─────────────┼─────────────┐
              │             │             │
         ┌─────────┐   ┌─────────┐   ┌─────────┐
         │  Nginx  │   │ PostgeSQL│   │  Redis  │
         │  (80)   │   │  (5432) │   │ (6379)  │
         └─────────┘   └─────────┘   └─────────┘
```

## 📱 Використання

### Веб-інтерфейс

1. Відкрийте `https://your-domain.com`
2. Створіть конфігурацію аналізу
3. Додайте сайти та ключові слова
4. Запустіть аналіз
5. Отримайте детальні звіти на email

### API

```bash
# Запуск аналізу
curl -X POST "https://your-domain.com/api/analysis/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "site_url": "https://partner.com",
    "positive_keywords": ["your-brand", "your-product"],
    "negative_keywords": ["competitor-a", "competitor-b"]
  }'

# Перевірка статусу
curl "https://your-domain.com/api/analysis/status/{task_id}"

# Отримання результату
curl "https://your-domain.com/api/analysis/result/{task_id}"
```

## 🔧 Управління

### Основні команди

```bash
# Статус сервісів
docker-compose ps

# Перегляд логів
docker-compose logs -f

# Перезапуск сервісу
docker-compose restart service-name

# Оновлення системи
./scripts/update.sh

# Резервне копіювання
./scripts/backup.sh
```

### SSL сертифікат

```bash
# Автоматичне налаштування Let's Encrypt
./scripts/setup-ssl.sh your-domain.com admin@your-domain.com
```

### Моніторинг

```bash
# Запуск з моніторингом
./scripts/deploy.sh monitoring

# Доступ до панелей
# Prometheus: https://your-domain.com:9090
# Grafana: https://your-domain.com:3000 (admin/admin)
```

## 🔒 Безпека

### Firewall

```bash
# Налаштування UFW
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

### Автоматичні оновлення

```bash
# Налаштування unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

## 📈 Масштабування

### Горизонтальне масштабування

```yaml
# docker-compose.override.yml
services:
  analysis-service:
    deploy:
      replicas: 3
```

### Вертикальне масштабування

```yaml
services:
  analysis-service:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
```

## 🚨 Troubleshooting

### Поширені проблеми

```bash
# Сервіс не запускається
docker-compose logs service-name

# Проблеми з пам'яттю
free -h
docker system prune -a

# Проблеми з SSL
certbot certificates
nginx -t
```

### Корисні команди

```bash
# Статус системи
./scripts/deploy.sh check

# Очищення Docker
docker system prune -a --volumes

# Перегляд ресурсів
docker stats
```

## 💰 Вартість на DigitalOcean

| Конфігурація | CPU | RAM | Диск | Ціна/місяць |
|-------------|-----|-----|------|-------------|
| Розробка    | 2   | 4GB | 80GB | $24         |
| Продакшн    | 4   | 8GB | 160GB| $48         |
| Високе навантаження | 8 | 16GB | 320GB | $96 |

## 🤝 Підтримка

- 📧 Email: support@your-domain.com
- 💬 Issues: [GitHub Issues](https://github.com/your-username/competitor-analysis/issues)
- 📖 Документація: [Wiki](https://github.com/your-username/competitor-analysis/wiki)

## 📝 Ліцензія

MIT License - використовуйте вільно для комерційних та некомерційних цілей.

## 🎯 Roadmap

- [ ] Telegram інтеграція
- [ ] Slack повідомлення  
- [ ] PDF звіти
- [ ] API для мобільних додатків
- [ ] Машинне навчання для покращення аналізу

---

**Готово до production використання за 5 хвилин! 🚀**