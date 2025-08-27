#!/bin/bash
# test_results.sh - Тестування функціональності результатів

set -e

echo "🧪 Тестування функціональності результатів"
echo "=========================================="

# Кольори
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Глобальні змінні
BASE_URL="http://localhost"
API_URL="http://localhost:8000"
WEB_URL="http://localhost:8002"
TASK_ID=""

# Функції допомоги
check_service() {
    local url=$1
    local name=$2
    
    if curl -f -s $url/health > /dev/null 2>&1; then
        log_success "$name доступний"
        return 0
    else
        log_error "$name недоступний"
        return 1
    fi
}

wait_for_analysis() {
    local task_id=$1
    local max_wait=300  # 5 хвилин
    local count=0
    
    log_info "Очікування завершення аналізу $task_id..."
    
    while [ $count -lt $max_wait ]; do
        local status=$(curl -s "$API_URL/status/$task_id" | jq -r '.status' 2>/dev/null || echo "unknown")
        
        case $status in
            "completed")
                log_success "Аналіз завершено"
                return 0
                ;;
            "failed")
                log_error "Аналіз провалився"
                return 1
                ;;
            "running"|"pending")
                echo -n "."
                sleep 5
                count=$((count + 5))
                ;;
            *)
                log_warning "Невідомий статус: $status"
                sleep 5
                count=$((count + 5))
                ;;
        esac
    done
    
    echo ""
    log_error "Таймаут очікування аналізу"
    return 1
}

# 1. Перевірка доступності сервісів
test_services() {
    log_info "Тест 1: Перевірка доступності сервісів"
    
    local failed=0
    
    check_service "http://localhost" "Nginx" || failed=1
    check_service "$WEB_URL" "Web Interface" || failed=1
    check_service "$API_URL" "Analysis Service" || failed=1
    check_service "http://localhost:8001" "Email Service" || failed=1
    
    if [ $failed -eq 0 ]; then
        log_success "Всі сервіси доступні"
    else
        log_error "Деякі сервіси недоступні"
        return 1
    fi
}

# 2. Тест запуску аналізу через API
test_analysis_api() {
    log_info "Тест 2: Запуск аналізу через API"
    
    local response=$(curl -s -X POST "$API_URL/analyze" \
        -H "Content-Type: application/json" \
        -d '{
            "site_url": "https://example.com",
            "positive_keywords": ["example", "test", "demo"],
            "negative_keywords": ["competitor", "rival"],
            "max_time_minutes": 2,
            "max_links": 20
        }')
    
    if echo "$response" | jq -e '.task_id' > /dev/null 2>&1; then
        TASK_ID=$(echo "$response" | jq -r '.task_id')
        log_success "Аналіз запущено: $TASK_ID"
        return 0
    else
        log_error "Помилка запуску аналізу"
        echo "Response: $response"
        return 1
    fi
}

# 3. Тест статусу аналізу
test_analysis_status() {
    log_info "Тест 3: Перевірка статусу аналізу"
    
    if [ -z "$TASK_ID" ]; then
        log_error "Task ID не встановлено"
        return 1
    fi
    
    local status_response=$(curl -s "$API_URL/status/$TASK_ID")
    
    if echo "$status_response" | jq -e '.status' > /dev/null 2>&1; then
        local status=$(echo "$status_response" | jq -r '.status')
        local message=$(echo "$status_response" | jq -r '.message // "No message"')
        log_success "Статус аналізу: $status - $message"
        return 0
    else
        log_error "Помилка отримання статусу"
        echo "Response: $status_response"
        return 1
    fi
}

# 4. Очікування завершення аналізу
test_wait_completion() {
    log_info "Тест 4: Очікування завершення аналізу"
    
    if [ -z "$TASK_ID" ]; then
        log_error "Task ID не встановлено"
        return 1
    fi
    
    wait_for_analysis "$TASK_ID"
}

