# Arxiu: gridbot_binance/main.py
from core.bot import GridBot
from utils.logger import log
from web.server import start_server
import sys
from colorama import Fore, Style

def main():
    log.info(f"{Fore.CYAN}Iniciando Sistema WEB (Modo Servidor)...{Style.RESET_ALL}")
    
    # 1. Instanciem el bot (en mode espera)
    bot = GridBot()
    
    log.info("Servidor web listo en http://localhost:8000")
    log.info("Usa 'pkill -f main.py' o Ctrl+C para detener el sistema.")
    
    try:
        # 2. Arrenquem la web (bloqueja el fil principal fins que s'atura)
        start_server(bot)
    except KeyboardInterrupt:
        pass
    finally:
        print()
        log.warning("🛑 Deteniendo sistema...")
        
        # Si el bot estava corrent, el tanquem netament
        if bot.is_running:
            bot.stop_logic()
            
        print(f"\n{Fore.GREEN}👋 ¡Sistema cerrado correctamente!{Style.RESET_ALL}\n")

if __name__ == "__main__":
    main()