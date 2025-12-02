# Arxiu: gridbot_binance/neteja.py
from core.exchange import BinanceConnector
from utils.logger import log
import json5

def main():
    log.warning("--- INICIANT NETEJA TOTAL D'ORDRES ---")
    
    # 1. Connectar
    connector = BinanceConnector()
    
    # 2. Llegir quins parells tenim al config
    try:
        with open('config/config.json5', 'r') as f:
            config = json5.load(f)
    except Exception as e:
        log.error(f"Error llegint config: {e}")
        return

    # Llista de parells activats
    active_pairs = [p['symbol'] for p in config['pairs'] if p['enabled']]
    
    if not active_pairs:
        log.warning("No hi ha parells habilitats al config per netejar.")
        return

    # 3. Cancel·lar ordres per a cada parell
    for symbol in active_pairs:
        log.info(f"Cancel·lant tot per a {symbol}...")
        connector.cancel_all_orders(symbol)
        
    log.success("Ordres cancel·lades correctament.")
    
    # ---------------------------------------------------------
    # 4. MOSTRAR SALDO ACTUALITZAT I VALOR TOTAL
    # ---------------------------------------------------------
    log.info("\n--- ESTAT ACTUAL DE LA CARTERA (WALLET) ---")
    
    # Identifiquem quines monedes estem utilitzant
    assets_to_check = set()
    for symbol in active_pairs:
        base, quote = symbol.split('/')
        assets_to_check.add(base)
        assets_to_check.add(quote)
    
    print("-" * 65)
    print(f"{'ACTIU':<6} | {'QUANTITAT':>15} | {'VALOR (USDC)':>15} | {'PREU ACT.'}")
    print("-" * 65)

    grand_total_usdc = 0.0

    for asset in sorted(list(assets_to_check)):
        total_balance = connector.get_total_balance(asset)
        
        if total_balance > 0:
            usdc_value = 0.0
            price_display = ""

            # Calcular valor en USDC
            if asset == 'USDC':
                usdc_value = total_balance
                price_display = "(1.0)"
            else:
                # Busquem el preu actual per fer la conversió
                symbol = f"{asset}/USDC"
                price = connector.fetch_current_price(symbol)
                if price:
                    usdc_value = total_balance * price
                    price_display = f"(@ {price:.4f})"
            
            # Sumar al total general
            grand_total_usdc += usdc_value

            # Mostrar línia formatada
            # :<6  -> alineat esquerra, 6 espais
            # :>15 -> alineat dreta, 15 espais
            # .2f  -> 2 decimals
            print(f"{asset:<6} | {total_balance:>15.8f} | {usdc_value:>15.2f} $ | {price_display}")
        else:
            # Si està a zero no cal mostrar valor, només quantitat
            # print(f"{asset:<6} | {0.0:>15.8f} | {'-':>15} |") 
            pass # Opcional: Ocultar els que estan a 0 per neteja visual
            
    print("-" * 65)
    log.success(f"💰 TOTAL CARTERA ESTIMAT: {grand_total_usdc:,.2f} USDC")
    print("-" * 65)
    
    log.info("Neteja i recompte finalitzat. A punt per arrencar.")

if __name__ == "__main__":
    main()