# Arxiu: gridbot_binance/web/server.py
from fastapi import FastAPI, Request, HTTPException
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
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

db = BotDatabase()
bot_instance = None 

# Model de dades per rebre la nova config
class ConfigUpdate(BaseModel):
    content: str

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

# --- API ESTAT (DASHBOARD) ---
@app.get("/api/status")
async def get_status():
    if not bot_instance: return {"status": "Offline"}
    
    # 1. Dades de Cartera (RAM en temps real)
    prices = db.get_all_prices()
    portfolio = []
    total_val = 0.0
    
    try:
        usdc = bot_instance.connector.get_asset_balance('USDC')
    except: usdc = 0.0
    portfolio.append({"name": "USDC", "value": round(usdc, 2)})
    total_val += usdc

    for symbol in bot_instance.active_pairs:
        base = symbol.split('/')[0]
        try:
            qty = bot_instance.connector.get_total_balance(base)
            price = prices.get(symbol, 0.0)
            if price == 0: price = bot_instance.connector.fetch_current_price(symbol)
            val = qty * price
            if val > 1:
                portfolio.append({"name": base, "value": round(val, 2)})
                total_val += val
        except: pass

    # 2. Consultes a DB
    
    # A. GLOBAL (Des de l'inici dels temps = 0)
    global_stats = db.get_stats(from_timestamp=0)
    
    first_run_ts = db.get_first_run_timestamp()
    total_uptime_str = format_uptime(time.time() - first_run_ts)

    # B. SESSIÓ (Des de l'arrencada actual)
    session_start = bot_instance.global_start_time
    session_stats = db.get_stats(from_timestamp=session_start)
    
    session_uptime_str = format_uptime(time.time() - session_start)

    return {
        "status": "Running" if bot_instance.is_running else "Stopped",
        "active_pairs": bot_instance.active_pairs,
        "balance_usdc": round(usdc, 2),
        "total_usdc_value": round(total_val, 2),
        "portfolio_distribution": portfolio,
        
        "session_trades_distribution": session_stats['trades_distribution'],
        "global_trades_distribution": global_stats['trades_distribution'],
        
        "stats": {
            "session": {
                "trades": session_stats['trades'],
                "profit": round(session_stats['profit'], 4),
                "best_coin": session_stats['best_coin'],
                "uptime": session_uptime_str
            },
            "global": {
                "trades": global_stats['trades'],
                "profit": round(global_stats['profit'], 2),
                "best_coin": global_stats['best_coin'],
                "uptime": total_uptime_str
            }
        }
    }

# --- API DETALLS ---
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

# --- API CONFIGURACIÓ ---
@app.get("/api/config")
async def get_config():
    try:
        config_path = 'config/config.json5'
        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="Arxiu no trobat")
            
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
        return {"status": "success", "message": "Configuració guardada correctament."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error de sintaxi JSON5: {e}")