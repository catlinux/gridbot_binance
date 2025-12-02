# Arxiu: gridbot_binance/web/server.py
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
import os
import time
from datetime import datetime
from core.database import BotDatabase 

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

db = BotDatabase()
bot_instance = None 

def start_server(bot, host="0.0.0.0", port=8000):
    global bot_instance
    bot_instance = bot
    uvicorn.run(app, host=host, port=port, log_level="error")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    if not bot_instance: return {"status": "Offline"}
    
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

    tot_trades = 0
    tot_profit = 0.0
    best_coin = "-"
    max_p = -999999.0

    if hasattr(bot_instance, 'session_stats'):
        for sym, stats in bot_instance.session_stats.items():
            tot_trades += stats['trades']
            tot_profit += stats['profit']
            if stats['profit'] > max_p and stats['profit'] > 0:
                max_p = stats['profit']
                best_coin = sym
    
    if best_coin == "-": best_coin = "Cap"

    uptime_sec = int(time.time() - bot_instance.global_start_time)
    
    return {
        "status": "Running" if bot_instance.is_running else "Stopped",
        "active_pairs": bot_instance.active_pairs,
        "balance_usdc": round(usdc, 2),
        "total_usdc_value": round(total_val, 2),
        "portfolio_distribution": portfolio,
        "session_trades": tot_trades,
        "session_profit": round(tot_profit, 4),
        "top_coin": best_coin,
        "uptime": f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m"
    }

# --- MODIFICAT PER ACCEPTAR TIMEFRAME ---
@app.get("/api/details/{symbol:path}")
async def get_pair_details(symbol: str, timeframe: str = '15m'):
    # Dades generals des de la DB (ràpid)
    data = db.get_pair_data(symbol)
    
    # Gràfic: El demanem DIRECTAMENT a Binance via el connector del bot
    # per tenir la temporalitat exacta que vol l'usuari al moment.
    raw_candles = []
    if bot_instance:
        try:
            # Demanem 100 espelmes del timeframe sol·licitat
            raw_candles = bot_instance.connector.fetch_candles(symbol, timeframe=timeframe, limit=100)
        except Exception as e:
            print(f"Error fetching candles live: {e}")
            # Si falla, intentem usar les de la DB com a backup (si coincideixen)
            if data['candles']: raw_candles = data['candles']
    else:
        # Mode offline: usem DB
        raw_candles = data['candles']

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