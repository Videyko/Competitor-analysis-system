set -e

echo "🔧 Швидке виправлення критичних помилок"
echo "====================================="

# Кольори
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "📝 $1"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Створення необхідних директорій
create_directories() {
    log_info "Створення необхідних директорій..."
    
    mkdir -p logs/{nginx,app}
    mkdir -p data/{uploads,exports}
    mkdir -p backups
    mkdir -p nginx/ssl
    mkdir -p monitoring
    
    # Права доступу
    chmod 755 logs data backups
    chmod 700 nginx/ssl
    
    log_success "Директорії створено"
}

# Створення файлу .env якщо його немає
create_env_file() {
    if [ ! -f .env ]; then
        log_info "Створення .env файлу..."
        
        cat > .env << 'EOF'
# Основні налаштування
DOMAIN=localhost
SECRET_KEY=your-very-secure-secret-key-change-this-in-production

# База даних PostgreSQL
POSTGRES_DB=competitor_db
POSTGRES_USER=competitor_user
POSTGRES_PASSWORD=secure-db-password

# Redis
REDIS_PASSWORD=secure-redis-password

# Email налаштування (Gmail)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-gmail-app-password

# OpenAI для ШІ аналізу (опціонально)
OPENAI_API_KEY=

# Налаштування аналізу
MAX_WORKERS=5
LOG_LEVEL=INFO

# Grafana
GRAFANA_PASSWORD=admin

# URL мікросервісів
ANALYSIS_SERVICE_URL=http://analysis-service:8000
EMAIL_SERVICE_URL=http://email-service:8001
EOF
        
        log_success ".env файл створено"
        log_error "ВАЖЛИВО: Налаштуйте .env файл перед запуском!"
    else
        log_success ".env файл вже існує"
    fi
}

# Виправлення прав доступу
fix_permissions() {
    log_info "Виправлення прав доступу..."
    
    # Docker файли
    chmod +x scripts/*.sh 2>/dev/null || true
    
    # Логи
    sudo chown -R $USER:$USER logs 2>/dev/null || true
    
    # Дані
    sudo chown -R $USER:$USER data 2>/dev/null || true
    
    log_success "Права доступу виправлено"
}

# Очищення старих контейнерів
cleanup_containers() {
    log_info "Очищення старих контейнерів..."
    
    # Зупинка контейнерів
    docker-compose down 2>/dev/null || true
    
    # Видалення старих образів
    docker image prune -f 2>/dev/null || true
    
    # Видалення неіспользуваних volume (обережно!)
    # docker volume prune -f 2>/dev/null || true
    
    log_success "Очищення завершено"
}

# Перевірка Docker
check_docker() {
    log_info "Перевірка Docker..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker не встановлено"
        echo "Встановіть Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose не встановлено"
        echo "Встановіть Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker не запущений"
        exit 1
    fi
    
    log_success "Docker працює"
}

# Перевірка мережі
check_network() {
    log_info "Перевірка мережі Docker..."
    
    # Створюємо мережу якщо її немає
    if ! docker network ls | grep -q "competitor_network"; then
        docker network create competitor_network 2>/dev/null || true
    fi
    
    log_success "Мережа налаштована"
}

# Створення SSL сертифікату для localhost
create_ssl_cert() {
    log_info "Створення SSL сертифікату для localhost..."
    
    if [ ! -f "nginx/ssl/cert.pem" ]; then
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/key.pem \
            -out nginx/ssl/cert.pem \
            -subj "/C=UA/ST=Kyiv/L=Kyiv/O=CompetitorAnalysis/CN=localhost" \
            2>/dev/null || true
        
        log_success "SSL сертифікат створено"
    else
        log_success "SSL сертифікат вже існує"
    fi
}

# Виправлення конфігурації nginx
fix_nginx_config() {
    log_info "Перевірка конфігурації nginx..."
    
    if [ ! -f "nginx/conf.d/default.conf" ]; then
        log_info "Створення базової конфігурації nginx..."
        
        mkdir -p nginx/conf.d
        cat > nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name _;

    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    location / {
        proxy_pass http://web-interface:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /api/analysis/ {
        rewrite ^/api/analysis/(.*)$ /$1 break;
        proxy_pass http://analysis-service:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/email/ {
        rewrite ^/api/email/(.*)$ /$1 break;
        proxy_pass http://email-service:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
        
        log_success "Конфігурація nginx створена"
    else
        log_success "Конфігурація nginx вже існує"
    fi
}

# Перезбудова та запуск
rebuild_and_start() {
    log_info "Перезбудова та запуск сервісів..."
    
    # Зупинка
    docker-compose down 2>/dev/null || true
    
    # Перезбудова
    docker-compose build --no-cache
    
    # Запуск
    docker-compose up -d
    
    log_success "Сервіси запущено"
}

# Очікування готовності сервісів
wait_for_services() {
    log_info "Очікування готовності сервісів..."
    
    max_attempts=60
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f -s http://localhost/health > /dev/null 2>&1; then
            log_success "Сервіси готові!"
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 5
        echo -n "."
    done
    
    echo ""
    log_error "Сервіси не запустилися за 5 хвилин"
    return 1
}

# Показ інформації
show_info() {
    echo ""
    echo "🎉 Виправлення завершено!"
    echo "========================"
    echo ""
    echo "🌐 Веб-інтерфейс: http://localhost"
    echo "📊 API документація:"
    echo "   - Analysis: http://localhost:8000/docs"
    echo "   - Email: http://localhost:8001/docs"
    echo "   - Web: http://localhost:8002/docs"
    echo ""
    echo "🔧 Корисні команди:"
    echo "   docker-compose logs -f                   # Дивитися логи"
    echo "   docker-compose ps                        # Статус сервісів"
    echo "   docker-compose restart service-name      # Перезапуск сервісу"
    echo "   ./test.sh                                # Тестування системи"
    echo ""
    echo "⚠️  Не забудьте налаштувати email в .env файлі!"
}

# Показ помилок
show_errors() {
    echo ""
    log_error "Виникли помилки. Перевірте логи:"
    echo ""
    docker-compose logs --tail=20
}

# Головна функція
main() {
    check_docker
    create_directories
    create_env_file
    fix_permissions
    check_network
    create_ssl_cert
    fix_nginx_config
    cleanup_containers
    rebuild_and_start
    
    if wait_for_services; then
        show_info
    else
        show_errors
        exit 1
    fi
}

# Запуск
case "${1:-}" in
    "clean")
        cleanup_containers
        ;;
    "env")
        create_env_file
        ;;
    "dirs")
        create_directories
        ;;
    "ssl")
        create_ssl_cert
        ;;
    "nginx")
        fix_nginx_config
        ;;
    "rebuild")
        rebuild_and_start
        ;;
    *)
        main
        ;;
esac
