// Arxiu: gridbot_binance/web/static/js/dashboard.js
import { fmtUSDC, fmtPrice, fmtInt, fmtCrypto, fmtPct, updateColorValue } from './utils.js';
import { renderDonut, renderLineChart, renderCandleChart, resetChartZoom, destroyChart } from './charts.js';
import { loadConfigForm, saveConfigForm, toggleCard, changeRsiTf, applyStrategy, setManual, analyzeSymbol } from './config.js';

// --- ESTAT GLOBAL ---
let currentMode = 'home';
let currentTimeframe = '15m';
let currentChartType = 'candles'; 
let dataCache = {}; 
let fullGlobalHistory = []; 

// --- EXPORTAR A WINDOW ---
window.loadConfigForm = loadConfigForm;
window.saveConfigForm = saveConfigForm;
window.toggleCard = toggleCard;
window.changeRsiTf = changeRsiTf;
window.applyStrategy = applyStrategy;
window.setManual = setManual;
window.setMode = setMode;
window.setTimeframe = setTimeframe;
window.setChartType = setChartType;
window.resetZoom = resetZoom; 
window.loadWallet = loadWallet;
window.resetStatistics = resetStatistics;
window.panicStop = panicStop;
window.panicStart = panicStart;
window.panicCancel = panicCancel;
window.panicSell = panicSell;
window.startEngine = startEngine;
window.stopEngine = stopEngine;
window.clearHistory = clearHistory;
window.closeOrder = closeOrder;
window.filterHistory = filterHistory; 
window.liquidateAsset = liquidateAsset;
window.resetGlobalChart = resetGlobalChart;
window.resetSessionChart = resetSessionChart;
window.resetGlobalPnL = resetGlobalPnL;
window.refreshOrders = refreshOrders;
window.resetCoinSession = resetCoinSession;
window.resetCoinGlobal = resetCoinGlobal;
window.changeTheme = changeTheme;

// --- FUNCIONS PRINCIPALS ---

async function init() {
    try {
        const savedTheme = localStorage.getItem('gridbot_theme') || 'light';
        changeTheme(savedTheme, false);

        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        if (data.active_pairs) syncTabs(data.active_pairs);
        loadHome();
    } catch (e) { console.error("Error init:", e); }
}

function syncTabs(activePairs) {
    if (!activePairs) return;
    const tabList = document.getElementById('mainTabs');
    const safeSymbols = activePairs.map(s => s.replace('/', '_'));
    const existingTabs = Array.from(tabList.querySelectorAll('li.nav-item button.nav-link'));
    existingTabs.forEach(btn => {
        const targetId = btn.getAttribute('data-bs-target').replace('#content-', '');
        if (!['home', 'config', 'wallet'].includes(targetId) && !safeSymbols.includes(targetId)) {
            btn.parentElement.remove();
            const contentDiv = document.getElementById(`content-${targetId}`);
            if (contentDiv) contentDiv.remove();
        }
    });
    activePairs.forEach(sym => ensureTabExists(sym));
}

