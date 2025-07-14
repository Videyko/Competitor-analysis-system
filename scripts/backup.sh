#!/bin/bash
# backup.sh - Скрипт резервного копіювання

set -e

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="competitor_analysis_$DATE"

echo "🔄 Створення резервної копії..."

# Створення директорії для резервних копій
mkdir -p $BACKUP_DIR

# Завантаження змінних середовища
source .env

# Резервне копіювання бази даних
echo "📁 Резервне копіювання бази даних..."
docker-compose exec -T postgres pg_dump \
    -U ${POSTGRES_USER:-competitor_user} \
    -d ${POSTGRES_DB:-competitor_db} \
    --clean --if-exists > $BACKUP_DIR/${BACKUP_NAME}_database.sql

# Резервне копіювання Redis
echo "💾 Резервне копіювання Redis..."
docker-compose exec -T redis redis-cli --rdb - > $BACKUP_DIR/${BACKUP_NAME}_redis.rdb

# Резервне копіювання конфігурацій
echo "⚙️ Резервне копіювання конфігурацій..."
tar -czf $BACKUP_DIR/${BACKUP_NAME}_config.tar.gz \
    .env docker-compose.yml nginx/ monitoring/ 2>/dev/null || true

# Резервне копіювання даних
echo "📊 Резервне копіювання даних..."
if [ -d "./data" ]; then
    tar -czf $BACKUP_DIR/${BACKUP_NAME}_data.tar.gz data/
fi

# Створення повної резервної копії
echo "📦 Створення повної резервної копії..."
tar -czf $BACKUP_DIR/${BACKUP_NAME}_full.tar.gz \
    $BACKUP_DIR/${BACKUP_NAME}_database.sql \
    $BACKUP_DIR/${BACKUP_NAME}_redis.rdb \
    $BACKUP_DIR/${BACKUP_NAME}_config.tar.gz \
    $BACKUP_DIR/${BACKUP_NAME}_data.tar.gz 2>/dev/null || true

# Очищення тимчасових файлів
rm -f $BACKUP_DIR/${BACKUP_NAME}_database.sql
rm -f $BACKUP_DIR/${BACKUP_NAME}_redis.rdb
rm -f $BACKUP_DIR/${BACKUP_NAME}_config.tar.gz
rm -f $BACKUP_DIR/${BACKUP_NAME}_data.tar.gz

# Видалення старих резервних копій (залишаємо останні 7)
find $BACKUP_DIR -name "competitor_analysis_*_full.tar.gz" -type f -mtime +7 -delete

echo "✅ Резервна копія створена: $BACKUP_DIR/${BACKUP_NAME}_full.tar.gz"

# Показ розміру резервної копії
if [ -f "$BACKUP_DIR/${BACKUP_NAME}_full.tar.gz" ]; then
    size=$(du -h "$BACKUP_DIR/${BACKUP_NAME}_full.tar.gz" | cut -f1)
    echo "📏 Розмір резервної копії: $size"
fi