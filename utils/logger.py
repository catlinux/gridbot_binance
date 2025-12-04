# Arxiu: gridbot_binance/utils/logger.py
import logging
import json5
import os

class BotLogger:
    def __init__(self, level='INFO'):
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s %(message)s', 
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger('GridBot')
        self.logger.setLevel(getattr(logging, level.upper()))
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(ch)

    def info(self, message): self.logger.info(message)
    def warning(self, message): self.logger.warning(message)
    def error(self, message): self.logger.error(message)
    def success(self, message): self.logger.info(f"✔ {message}")
    def debug(self, message): self.logger.debug(message) 

    def trade(self, symbol, side, price, amount):
        action = "COMPRA" if side == 'buy' else "VENTA"
        emoji = "⚡" if side == 'buy' else "💰"
        self.logger.info(f"{emoji} {action} {symbol} | Precio: {price} | Cantidad: {amount}")

config_path = 'config/config.json5'
level = 'INFO'
try:
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json5.load(f)
            level = config['system'].get('log_level', 'INFO')
except Exception as e:
    print(f"ATENCIÓN: No se pudo leer {config_path}. Usando log level: {level}. Error: {e}")

log = BotLogger(level=level)