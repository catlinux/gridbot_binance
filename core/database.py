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
        # Hem tret l'auto-manteniment com has demanat

    def _get_conn(self):
        """Crea una connexió nova (necessari per multithreading)."""
        return sqlite3.connect(DB_PATH, check_same_thread=False)

    def _init_db(self):
        """Crea les taules si no existeixen."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Taula 1: Dades de Mercat (Snapshot ràpid per la web)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                symbol TEXT PRIMARY KEY,
                price REAL,
                candles_json TEXT,
                updated_at REAL
            )
        ''')

        # Taula 2: Estat del Grid i Ordres
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS grid_status (
                symbol TEXT PRIMARY KEY,
                open_orders_json TEXT,
                grid_levels_json TEXT,
                stats_json TEXT,
                updated_at REAL
            )
        ''')

        # Taula 3: Històric de Trades (Persistent)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id TEXT PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                price REAL,
                amount REAL,
                cost REAL,
                timestamp REAL
            )
        ''')

        conn.commit()
        conn.close()

    def update_market_snapshot(self, symbol, price, candles):
        """Actualitza preu i gràfic."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO market_data (symbol, price, candles_json, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (symbol, price, json.dumps(candles), time.time()))
        conn.commit()
        conn.close()

    def update_grid_status(self, symbol, orders, levels, stats):
        """Actualitza l'estat del bot."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO grid_status (symbol, open_orders_json, grid_levels_json, stats_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (symbol, json.dumps(orders), json.dumps(levels), json.dumps(stats), time.time()))
        conn.commit()
        conn.close()

    def save_trades(self, trades):
        """Guarda nous trades (ignora els duplicats)."""
        if not trades: return
        conn = self._get_conn()
        cursor = conn.cursor()
        for t in trades:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO trade_history (id, symbol, side, price, amount, cost, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (t['id'], t['symbol'], t['side'], t['price'], t['amount'], t['cost'], t['timestamp']))
            except: pass
        conn.commit()
        conn.close()

    # --- MÈTODES DE LECTURA (PER AL WEB) ---

    def get_pair_data(self, symbol):
        """Recupera tot el necessari per pintar la pestanya de la moneda."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row # Per accedir per nom
        cursor = conn.cursor()

        # Dades de mercat
        cursor.execute("SELECT * FROM market_data WHERE symbol=?", (symbol,))
        market = cursor.fetchone()

        # Estat Grid
        cursor.execute("SELECT * FROM grid_status WHERE symbol=?", (symbol,))
        grid = cursor.fetchone()

        # Trades (Últims 50 per mostrar, tot i que es guarden tots)
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
        """Per al dashboard general."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, price FROM market_data")
        rows = cursor.fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}