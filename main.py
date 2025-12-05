# Arxiu: gridbot_binance/main.py
from core.bot import GridBot
from utils.logger import log
from web.server import start_server
import threading
import time
import sys
from colorama import Fore, Style

def run_bot_logic(bot):
    try:
        bot.start()
    except Exception as e:
        log.error(f"Error crítico en el hilo del bot: {e}")

def main():
    log.info("Iniciando Sistema Completo (Bot + Web)...")
    
    bot = GridBot()
    
    # Executem el bot en un fil paral·lel (daemon=True moria amb el principal)
    bot_thread = threading.Thread(target=run_bot_logic, args=(bot,), daemon=True)
    bot_thread.start()
    
    time.sleep(2)
    
    log.info("Iniciando servidor web en http://localhost:8000")
    log.info("Pulsa Ctrl+C en la terminal para detener todo el sistema.")
    
    try:
        # El servidor web bloqueja el fil principal aquí
        start_server(bot)
    except KeyboardInterrupt:
        # AQUI ÉS ON GESTIONEM LA SORTIDA AMIGABLE
        print()
        log.warning("🛑 Señal de parada recibida (Ctrl+C).")
        log.info("Deteniendo procesos y guardando estado...")
        
        # Donem un segon perquè l'usuari vegi que s'està tancant bé
        if bot:
            bot.is_running = False
            
        time.sleep(1)
        
        # Missatge final maco i amb colors
        print(f"\n{Fore.GREEN}👋 ¡Gracias por usar el GridBot!{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   El sistema se ha cerrado correctamente. ¡Hasta pronto!{Style.RESET_ALL}\n")
        
        sys.exit(0)

if __name__ == "__main__":
    main()