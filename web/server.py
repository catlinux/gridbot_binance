# Arxiu: gridbot_binance/web/server.py
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
import os
import pandas as pd
from datetime import datetime

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

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
    """
    Retorna l'estat global i la distribució de la cartera.
    """
    if not bot_instance: return {"status": "Offline"}
    
    portfolio = []
    total_value_usdc = 0.0

    # 1. Saldo USDC (Base)
    usdc_bal = bot_instance.connector.get_asset_balance('USDC')
    # Afegeix el bloquejat en ordres de compra (opcional, per ser precisos agafem 'total')
    try:
        full_balance = bot_instance.connector.exchange.fetch_balance()
        usdc_total = full_balance.get('USDC', {}).get('total', 0.0)
    except:
        usdc_total = usdc_bal

    portfolio.append({"name": "USDC", "value": round(usdc_total, 2)})
    total_value_usdc += usdc_total

    # 2. Calcular valor de cada moneda activa en USDC
    for symbol in bot_instance.active_pairs:
        base_asset = symbol.split('/')[0] # BTC, XRP...
        
        try:
            # Saldo total (lliure + bloquejat en vendes)
            asset_qty = full_balance.get(base_asset, {}).get('total', 0.0)
            
            # Preu actual
            current_price = bot_instance.connector.fetch_current_price(symbol)
            
            # Valor en USDC
            value_in_usdc = asset_qty * current_price
            
            if value_in_usdc > 1.0: # Només mostrem si val més d'1$
                portfolio.append({"name": base_asset, "value": round(value_in_usdc, 2)})
                total_value_usdc += value_in_usdc
                
        except Exception as e:
            print(f"Error calculant portfolio {symbol}: {e}")

    return {
        "status": "Running" if bot_instance.is_running else "Stopped",
        "active_pairs": bot_instance.active_pairs,
        "total_usdc_value": round(total_value_usdc, 2),
        "portfolio_distribution": portfolio
    }

@app.get("/api/details/{symbol:path}")
async def get_pair_details(symbol: str):
    if not bot_instance: return {}
    
    # Dades bàsiques
    current_price = bot_instance.connector.fetch_current_price(symbol)
    open_orders = bot_instance.connector.fetch_open_orders(symbol)
    
    # Històric
    trades = bot_instance.connector.fetch_my_trades(symbol, limit=20)
    if trades: trades.sort(key=lambda x: x['timestamp'], reverse=True)

    # Gràfic
    ohlcv = bot_instance.connector.fetch_candles(symbol, timeframe='5m', limit=100)
    chart_data = []
    for candle in ohlcv:
        dt = datetime.fromtimestamp(candle[0]/1000).strftime('%Y-%m-%d %H:%M')
        chart_data.append([dt, candle[1], candle[4], candle[3], candle[2]])

    # Estadístiques Addicionals (Línies Grid)
    # Recuperem les línies fixes per pintar-les o mostrar-les
    grid_lines = bot_instance.levels.get(symbol, [])

    return {
        "symbol": symbol,
        "price": current_price,
        "open_orders": open_orders,
        "trades": trades,
        "chart_data": chart_data,
        "grid_lines": grid_lines
    }