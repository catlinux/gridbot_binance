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

class ConfigUpdate(BaseModel): content: str

def start_server(bot, host="0.0.0.0", port=8000):
    global bot_instance
    bot_instance = bot
    uvicorn.run(app, host=host, port=port, log_level="error")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    # RESPOSTA PER DEFECTE SI ESTÀ OFF
    default_response = {
        "status": "Offline", "active_pairs": [], "balance_usdc": 0.0,
        "total_usdc_value": 0.0, "portfolio_distribution": [],
        "global": {"profit": 0.0, "trades": 0, "best_coin": "-"},
        "session": {"profit": 0.0, "trades": 0, "best_coin": "-"},
        "uptime": "--",
        "global_trades_distribution": [], "session_trades_distribution": []
    }

    if not bot_instance: return default_response
    
    # 1. PREUS I SALDO
    try: prices = db.get_all_prices()
    except: prices = {}
    
    portfolio = []
    total_val = 0.0
    try: usdc = bot_instance.connector.get_asset_balance('USDC') or 0.0
    except: usdc = 0.0
    
    portfolio.append({"name": "USDC", "value": round(usdc, 2)})
    total_val += usdc

    for symbol in bot_instance.active_pairs:
        base = symbol.split('/')[0]
        try:
            qty = bot_instance.connector.get_total_balance(base) or 0.0
            price = prices.get(symbol, 0.0)
            if price == 0: price = bot_instance.connector.fetch_current_price(symbol) or 0.0
            val = qty * price
            if val > 1:
                portfolio.append({"name": base, "value": round(val, 2)})
                total_val += val
        except: pass

    # 2. STATS GLOBALS
    try:
        db_stats = db.get_total_stats()
        global_dist = db.get_trades_breakdown() or []
    except:
        db_stats = {}
        global_dist = []

    g_profit = db_stats.get('total_profit') or 0.0
    g_trades = db_stats.get('total_trades') or 0
    g_coin = db_stats.get('best_coin') or "-"

    # 3. STATS SESSIÓ
    tot_trades = 0
    tot_profit = 0.0
    best_coin = "-"
    max_p = -999999.0
    session_dist = []

    if hasattr(bot_instance, 'session_stats'):
        for sym, stats in bot_instance.session_stats.items():
            t = stats.get('trades', 0)
            p = stats.get('profit', 0.0)
            tot_trades += t
            tot_profit += p
            if t > 0: session_dist.append({"name": sym, "value": t})
            if p > max_p and p != 0:
                max_p = p
                best_coin = sym
    
    if best_coin == "-": best_coin = "Cap"

    uptime_sec = int(time.time() - bot_instance.global_start_time)
    hours = uptime_sec // 3600
    mins = (uptime_sec % 3600) // 60
    
    return {
        "status": "Running" if bot_instance.is_running else "Stopped",
        "active_pairs": bot_instance.active_pairs,
        "balance_usdc": round(usdc, 2),
        "total_usdc_value": round(total_val, 2),
        "portfolio_distribution": portfolio,
        "global_trades_distribution": global_dist,
        "session_trades_distribution": session_dist,
        "global": { "profit": round(g_profit, 2), "trades": g_trades, "best_coin": g_coin },
        "session": { "profit": round(tot_profit, 2), "trades": tot_trades, "best_coin": best_coin },
        "uptime": f"{hours}h {mins}m"
    }

@app.get("/api/details/{symbol:path}")
async def get_pair_details(symbol: str, timeframe: str = '15m'):
    try: data = db.get_pair_data(symbol)
    except: return {}
    
    raw_candles = []
    if bot_instance:
        try: raw_candles = bot_instance.connector.fetch_candles(symbol, timeframe=timeframe, limit=100)
        except: pass
    if not raw_candles and data.get('candles'): raw_candles = data['candles']

    chart_data = []
    if raw_candles:
        for candle in raw_candles:
            try:
                dt = datetime.fromtimestamp(candle[0]/1000).strftime('%Y-%m-%d %H:%M')
                chart_data.append([dt, candle[1], candle[4], candle[3], candle[2]])
            except: pass

    return {
        "symbol": symbol,
        "price": data.get('price', 0.0),
        "open_orders": data.get('open_orders', []),
        "trades": data.get('trades', []),
        "chart_data": chart_data,
        "grid_lines": data.get('grid_levels', [])
    }

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
        return {"status": "success", "message": "Configuració guardada."}
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))