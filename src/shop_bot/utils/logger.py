"""
Красивый логгер в стиле современных фреймворков
"""
import logging
import sys
from datetime import datetime
from typing import Optional
import colorama
from colorama import Fore, Back, Style

# Инициализируем colorama для Windows
colorama.init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    """Кастомный форматтер с цветами и эмодзи"""
    
    # Цветовая схема для разных уровней
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA + Style.BRIGHT,
    }
    
    # Эмодзи для разных уровней
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '✨',
        'WARNING': '⚠️',
        'ERROR': '🚨',
        'CRITICAL': '💥',
    }
    
    # Цвета для разных компонентов
    TIME_COLOR = Fore.CYAN + Style.DIM
    MODULE_COLOR = Fore.BLUE + Style.BRIGHT
    FUNCTION_COLOR = Fore.MAGENTA
    RESET = Style.RESET_ALL
    
    def format(self, record):
        # Время
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]
        
        # Получаем цвет и эмодзи для уровня
        level_color = self.COLORS.get(record.levelname, Fore.WHITE)
        emoji = self.EMOJIS.get(record.levelname, '📝')
        
        # Модуль и функция
        module = record.module if hasattr(record, 'module') else 'unknown'
        funcname = record.funcName if hasattr(record, 'funcName') else 'unknown'
        
        # Создаем красивый префикс
        level_text = f"{level_color}{record.levelname:>8}{self.RESET}"
        time_text = f"{self.TIME_COLOR}{timestamp}{self.RESET}"
        module_text = f"{self.MODULE_COLOR}{module}{self.RESET}"
        func_text = f"{self.FUNCTION_COLOR}{funcname}(){self.RESET}"
        
        # Форматируем сообщение
        message = record.getMessage()
        
        # Собираем финальную строку
        formatted = f"{emoji} {time_text} {level_text} {module_text}.{func_text} → {message}"
        
        return formatted

class ShopBotLogger:
    """Главный класс для логирования бота"""
    
    def __init__(self, name: str = "ShopBot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Очищаем существующие хендлеры
        self.logger.handlers.clear()
        
        # Создаем консольный хендлер
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(ColoredFormatter())
        
        self.logger.addHandler(console_handler)
        
        # Предотвращаем дублирование логов
        self.logger.propagate = False
    
    def startup(self, message: str):
        """Красивое сообщение о запуске"""
        border = "═" * 60
        self.logger.info(f"{Fore.CYAN}{border}")
        self.logger.info(f"🚀 {Fore.WHITE + Style.BRIGHT}REMNA SHOP BOT STARTING{Style.RESET_ALL}")
        self.logger.info(f"   {message}")
        self.logger.info(f"{Fore.CYAN}{border}{Style.RESET_ALL}")
    
    def system(self, component: str, message: str, status: str = "OK"):
        """Системные сообщения"""
        if status == "OK":
            icon = "✅"
            color = Fore.GREEN
        elif status == "WARNING":
            icon = "⚠️"
            color = Fore.YELLOW
        elif status == "ERROR":
            icon = "❌"
            color = Fore.RED
        else:
            icon = "ℹ️"
            color = Fore.BLUE
            
        self.logger.info(f"{icon} {color}{component:>15}{Style.RESET_ALL} │ {message}")
    
    def payment(self, user_id: int, method: str, amount: float, status: str):
        """Логи платежей"""
        if status == "SUCCESS":
            icon = "💰"
            color = Fore.GREEN
        elif status == "PENDING":
            icon = "⏳"
            color = Fore.YELLOW
        elif status == "FAILED":
            icon = "💸"
            color = Fore.RED
        else:
            icon = "💳"
            color = Fore.BLUE
            
        self.logger.info(f"{icon} {color}PAYMENT{Style.RESET_ALL} │ User {user_id} │ {method} │ {amount}₽ │ {status}")
    
    def user_action(self, user_id: int, action: str, details: str = ""):
        """Действия пользователей"""
        icon = "👤"
        self.logger.info(f"{icon} {Fore.CYAN}USER{Style.RESET_ALL} │ {user_id} │ {action} │ {details}")
    
    def vpn_action(self, user_id: int, action: str, key_info: str = ""):
        """VPN операции"""
        if "create" in action.lower():
            icon = "🔑"
        elif "extend" in action.lower():
            icon = "⏰"
        elif "expire" in action.lower():
            icon = "⌛"
        else:
            icon = "🔐"
            
        self.logger.info(f"{icon} {Fore.MAGENTA}VPN{Style.RESET_ALL} │ User {user_id} │ {action} │ {key_info}")
    
    def backup(self, action: str, details: str = "", status: str = "OK"):
        """Операции бэкапа"""
        if status == "OK":
            icon = "💾"
            color = Fore.GREEN
        elif status == "ERROR":
            icon = "🗂️"
            color = Fore.RED
        else:
            icon = "📦"
            color = Fore.BLUE
            
        self.logger.info(f"{icon} {color}BACKUP{Style.RESET_ALL} │ {action} │ {details}")
    
    def api(self, endpoint: str, status_code: int, response_time: float = 0):
        """API запросы"""
        if 200 <= status_code < 300:
            icon = "🌐"
            color = Fore.GREEN
        elif 400 <= status_code < 500:
            icon = "🔍"
            color = Fore.YELLOW
        elif status_code >= 500:
            icon = "🔥"
            color = Fore.RED
        else:
            icon = "📡"
            color = Fore.BLUE
            
        time_str = f"{response_time:.3f}s" if response_time > 0 else ""
        self.logger.info(f"{icon} {color}API{Style.RESET_ALL} │ {endpoint} │ {status_code} │ {time_str}")
    
    def notification(self, user_id: int, type_: str, success: bool = True):
        """Уведомления пользователям"""
        if success:
            icon = "📱"
            color = Fore.GREEN
            status = "SENT"
        else:
            icon = "📵"
            color = Fore.RED
            status = "FAILED"
            
        self.logger.info(f"{icon} {color}NOTIFY{Style.RESET_ALL} │ User {user_id} │ {type_} │ {status}")
    
    def debug(self, message: str):
        self.logger.debug(message)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message: str):
        self.logger.critical(message)
    
    def shutdown(self):
        """Красивое сообщение о завершении"""
        border = "═" * 60
        self.logger.info(f"{Fore.RED}{border}")
        self.logger.info(f"🛑 {Fore.WHITE + Style.BRIGHT}REMNA SHOP BOT SHUTDOWN{Style.RESET_ALL}")
        self.logger.info(f"{Fore.RED}{border}{Style.RESET_ALL}")

# Создаем глобальный экземпляр логгера
bot_logger = ShopBotLogger()
