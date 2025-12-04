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

    # --- GESTIÓ DE SALDOS ---
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
    
    # -----------------------------------------

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

    def save_trades(self, trades):
        if not trades: return
        conn = self._get_conn()
        cursor = conn.cursor()
        for t in trades:
            try:
                fee_cost = 0.0
                fee_currency = ''
                if 'fee' in t and t['fee']:
                    fee_cost = float(t['fee'].get('cost', 0.0))
                    fee_currency = t['fee'].get('currency', '')

                symbol_parts = t['symbol'].split('/')
                quote_currency = symbol_parts[1] if len(symbol_parts) > 1 else 'USDC'
                fee_in_quote = 0.0
                
                if fee_cost > 0:
                    if fee_currency == quote_currency:
                        fee_in_quote = fee_cost
                    else:
                        fee_in_quote = fee_cost * t['price']

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

    def get_stats(self, from_timestamp=0):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, side, cost, fee_cost, amount FROM trade_history WHERE timestamp >= ?", (from_timestamp * 1000,))
        rows = cursor.fetchall()
        conn.close()

        total_trades = len(rows)
        cash_flow_per_coin = {} 
        qty_delta_per_coin = {} # NOU: Control de variació d'inventari
        trades_per_coin = {} 

        for symbol, side, cost, fee, amount in rows:
            # CASH FLOW:
            val = cost if side == 'sell' else -cost
            net_val = val - (fee if fee else 0.0)
            
            if symbol not in cash_flow_per_coin: cash_flow_per_coin[symbol] = 0.0
            cash_flow_per_coin[symbol] += net_val

            # INVENTORY DELTA (Canvi en la quantitat de monedes)
            if symbol not in qty_delta_per_coin: qty_delta_per_coin[symbol] = 0.0
            if side == 'buy':
                qty_delta_per_coin[symbol] += amount
            else:
                qty_delta_per_coin[symbol] -= amount

            if symbol not in trades_per_coin: trades_per_coin[symbol] = 0
            trades_per_coin[symbol] += 1

        best_coin = "-"
        highest_cf = -99999999.0
        for sym, val in cash_flow_per_coin.items():
            if val > highest_cf:
                highest_cf = val
                best_coin = sym
        if highest_cf == -99999999.0: best_coin = "-"

        trades_distribution = [{"name": k, "value": v} for k, v in trades_per_coin.items()]

        return {
            "trades": total_trades,
            "best_coin": best_coin,
            "trades_distribution": trades_distribution,
            "per_coin_stats": {
                "cash_flow": cash_flow_per_coin,
                "qty_delta": qty_delta_per_coin, # Retornem el delta
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

    def reset_all_statistics(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trade_history")
        now = str(time.time())
        cursor.execute("DELETE FROM bot_info WHERE key IN ('first_run', 'global_start_balance', 'session_start_balance')")
        cursor.execute("INSERT INTO bot_info (key, value) VALUES (?, ?)", ('first_run', now))
        conn.commit()
        conn.close()
        return True