// --- MODIFICACIÓ: ICONES DE MONEDES ---
function ensureTabExists(symbol) {
    const safe = symbol.replace('/', '_');
    if (document.getElementById(`content-${safe}`)) return;
    
    // 1. Extraiem el nom base (ex: "BTC" de "BTC/USDC") i el passem a minúscules
    const baseCoin = symbol.split('/')[0].toLowerCase();
    // 2. URL del CDN d'icones (utilitzem Cryptologos via jsDelivr)
    const iconUrl = `https://cdn.jsdelivr.net/gh/atomiclabs/cryptocurrency-icons@1a63530be6e374711a8554f31b17e4cb92c25fa5/128/color/${baseCoin}.png`;

    const tabList = document.getElementById('mainTabs');
    
    const li = document.createElement('li');
    li.className = 'nav-item';
    
    // 3. Creem el botó amb la imatge. Si falla la imatge (onerror), posem una icona genèrica.
    li.innerHTML = `
        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#content-${safe}" type="button" onclick="setMode('${symbol}')">
            <img src="${iconUrl}" class="coin-icon" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline-block'">
            <i class="fa-brands fa-bitcoin coin-fallback" style="display:none"></i>
            <span>${symbol}</span>
        </button>`;
    
    tabList.appendChild(li);

    const btnCandlesActive = currentChartType === 'candles' ? 'active' : '';
    const btnLineActive = currentChartType === 'line' ? 'active' : '';

    const div = document.createElement('div');
    div.className = 'tab-pane fade';
    div.id = `content-${safe}`;
    div.innerHTML = `
        <div class="row">
            <div class="col-lg-8 mb-3">
                <div class="card h-100">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center">
                            <span class="d-none d-sm-inline me-2">Gráfico</span>
                            <div class="btn-group me-2 tf-controls">
                                <button class="btn btn-outline-secondary btn-sm tf-btn" onclick="setTimeframe('1m')">1m</button>
                                <button class="btn btn-outline-secondary btn-sm tf-btn" onclick="setTimeframe('5m')">5m</button>
                                <button class="btn btn-outline-secondary btn-sm tf-btn active" onclick="setTimeframe('15m')">15m</button>
                                <button class="btn btn-outline-secondary btn-sm tf-btn" onclick="setTimeframe('1h')">1h</button>
                                <button class="btn btn-outline-secondary btn-sm tf-btn" onclick="setTimeframe('4h')">4h</button>
                            </div>
                            <div class="btn-group">
                                <button class="btn btn-outline-secondary btn-sm ${btnCandlesActive}" data-chart-type="candles" onclick="setChartType('candles')" title="Velas"><i class="fa-solid fa-chart-simple"></i></button>
                                <button class="btn btn-outline-secondary btn-sm ${btnLineActive}" data-chart-type="line" onclick="setChartType('line')" title="Línea"><i class="fa-solid fa-chart-line"></i></button>
                            </div>
                            <button class="btn btn-outline-secondary btn-sm ms-2" onclick="resetZoom('${symbol}')" title="Reset Zoom"><i class="fa-solid fa-compress"></i></button>
                        </div>
                        <div class="d-flex align-items-center">
                            <div class="btn-group btn-group-sm me-3">
                                <button class="btn btn-outline-danger" onclick="resetCoinSession('${symbol}')" title="Reset Sesión">Rst. Sesión</button>
                                <button class="btn btn-outline-danger" onclick="resetCoinGlobal('${symbol}')" title="Reset Global">Rst. Global</button>
                            </div>
                            <span class="fs-5 fw-bold text-primary" id="price-${safe}">--</span>
                        </div>
                    </div>
                    <div class="card-body p-1"><div id="chart-${safe}" class="chart-container"></div></div>
                </div>
            </div>
            <div class="col-lg-4 mb-3">
                <div class="card h-100">
                    <div class="card-header">Estado Grid</div>
                    <div class="card-body">
                        <div class="row g-2 text-center mb-4">
                            <div class="col-6"><div class="bg-buy p-3 rounded"><small class="d-block fw-bold mb-1">COMPRAS</small><b class="fs-3" id="count-buy-${safe}">0</b></div></div>
                            <div class="col-6"><div class="bg-sell p-3 rounded"><small class="d-block fw-bold mb-1">VENTAS</small><b class="fs-3" id="count-sell-${safe}">0</b></div></div>
                        </div>
                        <ul class="list-group list-group-flush">
                            <li class="list-group-item d-flex justify-content-between align-items-center mt-3 bg-light">
                                <strong>Balance Sesión</strong>
                                <div class="d-flex align-items-center gap-2">
                                    <b id="sess-pnl-${safe}">--</b>
                                    <button class="btn btn-xs btn-outline-danger" onclick="resetCoinSession('${symbol}')"><i class="fa-solid fa-rotate-right"></i></button>
                                </div>
                            </li>
                            <li class="list-group-item d-flex justify-content-between align-items-center bg-light">
                                <strong>Balance Global</strong>
                                <div class="d-flex align-items-center gap-2">
                                    <b id="glob-pnl-${safe}">--</b>
                                    <button class="btn btn-xs btn-outline-danger" onclick="resetCoinGlobal('${symbol}')"><i class="fa-solid fa-trash-can"></i></button>
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-md-6 mb-3"><div class="card h-100"><div class="card-header">Órdenes</div><div class="card-body p-0 table-responsive" style="max-height:300px"><table class="table table-custom table-striped mb-0"><thead class="table-light"><tr><th>Tipo</th><th>Precio</th><th>Vol</th></tr></thead><tbody id="orders-${safe}"></tbody></table></div></div></div>
            <div class="col-md-6 mb-3">
                <div class="card h-100">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span>Historial</span>
                        <button class="btn btn-sm btn-outline-secondary" onclick="clearHistory('${symbol}')"><i class="fa-solid fa-trash-can"></i></button>
                    </div>
                    <div class="card-body p-0 table-responsive" style="max-height:300px"><table class="table table-custom table-hover mb-0"><thead class="table-light"><tr><th>ID</th><th>Hora</th><th>Op</th><th>Precio</th><th>Total</th></tr></thead><tbody id="trades-${safe}"></tbody></table></div>
                </div>
            </div>
        </div>`;
    document.getElementById('mainTabsContent').appendChild(div);
}

