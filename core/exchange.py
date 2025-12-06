# Arxiu: gridbot_binance/core/exchange.py
import ccxt
import os
import json5
from dotenv import load_dotenv
from utils.logger import log

# Carreguem .env
load_dotenv(dotenv_path='config/.env', override=True)

class BinanceConnector:
    def __init__(self):
        self.exchange = None
        self.config_path = 'config/config.json5'
        self.last_config_mtime = 0 
        self.config = self._load_config()
        self._connect()
        # Intentem carregar mercats, si falla no passa res, ho reintentarem després
        try:
            if self.exchange: self.exchange.load_markets()
        except: pass

    def _load_config(self):
        try:
            mtime = os.path.getmtime(self.config_path)
            self.last_config_mtime = mtime
            with open(self.config_path, 'r') as f:
                return json5.load(f)
        except Exception as e:
            log.error(f"Error leyendo config.json5: {e}")
            if hasattr(self, 'config'): return self.config
            return {}

    def check_and_reload_config(self):
        try:
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime > self.last_config_mtime:
                log.warning("Detectado cambio en config.json5...")
                new_config = self._load_config()
                if new_config:
                    old_testnet = self.config.get('system', {}).get('use_testnet', True)
                    new_testnet = new_config.get('system', {}).get('use_testnet', True)
                    
                    self.config = new_config
                    
                    # Si ha canviat la xarxa O si abans no teníem connexió (self.exchange is None)
                    # intentem reconnectar
                    if old_testnet != new_testnet or self.exchange is None:
                        log.warning(f"🔄 RECONFIGURACIÓN DE RED: {'TESTNET' if new_testnet else 'REAL'}. Conectando...")
                        self._connect()
                        try: 
                            if self.exchange: self.exchange.load_markets()
                        except: pass
                        
                    return True
        except Exception as e:
            log.error(f"Error verificando config: {e}")
        return False

    def _connect(self):
        # Recarreguem variables d'entorn per si l'usuari ha tocat el .env sense reiniciar
        load_dotenv(dotenv_path='config/.env', override=True)
        
        use_testnet = self.config.get('system', {}).get('use_testnet', True)

        if use_testnet:
            api_key = os.getenv('BINANCE_API_KEY_TEST')
            secret_key = os.getenv('BINANCE_SECRET_KEY_TEST')
            log.info("📡 Intentando conectar a BINANCE TESTNET...")
        else:
            api_key = os.getenv('BINANCE_API_KEY_REAL')
            secret_key = os.getenv('BINANCE_SECRET_KEY_REAL')
            log.warning("🚨 Intentando conectar a BINANCE REAL (DINERO REAL) 🚨")

        # Si falten claus, NO PETEM. Simplement avisem i quedem a l'espera.
        if not api_key or not secret_key:
            log.error(f"❌ FALTAN CLAVES para modo {'TESTNET' if use_testnet else 'REAL'}. Configura el .env o cambia el modo en la Web.")
            self.exchange = None
            return

        try:
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': secret_key,
                'enableRateLimit': True, 
                'options': { 'defaultType': 'spot', 'adjustForTimeDifference': True }
            })

            if use_testnet:
                self.exchange.set_sandbox_mode(True)
            
            # Provem connexió bàsica
            self.exchange.fetch_time()
            log.success(f"✅ Conexión EXITOSA con Binance ({'TESTNET' if use_testnet else 'REAL'}).")

        except Exception as e:
            log.error(f"❌ Error de conexión: {e}")
            self.exchange = None

    def validate_connection(self):
        if not self.exchange: return False
        try:
            self.exchange.fetch_time() 
            return True
        except Exception:
            return False

    # Totes les funcions següents han de comprovar si self.exchange existeix
    def get_asset_balance(self, asset):
        if not self.exchange: return 0.0
        try:
            balance = self.exchange.fetch_balance()
            return balance.get(asset, {}).get('free', 0.0)
        except: return 0.0

    def get_total_balance(self, asset):
        if not self.exchange: return 0.0
        try:
            balance = self.exchange.fetch_balance()
            return balance.get(asset, {}).get('total', 0.0)
        except: return 0.0

    def fetch_current_price(self, symbol):
        if not self.exchange: return 0.0
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except: return 0.0

    def place_order(self, symbol, side, amount, price):
        if not self.exchange: return None
        try:
            order = self.exchange.create_order(symbol, 'limit', side, amount, price, {})
            log.trade(symbol, side, price, amount)
            return order
        except Exception as e:
            log.error(f"Error orden: {e}")
            return None

    def place_market_sell(self, symbol, amount):
        if not self.exchange: return None
        try:
            log.warning(f"Ejecutando Venta a Mercado {symbol} Cantidad: {amount}")
            return self.exchange.create_order(symbol, 'market', 'sell', amount)
        except Exception as e:
            log.error(f"Error Market Sell: {e}")
            return None

    def cancel_order(self, order_id, symbol):
        if not self.exchange: return None
        try:
            return self.exchange.cancel_order(order_id, symbol)
        except: return None

    def cancel_all_orders(self, symbol):
        if not self.exchange: return None
        try:
            return self.exchange.cancel_all_orders(symbol)
        except: return None
            
    def fetch_open_orders(self, symbol):
        if not self.exchange: return []
        try:
            return self.exchange.fetch_open_orders(symbol)
        except: return []

    def fetch_candles(self, symbol, timeframe='15m', limit=50):
        if not self.exchange: return []
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except: return []

    def fetch_my_trades(self, symbol, limit=20):
        if not self.exchange: return []
        try:
            return self.exchange.fetch_my_trades(symbol, limit=limit)
        except: return []