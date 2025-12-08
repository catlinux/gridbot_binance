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
    # 1. Carreguem la configuració inicial per saber Port i Host
    load_dotenv('config/.env', override=True)
    
    # Llegim el port i el host, amb valors per defecte si no hi són
    HOST = os.getenv('WEB_HOST', '0.0.0.0')
    PORT = int(os.getenv('WEB_PORT', 8000))

    log.info(f"{Fore.CYAN}Iniciando Sistema WEB (Modo Servidor)...{Style.RESET_ALL}")
    
    # Alerta inicial a Telegram
    send_msg(f"🖥️ <b>SISTEMA ONLINE (Port {PORT})</b>\nServidor web listo para recibir órdenes.")
    
    # 2. Instanciem el bot (es queda en standby)
    bot = GridBot()
    
    log.info(f"Servidor web listo en http://{HOST}:{PORT}")
    log.info("Usa 'pkill -f main.py' o Ctrl+C para detener el sistema.")
    
    try:
        # 3. Arrenquem la web (Això bloqueja el programa fins que es tanca)
        start_server(bot, host=HOST, port=PORT)
    except (KeyboardInterrupt, SystemExit):
        # Captura tant Ctrl+C com senyals de sistema
        pass
    finally:
        # 4. Bloc de neteja final (s'executa SEMPRE al tancar)
        print()
        log.warning("🛑 Deteniendo sistema...")
        send_msg("🔌 <b>SISTEMA OFF</b>\nApagando servidor...")
        
        # Si el motor del bot estava corrent, l'aturem suaument
        if bot.is_running:
            bot.stop_logic()
            
        print(f"\n{Fore.GREEN}👋 ¡Sistema cerrado correctamente!{Style.RESET_ALL}\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
