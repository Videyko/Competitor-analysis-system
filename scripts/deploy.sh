#!/bin/bash
# deploy.sh - Основний скрипт розгортання

set -e

echo "🚀 Розгортання системи аналізу конкурентів на DigitalOcean"
echo "============================================================"

# Кольори для виводу
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функції для логування
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Перевірка залежностей
check_dependencies() {
    log_info "Перевірка залежностей..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker не встановлено. Встановіть Docker та повторіть спробу."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose не встановлено. Встановіть Docker Compose та повторіть спробу."
        exit 1
    fi
    
    log_success "Всі залежності встановлено"
}

# Створення .env файлу
setup_environment() {
    log_info "Налаштування середовища..."
    
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            log_warning "Створено .env файл з прикладу. Будь ласка, налаштуйте його перед продовженням."
            echo ""
            echo "Редагуйте файл .env та встановіть наступні значення:"
            echo "- DOMAIN (ваш домен)"
            echo "- SECRET_KEY (безпечний ключ)"
            echo "- Паролі для бази даних та Redis"
            echo "- Налаштування email"
            echo "- OpenAI API ключ (опціонально)"
            echo ""
            read -p "Натисніть Enter після налаштування .env файлу..."
        else
            log_error ".env.example файл не знайдено"
            exit 1
        fi
    fi
    
    # Завантаження змінних середовища
    source .env
    
    # Перевірка обов'язкових змінних
    required_vars=("DOMAIN" "SECRET_KEY" "POSTGRES_PASSWORD" "REDIS_PASSWORD" "EMAIL_USER" "EMAIL_PASSWORD")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "Змінна $var не встановлена в .env файлі"
            exit 1
        fi
    done
    
    log_success "Середовище налаштовано"
}

# Створення необхідних директорій
create_directories() {
    log_info "Створення директорій..."
    
    mkdir -p logs/{nginx,app}
    mkdir -p data/{uploads,exports}
    mkdir -p backups
    mkdir -p nginx/ssl
    
    # Встановлення прав доступу
    chmod 755 logs data backups
    chmod 700 nginx/ssl
    
    log_success "Директорії створено"
}

# Генерація SSL сертифікатів
setup_ssl() {
    log_info "Налаштування SSL..."
    
    if [ "$DOMAIN" != "localhost" ] && [ ! -f "nginx/ssl/cert.pem" ]; then
        log_info "Генерація self-signed SSL сертифікату для $DOMAIN"
        
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/key.pem \
            -out nginx/ssl/cert.pem \
            -subj "/C=UA/ST=Kyiv/L=Kyiv/O=CompetitorAnalysis/CN=$DOMAIN"
        
        log_success "SSL сертифікат створено"
        log_warning "Використовується self-signed сертифікат. Для продакшн використовуйте Let's Encrypt"
    else
        log_info "SSL вже налаштовано або використовується localhost"
    fi
}

# Збірка та запуск контейнерів
deploy_containers() {
    log_info "Збірка та запуск контейнерів..."
    
    # Зупинка існуючих контейнерів
    docker-compose down 2>/dev/null || true
    
    # Збірка образів
    log_info "Збірка Docker образів..."
    docker-compose build --no-cache
    
    # Запуск основних сервісів
    log_info "Запуск основних сервісів..."
    docker-compose up -d redis postgres
    
    # Очікування готовності бази даних
    log_info "Очікування готовності бази даних..."
    sleep 15
    
    # Запуск решти сервісів
    log_info "Запуск всіх сервісів..."
    docker-compose up -d
    
    log_success "Контейнери запущено"
}

# Перевірка здоров'я сервісів
health_check() {
    log_info "Перевірка здоров'я сервісів..."
    
    max_attempts=30
    attempt=0
    
    services=("nginx:80" "analysis-service:8000" "email-service:8001" "web-interface:8002")
    
    for service in "${services[@]}"; do
        name=$(echo $service | cut -d: -f1)
        port=$(echo $service | cut -d: -f2)
        
        log_info "Перевірка $name..."
        attempt=0
        
        while [ $attempt -lt $max_attempts ]; do
            if curl -f -s http://localhost:$port/health > /dev/null 2>&1 || \
               curl -f -s http://localhost:$port/ > /dev/null 2>&1; then
                log_success "$name доступний"
                break
            fi
            
            attempt=$((attempt + 1))
            if [ $attempt -eq $max_attempts ]; then
                log_error "$name недоступний після $max_attempts спроб"
                return 1
            fi
            
            sleep 2
        done
    done
    
    log_success "Всі сервіси працюють"
}

# Показ інформації про розгортання
show_deployment_info() {
    echo ""
    echo "🎉 Розгортання завершено успішно!"
    echo "=================================="
    echo ""
    echo "🌐 Веб-інтерфейс: http://$DOMAIN"
    echo "🔍 API аналізу: http://$DOMAIN/api/analysis/"
    echo "📧 API email: http://$DOMAIN/api/email/"
    echo ""
    echo "📊 Моніторинг:"
    echo "   Prometheus: http://$DOMAIN:9090 (якщо увімкнено)"
    echo "   Grafana: http://$DOMAIN:3000 (якщо увімкнено)"
    echo ""
    echo "🔧 Управління:"
    echo "   Статус: docker-compose ps"
    echo "   Логи: docker-compose logs -f"
    echo "   Зупинка: docker-compose down"
    echo "   Оновлення: ./scripts/update.sh"
    echo "   Резервне копіювання: ./scripts/backup.sh"
    echo ""
    echo "📁 Важливі файли:"
    echo "   Логи: ./logs/"
    echo "   Дані: ./data/"
    echo "   Резервні копії: ./backups/"
    echo ""
}

# Основна функція
main() {
    echo "Починаємо розгортання..."
    
    check_dependencies
    setup_environment
    create_directories
    setup_ssl
    deploy_containers
    
    log_info "Очікування запуску сервісів..."
    sleep 30
    
    if health_check; then
        show_deployment_info
    else
        log_error "Деякі сервіси не запустилися. Перевірте логи: docker-compose logs"
        exit 1
    fi
}

# Обробка аргументів командного рядка
case "${1:-}" in
    "monitoring")
        log_info "Запуск з моніторингом..."
        export COMPOSE_PROFILES=monitoring
        main
        ;;
    "ssl")
        setup_ssl
        ;;
    "check")
        health_check
        ;;
    *)
        main
        ;;
esac