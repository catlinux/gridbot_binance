# Arxiu: gridbot_binance/utils/telegram.py
import requests
import os
import threading
import json5
from dotenv import load_dotenv
from utils.logger import log

# Carreguem variables d'entorn
load_dotenv(dotenv_path='config/.env')

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
CONFIG_PATH = 'config/config.json5'

def _check_enabled():
    """Llegeix la configuració per veure si Telegram està activat"""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                conf = json5.load(f)
                return conf.get('system', {}).get('telegram_enabled', True)
    except:
        return True # En cas de dubte, activat
    return True

def _send_request(message):
    """Funció interna que fa la petició HTTP"""
    if not TOKEN or not CHAT_ID:
        return
    
    # Comprovació de configuració
    if not _check_enabled():
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        log.error(f"Error enviant Telegram: {e}")

def send_msg(text):
    """
    Envia un missatge a Telegram en un fil separat per no bloquejar el Bot.
    Accepta HTML (negretes <b>, cursives <i>, etc).
    """
    if not TOKEN or not CHAT_ID:
        return

    # Executem en un thread (Daemon) perquè el bot no s'aturi esperant Telegram
    threading.Thread(target=_send_request, args=(text,), daemon=True).start()
