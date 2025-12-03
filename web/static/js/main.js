// Arxiu: gridbot_binance/web/static/js/main.js

let currentMode = 'home';
let charts = {};
let initialized = false;
let currentTimeframe = '15m';
let currentConfigObj = null; 

// FORMATTERS (Usamos es-ES para formato numérico España)
const fmtUSDC = (num) => { 
    if (num === undefined || num === null) return '--'; 
    return parseFloat(num).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); 
};
const fmtInt = (num) => { 
    if (num === undefined || num === null) return '--'; 
    return parseInt(num).toLocaleString('es-ES'); 
};
const fmtCrypto = (num) => { 
    if (!num) return '-'; 
    return num.toString().replace('.', ','); 
};
const fmtPct = (num) => {
    if (!num) return '0,00%';
    return parseFloat(num).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '%';
};

const updateColorValue = (elementId, value, suffix = '') => {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.innerText = fmtUSDC(value) + suffix;
    el.classList.remove('text-success', 'text-danger', 'text-dark');
    if (value >= 0) el.classList.add('text-success');
    else el.classList.add('text-danger');
};

function setMode(mode) {
    currentMode = mode;
    if (mode === 'home') loadHome();
    else if (mode !== 'config') loadSymbol(mode);
    if (mode !== 'home' && mode !== 'config') {
        setTimeout(() => {
            const safe = mode.replace('/', '_');
            if (charts[safe]) charts[safe].resize();
        }, 200);
    }
}

async function loadConfigForm() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        currentConfigObj = JSON5.parse(data.content);
        document.getElementById('sys-cycle').value = currentConfigObj.system.cycle_delay;
        const container = document.getElementById('coins-config-container');
        container.innerHTML = '';
        currentConfigObj.pairs.forEach((pair, index) => {
            const strategy = pair.strategy || currentConfigObj.default_strategy;
            const isEnabled = pair.enabled;
            const cardClass = isEnabled ? '' : 'coin-disabled';
            const checked = isEnabled ? 'checked' : '';
            const html = `
                <div class="col-md-6 col-xl-4 mb-4">
                    <div class="card h-100 coin-card ${cardClass}" id="card-pair-${index}">
                        <div class="card-header d-flex justify-content-between align-items-center"><span class="fw-bold fs-5">${pair.symbol}</span><div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" id="enable-${index}" ${checked} onchange="toggleCard(${index})"><label class="form-check-label fw-bold" for="enable-${index}">${isEnabled ? 'ON' : 'OFF'}</label></div></div>
                        <div class="card-body"><div class="mb-3"><label class="form-label">Inversión por Línea (USDC)</label><div class="input-group"><span class="input-group-text">$</span><input type="number" class="form-control" id="amount-${index}" value="${strategy.amount_per_grid}"></div></div><div class="row"><div class="col-6 mb-3"><label class="form-label">Nº Líneas</label><input type="number" class="form-control" id="qty-${index}" value="${strategy.grids_quantity}"></div><div class="col-6 mb-3"><label class="form-label">Spread (%)</label><div class="input-group"><input type="number" class="form-control" id="spread-${index}" value="${strategy.grid_spread}" step="0.1"><span class="input-group-text">%</span></div></div></div></div>
                    </div>
                </div>`;
            container.innerHTML += html;
        });
    } catch (e) { console.error(e); alert("Error leyendo la configuración."); }
}

function toggleCard(index) {
    const checkbox = document.getElementById(`enable-${index}`);
    const card = document.getElementById(`card-pair-${index}`);
    const label = checkbox.nextElementSibling;
    if (checkbox.checked) { card.classList.remove('coin-disabled'); label.innerText = 'ON'; } 
    else { card.classList.add('coin-disabled'); label.innerText = 'OFF'; }
}

async function saveConfigForm() {
    if (!currentConfigObj) return;
    currentConfigObj.system.cycle_delay = parseInt(document.getElementById('sys-cycle').value);
    currentConfigObj.pairs.forEach((pair, index) => {
        const isEnabled = document.getElementById(`enable-${index}`).checked;
        const amount = parseFloat(document.getElementById(`amount-${index}`).value);
        const qty = parseInt(document.getElementById(`qty-${index}`).value);
        const spread = parseFloat(document.getElementById(`spread-${index}`).value);
        pair.enabled = isEnabled;
        if (!pair.strategy) pair.strategy = {};
        pair.strategy.amount_per_grid = amount;
        pair.strategy.grids_quantity = qty;
        pair.strategy.grid_spread = spread;
    });
    const jsonString = JSON.stringify(currentConfigObj, null, 2);
    const msgBox = document.getElementById('config-alert');
    try {
        const res = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: jsonString }) });
        const data = await res.json();
        msgBox.style.display = 'block';
        if (res.ok) { msgBox.className = 'alert alert-success'; msgBox.innerHTML = '<i class="fa-solid fa-check-circle"></i> Configuración guardada! Recargando...'; setTimeout(() => { location.reload(); }, 1500); } else { msgBox.className = 'alert alert-danger'; msgBox.innerText = 'Error: ' + data.detail; }
    } catch (e) { alert("Error de conexión al guardar."); }
}

