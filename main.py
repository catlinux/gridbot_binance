# Arxiu: gridbot_binance/main.py
from core.bot import GridBot
from utils.logger import log
from web.server import start_server
import threading
import time
import sys

def run_bot_logic(bot):
    try:
        bot.start()
    except Exception as e:
        log.error(f"Error crític al fil del bot: {e}")

def main():
    log.info("Iniciant Sistema Complet (Bot + Web)...")
    
    bot = GridBot()
    
    bot_thread = threading.Thread(target=run_bot_logic, args=(bot,), daemon=True)
    bot_thread.start()
    
    time.sleep(2)
    
    log.info("Iniciant servidor web a http://localhost:8000")
    log.info("Prem Ctrl+C a la terminal per aturar tot el sistema.")
    
    try:
        start_server(bot)
    except KeyboardInterrupt:
        log.warning("Aturant sistema...")
        sys.exit(0)

if __name__ == "__main__":
    main()