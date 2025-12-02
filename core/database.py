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
        cursor.execute('''CREATE TABLE IF NOT EXISTS grid_status (symbol TEXT PRIMARY KEY, open_orders_json TEXT, grid_levels_json TEXT, stats_json TEXT, updated_at REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trade_history (id TEXT PRIMARY KEY, symbol TEXT, side TEXT, price REAL, amount REAL, cost REAL, timestamp REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS profit_history (trade_id TEXT PRIMARY KEY, symbol TEXT, profit REAL, timestamp REAL)''')
        conn.commit()
        conn.close()

    def update_market_snapshot(self, symbol, price, candles):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO market_data (symbol, price, candles_json, updated_at) VALUES (?, ?, ?, ?)', (symbol, price, json.dumps(candles), time.time()))
        conn.commit()
        conn.close()

    def update_grid_status(self, symbol, orders, levels, stats):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO grid_status (symbol, open_orders_json, grid_levels_json, stats_json, updated_at) VALUES (?, ?, ?, ?, ?)', (symbol, json.dumps(orders), json.dumps(levels), json.dumps(stats), time.time()))
        conn.commit()
        conn.close()

    def save_trades(self, trades):
        if not trades: return
        conn = self._get_conn()
        cursor = conn.cursor()
        for t in trades:
            try:
                cursor.execute('''INSERT OR IGNORE INTO trade_history (id, symbol, side, price, amount, cost, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)''', (t['id'], t['symbol'], t['side'], t['price'], t['amount'], t['cost'], t['timestamp']))
            except: pass
        conn.commit()
        conn.close()

    def register_profit(self, trade_id, symbol, profit, timestamp):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT OR IGNORE INTO profit_history (trade_id, symbol, profit, timestamp) VALUES (?, ?, ?, ?)', (trade_id, symbol, profit, timestamp))
            conn.commit()
        except: pass
        finally: conn.close()

    def get_total_stats(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(profit) FROM profit_history")
        total_profit = cursor.fetchone()[0] or 0.0
        cursor.execute("SELECT COUNT(*) FROM trade_history")
        total_trades = cursor.fetchone()[0] or 0
        cursor.execute("SELECT symbol, SUM(profit) as p FROM profit_history GROUP BY symbol ORDER BY p DESC LIMIT 1")
        row = cursor.fetchone()
        best_coin = row[0] if row else "Cap"
        conn.close()
        return {"total_profit": total_profit, "total_trades": total_trades, "best_coin": best_coin}

    # --- IMPRESCINDIBLE PER AL GRÀFIC ---
    def get_trades_breakdown(self):
        """Retorna recompte d'operacions per moneda."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, COUNT(*) as count FROM trade_history GROUP BY symbol")
            rows = cursor.fetchall()
            conn.close()
            return [{"name": row[0], "value": row[1]} for row in rows]
        except:
            return []

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