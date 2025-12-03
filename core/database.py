# Arxiu: gridbot_binance/core/database.py
import sqlite3
import json
import time
from utils.logger import log

DB_PATH = "bot_data.db"

class BotDatabase:
    def __init__(self):
        self.conn = None
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(DB_PATH, check_same_thread=False)

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS market_data (symbol TEXT PRIMARY KEY, price REAL, candles_json TEXT, updated_at REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS grid_status (symbol TEXT PRIMARY KEY, open_orders_json TEXT, grid_levels_json TEXT, updated_at REAL)''')
        
        # MODIFICAT: Afegim camps per a les comissions (fee)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id TEXT PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                price REAL,
                amount REAL,
                cost REAL,
                fee_cost REAL,
                fee_currency TEXT,
                timestamp REAL
            )
        ''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS bot_info (key TEXT PRIMARY KEY, value TEXT)''')
        
        cursor.execute("SELECT value FROM bot_info WHERE key='first_run'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO bot_info (key, value) VALUES (?, ?)", ('first_run', str(time.time())))

        conn.commit()
        conn.close()

    # --- SESSIÓ ---
    def set_session_start_balance(self, value):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO bot_info (key, value) VALUES (?, ?)", ('session_start_balance', str(value)))
        conn.commit()
        conn.close()

    def get_session_start_balance(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_info WHERE key='session_start_balance'")
        row = cursor.fetchone()
        conn.close()
        if row: return float(row[0])
        return 0.0

    # --- GLOBAL ---
    def set_global_start_balance_if_not_exists(self, value):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_info WHERE key='global_start_balance'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO bot_info (key, value) VALUES (?, ?)", ('global_start_balance', str(value)))
        conn.commit()
        conn.close()

    def get_global_start_balance(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_info WHERE key='global_start_balance'")
        row = cursor.fetchone()
        conn.close()
        if row: return float(row[0])
        return 0.0

    def update_market_snapshot(self, symbol, price, candles):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO market_data (symbol, price, candles_json, updated_at) VALUES (?, ?, ?, ?)''', (symbol, price, json.dumps(candles), time.time()))
        conn.commit()
        conn.close()

    def update_grid_status(self, symbol, orders, levels):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO grid_status (symbol, open_orders_json, grid_levels_json, updated_at) VALUES (?, ?, ?, ?)''', (symbol, json.dumps(orders), json.dumps(levels), time.time()))
        conn.commit()
        conn.close()

    # --- MODIFICAT: CÀLCUL I GUARDAT DE FEES ---
    def save_trades(self, trades):
        if not trades: return
        conn = self._get_conn()
        cursor = conn.cursor()
        
        for t in trades:
            try:
                # Extreure informació de la comissió si existeix
                fee_cost = 0.0
                fee_currency = ''
                
                if 'fee' in t and t['fee']:
                    fee_cost = float(t['fee'].get('cost', 0.0))
                    fee_currency = t['fee'].get('currency', '')

                # Normalització: Volem saber quant és la comissió en la moneda QUOTE (ex: USDC)
                # Si comprem BTC/USDC, la fee sol ser en BTC (Base). Si venem, en USDC (Quote).
                # Per simplificar l'emmagatzematge, si la fee no és la Quote, 
                # la convertim a valor Quote usant el preu del trade.
                
                symbol_parts = t['symbol'].split('/')
                quote_currency = symbol_parts[1] if len(symbol_parts) > 1 else 'USDC'
                
                fee_in_quote = 0.0
                
                if fee_cost > 0:
                    if fee_currency == quote_currency:
                        # La comissió ja està en dòlars/USDC
                        fee_in_quote = fee_cost
                    else:
                        # La comissió està en BTC o BNB. Aproximem el valor al preu del trade.
                        # Ex: 0.0001 BTC * 50000 $/BTC = 5$
                        fee_in_quote = fee_cost * t['price']

                # Guardem el valor normalitzat a 'fee_cost' per facilitar els càlculs després
                cursor.execute('''
                    INSERT OR IGNORE INTO trade_history (id, symbol, side, price, amount, cost, fee_cost, fee_currency, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (t['id'], t['symbol'], t['side'], t['price'], t['amount'], t['cost'], fee_in_quote, 'USDC_EQ', t['timestamp']))
            except Exception as e: 
                log.error(f"Error guardando trade DB: {e}")
                pass
        conn.commit()
        conn.close()

    def get_pair_data(self, symbol):
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM market_data WHERE symbol=?", (symbol,))
        market = cursor.fetchone()
        cursor.execute("SELECT * FROM grid_status WHERE symbol=?", (symbol,))
        grid = cursor.fetchone()
        cursor.execute("SELECT * FROM trade_history WHERE symbol=? ORDER BY timestamp DESC LIMIT 50", (symbol,))
        trades = cursor.fetchall()
        conn.close()
        return {
            "price": market['price'] if market else 0.0,
            "candles": json.loads(market['candles_json']) if market and market['candles_json'] else [],
            "open_orders": json.loads(grid['open_orders_json']) if grid and grid['open_orders_json'] else [],
            "grid_levels": json.loads(grid['grid_levels_json']) if grid and grid['grid_levels_json'] else [],
            "trades": [dict(row) for row in trades]
        }

    def get_all_prices(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, price FROM market_data")
        rows = cursor.fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}

    def get_first_run_timestamp(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_info WHERE key='first_run'")
        row = cursor.fetchone()
        conn.close()
        if row: return float(row[0])
        return time.time()

    # --- MODIFICAT: CÀLCUL AMB FEES ---
    def get_stats(self, from_timestamp=0):
        conn = self._get_conn()
        cursor = conn.cursor()
        # Recuperem també el fee_cost
        cursor.execute("SELECT symbol, side, cost, fee_cost FROM trade_history WHERE timestamp >= ?", (from_timestamp * 1000,))
        rows = cursor.fetchall()
        conn.close()

        total_trades = len(rows)
        pnl = 0.0
        pnl_per_coin = {}
        trades_per_coin = {} 

        for symbol, side, cost, fee in rows:
            # 1. PnL Brut (Cashflow)
            val = cost if side == 'sell' else -cost
            
            # 2. Restem la comissió (fee)
            # La fee SEMPRE és una despesa, tant si comprem com si venem.
            # fee ve normalitzat a USDC gràcies al save_trades modificat.
            net_val = val - (fee if fee else 0.0)

            pnl += net_val
            
            if symbol not in pnl_per_coin: pnl_per_coin[symbol] = 0.0
            pnl_per_coin[symbol] += net_val

            if symbol not in trades_per_coin: trades_per_coin[symbol] = 0
            trades_per_coin[symbol] += 1

        best_coin = "-"
        highest_pnl = -99999999.0
        for sym, val in pnl_per_coin.items():
            if val > highest_pnl:
                highest_pnl = val
                best_coin = sym
        if highest_pnl <= 0: best_coin = "-"

        trades_distribution = [{"name": k, "value": v} for k, v in trades_per_coin.items()]

        return {
            "trades": total_trades,
            "profit": pnl,
            "best_coin": best_coin,
            "trades_distribution": trades_distribution,
            "per_coin_stats": {
                "pnl": pnl_per_coin,
                "trades": trades_per_coin
            }
        }

    def get_all_active_orders(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, open_orders_json FROM grid_status")
        rows = cursor.fetchall()
        conn.close()
        all_orders = []
        for symbol, orders_json in rows:
            if not orders_json: continue
            try:
                orders = json.loads(orders_json)
                for o in orders:
                    o['symbol'] = symbol
                    all_orders.append(o)
            except: pass
        return all_orders