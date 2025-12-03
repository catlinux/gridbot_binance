# Arxiu: gridbot_binance/core/bot.py
from core.exchange import BinanceConnector
from core.database import BotDatabase
from utils.logger import log
import time
import math
import threading
import copy

class GridBot:
    def __init__(self):
        self.connector = BinanceConnector()
        self.db = BotDatabase()
        self.config = self.connector.config
        self.pairs_map = {}
        self._refresh_pairs_map()
        self.levels = {} 
        self.is_running = False
        self.reserved_inventory = {} 
        self.global_start_time = time.time()

    def _refresh_pairs_map(self):
        self.pairs_map = {p['symbol']: p for p in self.config['pairs'] if p['enabled']}
        self.active_pairs = list(self.pairs_map.keys())

    def _data_collector_loop(self):
        # Aquest log només surt un cop al principi
        log.info("Colector de datos iniciado (Background).")
        while self.is_running:
            current_pairs = list(self.active_pairs)
            for symbol in current_pairs:
                try:
                    price = self.connector.fetch_current_price(symbol)
                    candles = self.connector.fetch_candles(symbol, limit=100)
                    self.db.update_market_snapshot(symbol, price, candles)

                    open_orders = self.connector.fetch_open_orders(symbol) or []
                    grid_levels = self.levels.get(symbol, [])
                    self.db.update_grid_status(symbol, open_orders, grid_levels)

                    trades = self.connector.fetch_my_trades(symbol, limit=10)
                    self.db.save_trades(trades)
                except Exception: pass
                time.sleep(1)
            time.sleep(5)

    def _get_params(self, symbol):
        pair_config = self.pairs_map.get(symbol, {})
        return pair_config.get('strategy', self.config['default_strategy'])

    def _generate_fixed_levels(self, symbol, current_price):
        params = self._get_params(symbol)
        quantity = params['grids_quantity']
        spread_percent = params['grid_spread'] / 100 
        
        # Canviat a DEBUG o eliminat per no embrutar, només surt si es recalcula
        # log.info(f"Calculando rejilla {symbol}...") 
        
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
            except: clean_levels.append(p)
        return clean_levels

    def _get_amount_for_level(self, symbol, price):
        params = self._get_params(symbol)
        amount_usdc = params['amount_per_grid']
        base_amount = amount_usdc / price 
        market = self.connector.exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        if base_amount < min_amount: return 0.0
        try:
            amt_str = self.connector.exchange.amount_to_precision(symbol, base_amount)
            return float(amt_str)
        except: return 0.0

    def _ensure_grid_consistency(self, symbol):
        current_price = self.connector.fetch_current_price(symbol)
        open_orders = self.connector.fetch_open_orders(symbol)
        if current_price is None or open_orders is None: return 

        if symbol not in self.levels:
            log.info(f"[{symbol}] Generando nueva rejilla a {current_price} USDC")
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
                        log.warning(f"[{symbol}] Orden fuera de rango. Cancelando...")
                        self.connector.exchange.cancel_order(o['id'], symbol)
                        exists = False 
                    break
            if exists: continue 

            amount = self._get_amount_for_level(symbol, level_price)
            if amount == 0: continue

            # Comprovacions de saldo silencioses (només log si realment anem a posar l'ordre)
            if target_side == 'buy':
                balance = self.connector.get_asset_balance(quote_asset)
                if balance < amount * level_price: continue
            else: 
                balance = self.connector.get_asset_balance(base_asset)
                reserved = self.reserved_inventory.get(base_asset, 0.0)
                if (balance - reserved) < amount * 0.99: continue
                if balance < amount and balance > amount * 0.9:
                     try: amount = float(self.connector.exchange.amount_to_precision(symbol, balance))
                     except: pass

            # Aquest és l'únic moment que volem soroll: quan es posa una ordre
            # La funció place_order ja fa el log.trade
            self.connector.place_order(symbol, target_side, amount, level_price)

    def _handle_smart_reload(self):
        # Aquest missatge sí que és important, usem warning (groc) o success (verd)
        print() # Salt de línia per separar del status loop
        log.warning("🔄 CONFIGURACIÓN ACTUALIZADA: Analizando cambios...")
        old_map = copy.deepcopy(self.pairs_map)
        self.config = self.connector.config
        self._refresh_pairs_map()
        new_symbols = set(self.pairs_map.keys())
        old_symbols = set(old_map.keys())
        removed = old_symbols - new_symbols
        for symbol in removed:
            log.info(f"⛔ Deteniendo {symbol}. Cancelando órdenes...")
            self.connector.cancel_all_orders(symbol)
            if symbol in self.levels: del self.levels[symbol]
            if symbol in self.reserved_inventory: del self.reserved_inventory[symbol.split('/')[0]]
        added = new_symbols - old_symbols
        for symbol in added: log.success(f"✨ Activando {symbol}.")
        kept = old_symbols & new_symbols
        for symbol in kept:
            old_strat = old_map[symbol].get('strategy')
            new_strat = self.pairs_map[symbol].get('strategy')
            if old_strat != new_strat:
                log.warning(f"♻️ Cambio detectado en {symbol}. Reiniciando grid...")
                base_asset = symbol.split('/')[0]
                total_holding = self.connector.get_total_balance(base_asset)
                if total_holding > 0:
                    self.reserved_inventory[base_asset] = total_holding
                    log.info(f"🔒 {symbol}: Reservados {total_holding} {base_asset}.")
                self.connector.cancel_all_orders(symbol)
                if symbol in self.levels: del self.levels[symbol]
        log.success("Recarga completada. Volviendo a monitorización.")

    def manual_close_order(self, symbol, order_id, side, amount):
        print() # Salt de línia visual
        log.warning(f"MANUAL: Cerrando orden {order_id} ({side}) en {symbol}...")
        res = self.connector.cancel_order(order_id, symbol)
        if side == 'buy':
            log.success(f"Orden {order_id} cancelada. USDC recuperados.")
            return True
        elif side == 'sell':
            time.sleep(0.5)
            market_order = self.connector.place_market_sell(symbol, amount)
            if market_order:
                log.success(f"Activo vendido a mercado (Market Sell) correctamente.")
                return True
            else:
                log.error("No se ha podido ejecutar el Market Sell.")
                return False

    def start(self):
        log.info("--- INICIANDO GRIDBOT PROFESSIONAL ---")
        self.connector.validate_connection()
        log.warning("Limpiando órdenes antiguas iniciales...")
        for symbol in self.active_pairs:
            self.connector.cancel_all_orders(symbol)
        time.sleep(2)
        
        log.info("📸 Tomando instantánea del valor de la cartera...")
        initial_equity = self.connector.get_estimated_portfolio_value(self.active_pairs)
        self.db.set_session_start_balance(initial_equity)
        self.db.set_global_start_balance_if_not_exists(initial_equity)
        
        log.success(f"Valor Total Cartera: {initial_equity:.2f} USDC")

        self.is_running = True
        data_thread = threading.Thread(target=self._data_collector_loop, daemon=True)
        data_thread.start()
        try:
            self._monitoring_loop()
        except KeyboardInterrupt:
            self._shutdown()

    def _monitoring_loop(self):
        delay = self.config['system']['cycle_delay']
        while self.is_running:
            # 1. Check Config
            if self.connector.check_and_reload_config():
                self._handle_smart_reload()
            
            # 2. Check Grid Logic
            for symbol in self.active_pairs:
                self._ensure_grid_consistency(symbol)
            
            # 3. IMPRIMIR ESTAT COMPACTE (Això substitueix els logs repetitius)
            # Mostrem: Parells actius | Hora
            pairs_str = ", ".join([s.split('/')[0] for s in self.active_pairs])
            log.status(f"Escaneando {len(self.active_pairs)} pares: [{pairs_str}]... Esperando {delay}s")
            
            time.sleep(delay)

    def _shutdown(self):
        self.is_running = False
        print() # Salt de línia obligatori després del status loop
        log.warning("--- DETENIENDO GRIDBOT ---")
        log.success("Bot detenido.")