function setMode(m) {
    currentMode = m; dataCache = {};
    if(m==='home') loadHome();
    else if(m==='wallet') loadWallet();
    else if(m!=='config') loadSymbol(m);
}

function setTimeframe(tf) {
    currentTimeframe = tf;
    document.querySelectorAll('.tf-btn').forEach(b => { b.classList.remove('active'); if(b.innerText.toLowerCase()===tf) b.classList.add('active'); });
    if(currentMode !== 'home' && currentMode !== 'config' && currentMode !== 'wallet') {
        const safe = currentMode.replace('/', '_');
        destroyChart(safe); 
        loadSymbol(currentMode);
    }
}

function setChartType(type) {
    currentChartType = type;
    document.querySelectorAll('button[data-chart-type]').forEach(btn => {
        btn.classList.remove('active');
        if(btn.getAttribute('data-chart-type') === type) {
            btn.classList.add('active');
        }
    });
    if(currentMode!=='home' && currentMode!=='config' && currentMode!=='wallet') {
        const safe = currentMode.replace('/', '_');
        destroyChart(safe);
        loadSymbol(currentMode);
    }
}

function resetZoom(symbol) {
    const safe = symbol.replace('/', '_');
    resetChartZoom(safe); 
    loadSymbol(symbol); 
}

function filterHistory(hours) {
    const buttons = document.querySelectorAll('.hist-btn');
    buttons.forEach(btn => {
        btn.classList.remove('active');
        const val = btn.getAttribute('onclick');
        if(hours === 'all' && val.includes("'all'")) btn.classList.add('active');
        else if(val.includes(`(${hours})`)) btn.classList.add('active');
    });

    if (!fullGlobalHistory || fullGlobalHistory.length === 0) return;

    let filteredData = [];
    if (hours === 'all') {
        filteredData = fullGlobalHistory;
    } else {
        const now = Date.now();
        const cutoff = now - (hours * 3600 * 1000);
        filteredData = fullGlobalHistory.filter(d => d[0] >= cutoff);
    }

    renderLineChart('balanceChartGlobal', filteredData, '#3b82f6');
}

