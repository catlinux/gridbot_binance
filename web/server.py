# Arxiu: gridbot_binance/web/server.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles 
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import os
import time
import json5 
from datetime import datetime
from core.database import BotDatabase 
from utils.telegram import send_msg
from utils.logger import log
from dotenv import load_dotenv 

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

static_dir = os.path.join(BASE_DIR, "static")
if not os.path.exists(static_dir):
    os.makedirs(os.path.join(static_dir, "css"), exist_ok=True)
    os.makedirs(os.path.join(static_dir, "js"), exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

db = BotDatabase()
bot_instance = None 

class ConfigUpdate(BaseModel):
    content: str

class CloseOrderRequest(BaseModel):
    symbol: str
    order_id: str
    side: str
    amount: float

class LiquidateRequest(BaseModel):
    asset: str

# --- FUNCIÓ D'INICI DEL SERVIDOR ---
def start_server(bot, host=None, port=None):
    global bot_instance
    bot_instance = bot
    
    load_dotenv('config/.env', override=True)
    
    if host is None:
        host = os.getenv('WEB_HOST', '127.0.0.1') 
    
    if port is None:
        port = int(os.getenv('WEB_PORT', 8000))
        
    uvicorn.run(app, host=host, port=port, log_level="error")
# -----------------------------------

def format_uptime(seconds):
    if seconds < 0: return "0s"
    seconds = int(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    if days > 0: return f"{days}d {hours}h {mins}m"
    return f"{hours}h {mins}m"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    if not bot_instance: return {"status": "Offline"}
    
    try:
        status_text = "Stopped"
        if bot_instance.is_running:
            status_text = "Paused" if bot_instance.is_paused else "Running"

        prices = db.get_all_prices()
        portfolio = []
        current_total_equity = 0.0
        
        try:
            usdc_balance = bot_instance.connector.get_total_balance('USDC')
        except: usdc_balance = 0.0
        
        portfolio.append({"name": "USDC", "value": round(usdc_balance, 2)})
        current_total_equity += usdc_balance

        holding_values = {}
        current_prices_map = {}

        pairs_to_check = bot_instance.active_pairs if bot_instance.active_pairs else []
        
        for symbol in pairs_to_check:
            base = symbol.split('/')[0]
            try:
                qty = bot_instance.connector.get_total_balance(base)
                price = prices.get(symbol, 0.0)
                
                if price == 0 and bot_instance.is_running: 
                    price = bot_instance.connector.fetch_current_price(symbol)
                
                if price > 0:
                    current_prices_map[symbol] = price 
                    val = qty * price
                    holding_values[symbol] = val 
                    if val > 0.5: 
                        portfolio.append({"name": base, "value": round(val, 2)})
                        current_total_equity += val
            except: pass

        # --- CÀLCUL DE PNL ---
        global_start = db.get_global_start_balance()
        if global_start == 0: global_start = current_total_equity
        global_pnl_total = current_total_equity - global_start

        session_start_equity = db.get_session_start_balance()
        if session_start_equity == 0: session_start_equity = current_total_equity
        session_pnl_total = current_total_equity - session_start_equity

        global_stats = db.get_stats(from_timestamp=0)
        session_start_ts = bot_instance.global_start_time
        session_stats = db.get_stats(from_timestamp=session_start_ts)

        if bot_instance.is_running:
            session_uptime_str = format_uptime(time.time() - session_start_ts)
        else:
            session_uptime_str = "OFF"

        first_run_ts = db.get_first_run_timestamp()
        total_uptime_str = format_uptime(time.time() - first_run_ts)

        strategies_data = []
        global_cash_flow = global_stats['per_coin_stats']['cash_flow']
        session_cash_flow = session_stats['per_coin_stats']['cash_flow']
        global_trades_map = global_stats['per_coin_stats']['trades']

        for symbol in pairs_to_check:
            try:
                strat_conf = bot_instance.pairs_map.get(symbol, {}).get('strategy', {})
                trades_count = global_trades_map.get(symbol, 0)
                curr_price = current_prices_map.get(symbol, 0.0)
                curr_val = holding_values.get(symbol, 0.0)
                
                init_val_coin = db.get_coin_initial_balance(symbol)
                
                if init_val_coin == 0.0 and curr_val > 0:
                    init_val_coin = curr_val
                    db.set_coin_initial_balance(symbol, init_val_coin)

                cf_global = global_cash_flow.get(symbol, 0.0)
                strat_pnl_global = (curr_val - init_val_coin) + cf_global

                cf_session = session_cash_flow.get(symbol, 0.0)
                qty_delta = session_stats['per_coin_stats']['qty_delta'].get(symbol, 0.0)
                strat_pnl_session = (qty_delta * curr_price) + cf_session

                if trades_count == 0 and abs(strat_pnl_global) > (curr_val * 0.5) and curr_val > 0:
                     strat_pnl_global = 0.0

                strategies_data.append({
                    "symbol": symbol,
                    "grids": strat_conf.get('grids_quantity', '-'),
                    "amount": strat_conf.get('amount_per_grid', '-'),
                    "spread": strat_conf.get('grid_spread', '-'),
                    "total_trades": trades_count,
                    "total_pnl": round(strat_pnl_global, 2),  
                    "session_pnl": round(strat_pnl_session, 2)
                })
            except Exception as e:
                log.error(f"Error procesando stats {symbol}: {e}")

        return {
            "status": status_text,
            "active_pairs": pairs_to_check,
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
async def get_balance_history_api():
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
async def get_all_orders():
    try:
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
async def get_wallet_data():
    if not bot_instance or not bot_instance.connector.exchange:
        return []
    
    try:
        # Obtenim balanç complet (total, free, used)
        balances = bot_instance.connector.exchange.fetch_balance()
        if not balances: return []
        
        # Obtenim preus actuals de tot el mercat (més eficient que un per un)
        tickers = bot_instance.connector.exchange.fetch_tickers()
        
        wallet_list = []
        
        # Iterem sobre els actius que tenim (ignorant els que son 0)
        items = balances.get('total', {}).items()
        
        for asset, total_qty in items:
            if total_qty <= 0: continue
            
            usdc_value = 0.0
            price = 0.0
            
            if asset == 'USDC':
                usdc_value = total_qty
                price = 1.0
            elif asset == 'USDT':
                # Cas especial stablecoin
                usdc_value = total_qty
                price = 1.0
            else:
                # Busquem parell amb USDC
                symbol = f"{asset}/USDC"
                if symbol in tickers:
                    price = float(tickers[symbol]['last'])
                    usdc_value = total_qty * price
            
            # FILTRE: Només mostrem si val més d'1 USDC
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
        
        # Ordenem per valor de major a menor
        wallet_list.sort(key=lambda x: x['usdc_value'], reverse=True)
        return wallet_list
        
    except Exception as e:
        log.error(f"Error fetching wallet: {e}")
        return []

@app.post("/api/liquidate_asset")
async def liquidate_asset_api(req: LiquidateRequest):
    if not bot_instance or not bot_instance.connector.exchange:
        raise HTTPException(status_code=503, detail="Bot no conectado")
    
    asset = req.asset.upper()
    if asset == 'USDC':
        return {"status": "error", "message": "No se puede liquidar USDC."}
        
    symbol = f"{asset}/USDC"
    
    try:
        # 1. Cancel·lar ordres existents per alliberar saldo
        log.warning(f"LIQUIDACIÓN MANUAL: Cancelando órdenes de {symbol}...")
        bot_instance.connector.cancel_all_orders(symbol)
        time.sleep(1) # Esperem que l'exchange processi
        
        # 2. Obtenir saldo total disponible ara
        total_balance = bot_instance.connector.get_total_balance(asset)
        
        # 3. Vendre a mercat
        if total_balance > 0:
            log.warning(f"LIQUIDACIÓN MANUAL: Vendiendo {total_balance} {asset} a mercado...")
            # Usem place_market_sell que ja tens a exchange.py
            # Nota: Potser caldrà ajustar la precisió, ho fa exchange.py?
            # exchange.py: place_market_sell fa create_order('market', 'sell')
            
            # Assegurem precisió mínima
            # Per seguretat, fem la venda a través del connector
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

@app.post("/api/close_order")
async def close_order_api(req: CloseOrderRequest):
    if not bot_instance: raise HTTPException(status_code=503, detail="Bot no inicializado")
    success = bot_instance.manual_close_order(req.symbol, req.order_id, req.side, req.amount)
    if success: return {"status": "success", "message": "Orden cerrada."}
    else: raise HTTPException(status_code=400, detail="Error cerrando orden.")

@app.get("/api/details/{symbol:path}")
async def get_pair_details(symbol: str, timeframe: str = '15m'):
    try:
        data = db.get_pair_data(symbol)
        raw_candles = []
        if bot_instance and bot_instance.is_running:
            try: raw_candles = bot_instance.connector.fetch_candles(symbol, timeframe=timeframe, limit=100)
            except: pass
        if not raw_candles: raw_candles = data['candles']
        
        chart_data = []
        for candle in raw_candles:
            dt = datetime.fromtimestamp(candle[0]/1000).strftime('%Y-%m-%d %H:%M')
            chart_data.append([dt, candle[1], candle[4], candle[3], candle[2]])

        pnl_value = 0.0
        global_pnl = 0.0
        
        if bot_instance:
            current_price = data['price']
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
                
                session_start_ts = bot_instance.global_start_time
                session_stats = db.get_stats(from_timestamp=session_start_ts)
                cf_session = session_stats['per_coin_stats']['cash_flow'].get(symbol, 0.0)
                qty_delta = session_stats['per_coin_stats']['qty_delta'].get(symbol, 0.0)
                pnl_value = (qty_delta * current_price) + cf_session

        return {
            "symbol": symbol,
            "price": data['price'],
            "open_orders": data['open_orders'],
            "trades": data['trades'],
            "chart_data": chart_data,
            "grid_lines": data['grid_levels'],
            "session_pnl": round(pnl_value, 2), 
            "global_pnl": round(global_pnl, 2)   
        }
    except Exception as e:
        log.error(f"Error details {symbol}: {e}")
        return {"symbol": symbol, "price": 0, "open_orders": [], "trades": [], "chart_data": [], "grid_lines": [], "session_pnl": 0, "global_pnl": 0}

@app.get("/api/config")
async def get_config():
    try:
        with open('config/config.json5', 'r') as f: content = f.read()
        return {"content": content}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def save_config(config: ConfigUpdate):
    try:
        json5.loads(config.content)
        with open('config/config.json5', 'w') as f: f.write(config.content)
        
        # Forcem actualització immediata al bot
        if bot_instance:
            bot_instance.connector.check_and_reload_config()
            bot_instance.config = bot_instance.connector.config
            bot_instance._refresh_pairs_map()

        send_msg("💾 <b>CONFIGURACIÓN GUARDADA</b>\nSe han aplicado cambios desde la web.")
            
        return {"status": "success", "message": "Configuración guardada y aplicada."}
    except Exception as e: raise HTTPException(status_code=400, detail=f"Error JSON5: {e}")

@app.post("/api/reset_stats")
async def reset_stats_api():
    try:
        db.reset_all_statistics()
        if bot_instance:
            bot_instance.global_start_time = time.time()
            if bot_instance.is_running:
                bot_instance.capture_initial_snapshots()
        
        send_msg("⚠️ <b>RESET DE ESTADÍSTICAS</b>\nSe han borrado los datos históricos y reiniciado el PnL.")

        return {"status": "success", "message": "Estadísticas reiniciadas."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/panic/stop")
async def panic_stop_api():
    if bot_instance:
        bot_instance.panic_stop() 
        return {"status": "success", "message": "Bot PAUSADO."}
    return {"status": "error", "detail": "Bot no iniciado"}

@app.post("/api/panic/start")
async def panic_start_api():
    if bot_instance:
        bot_instance.resume_bot()
        return {"status": "success", "message": "Bot REANUDADO."}
    return {"status": "error", "detail": "Bot no iniciado"}

@app.post("/api/panic/cancel_all")
async def panic_cancel_all_api():
    if bot_instance:
        bot_instance.panic_cancel_all()
        return {"status": "success", "message": "Órdenes canceladas."}
    return {"status": "error", "detail": "Bot no iniciado"}

@app.post("/api/panic/sell_all")
async def panic_sell_all_api():
    if bot_instance:
        bot_instance.panic_sell_all()
        return {"status": "success", "message": "Venta pánico ejecutada."}
    return {"status": "error", "detail": "Bot no iniciado"}

@app.post("/api/engine/on")
async def engine_on_api():
    if bot_instance:
        if bot_instance.launch():
            return {"status": "success", "message": "Motor de trading ARRANCADO."}
        else:
            return {"status": "warning", "message": "El motor ya está corriendo."}
    return {"status": "error", "detail": "Error interno"}

@app.post("/api/engine/off")
async def engine_off_api():
    if bot_instance:
        bot_instance.stop_logic()
        return {"status": "success", "message": "Motor de trading APAGADO."}
    return {"status": "error", "detail": "Error interno"}
