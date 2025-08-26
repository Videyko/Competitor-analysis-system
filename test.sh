set -e

echo "🧪 Швидкий тест системи аналізу конкурентів"
echo "=========================================="

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

# Перевірка чи Docker запущений
check_docker() {
    log_info "Перевірка Docker..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker не встановлено"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker не запущений"
        exit 1
    fi
    
    log_success "Docker працює"
}

# Перевірка сервісів
check_services() {
    log_info "Перевірка статусу сервісів..."
    
    services=(
        "nginx:80:Nginx"
        "analysis-service:8000:Analysis Service" 
        "email-service:8001:Email Service"
        "web-interface:8002:Web Interface"
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r service port name <<< "$service_info"
        
        if curl -f -s http://localhost:$port/health > /dev/null 2>&1; then
            log_success "$name ($port) - OK"
        elif curl -f -s http://localhost:$port/ > /dev/null 2>&1; then
            log_success "$name ($port) - OK (no health endpoint)"
        else
            log_error "$name ($port) - НЕДОСТУПНИЙ"
        fi
    done
}

# Тест API аналізу
test_analysis_api() {
    log_info "Тестування Analysis API..."
    
    # Тест health endpoint
    if curl -f -s http://localhost:8000/health > /dev/null; then
        log_success "Analysis Service health - OK"
    else
        log_error "Analysis Service health - FAIL"
        return 1
    fi
    
    # Тест запуску аналізу
    log_info "Запуск тестового аналізу..."
    
    response=$(curl -s -X POST "http://localhost:8000/analyze" \
        -H "Content-Type: application/json" \
        -d '{
            "site_url": "https://example.com",
            "positive_keywords": ["example", "test"],
            "negative_keywords": ["competitor"],
            "max_time_minutes": 2,
            "max_links": 10
        }')
    
    if echo "$response" | grep -q "task_id"; then
        task_id=$(echo "$response" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
        log_success "Аналіз запущено: $task_id"
        
        # Перевіряємо статус
        sleep 2
        status_response=$(curl -s "http://localhost:8000/status/$task_id")
        if echo "$status_response" | grep -q "status"; then
            status=$(echo "$status_response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
            log_info "Статус аналізу: $status"
        fi
    else
        log_error "Помилка запуску аналізу"
        echo "Response: $response"
    fi
}

# Тест Email API
test_email_api() {
    log_info "Тестування Email API..."
    
    if curl -f -s http://localhost:8001/health > /dev/null; then
        log_success "Email Service health - OK"
    else
        log_error "Email Service health - FAIL"
    fi
}

# Тест веб-інтерфейсу
test_web_interface() {
    log_info "Тестування веб-інтерфейсу..."
    
    if curl -f -s http://localhost:8002/health > /dev/null; then
        log_success "Web Interface health - OK"
    else
        log_error "Web Interface health - FAIL"
    fi
    
    # Тест головної сторінки
    if curl -f -s http://localhost/ > /dev/null; then
        log_success "Головна сторінка доступна"
    else
        log_warning "Головна сторінка недоступна через nginx"
    fi
    
    # Тест прямого доступу до веб-інтерфейсу
    if curl -f -s http://localhost:8002/ > /dev/null; then
        log_success "Веб-інтерфейс доступний"
    else
        log_error "Веб-інтерфейс недоступний"
    fi
}

# Тест бази даних
test_database() {
    log_info "Тестування бази даних..."
    
    if docker-compose exec -T postgres pg_isready -U competitor_user > /dev/null 2>&1; then
        log_success "PostgreSQL доступна"
    else
        log_error "PostgreSQL недоступна"
    fi
}

# Тест Redis
test_redis() {
    log_info "Тестування Redis..."
    
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        log_success "Redis доступний"
    else
        log_error "Redis недоступний"
    fi
}

# Показ логів при помилках
show_logs() {
    log_info "Останні логи сервісів:"
    echo ""
    
    services=("nginx" "analysis-service" "email-service" "web-interface")
    
    for service in "${services[@]}"; do
        echo "=== $service ==="
        docker-compose logs --tail=5 "$service" 2>/dev/null || echo "Логи недоступні"
        echo ""
    done
}

# Головна функція тестування
main() {
    check_docker
    
    # Перевіряємо чи сервіси запущені
    if ! docker-compose ps | grep -q "Up"; then
        log_error "Сервіси не запущені. Запустіть: docker-compose up -d"
        exit 1
    fi
    
    log_info "Очікуємо 10 секунд для запуску сервісів..."
    sleep 10
    
    # Запускаємо тести
    check_services
    test_database
    test_redis
    test_analysis_api
    test_email_api
    test_web_interface
    
    echo ""
    log_success "Тестування завершено!"
    echo ""
    echo "🌐 Веб-інтерфейс: http://localhost"
    echo "📊 API документація:"
    echo "   - Analysis: http://localhost:8000/docs"
    echo "   - Email: http://localhost:8001/docs"
    echo "   - Web: http://localhost:8002/docs"
    echo ""
    
    # Показуємо логи якщо є помилки
    if docker-compose logs --tail=1 2>/dev/null | grep -i error; then
        log_warning "Знайдені помилки в логах:"
        show_logs
    fi
}

# Опції командного рядка
case "${1:-}" in
    "logs")
        show_logs
        ;;
    "services")
        check_services
        ;;
    "api")
        test_analysis_api
        ;;
    *)
        main
        ;;
esac
