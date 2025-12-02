# Arxiu: gridbot_binance/utils/logger.py

import logging
import json5
import os

class BotLogger:
    def __init__(self, level='INFO'):
        # Configurar el format del log
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s %(message)s', 
            datefmt='%H:%M:%S'
        )
        
        # Obtenir l'arrel del logger
        self.logger = logging.getLogger('GridBot')
        
        # Assegurar-se que el nivell és correcte (DEBUG, INFO, etc.)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Crear consola handler i assignar-li el format
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        
        # Evitar duplicats en la sortida si ja hi ha handlers definits
        if not self.logger.handlers:
            self.logger.addHandler(ch)

    # Mètodes de log estàndard
    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def success(self, message):
        # logging no té 'success', utilitzem info per estats de confirmació
        self.logger.info(f"✔ {message}")

    # MÈTODE DEBUG AFEEGIT PER AL DIAGNÒSTIC
    def debug(self, message):
        self.logger.debug(message) 

    # Mètode personalitzat per a trades
    def trade(self, symbol, side, price, amount):
        action = "COMPRA" if side == 'buy' else "VENDA"
        emoji = "⚡" if side == 'buy' else "💰"
        self.logger.info(f"{emoji} {action} {symbol} | Preu: {price} | Quantitat: {amount}")

# --- Inicialització Global de 'log' (CLAU per a la importació) ---

# Intentem llegir el config per obtenir el nivell de log desitjat
config_path = 'config/config.json5'
level = 'INFO' # Valor per defecte

try:
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json5.load(f)
            level = config['system'].get('log_level', 'INFO')
except Exception as e:
    # Si falla llegint el config, utilitzem l'INFO per defecte
    print(f"ATENCIÓ: No s'ha pogut llegir {config_path}. Usant log level: {level}. Error: {e}")

# AQUESTA LÍNIA EXPORTA L'OBJECTE 'log'
log = BotLogger(level=level)