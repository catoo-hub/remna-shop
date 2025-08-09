#!/bin/bash

# Скрипт мониторинга Remna Shop Bot

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Remna Shop Bot Monitoring${NC}"
echo "================================"

# Функция для проверки статуса сервиса
check_service() {
    if systemctl is-active --quiet remna-shop-bot; then
        echo -e "🟢 Service Status: ${GREEN}Running${NC}"
        UPTIME=$(systemctl show remna-shop-bot -p ActiveEnterTimestamp --value)
        echo -e "⏰ Uptime: ${GREEN}$UPTIME${NC}"
    else
        echo -e "🔴 Service Status: ${RED}Stopped${NC}"
        return 1
    fi
}

# Функция для проверки Docker контейнера
check_docker() {
    cd /opt/remna-shop
    if docker compose ps | grep -q "Up"; then
        echo -e "🐳 Docker Status: ${GREEN}Running${NC}"
        
        # Использование ресурсов
        echo -e "\n📊 Resource Usage:"
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
    else
        echo -e "🐳 Docker Status: ${RED}Stopped${NC}"
        return 1
    fi
}

# Функция для проверки логов на ошибки
check_logs() {
    echo -e "\n📝 Recent Errors (last 10):"
    
    if [ -f "/opt/remna-shop/logs/bot.log" ]; then
        ERROR_COUNT=$(tail -100 /opt/remna-shop/logs/bot.log | grep -i "error\|exception\|failed" | wc -l)
        if [ $ERROR_COUNT -gt 0 ]; then
            echo -e "${RED}Found $ERROR_COUNT errors:${NC}"
            tail -100 /opt/remna-shop/logs/bot.log | grep -i "error\|exception\|failed" | tail -10
        else
            echo -e "${GREEN}No recent errors found${NC}"
        fi
    else
        echo -e "${YELLOW}Log file not found${NC}"
    fi
}

# Функция для проверки места на диске
check_disk() {
    echo -e "\n💽 Disk Usage:"
    USAGE=$(df /opt/remna-shop | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $USAGE -gt 90 ]; then
        echo -e "${RED}⚠️  Disk usage: $USAGE%${NC}"
    elif [ $USAGE -gt 80 ]; then
        echo -e "${YELLOW}⚠️  Disk usage: $USAGE%${NC}"
    else
        echo -e "${GREEN}✅ Disk usage: $USAGE%${NC}"
    fi
    
    df -h /opt/remna-shop
}

# Функция для проверки размера логов
check_log_size() {
    echo -e "\n📄 Log Files Size:"
    if [ -d "/opt/remna-shop/logs" ]; then
        du -sh /opt/remna-shop/logs/* 2>/dev/null | while read size file; do
            filename=$(basename "$file")
            if [[ $size == *G ]]; then
                echo -e "${RED}⚠️  $filename: $size${NC}"
            elif [[ $size == *M ]] && [ ${size%M} -gt 100 ]; then
                echo -e "${YELLOW}⚠️  $filename: $size${NC}"
            else
                echo -e "${GREEN}✅ $filename: $size${NC}"
            fi
        done
    fi
}

# Функция для проверки подключения к API
check_api() {
    echo -e "\n🌐 API Connectivity:"
    
    # Проверяем доступность API из .env
    if [ -f "/opt/remna-shop/.env" ]; then
        API_URL=$(grep REMNA_API_URL /opt/remna-shop/.env | cut -d'=' -f2)
        if [ ! -z "$API_URL" ]; then
            if curl -s --connect-timeout 5 -k "$API_URL" > /dev/null; then
                echo -e "${GREEN}✅ Remnawave API: Accessible${NC}"
            else
                echo -e "${RED}❌ Remnawave API: Not accessible${NC}"
            fi
        fi
    fi
    
    # Проверяем Telegram API
    if curl -s --connect-timeout 5 https://api.telegram.org > /dev/null; then
        echo -e "${GREEN}✅ Telegram API: Accessible${NC}"
    else
        echo -e "${RED}❌ Telegram API: Not accessible${NC}"
    fi
}

# Функция для проверки бэкапов
check_backups() {
    echo -e "\n💾 Backup Status:"
    if [ -d "/opt/remna-shop/backups" ]; then
        BACKUP_COUNT=$(ls -1 /opt/remna-shop/backups/*.tar.gz 2>/dev/null | wc -l)
        if [ $BACKUP_COUNT -gt 0 ]; then
            LATEST_BACKUP=$(ls -t /opt/remna-shop/backups/*.tar.gz 2>/dev/null | head -1)
            BACKUP_DATE=$(stat -c %y "$LATEST_BACKUP" | cut -d' ' -f1)
            echo -e "${GREEN}✅ Latest backup: $BACKUP_DATE${NC}"
            echo -e "📁 Total backups: $BACKUP_COUNT"
        else
            echo -e "${YELLOW}⚠️  No backups found${NC}"
        fi
    else
        echo -e "${RED}❌ Backup directory not found${NC}"
    fi
}

# Функция для отображения статистики
show_stats() {
    echo -e "\n📈 Bot Statistics (from logs):"
    
    if [ -f "/opt/remna-shop/logs/bot.log" ]; then
        TODAY=$(date +%Y-%m-%d)
        
        # Подсчитываем события за сегодня
        USER_ACTIONS=$(grep "$TODAY" /opt/remna-shop/logs/bot.log | grep -c "user_action" || echo "0")
        PAYMENTS=$(grep "$TODAY" /opt/remna-shop/logs/bot.log | grep -c "payment" || echo "0")
        VPN_ACTIONS=$(grep "$TODAY" /opt/remna-shop/logs/bot.log | grep -c "vpn_action" || echo "0")
        
        echo -e "👥 User Actions Today: ${GREEN}$USER_ACTIONS${NC}"
        echo -e "💳 Payments Today: ${GREEN}$PAYMENTS${NC}"
        echo -e "🔐 VPN Actions Today: ${GREEN}$VPN_ACTIONS${NC}"
    fi
}

# Основная функция
main() {
    check_service
    check_docker
    check_api
    check_disk
    check_log_size
    check_backups
    check_logs
    show_stats
    
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${GREEN}Monitoring completed!${NC}"
    
    # Если есть аргумент --watch, запускаем в цикле
    if [ "$1" == "--watch" ]; then
        echo -e "\n${YELLOW}Watching mode enabled. Press Ctrl+C to exit.${NC}"
        while true; do
            sleep 30
            clear
            main
        done
    fi
}

# Запускаем мониторинг
main $1
