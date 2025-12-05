# Arxiu: gridbot_binance/utils/logger.py
import logging
import json5
import os
import sys
from datetime import datetime
from colorama import init, Fore, Back, Style

# Inicialitzar colors (autoreset neteja el color després de cada print)
init(autoreset=True)

class BotLogger:
    def __init__(self, level='INFO'):
        self.level = level.upper()
        # Desactivem logs de llibreries sorolloses
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("ccxt").setLevel(logging.WARNING)

    def _timestamp(self):
        return datetime.now().strftime('%H:%M:%S')

    def info(self, message):
        # Missatge general (Blanc/Gris)
        print(f"{Fore.LIGHTBLACK_EX}[{self._timestamp()}] {Fore.WHITE}ℹ️  {message}")

    def warning(self, message):
        # Alerta (Groc)
        print(f"{Fore.LIGHTBLACK_EX}[{self._timestamp()}] {Fore.YELLOW}⚠️  {message}")

    def error(self, message):
        # Error (Vermell brillant)
        print(f"{Fore.LIGHTBLACK_EX}[{self._timestamp()}] {Fore.RED}{Style.BRIGHT}❌ ERROR: {message}")

    def success(self, message):
        # Èxit (Verd)
        print(f"{Fore.LIGHTBLACK_EX}[{self._timestamp()}] {Fore.GREEN}✅ {message}")

    def trade(self, symbol, side, price, amount):
        # Operació (Format especial molt visible)
        ts = self._timestamp()
        if side.lower() == 'buy':
            # Fons Verd lletra Blanca
            print(f"\n{Back.GREEN}{Fore.WHITE} ⚡ COMPRA {symbol} {Style.RESET_ALL} {Fore.GREEN}@{price} | Cant: {amount} | Hora: {ts}")
        else:
            # Fons Vermell lletra Blanca
            print(f"\n{Back.RED}{Fore.WHITE} 💰 VENTA  {symbol} {Style.RESET_ALL} {Fore.RED}@{price} | Cant: {amount} | Hora: {ts}")
        print() # Espai extra

    def status(self, message):
        # BARRA D'ESTAT (Sobreescriu la línia actual)
        # \r torna al principi de la línia, end='' evita el salt de línia
        sys.stdout.write(f"\r{Fore.CYAN}{Style.BRIGHT}🤖 ESTAT: {Fore.RESET}{message} " + " " * 10)
        sys.stdout.flush()

config_path = 'config/config.json5'
level = 'INFO'
try:
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json5.load(f)
            level = config['system'].get('log_level', 'INFO')
except Exception: pass

log = BotLogger(level=level)