function setTimeframe(tf) {
    currentTimeframe = tf;
    document.querySelectorAll('.tf-btn').forEach(btn => { btn.classList.remove('active'); if(btn.innerText.toLowerCase() === tf) btn.classList.add('active'); });
    if (currentMode !== 'home' && currentMode !== 'config') loadSymbol(currentMode);
}

function renderDonut(domId, data, isCurrency = false) {
    const dom = document.getElementById(domId);
    if (!dom) return;
    const chart = echarts.getInstanceByDom(dom) || echarts.init(dom);
    const chartData = (data && data.length > 0) ? data : [{value: 0, name: 'Sin Datos'}];
    chart.setOption({ 
        tooltip: { trigger: 'item', formatter: function(params) { const val = isCurrency ? fmtUSDC(params.value) : fmtInt(params.value); return `${params.name}: ${val} (${params.percent}%)`; } }, 
        legend: { orient: 'vertical', left: '0%', top: 'center', itemGap: 10, textStyle: { fontSize: 11, color: '#6b7280' } }, 
        series: [{ type: 'pie', radius: ['40%', '80%'], center: ['65%', '50%'], label: { show: false, position: 'center' }, emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } }, data: chartData }] 
    });
}

async function loadGlobalOrders() {
    try {
        const res = await fetch('/api/orders');
        const orders = await res.json();
        const tbody = document.getElementById('global-orders-table');
        
        const thead = document.querySelector('#global-orders-table').previousElementSibling;
        if (thead) {
            thead.innerHTML = `
                <tr>
                    <th>Par</th>
                    <th>Tipo</th>
                    <th>Precio Orden</th>
                    <th>Precio Entrada</th>
                    <th>Precio Actual</th>
                    <th>PnL (Latente)</th>
                    <th>Valor ($)</th>
                    <th class="text-end">Acción</th>
                </tr>`;
        }

        if (orders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No hay órdenes activas</td></tr>';
            return;
        }

        orders.sort((a, b) => a.symbol.localeCompare(b.symbol) || b.price - a.price);

        tbody.innerHTML = orders.map(o => {
            const isBuy = o.side === 'buy';
            const typeBadge = isBuy ? '<span class="badge bg-success">COMPRA</span>' : '<span class="badge bg-danger">VENTA</span>';
            const actionBtnClass = isBuy ? 'btn-outline-secondary' : 'btn-outline-danger';
            const actionIcon = isBuy ? 'fa-times' : 'fa-money-bill-transfer';
            const actionText = isBuy ? 'Cancelar' : 'Vender';
            const actionTitle = isBuy ? 'Recuperar USDC' : 'Vender crypto a mercado';

            let pnlDisplay = '-';
            let entryDisplay = '-';
            let pnlClass = '';

            if (!isBuy && o.entry_price > 0 && o.current_price > 0) {
                const pnlPercent = ((o.current_price - o.entry_price) / o.entry_price) * 100;
                pnlDisplay = fmtPct(pnlPercent);
                pnlClass = pnlPercent >= 0 ? 'text-success fw-bold' : 'text-danger fw-bold';
                entryDisplay = fmtUSDC(o.entry_price);
            } else if (isBuy) {
                entryDisplay = '<small class="text-muted">Target</small>'; 
            }

            return `
                <tr>
                    <td class="fw-bold">${o.symbol}</td>
                    <td>${typeBadge}</td>
                    <td>${fmtUSDC(o.price)}</td>
                    <td class="text-muted">${entryDisplay}</td>
                    <td>${fmtUSDC(o.current_price)}</td>
                    <td class="${pnlClass}">${pnlDisplay}</td>
                    <td>${fmtUSDC(o.total_value)}</td>
                    <td class="text-end">
                        <button class="btn btn-sm ${actionBtnClass}" title="${actionTitle}" onclick="closeOrder('${o.symbol}', '${o.id}', '${o.side}', ${o.amount})">
                            <i class="fa-solid ${actionIcon} me-1"></i> ${actionText}
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) { console.error("Error cargando órdenes:", e); }
}

async function closeOrder(symbol, id, side, amount) {
    const action = side === 'buy' ? 'cancelar esta orden' : 'VENDER a mercado';
    if (!confirm(`¿Estás seguro que quieres ${action}?`)) return;

    try {
        const res = await fetch('/api/close_order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: symbol, order_id: id, side: side, amount: amount })
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            loadGlobalOrders(); 
            loadHome(); 
        } else {
            alert("Error: " + data.detail);
        }
    } catch (e) { alert("Error de conexión"); }
}

async function loadHome() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        document.getElementById('status-badge').innerText = data.status === 'Running' ? 'OPERATIVO' : 'DETENIDO';
        document.getElementById('status-badge').className = data.status === 'Running' ? 'badge bg-success' : 'badge bg-danger';
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
        
        const strategiesBody = document.getElementById('strategies-table-body');
        if (strategiesBody) {
            strategiesBody.innerHTML = data.strategies.map(s => {
                const pnlClass = s.total_pnl >= 0 ? 'text-success' : 'text-danger';
                const pnlSign = s.total_pnl >= 0 ? '+' : '';
                const safeSym = s.symbol.replace('/', '_');
                
                return `
                    <tr>
                        <td class="fw-bold">${s.symbol}</td>
                        <td><span class="badge bg-success bg-opacity-25 text-success">Activo</span></td>
                        <td><small>${s.grids} Líneas @ ${s.amount}$ (Spread ${s.spread}%)</small></td>
                        <td class="fw-bold">${s.total_trades}</td>
                        <td class="${pnlClass} fw-bold">${pnlSign}${fmtUSDC(s.total_pnl)} $</td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-outline-primary" onclick="document.querySelector('[data-bs-target=\\'#content-${safeSym}\\']').click()">
                                <i class="fa-solid fa-chart-line"></i> Ver
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
        }

        loadGlobalOrders();

    } catch(e) { console.error(e); }
}

async function loadSymbol(symbol) {
    const safe = symbol.replace('/', '_');
    try {
        const res = await fetch(`/api/details/${symbol}?timeframe=${currentTimeframe}`);
        if (!res.ok) return;
        const data = await res.json();
        
        document.getElementById(`price-${safe}`).innerText = `${fmtUSDC(data.price)} USDC`;
        renderCandleChart(safe, data.chart_data, data.grid_lines);
        
        const buys = data.open_orders.filter(o => o.side === 'buy').sort((a,b) => b.price - a.price);
        const sells = data.open_orders.filter(o => o.side === 'sell').sort((a,b) => a.price - b.price);
        document.getElementById(`count-buy-${safe}`).innerText = buys.length;
        document.getElementById(`count-sell-${safe}`).innerText = sells.length;
        document.getElementById(`next-buy-${safe}`).innerText = buys.length ? fmtCrypto(parseFloat(buys[0].price).toFixed(4)) : '-';
        document.getElementById(`next-sell-${safe}`).innerText = sells.length ? fmtCrypto(parseFloat(sells[0].price).toFixed(4)) : '-';
        
        const allOrders = [...sells.reverse(), ...buys];
        document.getElementById(`orders-${safe}`).innerHTML = allOrders.map(o => `<tr><td><b class="${o.side=='buy'?'text-buy':'text-sell'}">${o.side.toUpperCase() === 'BUY' ? 'COMPRA' : 'VENTA'}</b></td><td>${fmtCrypto(parseFloat(o.price).toFixed(5))}</td><td>${fmtCrypto(o.amount)}</td></tr>`).join('');
        document.getElementById(`trades-${safe}`).innerHTML = data.trades.map(t => `<tr><td>${new Date(t.timestamp).toLocaleTimeString()}</td><td><span class="badge ${t.side=='buy'?'bg-buy':'bg-sell'}">${t.side === 'buy' ? 'COMPRA' : 'VENTA'}</span></td><td>${fmtCrypto(parseFloat(t.price).toFixed(5))}</td><td>${fmtUSDC(t.cost)}</td></tr>`).join('');
    } catch(e) { console.error(e); }
}

function renderCandleChart(safeSym, data, gridLines) {
    const dom = document.getElementById(`chart-${safeSym}`);
    if(!dom) return;
    if (!data || data.length === 0) return;
    const currentPrice = data[data.length - 1][4]; 
    const validData = data.filter(d => d[4] > currentPrice * 0.5);
    let chart = echarts.getInstanceByDom(dom);
    if (!chart) chart = echarts.init(dom);
    const markLines = gridLines.map(p => ({ yAxis: p, lineStyle: { color: '#9ca3af', type: 'dashed', opacity: 0.5 } }));
    const option = { animation: false, grid: { left: 10, right: 60, top: 10, bottom: 20, containLabel: true }, tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } }, xAxis: { type: 'category', data: validData.map(i => i[0]), scale: true, boundaryGap: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { show: false } }, yAxis: { scale: true, position: 'right', splitLine: { show: true, lineStyle: { color: '#f3f4f6' } } }, dataZoom: [{ type: 'inside', start: 60, end: 100 }], series: [{ type: 'candlestick', data: validData.map(i => [i[1], i[2], i[3], i[4]]), itemStyle: { color: '#0ecb81', color0: '#f6465d', borderColor: '#0ecb81', borderColor0: '#f6465d' }, markLine: { symbol: 'none', data: markLines, label: { show: false }, silent: true } }] };
    chart.setOption(option);
}