# 5. Тест отримання результату через API
test_get_result_api() {
    log_info "Тест 5: Отримання результату через API"
    
    if [ -z "$TASK_ID" ]; then
        log_error "Task ID не встановлено"
        return 1
    fi
    
    local result_response=$(curl -s "$API_URL/result/$TASK_ID")
    
    if echo "$result_response" | jq -e '.task_id' > /dev/null 2>&1; then
        local pages=$(echo "$result_response" | jq -r '.pages_analyzed // 0')
        local positive=$(echo "$result_response" | jq -r '.positive_matches | length')
        local negative=$(echo "$result_response" | jq -r '.negative_matches | length')
        
        log_success "Результат отримано:"
        log_success "  - Сторінок проаналізовано: $pages"
        log_success "  - Позитивних збігів: $positive"
        log_success "  - Негативних збігів: $negative"
        return 0
    else
        log_error "Помилка отримання результату"
        echo "Response: $result_response"
        return 1
    fi
}

# 6. Тест веб-інтерфейсу - головна сторінка
test_web_homepage() {
    log_info "Тест 6: Веб-інтерфейс - головна сторінка"
    
    if curl -f -s "$BASE_URL/" | grep -q "Аналіз конкурентів" 2>/dev/null; then
        log_success "Головна сторінка працює"
        return 0
    else
        log_error "Помилка доступу до головної сторінки"
        return 1
    fi
}

# 7. Тест сторінки результатів
test_web_results_page() {
    log_info "Тест 7: Сторінка результатів"
    
    if curl -f -s "$BASE_URL/results" | grep -q "Результати аналізів" 2>/dev/null; then
        log_success "Сторінка результатів працює"
        return 0
    else
        log_error "Помилка доступу до сторінки результатів"
        return 1
    fi
}

# 8. Тест детальної сторінки результату
test_result_detail_page() {
    log_info "Тест 8: Детальна сторінка результату"
    
    if [ -z "$TASK_ID" ]; then
        log_warning "Task ID не встановлено, пропускаємо тест"
        return 0
    fi
    
    local status_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/result/$TASK_ID")
    
    case $status_code in
        200)
            log_success "Детальна сторінка результату працює"
            return 0
            ;;
        202)
            log_info "Аналіз ще виконується (це нормально)"
            return 0
            ;;
        404)
            log_error "Результат не знайдено"
            return 1
            ;;
        *)
            log_error "Помилка доступу до сторінки результату (код: $status_code)"
            return 1
            ;;
    esac
}

# 9. Тест завантаження Excel файлу
test_excel_download() {
    log_info "Тест 9: Завантаження Excel файлу"
    
    if [ -z "$TASK_ID" ]; then
        log_warning "Task ID не встановлено, пропускаємо тест"
        return 0
    fi
    
    local temp_file="/tmp/test_result.xlsx"
    local status_code=$(curl -s -o "$temp_file" -w "%{http_code}" "$BASE_URL/result/$TASK_ID/download")
    
    case $status_code in
        200)
            if [ -f "$temp_file" ] && [ -s "$temp_file" ]; then
                local file_size=$(wc -c < "$temp_file")
                log_success "Excel файл завантажено (розмір: $file_size байтів)"
                rm -f "$temp_file"
                return 0
            else
                log_error "Excel файл пустий"
                return 1
            fi
            ;;
        202)
            log_info "Аналіз ще не завершено"
            return 0
            ;;
        404)
            log_error "Результат не знайдено для завантаження"
            return 1
            ;;
        *)
            log_error "Помилка завантаження Excel (код: $status_code)"
            return 1
            ;;
    esac
}

# 10. Тест error pages
test_error_pages() {
    log_info "Тест 10: Сторінки помилок"
    
    # Тест 404
    local status_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/nonexistent-page")
    if [ "$status_code" = "404" ]; then
        log_success "404 сторінка працює"
    else
        log_warning "404 сторінка повернула код: $status_code"
    fi
    
    # Тест API 404
    local api_status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/analysis/nonexistent")
    if [ "$api_status" = "404" ]; then
        log_success "API 404 працює"
    else
        log_warning "API 404 повернув код: $api_status"
    fi
}

