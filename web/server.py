# Archivo: gridbot_binance/web/server.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles 
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import os
import time
import json5 
import math
from datetime import datetime
from core.database import BotDatabase 
from utils.telegram import send_msg
from utils.logger import log
from dotenv import load_dotenv 

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuración de estáticos y plantillas
static_dir = os.path.join(BASE_DIR, "static")
if not os.path.exists(static_dir):
    os.makedirs(os.path.join(static_dir, "css"), exist_ok=True)
    os.makedirs(os.path.join(static_dir, "js"), exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Instancias globales
db = BotDatabase()
bot_instance = None 

# Modelos Pydantic para validación
class ConfigUpdate(BaseModel):
    content: str

class CloseOrderRequest(BaseModel):
    symbol: str
    order_id: str
    side: str
    amount: float

class LiquidateRequest(BaseModel):
    asset: str

class ClearHistoryRequest(BaseModel):
    symbol: str

class CoinResetRequest(BaseModel):
    symbol: str

# NOU MODEL PER AJUSTOS DE CAPITAL
class BalanceAdjustRequest(BaseModel):
    asset: str    # EX: "USDC" o "BTC"
    amount: float # EX: 1000 (Ingrés) o -500 (Retirada)

# --- FUNCIÓN AUXILIAR CÁLCULO RSI ---
def _calculate_rsi(candles, period=14):
    try:
        if not candles or len(candles) < period + 1:
            return 50.0 
        
        closes = [float(c[4]) for c in candles]
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
        if avg_loss == 0: return 100.0
        if avg_gain == 0: return 0.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    except:
        return 50.0
# ----------------------------------

def start_server(bot, host=None, port=None):

#Inicia el servidor web Uvicorn. Recibe la instancia del bot para controlarlo desde la API.
    global bot_instance
    bot_instance = bot
    
    load_dotenv('config/.env', override=True)
    
    if host is None:
        host = os.getenv('WEB_HOST', '127.0.0.1') 
    
    if port is None:
        port = int(os.getenv('WEB_PORT', 8001))
        
    uvicorn.run(app, host=host, port=port, log_level="error")

def format_uptime(seconds):
    if seconds < 0: return "0s"
    seconds = int(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    if days > 0: return f"{days}d {hours}h {mins}m"
    return f"{hours}h {mins}m"

# --- RUTAS DE PÁGINA (VISTAS) ---

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    # Pasamos lista de pares activos a la plantilla para generar pestañas
    return templates.TemplateResponse("index.html", {"request": request})

# --- API ENDPOINTS (DATOS) ---

@app.get("/api/status")
def get_status():
    # Endpoint principal del Dashboard.
    if not bot_instance: return {"status": "Offline"}
    
    try:
        status_text = "Stopped"
        if bot_instance.is_running:
            status_text = "Paused" if bot_instance.is_paused else "Running"

        # OPTIMITZACIÓ: Llegir preus de la DB (snapshot) primer
        prices = db.get_all_prices()
        
        # --- OPTIMITZACIÓ CRÍTICA (ANTI-BAN) ---
        # Descarreguem TOTS els saldos en 1 sola petició a l'API
        # en lloc de fer-ne una per cada moneda dins del bucle.
        all_balances_cache = {}
        try:
            # Només si tenim connexió, demanem balances
            if bot_instance.connector and bot_instance.connector.exchange:
                all_balances_cache = bot_instance.connector.exchange.fetch_balance()
        except: pass
        
        # Helper per llegir del 'cache' d'aquesta petició
        def get_bal_safe(asset):
            if not all_balances_cache: return 0.0
            # --- CORRECCIÓ: Sumar FREE + USED (Bloquejat en ordres) ---
            data = all_balances_cache.get(asset, {})
            free = float(data.get('free', 0.0))
            used = float(data.get('used', 0.0))
            return free + used
        # ---------------------------------------

        portfolio = []
        current_total_equity = 0.0
        
        usdc_balance = get_bal_safe('USDC')
        
        portfolio.append({"name": "USDC", "value": round(usdc_balance, 2)})
        current_total_equity += usdc_balance

        holding_values = {}
        current_prices_map = {}

        pairs_to_check = []
        if bot_instance and bot_instance.config:
            pairs_to_check = [p['symbol'] for p in bot_instance.config.get('pairs', [])]
        
        for symbol in pairs_to_check:
            base = symbol.split('/')[0]
            try:
                # Ara fem servir la funció local (sense petició de xarxa)
                qty = get_bal_safe(base)
                
                # Usem el preu de la DB si existeix
                price = prices.get(symbol, 0.0)
                
                # Si és 0 i és crític, demanem a l'API (només fallback)
                if price == 0 and bot_instance.connector.exchange: 
                    price = bot_instance.connector.fetch_current_price(symbol)
                
                if price > 0:
                    current_prices_map[symbol] = price 
                    val = qty * price
                    holding_values[symbol] = val 
                    if val > 0.5: 
                        portfolio.append({"name": base, "value": round(val, 2)})
                        current_total_equity += val
            except: pass

        # Estadísticas Globales vs Sesión (Llegides de DB local -> RÀPID)
        global_stats = db.get_stats(from_timestamp=0)
        session_start_ts = bot_instance.global_start_time
        session_stats = db.get_stats(from_timestamp=session_start_ts)

        if bot_instance.is_running:
            session_uptime_str = format_uptime(time.time() - session_start_ts)
        else:
            session_uptime_str = "OFF"

        first_run_ts = db.get_first_run_timestamp()
        total_uptime_str = format_uptime(time.time() - first_run_ts)

        # Datos por estrategia
        strategies_data = []
        global_cash_flow = global_stats['per_coin_stats']['cash_flow']
        session_cash_flow = session_stats['per_coin_stats']['cash_flow']
        global_trades_map = global_stats['per_coin_stats']['trades']

        acc_global_pnl = 0.0
        acc_session_pnl = 0.0

        for symbol in pairs_to_check:
            try:
                pair_config = next((p for p in bot_instance.config['pairs'] if p['symbol'] == symbol), None)
                if not pair_config: continue

                strat_conf = pair_config.get('strategy', {})
                is_enabled = pair_config.get('enabled', False)

                trades_count = global_trades_map.get(symbol, 0)
                curr_price = current_prices_map.get(symbol, 0.0)
                curr_val = holding_values.get(symbol, 0.0)
                
                init_val_coin = db.get_coin_initial_balance(symbol)
                
                if init_val_coin == 0.0 and curr_val > 0:
                    init_val_coin = curr_val
                    db.set_coin_initial_balance(symbol, init_val_coin)

                # Cálculo PnL Global
                cf_global = global_cash_flow.get(symbol, 0.0)
                strat_pnl_global = (curr_val - init_val_coin) + cf_global

                # Cálculo PnL Sesión
                cf_session = session_cash_flow.get(symbol, 0.0)
                qty_delta = session_stats['per_coin_stats']['qty_delta'].get(symbol, 0.0)
                strat_pnl_session = (qty_delta * curr_price) + cf_session

                # Limpieza de valores fantasma
                if trades_count == 0 and abs(strat_pnl_global) > (curr_val * 0.5) and curr_val > 0:
                     strat_pnl_global = 0.0

                acc_global_pnl += strat_pnl_global
                acc_session_pnl += strat_pnl_session

                if is_enabled or trades_count > 0 or curr_val > 1.0:
                    strategies_data.append({
                        "symbol": symbol,
                        "enabled": is_enabled,
                        "grids": strat_conf.get('grids_quantity', '-'),
                        "amount": strat_conf.get('amount_per_grid', '-'),
                        "spread": strat_conf.get('grid_spread', '-'),
                        "total_trades": trades_count,
                        "total_pnl": round(strat_pnl_global, 2),  
                        "session_pnl": round(strat_pnl_session, 2)
                    })
            except Exception as e:
                log.error(f"Error procesando stats {symbol}: {e}")

        global_pnl_total = acc_global_pnl
        session_pnl_total = acc_session_pnl

        return {
            "status": status_text,
            "active_pairs": bot_instance.active_pairs if bot_instance else [], 
            "balance_usdc": round(usdc_balance, 2),
            "total_usdc_value": round(current_total_equity, 2),
            "portfolio_distribution": portfolio,
            "session_trades_distribution": session_stats['trades_distribution'],
            "global_trades_distribution": global_stats['trades_distribution'],
            "strategies": strategies_data,
            "stats": {
                "session": {
                    "trades": session_stats['trades'],
                    "profit": round(session_pnl_total, 2),
                    "best_coin": session_stats['best_coin'],
                    "uptime": session_uptime_str
                },
                "global": {
                    "trades": global_stats['trades'],
                    "profit": round(global_pnl_total, 2),
                    "best_coin": global_stats['best_coin'],
                    "uptime": total_uptime_str
                }
            }
        }
    except Exception as e:
        log.error(f"FATAL API ERROR: {e}")
        return {
            "status": "Error",
            "active_pairs": [],
            "balance_usdc": 0,
            "total_usdc_value": 0,
            "portfolio_distribution": [],
            "session_trades_distribution": [],
            "global_trades_distribution": [],
            "strategies": [],
            "stats": {
                "session": {"trades":0,"profit":0,"best_coin":"-","uptime":"-"},
                "global": {"trades":0,"profit":0,"best_coin":"-","uptime":"-"}
            }
        }

@app.get("/api/history/balance")
def get_balance_history_api():
    try:
        full_hist = db.get_balance_history(from_timestamp=0)
        session_start = bot_instance.global_start_time if bot_instance else 0
        session_hist = [x for x in full_hist if x[0] >= session_start]
        
        def fmt(rows):
            return [[r[0]*1000, round(r[1], 2)] for r in rows]
            
        return {
            "global": fmt(full_hist),
            "session": fmt(session_hist)
        }
    except: return {"global": [], "session": []}

@app.get("/api/orders")
def get_all_orders():
    try:
        # OPTIMITZACIÓ: Llegir directament de la DB, que s'actualitza cada cicle del bot.
        # Això és instantani i no carrega l'exchange.
        raw_orders = db.get_all_active_orders()
        prices = db.get_all_prices()
        enhanced_orders = []
        
        active_symbols = set()
        if bot_instance:
            active_symbols = set(bot_instance.active_pairs)
        
        for o in raw_orders:
            symbol = o['symbol']
            
            if bot_instance and bot_instance.is_running:
                if symbol not in active_symbols:
                    continue

            current_price = prices.get(symbol, 0.0)
            # Només si la DB està buida (cas extrany), preguntem.
            if current_price == 0 and bot_instance and bot_instance.is_running:
                 current_price = bot_instance.connector.fetch_current_price(symbol)

            o['current_price'] = current_price
            o['total_value'] = o['amount'] * o['price']
            o['entry_price'] = 0.0
            if o['side'] == 'sell' and bot_instance:
                try:
                    strat = bot_instance.pairs_map.get(symbol, {}).get('strategy', bot_instance.config['default_strategy'])
                    spread = strat['grid_spread']
                    o['entry_price'] = o['price'] / (1 + (spread / 100.0))
                except: pass
            enhanced_orders.append(o)
        return enhanced_orders
    except: return []

@app.get("/api/wallet")
def get_wallet_data():
    if not bot_instance or not bot_instance.connector.exchange:
        return []
    
    try:
        # Aquesta funció és inevitablement lenta perquè necessita precisió total
        # Però com que no es crida automàticament cada segon (només a la pestanya Wallet), està bé.
        balances = bot_instance.connector.exchange.fetch_balance()
        if not balances: return []
        
        tickers = bot_instance.connector.exchange.fetch_tickers()
        wallet_list = []
        items = balances.get('total', {}).items()
        
        for asset, total_qty in items:
            if total_qty <= 0: continue
            
            usdc_value = 0.0
            price = 0.0
            
            if asset == 'USDC':
                usdc_value = total_qty
                price = 1.0
            elif asset == 'USDT':
                usdc_value = total_qty
                price = 1.0
            else:
                symbol = f"{asset}/USDC"
                if symbol in tickers:
                    price = float(tickers[symbol]['last'])
                    usdc_value = total_qty * price
            
            if usdc_value >= 1.0:
                free_qty = balances.get(asset, {}).get('free', 0.0)
                used_qty = balances.get(asset, {}).get('used', 0.0)
                
                wallet_list.append({
                    "asset": asset,
                    "free": free_qty,
                    "locked": used_qty,
                    "total": total_qty,
                    "usdc_value": round(usdc_value, 2),
                    "price": price
                })
        
        wallet_list.sort(key=lambda x: x['usdc_value'], reverse=True)
        return wallet_list
        
    except Exception as e:
        log.error(f"Error fetching wallet: {e}")
        return []

@app.post("/api/liquidate_asset")
def liquidate_asset_api(req: LiquidateRequest):
    # Venta de Pánico Selectiva.
    if not bot_instance or not bot_instance.connector.exchange:
        raise HTTPException(status_code=503, detail="Bot no conectado")
    
    asset = req.asset.upper()
    if asset == 'USDC':
        return {"status": "error", "message": "No se puede liquidar USDC."}
        
    symbol = f"{asset}/USDC"
    
    try:
        log.warning(f"LIQUIDACIÓN MANUAL: Cancelando órdenes de {symbol}...")
        bot_instance.connector.cancel_all_orders(symbol)
        time.sleep(1) 
        
        total_balance = bot_instance.connector.get_total_balance(asset)
        
        if total_balance > 0:
            log.warning(f"LIQUIDACIÓN MANUAL: Vendiendo {total_balance} {asset} a mercado...")
            order = bot_instance.connector.place_market_sell(symbol, total_balance)
            
            if order:
                msg = f"Activo {asset} liquidado a USDC."
                log.success(msg)
                send_msg(f"🔥 <b>LIQUIDACIÓN MANUAL</b>\nSe ha vendido todo el {asset} a USDC.")
                return {"status": "success", "message": msg}
            else:
                raise HTTPException(status_code=400, detail="Error al ejecutar la orden de venta.")
        else:
            return {"status": "warning", "message": "Saldo insuficiente para vender."}

    except Exception as e:
        log.error(f"Error liquidando {asset}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/history/clear")
def clear_history_api(req: ClearHistoryRequest):
    symbol = req.symbol
    keep_ids = []
    # Intentamos salvar los trades vinculados a ventas abiertas
    try:
        with open('config/config.json5', 'r') as f: config = json5.load(f)
        pair_conf = next((p for p in config['pairs'] if p['symbol'] == symbol), None)
        spread = pair_conf['strategy']['grid_spread'] if pair_conf else 1.0
        open_orders = []
        if bot_instance and bot_instance.connector.exchange:
            try: open_orders = bot_instance.connector.fetch_open_orders(symbol)
            except: pass
        if not open_orders:
            data = db.get_pair_data(symbol)
            open_orders = data.get('open_orders', [])
        active_sells = [o for o in open_orders if o['side'] == 'sell']
        for o in active_sells:
            sell_price = float(o['price'])
            uuid = db.get_buy_trade_uuid_for_sell_order(symbol, sell_price, spread)
            if uuid: keep_ids.append(uuid)
    except: pass

    try:
        count = db.delete_history_smart(symbol, keep_ids)
        return {"status": "success", "message": f"Historial limpiado. Borrados: {count}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS MANTENIMIENTO ---

@app.post("/api/balance/adjust")
def adjust_balance_api(req: BalanceAdjustRequest):
    """
    Gestiona Ingressos (+) i Retirades (-) per no afectar el PnL (Benefici).
    """
    try:
        asset = req.asset.upper()
        amount = req.amount
        
        # 1. Calculem el valor en USDC de l'ajust
        value_usdc = 0.0
        
        if asset == 'USDC' or asset == 'USDT':
            value_usdc = amount
        elif bot_instance and bot_instance.connector.exchange:
            # Si és una moneda (ex: he ingressat 0.5 BTC), busquem el preu
            symbol = f"{asset}/USDC"
            price = bot_instance.connector.fetch_current_price(symbol)
            value_usdc = amount * price
            
            # També ajustem el "cost inicial" d'aquesta moneda en particular
            # perquè el PnL de la moneda no es dispari.
            db.adjust_coin_initial_balance(symbol, value_usdc)
        
        # 2. Ajustem els balanços inicials GLOBALS i de SESSIÓ
        # Si ingresso 1000, el balanç inicial puja 1000 -> PnL (Actual - Inicial) es manté igual.
        db.adjust_balance_history(value_usdc)
        
        tipo = "Ingrés" if amount > 0 else "Retirada"
        log.info(f"💰 AJUST CAPITAL: {tipo} de {amount} {asset} ({value_usdc:.2f} USDC)")
        send_msg(f"📝 <b>CAPITAL {tipo.upper()}</b>\nS'ha ajustat la comptabilitat: {amount} {asset}")
        
        return {"status": "success", "message": f"Comptabilitat ajustada ({value_usdc:.2f} USDC)."}
        
    except Exception as e:
        log.error(f"Error ajustant capital: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset_stats")
def reset_stats_api():
    try:
        # 1. Borrado de base de datos
        db.reset_all_statistics()
        
        # 2. RE-SNAPSHOT INMEDIATO (Correcció PnL Fantasma)
        # Forçamos que el valor inicial sigui EXACTAMENT el que tenim ara mateix.
        if bot_instance:
            bot_instance.global_start_time = time.time()
            bot_instance.levels = {} 
            
            # Recalculamos equidad total YA
            initial_equity = bot_instance.calculate_total_equity()
            
            # Guardamos como punto de partida Global y Sesión
            db.set_session_start_balance(initial_equity)
            db.set_global_start_balance_if_not_exists(initial_equity)
            
            # Forçamos snapshot per a cada moneda activa també
            if bot_instance.active_pairs:
                log.info("📸 Forçant snapshot inicial de preus per Reset...")
                bot_instance.capture_initial_snapshots()

        send_msg("⚠️ <b>RESET TOTAL</b>\nSe han borrado todas las estadísticas y reiniciado el punto 0.")
        return {"status": "success", "message": "Reset Total completado. PnL a 0."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset/chart/global")
def reset_global_chart_api():
    try:
        db.clear_balance_history()
        return {"status": "success", "message": "Gráfica Global reiniciada."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset/chart/session")
def reset_session_chart_api():
    try:
        # Reiniciar sesión (afecta gráfica y PnL sesión)
        new_time = time.time()
        db.set_session_start_time(new_time)
        if bot_instance:
            bot_instance.global_start_time = new_time
            # Recalcular balance inicial sesión
            initial_equity = bot_instance.calculate_total_equity()
            db.set_session_start_balance(initial_equity)
        return {"status": "success", "message": "Gráfica/PnL Sesión reiniciados."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset/pnl/global")
def reset_global_pnl_api():
    try:
        db.clear_all_trades_history()
        return {"status": "success", "message": "Historial de PnL Global borrado."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/refresh_orders")
def refresh_orders_api():
    try:
        db.clear_orders_cache()
        return {"status": "success", "message": "Caché de órdenes limpiada."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset/coin/session")
def reset_coin_session_api(req: CoinResetRequest):
    try:
        db.set_coin_session_start(req.symbol, time.time())
        # Tambien reiniciamos el balance inicial de esta moneda para el PnL
        if bot_instance:
             try:
                base = req.symbol.split('/')[0]
                qty = bot_instance.connector.get_total_balance(base)
                price = bot_instance.connector.fetch_current_price(req.symbol)
                db.set_coin_initial_balance(req.symbol, qty * price)
             except: pass
        return {"status": "success", "message": f"Sesión reiniciada para {req.symbol}."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset/coin/global")
def reset_coin_global_api(req: CoinResetRequest):
    try:
        db.delete_trades_for_symbol(req.symbol)
        # También reiniciamos el saldo inicial para que el PnL global no quede "loco"
        if bot_instance:
             try:
                base = req.symbol.split('/')[0]
                qty = bot_instance.connector.get_total_balance(base)
                price = bot_instance.connector.fetch_current_price(req.symbol)
                db.set_coin_initial_balance(req.symbol, qty * price)
             except: pass
        return {"status": "success", "message": f"Historial Global borrado para {req.symbol}."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- ANÁLISIS TÉCNICO ---

@app.get("/api/strategy/analyze/")
def analyze_strategy(symbol: str, timeframe: str = '4h'):
    try:
        rsi = 50.0
        # Intentamos usar el bot para descargar velas
        if bot_instance and bot_instance.connector.exchange:
            try: 
                raw_candles = bot_instance.connector.fetch_candles(symbol, timeframe=timeframe, limit=500)
                if raw_candles: rsi = _calculate_rsi(raw_candles)
            except: pass
        
        # Sugerencias básicas
        base_s = {"conservative": 1.0, "moderate": 0.8, "aggressive": 0.5}
        if timeframe == '15m': base_s = {"conservative": 0.6, "moderate": 0.4, "aggressive": 0.25}
        elif timeframe == '1h': base_s = {"conservative": 0.8, "moderate": 0.6, "aggressive": 0.35}
        
        suggestions = {
            "rsi": rsi,
            "conservative": {"grids": 8, "spread": base_s["conservative"]},
            "moderate": {"grids": 10, "spread": base_s["moderate"]},
            "aggressive": {"grids": 12, "spread": base_s["aggressive"]}
        }
        
        if rsi < 35: 
            suggestions["conservative"]["grids"] += 2; suggestions["conservative"]["spread"] += 0.2
            suggestions["moderate"]["grids"] += 4; suggestions["aggressive"]["grids"] += 6; suggestions["aggressive"]["spread"] -= 0.1
        elif rsi > 65:
            suggestions["conservative"]["grids"] -= 3; suggestions["conservative"]["spread"] += 0.5 
            suggestions["moderate"]["grids"] -= 2; suggestions["moderate"]["spread"] += 0.2
            
        for k in suggestions:
            if k != "rsi": suggestions[k]["spread"] = round(suggestions[k]["spread"], 2)

        return suggestions
    except Exception:
        return {"rsi": 50, "conservative": {"grids": 8, "spread": 1.0}, "moderate": {"grids": 10, "spread": 0.8}, "aggressive": {"grids": 12, "spread": 0.5}}

@app.post("/api/close_order")
def close_order_api(req: CloseOrderRequest):
    if not bot_instance: raise HTTPException(status_code=503, detail="Bot no inicializado")
    success = bot_instance.manual_close_order(req.symbol, req.order_id, req.side, req.amount)
    if success: return {"status": "success", "message": "Orden cerrada."}
    else: raise HTTPException(status_code=400, detail="Error cerrando orden.")

@app.get("/api/details/{symbol:path}")
def get_pair_details(symbol: str, timeframe: str = '15m'):
    try:
        # OPTIMITZACIÓ: Llegim les dades (espelmes i ordres) de la DB primer
        # Així la web carrega instantàniament sense esperar l'API de Binance.
        data = db.get_pair_data(symbol)
        
        raw_candles = data.get('candles', [])
        # Si no hi ha dades guardades (bot apagat o nova moneda), només llavors demanem.
        if not raw_candles and bot_instance and bot_instance.is_running:
            try: raw_candles = bot_instance.connector.fetch_candles(symbol, timeframe=timeframe, limit=500)
            except: pass
        
        chart_data = []
        for candle in raw_candles:
            dt = datetime.fromtimestamp(candle[0]/1000).strftime('%Y-%m-%d %H:%M')
            chart_data.append([dt, candle[1], candle[4], candle[3], candle[2]])

        pnl_value = 0.0
        global_pnl = 0.0
        
        if bot_instance:
            current_price = data.get('price', 0.0)
            if current_price == 0 and bot_instance.is_running: 
                current_price = bot_instance.connector.fetch_current_price(symbol)

            if current_price > 0:
                global_stats = db.get_stats(from_timestamp=0)
                cf_global = global_stats['per_coin_stats']['cash_flow'].get(symbol, 0.0)
                base = symbol.split('/')[0]
                qty_held = 0.0
                try: qty_held = bot_instance.connector.get_total_balance(base)
                except: pass
                
                current_val = qty_held * current_price
                init_val = db.get_coin_initial_balance(symbol)
                
                if init_val == 0.0 and current_val > 0:
                    init_val = current_val
                    db.set_coin_initial_balance(symbol, init_val)

                global_pnl = (current_val - init_val) + cf_global
                
                # Sesión: Miramos si esta moneda tiene un inicio específico
                coin_session_ts = db.get_coin_session_start(symbol)
                if coin_session_ts == 0: coin_session_ts = bot_instance.global_start_time
                
                session_stats = db.get_stats(from_timestamp=coin_session_ts)
                cf_session = session_stats['per_coin_stats']['cash_flow'].get(symbol, 0.0)
                qty_delta = session_stats['per_coin_stats']['qty_delta'].get(symbol, 0.0)
                pnl_value = (qty_delta * current_price) + cf_session

        return {
            "symbol": symbol,
            "price": data.get('price', 0.0), # Preu directe DB
            "open_orders": data.get('open_orders', []), # Ordres directe DB
            "trades": data.get('trades', []),
            "chart_data": chart_data,
            "grid_lines": data.get('grid_levels', []),
            "session_pnl": round(pnl_value, 2), 
            "global_pnl": round(global_pnl, 2)   
        }
    except Exception as e:
        log.error(f"Error details {symbol}: {e}")
        return {"symbol": symbol, "price": 0, "open_orders": [], "trades": [], "chart_data": [], "grid_lines": [], "session_pnl": 0, "global_pnl": 0}

@app.get("/api/config")
def get_config():
    try:
        with open('config/config.json5', 'r') as f: content = f.read()
        return {"content": content}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
def save_config(config: ConfigUpdate):
    try:
        json5.loads(config.content)
        with open('config/config.json5', 'w') as f: f.write(config.content)
        if bot_instance:
            bot_instance.connector.check_and_reload_config()
            bot_instance.config = bot_instance.connector.config
            bot_instance._refresh_pairs_map()
        send_msg("💾 <b>CONFIGURACIÓN GUARDADA</b>\nSe han aplicado cambios desde la web.")
        return {"status": "success", "message": "Configuración guardada y aplicada."}
    except Exception as e: raise HTTPException(status_code=400, detail=f"Error JSON5: {e}")

# --- BOTONES DE PÁNICO ---

@app.post("/api/panic/stop")
def panic_stop_api():
    if bot_instance:
        bot_instance.panic_stop() 
        return {"status": "success", "message": "Bot PAUSADO."}
    return {"status": "error", "detail": "Bot no iniciado"}

@app.post("/api/panic/start")
def panic_start_api():
    if bot_instance:
        bot_instance.resume_bot()
        return {"status": "success", "message": "Bot REANUDADO."}
    return {"status": "error", "detail": "Bot no iniciado"}

@app.post("/api/panic/cancel_all")
def panic_cancel_all_api():
    if bot_instance:
        bot_instance.panic_cancel_all()
        return {"status": "success", "message": "Órdenes canceladas."}
    return {"status": "error", "detail": "Bot no iniciado"}

@app.post("/api/panic/sell_all")
def panic_sell_all_api():
    if bot_instance:
        bot_instance.panic_sell_all()
        return {"status": "success", "message": "Venta pánico ejecutada."}
    return {"status": "error", "detail": "Bot no iniciado"}

@app.post("/api/engine/on")
def engine_on_api():
    if bot_instance:
        if bot_instance.launch(): return {"status": "success", "message": "Motor de trading ARRANCADO."}
        else: return {"status": "warning", "message": "El motor ya está corriendo."}
    return {"status": "error", "detail": "Error interno"}

@app.post("/api/engine/off")
def engine_off_api():
    if bot_instance:
        bot_instance.stop_logic()
        return {"status": "success", "message": "Motor de trading APAGADO."}
    return {"status": "error", "detail": "Error interno"}