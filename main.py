# Arxiu: gridbot_binance/main.py
from core.bot import GridBot
from utils.logger import log
from web.server import start_server
from utils.telegram import send_msg 
import sys
import os
from dotenv import load_dotenv
from colorama import Fore, Style

def main():
    # 1. Carreguem la configuració aquí mateix per saber el port
    load_dotenv('config/.env', override=True)
    
    # Llegim el port i el host, amb valors per defecte si no hi són
    HOST = os.getenv('WEB_HOST', '0.0.0.0')
    PORT = int(os.getenv('WEB_PORT', 8000))

    log.info(f"{Fore.CYAN}Iniciando Sistema WEB (Modo Servidor)...{Style.RESET_ALL}")
    
    # Missatge Telegram (opcional, si vols diferenciar entorns pots canviar el text)
    send_msg(f"🖥️ <b>SISTEMA ONLINE (Port {PORT})</b>\nServidor web listo.")
    
    bot = GridBot()
    
    # Log real amb les variables reals
    log.info(f"Servidor web listo en http://{HOST}:{PORT}")
    log.info("Usa 'pkill -f main.py' o Ctrl+C para detener el sistema.")
    
    try:
        # Passem explícitament el host i el port al servidor
        start_server(bot, host=HOST, port=PORT)
    except KeyboardInterrupt:
        pass
    finally:
        print()
        log.warning("🛑 Deteniendo sistema...")
        send_msg("🔌 <b>SISTEMA OFF</b>\nApagando servidor...")
        
        if bot.is_running:
            bot.stop_logic()
            
        print(f"\n{Fore.GREEN}👋 ¡Sistema cerrado correctamente!{Style.RESET_ALL}\n")

if __name__ == "__main__":
    main()