# Arxiu: gridbot_binance/core/bot.py
from core.exchange import BinanceConnector
from utils.logger import log
import time
import math

class GridBot:
    def __init__(self):
        self.connector = BinanceConnector()
        self.config = self.connector.config
        self._refresh_pairs_map()
        self.levels = {} 
        self.is_running = False
        
        # Diccionari per protegir les "Bosses" (Bags)
        # self.reserved_inventory['BTC'] = 0.05
        self.reserved_inventory = {} 

    def _refresh_pairs_map(self):
        self.pairs_map = {p['symbol']: p for p in self.config['pairs'] if p['enabled']}
        self.active_pairs = list(self.pairs_map.keys())

    def _get_params(self, symbol):
        pair_config = self.pairs_map.get(symbol, {})
        return pair_config.get('strategy', self.config['default_strategy'])

    def _generate_fixed_levels(self, symbol, current_price):
        params = self._get_params(symbol)
        quantity = params['grids_quantity']
        spread_percent = params['grid_spread'] / 100 
        
        log.info(f"Calculant graella {symbol}. Spread: {params['grid_spread']}% | Nivells: {quantity}")
        
        levels = []
        for i in range(1, int(quantity / 2) + 1):
            levels.append(current_price * (1 - (spread_percent * i))) 
            levels.append(current_price * (1 + (spread_percent * i))) 
            
        levels.sort()
        clean_levels = []
        for p in levels:
            try:
                p_str = self.connector.exchange.price_to_precision(symbol, p)
                clean_levels.append(float(p_str))
            except:
                clean_levels.append(p)
        return clean_levels

    def _get_amount_for_level(self, symbol, price):
        params = self._get_params(symbol)
        amount_usdc = params['amount_per_grid']
        base_amount = amount_usdc / price 
        
        market = self.connector.exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        
        if base_amount < min_amount:
            return 0.0
        try:
            amt_str = self.connector.exchange.amount_to_precision(symbol, base_amount)
            return float(amt_str)
        except:
            return 0.0

    def _ensure_grid_consistency(self, symbol):
        current_price = self.connector.fetch_current_price(symbol)
        open_orders = self.connector.fetch_open_orders(symbol)
        if current_price is None or open_orders is None: return 

        if symbol not in self.levels:
            self.levels[symbol] = self._generate_fixed_levels(symbol, current_price)

        my_levels = self.levels[symbol]
        base_asset, quote_asset = symbol.split('/')
        params = self._get_params(symbol)
        spread_val = params['grid_spread'] / 100
        margin = current_price * (spread_val * 0.1) 

        for level_price in my_levels:
            target_side = None
            if level_price > current_price + margin: target_side = 'sell'
            elif level_price < current_price - margin: target_side = 'buy'
            else: continue 

            exists = False
            for o in open_orders:
                if math.isclose(o['price'], level_price, rel_tol=1e-5):
                    if o['side'] == target_side: exists = True
                    else:
                        log.info(f"[{symbol}] Preu creuat a {level_price}. Cancel·lant ordre antiga...")
                        self.connector.exchange.cancel_order(o['id'], symbol)
                        exists = False 
                    break
            if exists: continue 

            amount = self._get_amount_for_level(symbol, level_price)
            if amount == 0: continue

            if target_side == 'buy':
                balance = self.connector.get_asset_balance(quote_asset)
                if balance < amount * level_price:
                    log.error(f"[{symbol}] Fons insuficients {quote_asset} per comprar.")
                    continue
                log.warning(f"[{symbol}] Creant ordre {target_side.upper()} a {level_price}...")
                self.connector.place_order(symbol, target_side, amount, level_price)
            
            else: # SELL SIDE - AMB PROTECCIÓ D'INVENTARI
                balance = self.connector.get_asset_balance(base_asset)
                
                # Calculem quant tenim realment "lliure" per al grid (ignorant les bosses velles)
                reserved = self.reserved_inventory.get(base_asset, 0.0)
                available_for_grid = balance - reserved
                
                # Si el saldo disponible per al grid és menor que l'ordre, NO VENEM
                # (Això protegeix les teves monedes velles)
                if available_for_grid < amount * 0.99: # 1% marge error
                    # No fem log d'error aquí per no saturar, simplement no posem l'ordre
                    # perquè vol dir que encara no hem comprat prou "nou" per vendre.
                    continue

                log.warning(f"[{symbol}] Creant ordre {target_side.upper()} a {level_price}...")
                self.connector.place_order(symbol, target_side, amount, level_price)

    def start(self):
        log.info("--- INICIANT GRIDBOT MULTI-ASSET ---")
        self.connector.validate_connection()
        
        # A l'inici normal, NO reservem inventari (assumim que vols utilitzar el que hi hagi)
        # O SI VOLS PROTEGIR SEMPRE L'INICI, descomenta les línies de sota.
        # Per defecte, a l'inici netejem i comencem.
        
        log.warning("Netejant ordres antigues...")
        for symbol in self.active_pairs:
            self.connector.cancel_all_orders(symbol)
            
        log.info("Esperant 5 segons post-neteja...")
        time.sleep(5)

        self.is_running = True
        try:
            self._monitoring_loop()
        except KeyboardInterrupt:
            self._shutdown()

    def _monitoring_loop(self):
        delay = self.config['system']['cycle_delay']
        while self.is_running:
            
            # --- HOT RELOAD AMB PROTECCIÓ ---
            if self.connector.check_and_reload_config():
                log.warning("🔄 CONFIGURACIÓ ACTUALITZADA: Aplicant canvis...")
                self.config = self.connector.config
                self._refresh_pairs_map() 
                self.levels = {} 

                # 1. ANALITZAR INVENTARI ACTUAL ABANS DE CANCEL·LAR
                # Guardem el que tenim ara com a "reserva" per no vendre-ho barat
                for symbol in self.active_pairs:
                    base_asset = symbol.split('/')[0]
                    total_holding = self.connector.get_total_balance(base_asset)
                    if total_holding > 0:
                        self.reserved_inventory[base_asset] = total_holding
                        log.info(f"🔒 PROTECCIÓ: Reservats {total_holding} {base_asset}. No es vendran amb la nova graella.")

                # 2. Ara sí, cancel·lem ordres (el saldo tornarà al wallet, però ja està reservat virtualment)
                for symbol in self.active_pairs:
                    log.info(f"Cancel·lant ordres de {symbol}...")
                    self.connector.cancel_all_orders(symbol)
                
                log.info("Canvis aplicats. Generant noves línies...")
            # -------------------------------

            for symbol in self.active_pairs:
                self._ensure_grid_consistency(symbol)
            time.sleep(delay)

    def _shutdown(self):
        self.is_running = False
        print()
        log.warning("--- ATURANT GRIDBOT ---")
        log.success("Bot aturat.")