# Arxiu: gridbot_binance/utils/logger.py
import logging
import json5
import os
import sys
from datetime import datetime
from colorama import init, Fore, Style

# Inicialitzem colorama per a Windows/Linux
init(autoreset=True)

class BotLogger:
    def __init__(self, level='INFO'):
        self.logger = logging.getLogger('GridBot')
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Format net sense colors per als fitxers (si volguessis guardar logs en disc)
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
        
        # Netegem handlers anteriors
        if self.logger.handlers:
            self.logger.handlers = []
            
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def _print(self, color, prefix, message):
        """Mètode intern per imprimir amb color i timestamp."""
        now = datetime.now().strftime('%H:%M:%S')
        print(f"{Style.DIM}[{now}]{Style.RESET_ALL} {color}{prefix} {message}{Style.RESET_ALL}")

    def info(self, message):
        self._print(Fore.CYAN, "[INFO]", message)

    def warning(self, message):
        self._print(Fore.YELLOW, "[ALERTA]", message)

    def error(self, message):
        self._print(Fore.RED + Style.BRIGHT, "[ERROR]", message)

    def success(self, message):
        self._print(Fore.GREEN + Style.BRIGHT, "[OK]", message)

    def trade(self, symbol, side, price, amount):
        """Format especial per a operacions."""
        if side == 'buy':
            color = Fore.GREEN + Style.BRIGHT
            icon = "🟢 COMPRA"
        else:
            color = Fore.MAGENTA + Style.BRIGHT
            icon = "🔴 VENDA"
        
        msg = f"{symbol} | Preu: {price} | Qty: {amount}"
        print(f"\n{color}{'='*60}\n {icon} {msg}\n{'='*60}{Style.RESET_ALL}\n")

    def status(self, message):
        """
        Imprimeix sobre la mateixa línia per no omplir la terminal.
        Utilitza retorn de carro (\r) i neteja la línia.
        """
        now = datetime.now().strftime('%H:%M:%S')
        # \033[K neteja la línia des del cursor fins al final
        print(f"\r{Style.DIM}[{now}]{Style.RESET_ALL} {Fore.BLUE}[MONITOR]{Style.RESET_ALL} {message}\033[K", end="", flush=True)

# Configuració inicial
config_path = 'config/config.json5'
level = 'INFO'
try:
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json5.load(f)
            level = config['system'].get('log_level', 'INFO')
except Exception: pass

log = BotLogger(level=level)