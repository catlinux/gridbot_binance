# Archivo: gridbot_binance/core/database.py
import sqlite3
import json
import time
import os
from utils.logger import log

DB_FOLDER = "data"
DB_NAME = "bot_data.db"
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

class BotDatabase:
    def __init__(self):
        if not os.path.exists(DB_FOLDER):
            os.makedirs(DB_FOLDER)
        # Ya no guardamos self.conn aquí para evitar conflictos de hilos
        self._init_db()

    def _get_conn(self):
        """Abre una conexión nueva segura para el hilo actual"""
        return sqlite3.connect(DB_PATH, timeout=30) # Timeout alto para evitar bloqueos

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
            except Exception as e:
                log.warning(f"No se pudo activar WAL: {e}")
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS market_data (symbol TEXT PRIMARY KEY, price REAL, candles_json TEXT, updated_at REAL)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS grid_status (symbol TEXT PRIMARY KEY, open_orders_json TEXT, grid_levels_json TEXT, updated_at REAL)''')
            
            try:
                cursor.execute("ALTER TABLE grid_status ADD COLUMN setup_done BOOLEAN DEFAULT 0")
            except: pass 

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
            
            try:
                cursor.execute("ALTER TABLE trade_history ADD COLUMN buy_id INTEGER")
            except: pass 
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS balance_history (
                    timestamp REAL PRIMARY KEY,
                    equity REAL
                )
            ''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS bot_info (key TEXT PRIMARY KEY, value TEXT)''')
            
            cursor.execute("SELECT value FROM bot_info WHERE key='next_buy_id'")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO bot_info (key, value) VALUES (?, ?)", ('next_buy_id', '1'))
                
            cursor.execute("SELECT value FROM bot_info WHERE key='first_run'")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO bot_info (key, value) VALUES (?, ?)", ('first_run', str(time.time())))
            
            conn.commit()

    def get_next_buy_id(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key='next_buy_id'")
            row = cursor.fetchone()
            current_id = int(row[0]) if row else 1
            
            assigned_id = current_id
            next_id = current_id + 1
            # Canviem el límit de 500 a 1000 com has demanat
            if next_id > 1000: next_id = 1
            
            cursor.execute("INSERT OR REPLACE INTO bot_info (key, value) VALUES (?, ?)", ('next_buy_id', str(next_id)))
            conn.commit()
            return assigned_id

    def set_trade_buy_id(self, trade_id, buy_id):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE trade_history SET buy_id = ? WHERE id = ?", (buy_id, trade_id))
            conn.commit()

    def get_last_buy_price(self, symbol):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM trade_history WHERE symbol=? AND side='buy' ORDER BY timestamp DESC LIMIT 1", (symbol,))
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def find_linked_buy_id(self, symbol, sell_price, spread_pct):
        target_buy_price = sell_price / (1 + (spread_pct / 100))
        min_p = target_buy_price * 0.99
        max_p = target_buy_price * 1.01
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT buy_id FROM trade_history 
                WHERE symbol=? AND side='buy' AND price >= ? AND price <= ? 
                ORDER BY timestamp DESC LIMIT 1
            ''', (symbol, min_p, max_p))
            row = cursor.fetchone()
            return row[0] if row else None

    def log_balance_snapshot(self, equity):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO balance_history (timestamp, equity) VALUES (?, ?)", (time.time(), equity))
            conn.commit()

    def get_balance_history(self, from_timestamp=0):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, equity FROM balance_history WHERE timestamp >= ? ORDER BY timestamp ASC", (from_timestamp,))
            rows = cursor.fetchall()
            return rows

    def set_session_start_balance(self, value):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO bot_info (key, value) VALUES (?, ?)", ('session_start_balance', str(value)))
            conn.commit()

    def get_session_start_balance(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key='session_start_balance'")
            row = cursor.fetchone()
            if row: return float(row[0])
            return 0.0

    def set_global_start_balance_if_not_exists(self, value):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key='global_start_balance'")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO bot_info (key, value) VALUES (?, ?)", ('global_start_balance', str(value)))
            conn.commit()

    def get_global_start_balance(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key='global_start_balance'")
            row = cursor.fetchone()
            if row: return float(row[0])
            return 0.0

    def set_coin_initial_balance(self, symbol, value_usdc):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key='coins_initial_equity'")
            row = cursor.fetchone()
            data = {}
            if row:
                try: data = json.loads(row[0])
                except: pass
            data[symbol] = value_usdc
            cursor.execute("INSERT OR REPLACE INTO bot_info (key, value) VALUES (?, ?)", ('coins_initial_equity', json.dumps(data)))
            conn.commit()

    def get_coin_initial_balance(self, symbol):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key='coins_initial_equity'")
            row = cursor.fetchone()
            if row:
                try:
                    data = json.loads(row[0])
                    return float(data.get(symbol, 0.0))
                except: pass
            return 0.0

    def reset_coin_initial_balances(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bot_info WHERE key='coins_initial_equity'")
            conn.commit()

    def update_market_snapshot(self, symbol, price, candles):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT OR REPLACE INTO market_data (symbol, price, candles_json, updated_at) VALUES (?, ?, ?, ?)''', (symbol, price, json.dumps(candles), time.time()))
            conn.commit()

    def update_grid_status(self, symbol, orders, levels):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT setup_done FROM grid_status WHERE symbol=?", (symbol,))
            row = cursor.fetchone()
            setup_val = row[0] if row else 0
            
            cursor.execute('''INSERT OR REPLACE INTO grid_status (symbol, open_orders_json, grid_levels_json, updated_at, setup_done) VALUES (?, ?, ?, ?, ?)''', (symbol, json.dumps(orders), json.dumps(levels), time.time(), setup_val))
            conn.commit()

    def set_symbol_setup_done(self, symbol, status=True):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            val = 1 if status else 0
            cursor.execute("UPDATE grid_status SET setup_done=? WHERE symbol=?", (val, symbol))
            if cursor.rowcount == 0:
                 cursor.execute("INSERT INTO grid_status (symbol, setup_done, updated_at) VALUES (?, ?, ?)", (symbol, val, time.time()))
            conn.commit()

    def get_symbol_setup_done(self, symbol):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT setup_done FROM grid_status WHERE symbol=?", (symbol,))
            row = cursor.fetchone()
            if row: return bool(row[0])
            return False

    def save_trades(self, trades):
        if not trades: return
        with self._get_conn() as conn:
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

    def get_pair_data(self, symbol):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM market_data WHERE symbol=?", (symbol,))
            market_row = cursor.fetchone()
            market = {}
            if market_row:
                cols = [d[0] for d in cursor.description]
                market = dict(zip(cols, market_row))

            cursor.execute("SELECT * FROM grid_status WHERE symbol=?", (symbol,))
            grid_row = cursor.fetchone()
            grid = {}
            if grid_row:
                cols = [d[0] for d in cursor.description]
                grid = dict(zip(cols, grid_row))

            cursor.execute("SELECT * FROM trade_history WHERE symbol=? ORDER BY timestamp DESC LIMIT 50", (symbol,))
            trades_rows = cursor.fetchall()
            trades = []
            if trades_rows:
                cols = [d[0] for d in cursor.description]
                for row in trades_rows:
                    t_dict = dict(zip(cols, row))
                    if 'buy_id' not in t_dict: t_dict['buy_id'] = None
                    trades.append(t_dict)
            
            return {
                "price": market.get('price', 0.0),
                "candles": json.loads(market.get('candles_json', '[]')) if market.get('candles_json') else [],
                "open_orders": json.loads(grid.get('open_orders_json', '[]')) if grid.get('open_orders_json') else [],
                "grid_levels": json.loads(grid.get('grid_levels_json', '[]')) if grid.get('grid_levels_json') else [],
                "trades": trades
            }

    def get_all_prices(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, price FROM market_data")
            rows = cursor.fetchall()
            return {r[0]: r[1] for r in rows}

    def get_first_run_timestamp(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key='first_run'")
            row = cursor.fetchone()
            if row: return float(row[0])
            return time.time()

    def get_stats(self, from_timestamp=0):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, side, cost, fee_cost, amount, timestamp FROM trade_history WHERE timestamp >= ?", (int(from_timestamp * 1000),))
            rows = cursor.fetchall()

            total_trades = len(rows)
            cash_flow_per_coin = {} 
            qty_delta_per_coin = {} 
            trades_per_coin = {} 

            # Recuperamos sesiones individuales
            cursor.execute("SELECT key, value FROM bot_info WHERE key LIKE 'session_start_%'")
            session_rows = cursor.fetchall()
            coin_sessions = {}
            for k, v in session_rows:
                sym = k.replace('session_start_', '')
                try: coin_sessions[sym] = float(v)
                except: pass

            for symbol, side, cost, fee, amount, ts in rows:
                session_start_coin = coin_sessions.get(symbol, 0.0)
                if from_timestamp > 0 and session_start_coin > 0 and ts < (session_start_coin * 1000):
                    continue
                
                val = cost if side == 'sell' else -cost
                net_val = val - (fee if fee else 0.0)
                
                if symbol not in cash_flow_per_coin: cash_flow_per_coin[symbol] = 0.0
                cash_flow_per_coin[symbol] += net_val

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
                    "qty_delta": qty_delta_per_coin,
                    "trades": trades_per_coin
                }
            }

    def get_all_active_orders(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, open_orders_json FROM grid_status")
            rows = cursor.fetchall()
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

    def prune_old_data(self, days_keep=30):
        cutoff = time.time() - (days_keep * 24 * 3600)
        cutoff_ms = cutoff * 1000
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trade_history WHERE timestamp < ?", (cutoff_ms,))
            deleted_trades = cursor.rowcount
            
            cursor.execute("DELETE FROM balance_history WHERE timestamp < ?", (cutoff,))
            deleted_balance = cursor.rowcount
            
            if deleted_trades > 0 or deleted_balance > 0:
                cursor.execute("VACUUM")

            conn.commit()
            return deleted_trades, deleted_balance

    def assign_id_to_trade_if_missing(self, trade_id):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT buy_id FROM trade_history WHERE id=?", (trade_id,))
            row = cursor.fetchone()
            
            if row and row[0] is not None:
                found_id = row[0]
                return found_id
                
            new_id = self.get_next_buy_id() # Esta función abre su propia conexión, correcto
            
            # ¿Necesitamos set_trade_buy_id en una nueva transacción o en esta?
            # Como usamos _get_conn en set_trade_buy_id, mejor llamarla fuera o usar la conexión actual.
            # Por simplicidad y seguridad de hilos, llamamos a self.set_trade_buy_id que abre la suya.
            
        self.set_trade_buy_id(trade_id, new_id)
        return new_id

    def get_buy_trade_uuid_for_sell_order(self, symbol, sell_price, spread_pct):
        target = sell_price / (1 + (spread_pct / 100))
        min_p = target * 0.995 
        max_p = target * 1.005
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM trade_history 
                WHERE symbol=? AND side='buy' AND price >= ? AND price <= ? 
                ORDER BY timestamp DESC LIMIT 1
            ''', (symbol, min_p, max_p))
            row = cursor.fetchone()
            return row[0] if row else None

    def delete_history_smart(self, symbol, keep_uuids):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if not keep_uuids:
                cursor.execute("DELETE FROM trade_history WHERE symbol=?", (symbol,))
            else:
                placeholders = ','.join(['?'] * len(keep_uuids))
                sql = f"DELETE FROM trade_history WHERE symbol=? AND id NOT IN ({placeholders})"
                params = [symbol] + keep_uuids
                cursor.execute(sql, params)
            count = cursor.rowcount
            conn.commit()
            return count

    def set_session_start_time(self, timestamp):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO bot_info (key, value) VALUES (?, ?)", ('session_start_time', str(timestamp)))
            conn.commit()

    def get_session_start_time(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key='session_start_time'")
            row = cursor.fetchone()
            if row: return float(row[0])
            return 0.0

    def get_all_stored_grids(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, grid_levels_json FROM grid_status")
            rows = cursor.fetchall()
            grids = {}
            for symbol, levels_json in rows:
                try:
                    if levels_json:
                        grids[symbol] = json.loads(levels_json)
                except: pass
            return grids

    def clear_session_data(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bot_info WHERE key='session_start_time'")
            cursor.execute("DELETE FROM bot_info WHERE key='session_start_balance'")
            cursor.execute("DELETE FROM bot_info WHERE key LIKE 'session_start_%'")
            conn.commit()

    # --- NUEVAS FUNCIONES DE GESTIÓN DE DATOS ---
    
    def reset_all_statistics(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trade_history")
            cursor.execute("DELETE FROM balance_history")
            cursor.execute("UPDATE grid_status SET setup_done=0")
            
            now = str(time.time())
            cursor.execute("DELETE FROM bot_info WHERE key IN ('first_run', 'global_start_balance', 'session_start_balance', 'coins_initial_equity', 'next_buy_id')")
            cursor.execute("INSERT INTO bot_info (key, value) VALUES (?, ?)", ('first_run', now))
            cursor.execute("INSERT INTO bot_info (key, value) VALUES (?, ?)", ('next_buy_id', '1'))
            
            # Limpieza de sesión integrada
            cursor.execute("DELETE FROM bot_info WHERE key='session_start_time'")
            cursor.execute("DELETE FROM bot_info WHERE key='session_start_balance'")
            cursor.execute("DELETE FROM bot_info WHERE key LIKE 'session_start_%'")
            
            conn.commit()
        return True

    def clear_balance_history(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM balance_history")
            conn.commit()

    def clear_all_trades_history(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trade_history")
            conn.commit()

    def clear_orders_cache(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE grid_status SET open_orders_json = '[]'")
            conn.commit()

    def delete_trades_for_symbol(self, symbol):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trade_history WHERE symbol=?", (symbol,))
            conn.commit()

    def set_coin_session_start(self, symbol, timestamp):
        key = f"session_start_{symbol}"
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO bot_info (key, value) VALUES (?, ?)", (key, str(timestamp)))
            conn.commit()

    def get_coin_session_start(self, symbol):
        key = f"session_start_{symbol}"
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key=?", (key,))
            row = cursor.fetchone()
            if row: return float(row[0])
            return 0.0

    # --- NOVES FUNCIONS PER GESTIÓ DE CAPITAL (CAPITAL ADJUSTMENT) ---

    def adjust_balance_history(self, delta_usdc):
        """Ajusta el balanç inicial global i de sessió (per ingressos/retirades)"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 1. Ajustar Global Start Balance
            cursor.execute("SELECT value FROM bot_info WHERE key='global_start_balance'")
            row = cursor.fetchone()
            current_glob = float(row[0]) if row else 0.0
            new_glob = current_glob + delta_usdc
            cursor.execute("INSERT OR REPLACE INTO bot_info (key, value) VALUES (?, ?)", ('global_start_balance', str(new_glob)))
            
            # 2. Ajustar Session Start Balance
            cursor.execute("SELECT value FROM bot_info WHERE key='session_start_balance'")
            row = cursor.fetchone()
            current_sess = float(row[0]) if row else 0.0
            new_sess = current_sess + delta_usdc
            cursor.execute("INSERT OR REPLACE INTO bot_info (key, value) VALUES (?, ?)", ('session_start_balance', str(new_sess)))
            
            conn.commit()

    def adjust_coin_initial_balance(self, symbol, delta_usdc):
        """Ajusta el valor inicial d'una moneda específica (si ingressem crypto directament)"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_info WHERE key='coins_initial_equity'")
            row = cursor.fetchone()
            data = {}
            if row:
                try: data = json.loads(row[0])
                except: pass
            
            current_val = float(data.get(symbol, 0.0))
            data[symbol] = current_val + delta_usdc
            
            cursor.execute("INSERT OR REPLACE INTO bot_info (key, value) VALUES (?, ?)", ('coins_initial_equity', json.dumps(data)))
            conn.commit()