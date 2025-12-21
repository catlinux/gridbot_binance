# Archivo: gridbot_binance/limpieza.py
from core.exchange import BinanceConnector
from utils.logger import log
import json5

def main():
    # Herramienta de emergencia para cancelar todas las órdenes. Útil si el bot se queda colgado o quieres limpiar todo rápidamente.
    log.warning("--- INICIANDO LIMPIEZA TOTAL DE ÓRDENES ---")
    
    connector = BinanceConnector()
    
    try:
        with open('config/config.json5', 'r') as f:
            config = json5.load(f)
    except Exception as e:
        log.error(f"Error leyendo configuración: {e}")
        return

    # Filtramos solo los pares que están activados en la config
    active_pairs = [p['symbol'] for p in config['pairs'] if p['enabled']]
    
    if not active_pairs:
        log.warning("No hay pares habilitados en la configuración para limpiar.")
        return

    # Cancelamos órdenes par por par
    for symbol in active_pairs:
        log.info(f"Cancelando todo para {symbol}...")
        connector.cancel_all_orders(symbol)
        
    log.success("Órdenes canceladas correctamente.")
    
    # Mostramos resumen final de la cartera (Wallet)
    log.info("\n--- ESTADO ACTUAL DE LA CARTERA (WALLET) ---")
    
    assets_to_check = set()
    for symbol in active_pairs:
        base, quote = symbol.split('/')
        assets_to_check.add(base)
        assets_to_check.add(quote)
    
    print("-" * 65)
    print(f"{'ACTIVO':<6} | {'CANTIDAD':>15} | {'VALOR (USDC)':>15} | {'PRECIO ACT.'}")
    print("-" * 65)

    grand_total_usdc = 0.0

    # Iteramos activos y calculamos valor aproximado
    for asset in sorted(list(assets_to_check)):
        total_balance = connector.get_total_balance(asset)
        
        if total_balance > 0:
            usdc_value = 0.0
            price_display = ""

            if asset == 'USDC':
                usdc_value = total_balance
                price_display = "(1.0)"
            else:
                symbol = f"{asset}/USDC"
                price = connector.fetch_current_price(symbol)
                if price:
                    usdc_value = total_balance * price
                    price_display = f"(@ {price:.4f})"
            
            grand_total_usdc += usdc_value

            print(f"{asset:<6} | {total_balance:>15.8f} | {usdc_value:>15.2f} $ | {price_display}")
        else:
            pass
            
    print("-" * 65)
    log.success(f"💰 TOTAL CARTERA ESTIMADO: {grand_total_usdc:,.2f} USDC")
    print("-" * 65)
    
    log.info("Limpieza y recuento finalizado. Listo para arrancar.")

if __name__ == "__main__":
    main()
