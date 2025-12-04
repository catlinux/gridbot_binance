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

def start_server(bot, host="0.0.0.0", port=8000):
    global bot_instance
    bot_instance = bot
    uvicorn.run(app, host=host, port=port, log_level="error")

def format_uptime(seconds):
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
    
    prices = db.get_all_prices()
    portfolio = []
    current_total_equity = 0.0
    
    # 1. Obtenir USDC total
    try:
        usdc_balance = bot_instance.connector.get_total_balance('USDC')
    except: usdc_balance = 0.0
    
    portfolio.append({"name": "USDC", "value": round(usdc_balance, 2)})
    current_total_equity += usdc_balance

    holding_values = {}
    current_prices_map = {}

    # 2. Obtenir Valor Crypto
    for symbol in bot_instance.active_pairs:
        base = symbol.split('/')[0]
        try:
            qty = bot_instance.connector.get_total_balance(base)
            price = prices.get(symbol, 0.0)
            if price == 0: price = bot_instance.connector.fetch_current_price(symbol)
            
            current_prices_map[symbol] = price 
            
            val = qty * price
            holding_values[symbol] = val 
            
            if val > 0.5: 
                portfolio.append({"name": base, "value": round(val, 2)})
                current_total_equity += val
        except: pass

    # --- PnL GLOBAL (Es manté per Equity real) ---
    global_start = db.get_global_start_balance()
    if global_start == 0: global_start = current_total_equity
    global_pnl_total = current_total_equity - global_start
    # ---------------------------------------------

    # Obtenir estadístiques detallades
    global_stats = db.get_stats(from_timestamp=0)
    global_cash_flow = global_stats['per_coin_stats']['cash_flow']
    global_trades_map = global_stats['per_coin_stats']['trades']
    
    session_start_ts = bot_instance.global_start_time
    session_stats = db.get_stats(from_timestamp=session_start_ts)
    session_cash_flow = session_stats['per_coin_stats']['cash_flow']
    session_qty_delta = session_stats['per_coin_stats']['qty_delta']

    first_run_ts = db.get_first_run_timestamp()
    total_uptime_str = format_uptime(time.time() - first_run_ts)
    session_uptime_str = format_uptime(time.time() - session_start_ts)

    # Preparar dades per la taula d'Estratègies
    strategies_data = []
    
    # Variable per acumular el PnL de sessió exacte de la taula
    accumulated_session_pnl = 0.0

    for symbol in bot_instance.active_pairs:
        strat_conf = bot_instance.pairs_map.get(symbol, {}).get('strategy', {})
        trades_count = global_trades_map.get(symbol, 0)
        curr_price = current_prices_map.get(symbol, 0.0)
        
        # 1. PnL Global (Aprox)
        cf_global = global_cash_flow.get(symbol, 0.0)
        curr_val = holding_values.get(symbol, 0.0)
        strat_pnl_global = curr_val + cf_global
        
        # 2. PnL Sessió (Calculat amb Delta d'Inventari)
        cf_session = session_cash_flow.get(symbol, 0.0)
        qty_change = session_qty_delta.get(symbol, 0.0)
        
        inventory_value_change = qty_change * curr_price
        strat_pnl_session = inventory_value_change + cf_session
        
        # Sumem al total acumulat
        accumulated_session_pnl += strat_pnl_session

        strategies_data.append({
            "symbol": symbol,
            "grids": strat_conf.get('grids_quantity', '-'),
            "amount": strat_conf.get('amount_per_grid', '-'),
            "spread": strat_conf.get('grid_spread', '-'),
            "total_trades": trades_count,
            "total_pnl": round(strat_pnl_global, 2),  
            "session_pnl": round(strat_pnl_session, 2)
        })

    return {
        "status": "Running" if bot_instance.is_running else "Stopped",
        "active_pairs": bot_instance.active_pairs,
        "balance_usdc": round(usdc_balance, 2),
        "total_usdc_value": round(current_total_equity, 2),
        "portfolio_distribution": portfolio,
        "session_trades_distribution": session_stats['trades_distribution'],
        "global_trades_distribution": global_stats['trades_distribution'],
        "strategies": strategies_data,
        "stats": {
            "session": {
                "trades": session_stats['trades'],
                "profit": round(accumulated_session_pnl, 2), # ARA SÍ: Suma exacta de les estratègies
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

@app.get("/api/orders")
async def get_all_orders():
    raw_orders = db.get_all_active_orders()
    prices = db.get_all_prices()
    enhanced_orders = []
    
    for o in raw_orders:
        symbol = o['symbol']
        current_price = prices.get(symbol, 0.0)
        if current_price == 0 and bot_instance:
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

@app.post("/api/close_order")
async def close_order_api(req: CloseOrderRequest):
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot no iniciado")
    
    success = bot_instance.manual_close_order(req.symbol, req.order_id, req.side, req.amount)
    if success:
        return {"status": "success", "message": "Orden cerrada y convertida a USDC correctamente."}
    else:
        raise HTTPException(status_code=400, detail="Error cerrando la orden.")

@app.get("/api/details/{symbol:path}")
async def get_pair_details(symbol: str, timeframe: str = '15m'):
    data = db.get_pair_data(symbol)
    raw_candles = []
    if bot_instance:
        try:
            raw_candles = bot_instance.connector.fetch_candles(symbol, timeframe=timeframe, limit=100)
        except: pass
    if not raw_candles: raw_candles = data['candles']
    chart_data = []
    for candle in raw_candles:
        dt = datetime.fromtimestamp(candle[0]/1000).strftime('%Y-%m-%d %H:%M')
        chart_data.append([dt, candle[1], candle[4], candle[3], candle[2]])
    return {
        "symbol": symbol,
        "price": data['price'],
        "open_orders": data['open_orders'],
        "trades": data['trades'],
        "chart_data": chart_data,
        "grid_lines": data['grid_levels']
    }

@app.get("/api/config")
async def get_config():
    try:
        config_path = 'config/config.json5'
        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        with open(config_path, 'r') as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def save_config(config: ConfigUpdate):
    try:
        json5.loads(config.content)
        with open('config/config.json5', 'w') as f:
            f.write(config.content)
        return {"status": "success", "message": "Configuración guardada correctamente."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error de sintaxis JSON5: {e}")

@app.post("/api/reset_stats")
async def reset_stats_api():
    try:
        db.reset_all_statistics()
        if bot_instance:
            bot_instance.global_start_time = time.time()
            current_equity = bot_instance.calculate_total_equity()
            db.set_session_start_balance(current_equity)
            db.set_global_start_balance_if_not_exists(current_equity)
            
        return {"status": "success", "message": "Estadísticas reiniciadas correctamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))