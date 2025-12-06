# Arxiu: gridbot_binance/core/bot.py
from core.exchange import BinanceConnector
from core.database import BotDatabase
from utils.logger import log
import time
import math
import threading
import copy
from colorama import Fore, Style

class GridBot:
    def __init__(self):
        self.connector = BinanceConnector()
        self.db = BotDatabase()
        self.config = self.connector.config
        self.pairs_map = {}
        self._refresh_pairs_map()
        self.levels = {} 
        self.is_running = False
        self.is_paused = False 
        self.reserved_inventory = {} 
        self.global_start_time = 0
        self.bot_thread = None 

    def _refresh_pairs_map(self):
        self.pairs_map = {p['symbol']: p for p in self.config['pairs'] if p['enabled']}
        self.active_pairs = list(self.pairs_map.keys())

    # --- BUCLE DE DADES (BACKGROUND) ---
    def _data_collector_loop(self):
        """Bucle secundari: Recull preus, ordres i trades per a la UI i DB"""
        while self.is_running:
            # Si estem pausats o sense connexió, esperem sense fer peticions
            if self.is_paused or not self.connector.exchange:
                time.sleep(1)
                continue

            current_pairs = list(self.active_pairs)
            for symbol in current_pairs:
                try:
                    # 1. Preu i espelmes
                    price = self.connector.fetch_current_price(symbol)
                    candles = self.connector.fetch_candles(symbol, limit=100)
                    self.db.update_market_snapshot(symbol, price, candles)

                    # 2. Ordres obertes i estat del grid
                    open_orders = self.connector.fetch_open_orders(symbol) or []
                    grid_levels = self.levels.get(symbol, [])
                    self.db.update_grid_status(symbol, open_orders, grid_levels)

                    # 3. Històric de trades recents
                    trades = self.connector.fetch_my_trades(symbol, limit=10)
                    self.db.save_trades(trades)
                except Exception: pass
                time.sleep(1) # Petit delay per no saturar API
            
            time.sleep(2) # Espera entre cicles de dades

    # --- LÒGICA DE NEGOCI I CALCULS ---
    def _get_params(self, symbol):
        pair_config = self.pairs_map.get(symbol, {})
        return pair_config.get('strategy', self.config['default_strategy'])

    def _generate_fixed_levels(self, symbol, current_price):
        params = self._get_params(symbol)
        quantity = params['grids_quantity']
        spread_percent = params['grid_spread'] / 100 
        log.info(f"Calculando rejilla {symbol} ({current_price})...")
        levels = []
        for i in range(1, int(quantity / 2) + 1):
            levels.append(current_price * (1 - (spread_percent * i))) 
            levels.append(current_price * (1 + (spread_percent * i))) 
        levels.sort()
        
        # Neteja de decimals segons precisió exchange
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
        
        # Validació de mínims de l'exchange
        market = self.connector.exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        if base_amount < min_amount: return 0.0
        
        try:
            amt_str = self.connector.exchange.amount_to_precision(symbol, base_amount)
            return float(amt_str)
        except: return 0.0

    def _ensure_grid_consistency(self, symbol):
        current_price = self.connector.fetch_current_price(symbol)
        if current_price == 0: return # Error de lectura

        open_orders = self.connector.fetch_open_orders(symbol)
        
        # Si no tenim grid creat, el creem
        if symbol not in self.levels:
            self.levels[symbol] = self._generate_fixed_levels(symbol, current_price)

        my_levels = self.levels[symbol]
        base_asset, quote_asset = symbol.split('/')
        params = self._get_params(symbol)
        spread_val = params['grid_spread'] / 100
        margin = current_price * (spread_val * 0.1) 

        for level_price in my_levels:
            # Decidim si toca comprar o vendre en aquest nivell
            target_side = None
            if level_price > current_price + margin: target_side = 'sell'
            elif level_price < current_price - margin: target_side = 'buy'
            else: continue # Estem massa a prop del preu actual

            # Comprovem si ja existeix l'ordre
            exists = False
            for o in open_orders:
                if math.isclose(o['price'], level_price, rel_tol=1e-5):
                    if o['side'] == target_side: exists = True
                    else:
                        # Si hi ha una ordre del tipus contrari (e.g. sell on toca buy), cancel·lem
                        self.connector.exchange.cancel_order(o['id'], symbol)
                        exists = False 
                    break
            if exists: continue 

            # Creem la nova ordre
            amount = self._get_amount_for_level(symbol, level_price)
            if amount == 0: continue

            if target_side == 'buy':
                balance = self.connector.get_asset_balance(quote_asset)
                if balance < amount * level_price: continue
            else: 
                balance = self.connector.get_asset_balance(base_asset)
                reserved = self.reserved_inventory.get(base_asset, 0.0)
                # No venem el que tenim reservat per "Hold"
                if (balance - reserved) < amount * 0.99: continue
                # Ajust per errors d'arrodoniment
                if balance < amount and balance > amount * 0.9:
                      try: amount = float(self.connector.exchange.amount_to_precision(symbol, balance))
                      except: pass

            log.warning(f"[{symbol}] Creando orden {target_side} @ {level_price}")
            self.connector.place_order(symbol, target_side, amount, level_price)

    def _handle_smart_reload(self):
        print() 
        log.warning("🔄 CONFIGURACIÓN ACTUALIZADA: Analizando cambios...")
        
        old_testnet = self.config.get('system', {}).get('use_testnet', True)
        new_config = self.connector.config 
        new_testnet = new_config.get('system', {}).get('use_testnet', True)
        
        self.config = new_config
        self._refresh_pairs_map()
        
        # CAS 1: Canvi de Xarxa (Testnet <-> Real)
        if old_testnet != new_testnet:
            network_name = "TESTNET" if new_testnet else "REAL"
            log.warning(f"🚨 CAMBIO DE RED DETECTADO A: {network_name}. Reiniciando sistema...")
            
            self.levels = {}
            self.reserved_inventory = {}
            self.db.reset_all_statistics()
            
            log.info("Recalculando patrimonio en la nueva red...")
            initial_equity = self.calculate_total_equity()
            self.db.set_session_start_balance(initial_equity)
            self.db.set_global_start_balance_if_not_exists(initial_equity)
            self.capture_initial_snapshots()
            self.global_start_time = time.time()
            
            log.success(f"✅ Sistema reiniciado en modo {network_name}.")
            return

        # CAS 2: Canvi d'estratègia o parells (mateixa xarxa)
        new_symbols = set(self.pairs_map.keys())
        active_running_symbols = set(self.levels.keys())
        
        removed = active_running_symbols - new_symbols
        for symbol in removed:
            log.info(f"⛔ Deteniendo {symbol}. Cancelando órdenes...")
            self.connector.cancel_all_orders(symbol)
            if symbol in self.levels: del self.levels[symbol]
            if symbol in self.reserved_inventory: del self.reserved_inventory[symbol.split('/')[0]]
            
        added = new_symbols - active_running_symbols
        for symbol in added: log.success(f"✨ Activando {symbol}.")
        
        log.info("✅ Recarga completada.")

    # --- UTILITATS MANUALS ---
    def manual_close_order(self, symbol, order_id, side, amount):
        print()
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

    def calculate_total_equity(self):
        total_usdc = 0.0
        try:
            total_usdc += self.connector.get_total_balance('USDC')
        except: pass
        for symbol in self.active_pairs:
            base = symbol.split('/')[0]
            try:
                qty = self.connector.get_total_balance(base)
                if qty > 0:
                    price = self.connector.fetch_current_price(symbol)
                    total_usdc += (qty * price)
            except: pass
        return total_usdc

    def capture_initial_snapshots(self):
        for symbol in self.active_pairs:
            base = symbol.split('/')[0]
            try:
                qty = self.connector.get_total_balance(base)
                price = self.connector.fetch_current_price(symbol)
                initial_value = qty * price
                self.db.set_coin_initial_balance(symbol, initial_value)
            except Exception as e:
                log.error(f"Error snapshot {symbol}: {e}")

    # --- ACCIONS DE PÀNIC / CONTROL ---
    
    def panic_stop(self):
        print()
        log.warning("⛔ ACCIÓN DE USUARIO: PAUSANDO BOT...")
        self.is_paused = True
        return True

    def resume_bot(self):
        print()
        log.success("▶️ ACCIÓN DE USUARIO: REANUDANDO BOT...")
        self.is_paused = False
        return True

    def panic_cancel_all(self):
        print()
        log.warning("⛔ ACCIÓN DE PÁNICO: Cancelando todas las órdenes...")
        count = 0
        for symbol in self.active_pairs:
            self.connector.cancel_all_orders(symbol)
            grid_levels = self.levels.get(symbol, [])
            self.db.update_grid_status(symbol, [], grid_levels)
            count += 1
        return count

    def panic_sell_all(self):
        print()
        log.warning("🔥 ACCIÓN DE PÁNICO: VENDIENDO TODO A USDC...")
        sold_count = 0
        self.panic_cancel_all()
        time.sleep(2) 

        for symbol in self.active_pairs:
            try:
                base_asset = symbol.split('/')[0]
                amount = self.connector.get_asset_balance(base_asset)
                price = self.connector.fetch_current_price(symbol)
                value_usdc = amount * price
                
                if value_usdc > 2.0: 
                    log.warning(f"Vendiendo {amount} {base_asset} a mercado...")
                    self.connector.place_market_sell(symbol, amount)
                    sold_count += 1
                    time.sleep(0.5) 
            except Exception as e:
                log.error(f"Error Panic Sell {symbol}: {e}")
        return sold_count

    # --- MOTOR PRINCIPAL (ENGINE) ---

    def _run_engine(self):
        """Aquesta és la funció principal que s'executa en un fil apart."""
        log.info(f"{Fore.CYAN}--- INICIANDO GRIDBOT PROFESSIONAL ---{Style.RESET_ALL}")
        
        # 1. Configurar i Connectar
        self.connector.check_and_reload_config()
        self.config = self.connector.config 
        self.connector.validate_connection()
        
        # 2. Inicialitzar Estat Econòmic
        log.info("Calculando patrimonio inicial...")
        initial_equity = self.calculate_total_equity()
        log.info(f"💰 Patrimonio Inicial Total: {Fore.GREEN}{initial_equity:.2f} USDC{Fore.RESET}")
        
        self.db.set_session_start_balance(initial_equity)
        self.db.set_global_start_balance_if_not_exists(initial_equity)
        self.capture_initial_snapshots()
        self.global_start_time = time.time()

        # 3. Neteja Inicial
        log.warning("Limpiando órdenes antiguas iniciales...")
        for symbol in self.active_pairs:
            self.connector.cancel_all_orders(symbol)
        
        log.info("Arrancando motores...")
        time.sleep(2)
        
        # 4. Arrencada de bucles
        self.is_running = True
        self.is_paused = False 
        
        data_thread = threading.Thread(target=self._data_collector_loop, daemon=True)
        data_thread.start()
        
        try:
            self._monitoring_loop()
        except KeyboardInterrupt:
            # Això només passaria si matem el fil directament, cosa que no fem
            pass
        finally:
            log.info("Motor detenido.")

    def launch(self):
        """Llança el motor en segon pla (Web control)"""
        if self.is_running:
            log.warning("El bot ja està corrent!")
            return False
        
        self.bot_thread = threading.Thread(target=self._run_engine, daemon=True)
        self.bot_thread.start()
        return True

    def stop_logic(self):
        """Atura el motor"""
        if not self.is_running: return
        log.warning("Aturando lógica del bot...")
        self.is_running = False
        # No fem join per evitar bloquejos, deixem que el thread mori sol al acabar el bucle
        log.success("Bot aturado.")

    def _monitoring_loop(self):
        delay = self.config['system']['cycle_delay']
        spin_chars = ["|", "/", "-", "\\"]
        idx = 0
        
        while self.is_running:
            # A. Mode Pausa (Només check config)
            if self.is_paused:
                # Permetem canviar de xarxa fins i tot en pausa
                if self.connector.check_and_reload_config():
                    self._handle_smart_reload()
                    
                log.status(f"{Fore.YELLOW}PAUSADO{Fore.RESET} - Esperando comando... {spin_chars[idx]}")
                idx = (idx + 1) % 4
                time.sleep(1)
                continue
            
            # B. Mode Sense Connexió (Només check config)
            if not self.connector.exchange:
                if self.connector.check_and_reload_config():
                    self._handle_smart_reload()

                log.status(f"{Fore.RED}SIN CONEXIÓN{Fore.RESET} - Revisa API Keys / Red... {spin_chars[idx]}")
                idx = (idx + 1) % 4
                time.sleep(1)
                continue

            # C. Mode Operatiu Normal
            if self.connector.check_and_reload_config():
                self._handle_smart_reload()
            
            for symbol in self.active_pairs:
                self._ensure_grid_consistency(symbol)
            
            display_status = f"{Fore.GREEN}EN MARXA{Fore.RESET} | Monitorizando {len(self.active_pairs)} pares | {spin_chars[idx]}"
            log.status(display_status)
            idx = (idx + 1) % 4
            
            time.sleep(delay)