async function loadHome() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        if (data.active_pairs) syncTabs(data.active_pairs);
        
        const badge = document.getElementById('status-badge');
        let engineBtn = document.getElementById('btn-engine-toggle');
        if (engineBtn) engineBtn.remove(); 
        
        const isStopped = data.status === 'Stopped';
        document.querySelectorAll('.tf-controls').forEach(el => { el.style.display = isStopped ? 'none' : 'inline-flex'; });

        if(isStopped) { badge.innerText = 'DETENIDO'; badge.className = 'badge bg-danger me-2'; }
        else { badge.innerText = data.status === 'Paused' ? 'PAUSADO' : 'OPERATIVO'; badge.className = data.status === 'Paused' ? 'badge bg-warning text-dark me-2' : 'badge bg-success me-2'; }

        document.getElementById('total-balance').innerText = `${fmtUSDC(data.total_usdc_value)} USDC`;
        updateColorValue('dash-profit-session', data.stats.session.profit, ' $');
        updateColorValue('dash-profit-total', data.stats.global.profit, ' $');
        document.getElementById('dash-trades-session').innerText = fmtInt(data.stats.session.trades);
        document.getElementById('dash-coin-session').innerText = data.stats.session.best_coin;
        document.getElementById('dash-uptime-session').innerText = data.stats.session.uptime;
        document.getElementById('dash-trades-total').innerText = fmtInt(data.stats.global.trades);
        document.getElementById('dash-coin-total').innerText = data.stats.global.best_coin;
        document.getElementById('dash-uptime-total').innerText = data.stats.global.uptime;

        renderDonut('pieChart', data.portfolio_distribution, true);
        renderDonut('sessionTradesChart', data.session_trades_distribution, false);
        renderDonut('globalTradesChart', data.global_trades_distribution, false);
        
        loadBalanceCharts();
        loadGlobalOrders();

        const stTable = document.getElementById('strategies-table-body');
        if(stTable) {
            stTable.innerHTML = data.strategies.map(s => {
                const safe = s.symbol.replace('/', '_');
                return `<tr><td class="fw-bold">${s.symbol}</td><td><span class="badge bg-success bg-opacity-25 text-success">Activo</span></td><td><small>${s.grids} Líneas @ ${s.amount}$ (${s.spread}%)</small></td><td class="fw-bold">${s.total_trades}</td><td class="${s.total_pnl>=0?'text-success':'text-danger'} fw-bold">${fmtUSDC(s.total_pnl)} $</td><td class="${s.session_pnl>=0?'text-success':'text-danger'} fw-bold">${fmtUSDC(s.session_pnl)} $</td><td class="text-end"><button class="btn btn-sm btn-outline-primary" onclick="document.querySelector('[data-bs-target=\\'#content-${safe}\\']').click()"><i class="fa-solid fa-chart-line"></i></button></td></tr>`;
            }).join('');
        }
    } catch(e) { console.error(e); }
}

async function loadSymbol(symbol) {
    const safe = symbol.replace('/', '_');
    try {
        const res = await fetch(`/api/details/${symbol}?timeframe=${currentTimeframe}&_=${Date.now()}`);
        if (!res.ok) return;
        const data = await res.json();
        
        document.getElementById(`price-${safe}`).innerText = `${fmtPrice(data.price)} USDC`;
        
        renderCandleChart(safe, data.chart_data, data.grid_lines, data.open_orders, currentChartType);
        
        document.getElementById(`count-buy-${safe}`).innerText = data.open_orders.filter(o => o.side === 'buy').length;
        document.getElementById(`count-sell-${safe}`).innerText = data.open_orders.filter(o => o.side === 'sell').length;
        updateColorValue(`sess-pnl-${safe}`, data.session_pnl, ' $');
        updateColorValue(`glob-pnl-${safe}`, data.global_pnl, ' $');
        
        const allOrders = [...data.open_orders].sort((a,b) => b.price - a.price);
        document.getElementById(`orders-${safe}`).innerHTML = allOrders.map(o => `<tr><td><b class="${o.side=='buy'?'text-buy':'text-sell'}">${o.side.toUpperCase()}</b></td><td>${fmtPrice(o.price)}</td><td>${fmtCrypto(o.amount)}</td></tr>`).join('');
        
        document.getElementById(`trades-${safe}`).innerHTML = data.trades.map(t => {
            let idBadge = t.buy_id || '-';
            if(t.side === 'sell' && t.buy_id) idBadge = '⮑ ' + t.buy_id; 
            return `<tr><td><span class="badge bg-secondary">${idBadge}</span></td><td>${new Date(t.timestamp).toLocaleTimeString()}</td><td><span class="badge ${t.side=='buy'?'bg-buy':'bg-sell'}">${t.side.toUpperCase()}</span></td><td>${fmtPrice(t.price)}</td><td>${fmtUSDC(t.cost)}</td></tr>`;
        }).join('');

    } catch(e) { console.error(e); }
}