async function init() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        const tabList = document.getElementById('mainTabs');
        const tabContent = document.getElementById('mainTabsContent');

        if (!initialized && data.active_pairs.length > 0) {
            data.active_pairs.forEach(sym => {
                const safe = sym.replace('/', '_');
                const li = document.createElement('li');
                li.className = 'nav-item';
                li.innerHTML = `<button class="nav-link" data-bs-toggle="tab" data-bs-target="#content-${safe}" type="button" onclick="setMode('${sym}')">${sym}</button>`;
                tabList.appendChild(li);

                const div = document.createElement('div');
                div.className = 'tab-pane fade';
                div.id = `content-${safe}`;
                div.innerHTML = `
                    <div class="row">
                        <div class="col-lg-8 mb-3">
                            <div class="card h-100">
                                <div class="card-header d-flex justify-content-between align-items-center">
                                    <div class="d-flex align-items-center">
                                        <span>Gráfico Precio</span>
                                        <div class="btn-group ms-3" role="group">
                                            <button type="button" class="btn btn-outline-secondary tf-btn" onclick="setTimeframe('1m')">1m</button>
                                            <button type="button" class="btn btn-outline-secondary tf-btn" onclick="setTimeframe('5m')">5m</button>
                                            <button type="button" class="btn btn-outline-secondary tf-btn active" onclick="setTimeframe('15m')">15m</button>
                                            <button type="button" class="btn btn-outline-secondary tf-btn" onclick="setTimeframe('1h')">1h</button>
                                            <button type="button" class="btn btn-outline-secondary tf-btn" onclick="setTimeframe('4h')">4h</button>
                                            <button type="button" class="btn btn-outline-secondary tf-btn" onclick="setTimeframe('1d')">1d</button>
                                            <button type="button" class="btn btn-outline-secondary tf-btn" onclick="setTimeframe('1w')">1w</button>
                                        </div>
                                    </div>
                                    <span class="fs-5 fw-bold text-primary" id="price-${safe}">--</span>
                                </div>
                                <div class="card-body p-1"><div id="chart-${safe}" class="chart-container"></div></div>
                            </div>
                        </div>
                        <div class="col-lg-4 mb-3"><div class="card h-100"><div class="card-header">Estado del Grid</div><div class="card-body"><div class="row g-2 text-center mb-4"><div class="col-6"><div class="bg-buy p-3 rounded"><small class="d-block fw-bold mb-1">COMPRAS</small><b class="fs-3" id="count-buy-${safe}">0</b></div></div><div class="col-6"><div class="bg-sell p-3 rounded"><small class="d-block fw-bold mb-1">VENTAS</small><b class="fs-3" id="count-sell-${safe}">0</b></div></div></div><ul class="list-group list-group-flush"><li class="list-group-item d-flex justify-content-between"><span>Próx. Compra</span><b class="text-buy" id="next-buy-${safe}">--</b></li><li class="list-group-item d-flex justify-content-between"><span>Próx. Venta</span><b class="text-sell" id="next-sell-${safe}">--</b></li></ul></div></div></div>
                    </div>
                    <div class="row">
                        <div class="col-md-6 mb-3"><div class="card h-100"><div class="card-header">Órdenes Activas</div><div class="card-body p-0 table-responsive" style="max-height:300px"><table class="table table-custom table-striped mb-0"><thead class="table-light"><tr><th>Tipo</th><th>Precio</th><th>Volumen</th></tr></thead><tbody id="orders-${safe}"></tbody></table></div></div></div>
                        <div class="col-md-6 mb-3"><div class="card h-100"><div class="card-header">Histórico de Operaciones</div><div class="card-body p-0 table-responsive" style="max-height:300px"><table class="table table-custom table-hover mb-0"><thead class="table-light"><tr><th>Hora</th><th>Op</th><th>Precio</th><th>Total (USDC)</th></tr></thead><tbody id="trades-${safe}"></tbody></table></div></div></div>
                    </div>`;
                tabContent.appendChild(div);
            });
            initialized = true;
        }
        loadHome();
    } catch (e) { console.error("Error init:", e); }
}

init();
setInterval(() => { if (currentMode === 'home') { loadHome(); } else if (currentMode !== 'config') loadSymbol(currentMode); }, 4000);