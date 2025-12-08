# Arxiu: gridbot_binance/core/exchange.py
import ccxt
import os
import json5
from dotenv import load_dotenv
from utils.logger import log

# Carreguem .env (override=True permet recarregar si canvia)
load_dotenv(dotenv_path='config/.env', override=True)

class BinanceConnector:
    def __init__(self):
        self.exchange = None
        self.config_path = 'config/config.json5'
        self.last_config_mtime = 0 
        self.config = self._load_config()
        self._connect()
        try:
            if self.exchange: self.exchange.load_markets()
        except Exception as e:
            log.error(f"Error cargando mercados: {e}")

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

        if not api_key or not secret_key:
            log.error(f"❌ FALTAN CLAVES para modo {'TESTNET' if use_testnet else 'REAL'}.")
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

    def get_asset_balance(self, asset):
        if not self.exchange: return 0.0
        try:
            balance = self.exchange.fetch_balance()
            return float(balance.get(asset, {}).get('free', 0.0))
        except Exception as e:
            return 0.0

    def get_total_balance(self, asset):
        if not self.exchange: return 0.0
        try:
            balance = self.exchange.fetch_balance()
            if asset in balance:
                free = float(balance[asset].get('free', 0.0))
                used = float(balance[asset].get('used', 0.0)) 
                return free + used
            return 0.0
        except Exception as e:
            return 0.0

    def fetch_current_price(self, symbol):
        if not self.exchange: return 0.0
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            return 0.0

    def place_order(self, symbol, side, amount, price):
        if not self.exchange: return None
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
        if not self.exchange: return None
        try:
            log.warning(f"Ejecutando Venta a Mercado {symbol} Cantidad: {amount}")
            return self.exchange.create_order(symbol, 'market', 'sell', amount)
        except Exception as e:
            log.error(f"Error en Market Sell: {e}")
            return None

    # --- FUNCIÓ NOVA ---
    def place_market_buy(self, symbol, amount_usdc):
        """Compra a mercat especificant quants USDC volem gastar (quoteOrderQty)"""
        if not self.exchange: return None
        try:
            log.warning(f"Ejecutando COMPRA INICIAL a Mercado {symbol} Valor: {amount_usdc} USDC")
            # En Binance, per comprar X valor de quote (USDC), fem servir create_order amb params
            # Nota: CCXT gestiona 'cost' o 'quoteOrderQty' depenent de l'exchange, per simplificar
            # calculem quantitat base aproximada o usem el mètode específic si cal.
            # Per seguretat amb CCXT genèric, calcularem la quantitat base.
            
            price = self.fetch_current_price(symbol)
            if price == 0: return None
            
            amount_base = amount_usdc / price
            # Apliquem precisió
            amount_base = self.exchange.amount_to_precision(symbol, amount_base)
            
            return self.exchange.create_order(symbol, 'market', 'buy', amount_base)
        except Exception as e:
            log.error(f"Error en Market Buy: {e}")
            return None
    # -------------------

    def cancel_order(self, order_id, symbol):
        if not self.exchange: return None
        try:
            return self.exchange.cancel_order(order_id, symbol)
        except Exception as e:
            log.error(f"Error cancelando orden {order_id}: {e}")
            return None

    def cancel_all_orders(self, symbol):
        if not self.exchange: return None
        try:
            return self.exchange.cancel_all_orders(symbol)
        except ccxt.OrderNotFound:
            return None
        except Exception as e:
            if "-2011" in str(e): return None
            log.error(f"Error cancelando órdenes {symbol}: {e}")
            return None
            
    def fetch_open_orders(self, symbol):
        if not self.exchange: return []
        try:
            return self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            return []

    def fetch_candles(self, symbol, timeframe='15m', limit=50):
        if not self.exchange: return []
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            log.error(f"Error obteniendo velas: {e}")
            return []

    def fetch_my_trades(self, symbol, limit=20):
        if not self.exchange: return []
        try:
            return self.exchange.fetch_my_trades(symbol, limit=limit)
        except Exception as e:
            return []