async function loadWallet() { const tbody = document.getElementById('wallet-table-body'); tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4"><div class="spinner-border text-primary"></div></td></tr>'; try { const res = await fetch('/api/wallet'); const data = await res.json(); if(data.length===0) { tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Sin activos</td></tr>'; return; } tbody.innerHTML = data.map(item => { const freeVal = item.free * item.price; const lockedVal = item.locked * item.price; let btn = (item.asset!=='USDC' && item.asset!=='USDT') ? `<button class="btn btn-sm btn-outline-danger" onclick="liquidateAsset('${item.asset}')">Vender</button>` : '<span class="text-muted small">Base</span>'; return `<tr><td class="fw-bold">${item.asset}</td><td>${fmtCrypto(item.free)} <small class="text-muted">(${fmtUSDC(freeVal)}$)</small></td><td class="${item.locked>0?'text-danger':''}">${fmtCrypto(item.locked)} <small class="text-muted">(${fmtUSDC(lockedVal)}$)</small></td><td>${fmtCrypto(item.total)}</td><td class="fw-bold">${fmtUSDC(item.usdc_value)}$</td><td class="text-end">${btn}</td></tr>`; }).join(''); } catch(e) { tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error</td></tr>'; } }
async function loadGlobalOrders() { try { const res = await fetch('/api/orders'); const orders = await res.json(); const tbody = document.getElementById('global-orders-table'); if(orders.length === 0) { tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No hay órdenes</td></tr>'; return; } orders.sort((a,b) => a.symbol.localeCompare(b.symbol) || b.price - a.price); tbody.innerHTML = orders.map(o => { const isBuy = o.side === 'buy'; let pnlDisplay = '-', pnlClass = ''; if(!isBuy && o.entry_price > 0) { const pnl = ((o.current_price - o.entry_price)/o.entry_price)*100; pnlDisplay = fmtPct(pnl); pnlClass = pnl>=0 ? 'text-success fw-bold':'text-danger fw-bold'; } return `<tr><td class="fw-bold">${o.symbol}</td><td><span class="badge ${isBuy?'bg-success':'bg-danger'}">${isBuy?'COMPRA':'VENTA'}</span></td><td>${fmtPrice(o.price)}</td><td class="text-muted">${isBuy?'-':fmtPrice(o.entry_price)}</td><td>${fmtPrice(o.current_price)}</td><td class="${pnlClass}">${pnlDisplay}</td><td>${fmtUSDC(o.total_value)}</td><td class="text-end"><button class="btn btn-sm btn-outline-secondary" onclick="closeOrder('${o.symbol}','${o.id}','${o.side}',${o.amount})"><i class="fa-solid fa-times"></i></button></td></tr>`; }).join(''); } catch(e) {} }
async function loadBalanceCharts() { try { const res = await fetch('/api/history/balance'); if (!res.ok) return; const data = await res.json(); fullGlobalHistory = data.global; renderLineChart('balanceChartSession', data.session, '#0ecb81'); const activeBtn = document.querySelector('.hist-btn.active'); if(activeBtn && activeBtn.innerText === '24h') filterHistory(24); else if(activeBtn && activeBtn.innerText === '7d') filterHistory(168); else renderLineChart('balanceChartGlobal', fullGlobalHistory, '#3b82f6'); } catch(e) { console.error("Error loading charts", e); } }
async function closeOrder(s, i, side, a) { const result = await Swal.fire({ title: '¿Cancelar Orden?', text: `${side.toUpperCase()} ${s} - Cantidad: ${a}`, icon: 'warning', showCancelButton: true, confirmButtonColor: '#d33', cancelButtonColor: '#3085d6', confirmButtonText: 'Sí, cancelar' }); if (result.isConfirmed) { postAction('/api/close_order', { symbol: s, order_id: i, side: side, amount: a }); } }
async function liquidateAsset(a) { const result = await Swal.fire({ title: `¿Liquidar ${a}?`, text: "Se cancelarán las órdenes y se venderá todo a mercado.", icon: 'warning', showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Sí, vender todo' }); if (result.isConfirmed) { postAction('/api/liquidate_asset', { asset: a }, loadWallet); } }
async function clearHistory(s) { const result = await Swal.fire({ title: '¿Borrar Historial?', text: `Se eliminarán los trades antiguos de ${s} de la base de datos.`, icon: 'question', showCancelButton: true, confirmButtonText: 'Sí, borrar' }); if (result.isConfirmed) { postAction('/api/history/clear', { symbol: s }); } }
async function resetStatistics() { const result = await Swal.fire({ title: '¿RESET TOTAL?', text: "ESTO ES IRREVERSIBLE. Borrará todo el historial y gráficas.", icon: 'error', showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Sí, reiniciar todo' }); if (result.isConfirmed) { postAction('/api/reset_stats', {}, () => location.reload()); } }
async function panicStop() { const result = await Swal.fire({ title: '¿Pausar Operaciones?', text: "El bot dejará de analizar el mercado.", icon: 'warning', showCancelButton: true, confirmButtonText: 'Pausar' }); if (result.isConfirmed) postAction('/api/panic/stop'); }
async function panicStart() { postAction('/api/panic/start'); }
async function panicCancel() { const result = await Swal.fire({ title: '¿CANCELAR TODO?', text: "Se borrarán todas las órdenes del Exchange.", icon: 'error', showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Sí, cancelar todo' }); if (result.isConfirmed) postAction('/api/panic/cancel_all'); }
async function panicSell() { const result = await Swal.fire({ title: '¿VENDER TODO?', text: "PELIGRO: Se venderán todas las posiciones a mercado.", icon: 'error', showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Sí, vender todo' }); if (result.isConfirmed) postAction('/api/panic/sell_all'); }
async function startEngine() { const result = await Swal.fire({ title: '¿Arrancar Motor?', text: "Iniciará la operativa automática.", icon: 'question', showCancelButton: true, confirmButtonText: 'Arrancar' }); if (result.isConfirmed) postAction('/api/engine/on'); }
async function stopEngine() { const result = await Swal.fire({ title: '¿Detener Motor?', text: "Se detendrá el análisis de mercado.", icon: 'warning', showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Detener' }); if (result.isConfirmed) postAction('/api/engine/off'); }
async function resetGlobalChart() { const result = await Swal.fire({ title: '¿Borrar Gráfica Global?', text: "Se eliminará el historial visual del balance.", icon: 'question', showCancelButton: true, confirmButtonText: 'Borrar' }); if (result.isConfirmed) postAction('/api/reset/chart/global'); }
async function resetSessionChart() { const result = await Swal.fire({ title: '¿Reiniciar Sesión?', text: "Se reiniciará la gráfica de sesión y el contador de PnL de sesión.", icon: 'question', showCancelButton: true, confirmButtonText: 'Reiniciar' }); if (result.isConfirmed) postAction('/api/reset/chart/session'); }
async function resetGlobalPnL() { const result = await Swal.fire({ title: '¿Borrar Historial PnL?', text: "Se eliminarán todos los registros de trades pasados.", icon: 'warning', showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Borrar' }); if (result.isConfirmed) postAction('/api/reset/pnl/global'); }
async function refreshOrders() { postAction('/api/refresh_orders'); }
async function resetCoinSession(symbol) { const result = await Swal.fire({ title: `¿Reiniciar Sesión ${symbol}?`, text: "Solo afectará al contador de esta moneda.", icon: 'question', showCancelButton: true, confirmButtonText: 'Reiniciar' }); if (result.isConfirmed) postAction('/api/reset/coin/session', { symbol: symbol }); }
async function resetCoinGlobal(symbol) { const result = await Swal.fire({ title: `¿Borrar Historial ${symbol}?`, text: "Se eliminarán los trades antiguos de esta moneda.", icon: 'warning', showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Borrar' }); if (result.isConfirmed) postAction('/api/reset/coin/global', { symbol: symbol }); }

async function postAction(url, body={}, cb=null) { try { const res = await fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) }); const d = await res.json(); if(res.ok) { if(cb) await cb(); else { dataCache={}; await loadHome(); } Swal.fire({title:'Éxito', text:d.message, icon:'success', timer:1500, showConfirmButton:false}); } else Swal.fire('Error', d.detail, 'error'); } catch(e) { Swal.fire('Error', 'Conexión', 'error'); } }

function changeTheme(themeName, reloadData = true) {
    const link = document.getElementById('theme-stylesheet');
    if (themeName === 'default' || themeName === 'light') {
        link.href = "/static/css/themes/light.css";
        localStorage.setItem('gridbot_theme', 'light');
    } else {
        link.href = `/static/css/themes/${themeName}.css`; 
        localStorage.setItem('gridbot_theme', themeName);
    }
    
    if (reloadData) {
        setTimeout(() => {
            if (currentMode === 'home') loadHome();
            else if (currentMode !== 'config' && currentMode !== 'wallet') loadSymbol(currentMode);
        }, 100);
    }
}

// Loop principal
init();
setInterval(() => {
    if(currentMode === 'home') { loadHome(); } 
    else if(currentMode !== 'config' && currentMode !== 'wallet') loadSymbol(currentMode);
}, 4000);