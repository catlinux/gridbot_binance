# Arxiu: gridbot_binance/core/exchange.py
import ccxt
import os
import json5
from dotenv import load_dotenv
from utils.logger import log

load_dotenv(dotenv_path='config/.env')

class BinanceConnector:
    def __init__(self):
        self.exchange = None
        self.config_path = 'config/config.json5'
        self.last_config_mtime = 0 
        self.config = self._load_config()
        self._connect()
        try:
            self.exchange.load_markets()
        except Exception as e:
            log.error(f"Error cargando mercados: {e}")
            exit(1)

    def _load_config(self):
        try:
            mtime = os.path.getmtime(self.config_path)
            self.last_config_mtime = mtime
            with open(self.config_path, 'r') as f:
                return json5.load(f)
        except Exception as e:
            log.error(f"Error leyendo config.json5: {e}")
            if hasattr(self, 'config'): return self.config
            exit(1)

    def check_and_reload_config(self):
        try:
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime > self.last_config_mtime:
                log.warning("Detectado cambio en config.json5. Recargando...")
                new_config = self._load_config()
                if new_config:
                    self.config = new_config
                    return True
        except Exception as e:
            log.error(f"Error verificando config: {e}")
        return False

    def _connect(self):
        api_key = os.getenv('BINANCE_API_KEY')
        secret_key = os.getenv('BINANCE_SECRET_KEY')
        use_testnet = os.getenv('USE_TESTNET', 'False').lower() == 'true'

        if not api_key or not secret_key:
            log.error("Faltan las claves API en el archivo .env")
            exit(1)

        try:
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': secret_key,
                'enableRateLimit': True, 
                'options': { 'defaultType': 'spot', 'adjustForTimeDifference': True }
            })

            if use_testnet:
                self.exchange.set_sandbox_mode(True)
                log.warning("Modo TESTNET activado.")
            else:
                log.info("Modo REAL activado.")

        except Exception as e:
            log.error(f"Error inicializando CCXT: {e}")
            exit(1)

    def validate_connection(self):
        try:
            self.exchange.fetch_time() 
            log.success("Conexión con Binance establecida correctamente.")
            return True
        except Exception as e:
            log.error(f"Error de conexión API: {e}")
            return False

    def get_asset_balance(self, asset):
        try:
            balance = self.exchange.fetch_balance()
            return balance.get(asset, {}).get('free', 0.0)
        except Exception as e:
            log.error(f"Error obteniendo saldo de {asset}: {e}")
            return 0.0

    def get_total_balance(self, asset):
        try:
            balance = self.exchange.fetch_balance()
            return balance.get(asset, {}).get('total', 0.0)
        except Exception as e:
            log.error(f"Error obteniendo saldo TOTAL de {asset}: {e}")
            return 0.0

    def fetch_current_price(self, symbol):
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            log.error(f"Error obteniendo precio para {symbol}: {e}")
            return 0.0

    def place_order(self, symbol, side, amount, price):
        params = {}
        try:
            order = self.exchange.create_order(symbol, 'limit', side, amount, price, params)
            log.trade(symbol, side, price, amount)
            return order
        except ccxt.InsufficientFunds as e:
             log.error(f"FONDOS INSUFICIENTES: {e}")
             return None
        except Exception as e:
            log.error(f"Error colocando orden: {e}")
            return None

    def place_market_sell(self, symbol, amount):
        try:
            log.warning(f"Ejecutando Venta a Mercado {symbol} Cantidad: {amount}")
            return self.exchange.create_order(symbol, 'market', 'sell', amount)
        except Exception as e:
            log.error(f"Error en Market Sell: {e}")
            return None

    def cancel_order(self, order_id, symbol):
        try:
            return self.exchange.cancel_order(order_id, symbol)
        except Exception as e:
            log.error(f"Error cancelando orden {order_id}: {e}")
            return None

    def cancel_all_orders(self, symbol):
        try:
            return self.exchange.cancel_all_orders(symbol)
        except ccxt.OrderNotFound:
            return None
        except Exception as e:
            if "-2011" in str(e): return None
            log.error(f"Error cancelando órdenes {symbol}: {e}")
            return None
            
    def fetch_open_orders(self, symbol):
        try:
            return self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            log.warning(f"Error API obteniendo órdenes ({symbol}): {e}")
            return None 

    def fetch_candles(self, symbol, timeframe='15m', limit=50):
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            log.error(f"Error obteniendo velas: {e}")
            return []

    def fetch_my_trades(self, symbol, limit=20):
        try:
            return self.exchange.fetch_my_trades(symbol, limit=limit)
        except Exception as e:
            log.error(f"Error obteniendo trades: {e}")
            return []