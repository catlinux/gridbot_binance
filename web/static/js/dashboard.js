// Arxiu: gridbot_binance/web/static/js/dashboard.js

// ==========================================
// 1. VARIABLES GLOBALS I ESTAT
// ==========================================
let currentMode = 'home';
let charts = {};
let initialized = false;
let currentTimeframe = '15m';
let currentConfigObj = null; 
let fullGlobalHistory = []; 

// ==========================================
// 2. FORMATTERS I HELPERS
// ==========================================

const fmtUSDC = (num) => { 
    if (num === undefined || num === null) return '--'; 
    return parseFloat(num).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); 
};

const fmtPrice = (num) => {
    if (num === undefined || num === null) return '--';
    const val = parseFloat(num);
    if (val < 1.0) return val.toLocaleString('es-ES', { minimumFractionDigits: 5, maximumFractionDigits: 5 });
    if (val < 10.0) return val.toLocaleString('es-ES', { minimumFractionDigits: 4, maximumFractionDigits: 4 });
    if (val >= 1000) return val.toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    return val.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const fmtInt = (num) => { 
    if (num === undefined || num === null) return '--'; 
    return parseInt(num).toLocaleString('es-ES'); 
};

const fmtCrypto = (num) => { 
    if (!num) return '-'; 
    const val = parseFloat(num);
    let dec = val < 1 ? 5 : 2;
    return val.toLocaleString('es-ES', { minimumFractionDigits: dec, maximumFractionDigits: dec });
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


// ==========================================
// 3. GESTIÓ DE LA UI
// ==========================================

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

function setTimeframe(tf) {
    currentTimeframe = tf;
    document.querySelectorAll('.tf-btn').forEach(btn => { 
        btn.classList.remove('active'); 
        if(btn.innerText.toLowerCase() === tf) btn.classList.add('active'); 
    });
    if (currentMode !== 'home' && currentMode !== 'config') loadSymbol(currentMode);
}

function ensureTabExists(symbol) {
    const safe = symbol.replace('/', '_');
    const tabList = document.getElementById('mainTabs');
    const tabContent = document.getElementById('mainTabsContent');
    
    if (document.getElementById(`content-${safe}`)) return;

    const li = document.createElement('li');
    li.className = 'nav-item';
    li.innerHTML = `<button class="nav-link" data-bs-toggle="tab" data-bs-target="#content-${safe}" type="button" onclick="setMode('${symbol}')">${symbol}</button>`;
    
    const configTabLi = document.getElementById('tab-config').parentElement;
    tabList.insertBefore(li, configTabLi);

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
            <div class="col-lg-4 mb-3">
                <div class="card h-100">
                    <div class="card-header">Estado del Grid</div>
                    <div class="card-body">
                        <div class="row g-2 text-center mb-4">
                            <div class="col-6"><div class="bg-buy p-3 rounded"><small class="d-block fw-bold mb-1">COMPRAS</small><b class="fs-3" id="count-buy-${safe}">0</b></div></div>
                            <div class="col-6"><div class="bg-sell p-3 rounded"><small class="d-block fw-bold mb-1">VENTAS</small><b class="fs-3" id="count-sell-${safe}">0</b></div></div>
                        </div>
                        <ul class="list-group list-group-flush">
                            <li class="list-group-item d-flex justify-content-between"><span>Próx. Compra</span><b class="text-buy" id="next-buy-${safe}">--</b></li>
                            <li class="list-group-item d-flex justify-content-between"><span>Próx. Venta</span><b class="text-sell" id="next-sell-${safe}">--</b></li>
                            <li class="list-group-item d-flex justify-content-between mt-3 bg-light"><strong>Balance Sesión</strong><b id="sess-pnl-${safe}">--</b></li>
                            <li class="list-group-item d-flex justify-content-between bg-light"><strong>Balance Global</strong><b id="glob-pnl-${safe}">--</b></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-md-6 mb-3"><div class="card h-100"><div class="card-header">Órdenes Activas</div><div class="card-body p-0 table-responsive" style="max-height:300px"><table class="table table-custom table-striped mb-0"><thead class="table-light"><tr><th>Tipo</th><th>Precio</th><th>Volumen</th></tr></thead><tbody id="orders-${safe}"></tbody></table></div></div></div>
            <div class="col-md-6 mb-3"><div class="card h-100"><div class="card-header">Histórico de Operaciones</div><div class="card-body p-0 table-responsive" style="max-height:300px"><table class="table table-custom table-hover mb-0"><thead class="table-light"><tr><th>Hora</th><th>Op</th><th>Precio</th><th>Total (USDC)</th></tr></thead><tbody id="trades-${safe}"></tbody></table></div></div></div>
        </div>`;
    tabContent.appendChild(div);
}

function syncTabs(activePairs) {
    if (!activePairs) return;
    const tabList = document.getElementById('mainTabs');
    const safeSymbols = activePairs.map(s => s.replace('/', '_'));

    const existingTabs = Array.from(tabList.querySelectorAll('li.nav-item button.nav-link'));
    existingTabs.forEach(btn => {
        const targetId = btn.getAttribute('data-bs-target').replace('#content-', '');
        if (targetId !== 'home' && targetId !== 'config' && !safeSymbols.includes(targetId)) {
            btn.parentElement.remove();
            const contentDiv = document.getElementById(`content-${targetId}`);
            if (contentDiv) contentDiv.remove();
        }
    });

    activePairs.forEach(sym => {
        ensureTabExists(sym);
    });
}

// --- CONFIG FORM ---
async function loadConfigForm() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        currentConfigObj = JSON5.parse(data.content);
        
        document.getElementById('sys-cycle').value = currentConfigObj.system.cycle_delay;
        
        const configTab = document.getElementById('content-config');
        const systemCardBody = configTab.querySelector('.card-body'); 
        
        if (systemCardBody && !document.getElementById('sys-testnet-container')) {
            const div = document.createElement('div');
            div.id = 'sys-testnet-container'; 
            div.className = 'mt-3 p-3 bg-light border rounded';
            div.innerHTML = `
                <div class="form-check form-switch">
                    <input class="form-check-input" type="checkbox" role="switch" id="sys-testnet">
                    <label class="form-check-label fw-bold" for="sys-testnet">
                        MODO TESTNET (Simulación)
                    </label>
                    <div class="form-text">Si desmarcas esta casilla, operarás con DINERO REAL en Binance.</div>
                </div>
            `;
            systemCardBody.appendChild(div);
        }
        
        if (document.getElementById('sys-testnet')) {
            const isTest = currentConfigObj.system.use_testnet !== undefined ? currentConfigObj.system.use_testnet : true;
            document.getElementById('sys-testnet').checked = isTest;
        }

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
    
    const testnetCheckbox = document.getElementById('sys-testnet');
    if (testnetCheckbox) {
        currentConfigObj.system.use_testnet = testnetCheckbox.checked;
    }

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
        if (res.ok) { 
            msgBox.className = 'alert alert-success'; 
            msgBox.innerHTML = '<i class="fa-solid fa-check-circle"></i> Configuración guardada! Recargando...'; 
            setTimeout(() => { location.reload(); }, 1500); 
        } else { 
            msgBox.className = 'alert alert-danger'; 
            msgBox.innerText = 'Error: ' + data.detail; 
        }
    } catch (e) { alert("Error de conexión al guardar."); }
}


// ==========================================
// 4. GRÀFICS (ECHARTS LOGIC)
// ==========================================

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

function renderLineChart(domId, data, color) {
    const dom = document.getElementById(domId);
    if (!dom) return;
    if (!data || data.length === 0) return;

    let chart = echarts.getInstanceByDom(dom);
    if (!chart) chart = echarts.init(dom);
    
    const option = {
        tooltip: {
            trigger: 'axis',
            formatter: function (params) {
                const date = new Date(params[0].value[0]);
                const val = fmtUSDC(params[0].value[1]);
                return `${date.toLocaleString()}<br/><b>${val} USDC</b>`;
            }
        },
        grid: { left: 10, right: 10, top: 10, bottom: 10, containLabel: true },
        xAxis: {
            type: 'time',
            splitLine: { show: false },
            axisLabel: { fontSize: 10 }
        },
        yAxis: {
            type: 'value',
            scale: true, 
            splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } },
            axisLabel: { fontSize: 10 }
        },
        series: [{
            type: 'line',
            showSymbol: false,
            data: data,
            itemStyle: { color: color },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: color },
                    { offset: 1, color: 'rgba(255, 255, 255, 0)' }
                ]),
                opacity: 0.2
            },
            lineStyle: { width: 2 }
        }]
    };
    chart.setOption(option);
}

// --- FUNCIÓ RESTAURADA ---
async function loadBalanceCharts() {
    try {
        const res = await fetch('/api/history/balance');
        if (!res.ok) return;
        const data = await res.json();
        fullGlobalHistory = data.global; 
        renderLineChart('balanceChartSession', data.session, '#0ecb81');
        renderLineChart('balanceChartGlobal', fullGlobalHistory, '#3b82f6'); 
    } catch(e) { console.error("Error loading charts", e); }
}

// --- FUNCIÓ DE CANDLES (AMB CORRECCIÓ OVERLAP) ---
function renderCandleChart(safeSym, data, gridLines, activeOrders = []) {
    const dom = document.getElementById(`chart-${safeSym}`);
    if(!dom) return;
    if (!data || data.length === 0) return;
    
    let chart = echarts.getInstanceByDom(dom);
    if (!chart) chart = echarts.init(dom);

    // 1. Dades Preu Tancament
    const priceData = data.map(i => [i[0], parseFloat(i[2])]); 
    
    // 2. CÀLCUL MANUAL DE LÍMITS DE L'EIX Y
    let allPrices = [];
    
    data.forEach(candle => {
        const low = parseFloat(candle[3]);
        const high = parseFloat(candle[4]);
        if (!isNaN(low)) allPrices.push(low);
        if (!isNaN(high)) allPrices.push(high);
    });

    activeOrders.forEach(o => {
        const p = parseFloat(o.price);
        if (!isNaN(p)) allPrices.push(p);
    });

    gridLines.forEach(g => {
        const p = parseFloat(g);
        if (!isNaN(p)) allPrices.push(p);
    });

    let yMin = 0; 
    let yMax = 0;

    if (allPrices.length > 0) {
        yMin = Math.min(...allPrices);
        yMax = Math.max(...allPrices);

        const padding = (yMax - yMin) * 0.05; 
        const safePadding = padding === 0 ? yMin * 0.02 : padding; 
        
        yMin -= safePadding;
        yMax += safePadding;
    } else {
        const lastPrice = priceData.length ? priceData[priceData.length-1][1] : 0;
        yMin = lastPrice * 0.95;
        yMax = lastPrice * 1.05;
    }

    const gridMarkLines = gridLines.map(p => ({
        yAxis: parseFloat(p),
        lineStyle: { color: '#e5e7eb', type: 'dotted', width: 1 },
        label: { show: false },
        silent: true
    }));

    const orderMarkLines = activeOrders.map(o => ({
        yAxis: parseFloat(o.price),
        lineStyle: {
            color: o.side === 'buy' ? '#0ecb81' : '#f6465d',
            type: 'solid',
            width: 1.5
        },
        label: {
            show: true,
            position: 'end',
            formatter: (o.side === 'buy' ? 'COMPRA' : 'VENTA') + ' ' + fmtPrice(o.price),
            color: '#fff',
            backgroundColor: o.side === 'buy' ? '#0ecb81' : '#f6465d',
            padding: [3, 5],
            borderRadius: 3,
            fontSize: 10,
            fontWeight: 'bold',
            distance: [0, 0]
        }
    }));

    const option = { 
        animation: false, 
        grid: { left: 10, right: 85, top: 10, bottom: 20, containLabel: true }, 
        
        tooltip: { 
            trigger: 'axis', 
            axisPointer: { type: 'cross' },
            formatter: function (params) {
                if(!params || params.length === 0) return '';
                const date = params[0].axisValue;
                const val = fmtPrice(params[0].data[1]);
                return `<b>${date}</b><br/>Precio: ${val}`;
            }
        }, 
        
        xAxis: { 
            type: 'category', 
            data: data.map(i => i[0]), 
            scale: true, 
            boundaryGap: false,
            axisLine: { show: false }, 
            axisTick: { show: false }, 
            axisLabel: { show: false } 
        }, 
        yAxis: { 
            type: 'value',
            position: 'right', 
            min: yMin,
            max: yMax,
            splitLine: { show: true, lineStyle: { color: '#f3f4f6' } },
            axisLabel: { 
                formatter: function (value) { return fmtPrice(value); },
                fontSize: 10 
            }
        }, 
        series: [
            { 
                type: 'line', 
                data: priceData,
                showSymbol: false,
                lineStyle: { width: 2, color: '#3b82f6' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
                        { offset: 1, color: 'rgba(59, 130, 246, 0)' }
                    ])
                },
                markLine: { 
                    symbol: 'none', 
                    data: [...gridMarkLines, ...orderMarkLines],
                    silent: true,
                    labelLayout: {
                        hideOverlap: false 
                    },
                    animation: false
                } 
            }
        ] 
    };
    
    chart.setOption(option);
}


// ==========================================
// 5. API CALLS & DATA FETCHING
// ==========================================

async function loadHome() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        if (data.active_pairs) {
            syncTabs(data.active_pairs);
        }
        
        const badge = document.getElementById('status-badge');
        const headerDiv = badge.parentElement;

        let engineBtn = document.getElementById('btn-engine-toggle');
        if (!engineBtn) {
            engineBtn = document.createElement('button');
            engineBtn.id = 'btn-engine-toggle';
            engineBtn.className = 'btn btn-sm btn-outline-light ms-3';
            engineBtn.onclick = toggleEngine;
            headerDiv.insertBefore(engineBtn, badge.nextSibling);
        }

        if (data.status === 'Stopped') {
            badge.innerText = 'DETENIDO';
            badge.className = 'badge bg-danger me-2';
            engineBtn.innerHTML = '<i class="fa-solid fa-power-off me-1"></i> ENCENDER SISTEMA';
            engineBtn.className = 'btn btn-sm btn-success fw-bold ms-3';
        } else {
            engineBtn.innerHTML = '<i class="fa-solid fa-power-off me-1"></i> APAGAR SISTEMA';
            engineBtn.className = 'btn btn-sm btn-outline-danger ms-3';
            
            if (data.status === 'Paused') {
                badge.innerText = 'PAUSADO';
                badge.className = 'badge bg-warning text-dark me-2';
            } else {
                badge.innerText = 'OPERATIVO';
                badge.className = 'badge bg-success me-2';
            }
        }

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
        
        // Recuperada la crida a la funció
        loadBalanceCharts();

        const strategiesBody = document.getElementById('strategies-table-body');
        if (strategiesBody) {
            strategiesBody.innerHTML = data.strategies.map(s => {
                
                let displayTotalPnl = s.total_pnl;
                if (Math.abs(displayTotalPnl) > 5000) displayTotalPnl = 0.00;

                const totalPnlClass = displayTotalPnl >= 0 ? 'text-success' : 'text-danger';
                const totalPnlSign = displayTotalPnl >= 0 ? '+' : '';
                const totalPnlText = `${totalPnlSign}${fmtUSDC(displayTotalPnl)} $`;
                const totalPnlFinalClass = s.total_trades > 0 || displayTotalPnl !== 0 ? totalPnlClass : 'text-muted';

                const sessPnlClass = s.session_pnl >= 0 ? 'text-success' : 'text-danger';
                const sessPnlSign = s.session_pnl >= 0 ? '+' : '';
                const sessPnlText = `${sessPnlSign}${fmtUSDC(s.session_pnl)} $`;

                const safeSym = s.symbol.replace('/', '_');
                
                return `
                    <tr>
                        <td class="fw-bold">${s.symbol}</td>
                        <td><span class="badge bg-success bg-opacity-25 text-success">Activo</span></td>
                        <td><small>${s.grids} Líneas @ ${s.amount}$ (Spread ${s.spread}%)</small></td>
                        <td class="fw-bold">${s.total_trades}</td>
                        <td class="${totalPnlFinalClass} fw-bold">${totalPnlText}</td>
                        <td class="${sessPnlClass} fw-bold">${sessPnlText}</td>
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
        
        document.getElementById(`price-${safe}`).innerText = `${fmtPrice(data.price)} USDC`;
        
        renderCandleChart(safe, data.chart_data, data.grid_lines, data.open_orders);
        
        const buys = data.open_orders.filter(o => o.side === 'buy').sort((a,b) => b.price - a.price);
        const sells = data.open_orders.filter(o => o.side === 'sell').sort((a,b) => a.price - b.price);
        document.getElementById(`count-buy-${safe}`).innerText = buys.length;
        document.getElementById(`count-sell-${safe}`).innerText = sells.length;
        
        document.getElementById(`next-buy-${safe}`).innerText = buys.length ? fmtPrice(buys[0].price) : '-';
        document.getElementById(`next-sell-${safe}`).innerText = sells.length ? fmtPrice(sells[0].price) : '-';
        
        updateColorValue(`sess-pnl-${safe}`, data.session_pnl, ' $');
        updateColorValue(`glob-pnl-${safe}`, data.global_pnl, ' $');
        
        const allOrders = [...sells.reverse(), ...buys];
        document.getElementById(`orders-${safe}`).innerHTML = allOrders.map(o => `<tr><td><b class="${o.side=='buy'?'text-buy':'text-sell'}">${o.side.toUpperCase() === 'BUY' ? 'COMPRA' : 'VENTA'}</b></td><td>${fmtPrice(o.price)}</td><td>${fmtCrypto(o.amount)}</td></tr>`).join('');
        document.getElementById(`trades-${safe}`).innerHTML = data.trades.map(t => `<tr><td>${new Date(t.timestamp).toLocaleTimeString()}</td><td><span class="badge ${t.side=='buy'?'bg-buy':'bg-sell'}">${t.side === 'buy' ? 'COMPRA' : 'VENTA'}</span></td><td>${fmtPrice(t.price)}</td><td>${fmtUSDC(t.cost)}</td></tr>`).join('');
    } catch(e) { console.error(e); }
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
                entryDisplay = fmtPrice(o.entry_price);
            } else if (isBuy) {
                entryDisplay = '<small class="text-muted">Target</small>'; 
            }

            return `
                <tr>
                    <td class="fw-bold">${o.symbol}</td>
                    <td>${typeBadge}</td>
                    <td>${fmtPrice(o.price)}</td>
                    <td class="text-muted">${entryDisplay}</td>
                    <td>${fmtPrice(o.current_price)}</td>
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


// ==========================================
// 6. FUNCIONS DE CONTROL I INICIALITZACIÓ
// ==========================================

async function toggleEngine() {
    const btn = document.getElementById('btn-engine-toggle');
    const isTurningOn = btn.classList.contains('btn-success');
    const action = isTurningOn ? 'ENCENDER' : 'APAGAR';
    
    if (!confirm(`¿Seguro que quieres ${action} el motor de trading?`)) return;
    
    const endpoint = isTurningOn ? '/api/engine/on' : '/api/engine/off';
    
    try {
        const res = await fetch(endpoint, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            loadHome();
        } else {
            alert("Error: " + data.message);
        }
    } catch (e) { alert("Error de conexión"); }
}

async function resetStatistics() {
    if (!confirm("⚠️ ATENCIÓN ⚠️\n\n¿Estás seguro de que quieres borrar TODAS las estadísticas?\n\nSe pondrá a cero el PnL, el historial de operaciones y los tiempos de sesión.\nEsta acción no se puede deshacer.")) {
        return;
    }
    try {
        const res = await fetch('/api/reset_stats', { method: 'POST' });
        const data = await res.json();
        if (res.ok) { alert(data.message); location.reload(); } else { alert("Error: " + data.detail); }
    } catch (e) { alert("Error de conexión."); }
}

async function panicStop() {
    if (!confirm("✋ ¿PAUSAR EL BOT?\n\nSe detendrá la lógica de trading para TODAS las monedas.\nNo se pondrán nuevas órdenes.")) return;
    try {
        const res = await fetch('/api/panic/stop', { method: 'POST' });
        const data = await res.json();
        if (res.ok) { alert(data.message); loadHome(); } else { alert("Error: " + data.detail); }
    } catch (e) { alert("Error de conexión."); }
}

async function panicStart() {
    try {
        const res = await fetch('/api/panic/start', { method: 'POST' });
        const data = await res.json();
        if (res.ok) { alert(data.message); loadHome(); } else { alert("Error: " + data.detail); }
    } catch (e) { alert("Error de conexión."); }
}

async function panicCancel() {
    if (!confirm("🗑️ ¿CANCELAR TODO?\n\nSe borrarán TODAS las órdenes limit abiertas en el Exchange para las monedas activas.")) return;
    try {
        const res = await fetch('/api/panic/cancel_all', { method: 'POST' });
        const data = await res.json();
        if (res.ok) { alert(data.message); loadHome(); } else { alert("Error: " + data.detail); }
    } catch (e) { alert("Error de conexión."); }
}

async function panicSell() {
    if (!confirm("🔥 ¡PELIGRO! ¿VENDER TODO A USDC?\n\n1. Se cancelarán todas las órdenes.\n2. Se venderán todas las criptomonedas activas a precio de mercado.\n\n¿Estás 100% seguro?")) return;
    try {
        const res = await fetch('/api/panic/sell_all', { method: 'POST' });
        const data = await res.json();
        if (res.ok) { alert(data.message); loadHome(); } else { alert("Error: " + data.detail); }
    } catch (e) { alert("Error de conexión."); }
}

async function init() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        
        if (!initialized && data.active_pairs) {
            syncTabs(data.active_pairs);
            initialized = true;
        }
        loadHome();
    } catch (e) { console.error("Error init:", e); }
}

// MAIN LOOP
init();
setInterval(() => { 
    if (currentMode === 'home') { 
        loadHome(); 
        loadBalanceCharts(); 
    } else if (currentMode !== 'config') { 
        loadSymbol(currentMode); 
    } 
}, 4000);