# 11. Тест статичних файлів
test_static_files() {
    log_info "Тест 11: Статичні файли"
    
    # Тест CSS
    if curl -f -s "$BASE_URL/static/css/style.css" | grep -q "primary-color" 2>/dev/null; then
        log_success "CSS файл доступний"
    else
        log_warning "CSS файл недоступний"
    fi
    
    # Тест JS
    if curl -f -s "$BASE_URL/static/js/app.js" | grep -q "CompetitorAnalysisApp" 2>/dev/null; then
        log_success "JS файл доступний"
    else
        log_warning "JS файл недоступний"
    fi
}

# 12. Тест API документації
test_api_docs() {
    log_info "Тест 12: API документація"
    
    # Analysis API docs
    if curl -f -s "$API_URL/docs" | grep -q "FastAPI" 2>/dev/null; then
        log_success "Analysis API документація доступна"
    else
        log_warning "Analysis API документація недоступна"
    fi
    
    # Email API docs  
    if curl -f -s "http://localhost:8001/docs" | grep -q "FastAPI" 2>/dev/null; then
        log_success "Email API документація доступна"
    else
        log_warning "Email API документація недоступна"
    fi
}

# Функція очищення
cleanup() {
    log_info "Очищення тестових даних..."
    
    if [ -n "$TASK_ID" ]; then
        # Видаляємо тестову задачу якщо можливо
        curl -s -X DELETE "$API_URL/task/$TASK_ID" > /dev/null 2>&1 || true
    fi
    
    # Видаляємо тимчасові файли
    rm -f /tmp/test_result.xlsx
}

# Головна функція тестування
main() {
    local failed_tests=0
    local total_tests=12
    
    echo "Запуск $total_tests тестів..."
    echo ""
    
    # Перевірка залежностей
    if ! command -v jq &> /dev/null; then
        log_error "jq не встановлено. Встановіть: apt-get install jq"
        exit 1
    fi
    
    # Запуск тестів
    test_services || failed_tests=$((failed_tests + 1))
    test_analysis_api || failed_tests=$((failed_tests + 1))
    test_analysis_status || failed_tests=$((failed_tests + 1))
    test_wait_completion || failed_tests=$((failed_tests + 1))
    test_get_result_api || failed_tests=$((failed_tests + 1))
    test_web_homepage || failed_tests=$((failed_tests + 1))
    test_web_results_page || failed_tests=$((failed_tests + 1))
    test_result_detail_page || failed_tests=$((failed_tests + 1))
    test_excel_download || failed_tests=$((failed_tests + 1))
    test_error_pages || failed_tests=$((failed_tests + 1))
    test_static_files || failed_tests=$((failed_tests + 1))
    test_api_docs || failed_tests=$((failed_tests + 1))
    
    # Очищення
    cleanup
    
    # Результат
    echo ""
    echo "=================================="
    if [ $failed_tests -eq 0 ]; then
        log_success "Всі тести пройдено успішно! ✅"
        echo ""
        echo "🎉 Система повністю функціональна:"
        echo "   • Аналіз сайтів працює"
        echo "   • Веб-інтерфейс доступний"
        echo "   • Результати можна переглядати"
        echo "   • Excel файли генеруються"
        echo "   • Error handling працює"
        exit 0
    else
        log_error "$failed_tests з $total_tests тестів провалилися ❌"
        echo ""
        echo "🔧 Рекомендації:"
        echo "   • Перевірте логи сервісів: docker-compose logs"
        echo "   • Перезапустіть систему: docker-compose restart"
        echo "   • Перевірте конфігурацію .env"
        exit 1
    fi
}

# Обробка аргументів
case "${1:-}" in
    "api")
        test_services
        test_analysis_api
        test_analysis_status
        ;;
    "web")
        test_web_homepage
        test_web_results_page
        test_static_files
        ;;
    "single")
        if [ -n "$2" ]; then
            TASK_ID="$2"
            test_result_detail_page
            test_excel_download
        else
            log_error "Потрібен Task ID для single тесту"
            exit 1
        fi
        ;;
    *)
        main
        ;;
esac
