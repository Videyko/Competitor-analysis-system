#!/bin/bash
# setup-ssl.sh - Скрипт налаштування Let's Encrypt SSL

set -e

if [ -z "$1" ]; then
    echo "Використання: ./setup-ssl.sh <домен> [email]"
    echo "Приклад: ./setup-ssl.sh example.com admin@example.com"
    exit 1
fi

DOMAIN="$1"
EMAIL="${2:-admin@$DOMAIN}"

echo "🔒 Налаштування Let's Encrypt SSL для домену: $DOMAIN"

# Перевірка чи працює nginx
if ! docker-compose ps nginx | grep -q "Up"; then
    echo "❌ Nginx не запущено. Запустіть систему спочатку: ./scripts/deploy.sh"
    exit 1
fi

# Створення директорії для certbot
docker-compose exec nginx mkdir -p /var/www/certbot

# Отримання сертифікату
echo "📜 Отримання SSL сертифікату..."
docker run --rm \
    -v ./nginx/ssl:/etc/letsencrypt \
    -v ./nginx/www:/var/www/certbot \
    certbot/certbot \
    certonly --webroot \
    -w /var/www/certbot \
    -d $DOMAIN \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email

# Копіювання сертифікатів
if [ -f "./nginx/ssl/live/$DOMAIN/fullchain.pem" ]; then
    cp "./nginx/ssl/live/$DOMAIN/fullchain.pem" "./nginx/ssl/cert.pem"
    cp "./nginx/ssl/live/$DOMAIN/privkey.pem" "./nginx/ssl/key.pem"
    
    # Перезавантаження nginx
    docker-compose restart nginx
    
    echo "✅ SSL сертифікат успішно встановлено!"
    echo "🔄 Для автоматичного поновлення додайте до crontab:"
    echo "0 12 * * * /path/to/project/scripts/renew-ssl.sh"
else
    echo "❌ Помилка отримання SSL сертифікату"
    exit 1
fi