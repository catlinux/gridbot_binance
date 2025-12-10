import { fmtUSDC, fmtPrice, fmtInt } from './utils.js';

// Cache local per als gràfics
let chartCache = {};

export function renderDonut(domId, data, isCurrency = false) {
    const dom = document.getElementById(domId);
    if (!dom) return;
    const chart = echarts.getInstanceByDom(dom) || echarts.init(dom);
    const chartData = (data && data.length > 0) ? data : [{value: 0, name: 'Sin Datos'}];
    
    const cacheKey = domId + JSON.stringify(chartData);
    if (chartCache[cacheKey]) return;
    chartCache[cacheKey] = true;

    chart.setOption({ 
        tooltip: { trigger: 'item', formatter: function(params) { const val = isCurrency ? fmtUSDC(params.value) : fmtInt(params.value); return `${params.name}: ${val} (${params.percent}%)`; } }, 
        legend: { orient: 'vertical', left: '0%', top: 'center', itemGap: 10, textStyle: { fontSize: 11, color: '#6b7280' } }, 
        series: [{ type: 'pie', radius: ['40%', '80%'], center: ['65%', '50%'], label: { show: false, position: 'center' }, emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } }, data: chartData }] 
    });
}

export function renderLineChart(domId, data, color) {
    const dom = document.getElementById(domId);
    if (!dom) return;
    if (!data || data.length === 0) return;

    const cacheKey = domId + data.length;
    if (chartCache[cacheKey]) return;
    chartCache[cacheKey] = true;

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
        xAxis: { type: 'time', splitLine: { show: false }, axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', scale: true, splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } }, axisLabel: { fontSize: 10 } },
        series: [{
            type: 'line', showSymbol: false, data: data, itemStyle: { color: color },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: color }, { offset: 1, color: 'rgba(255, 255, 255, 0)' }]), opacity: 0.2 },
            lineStyle: { width: 2 }
        }]
    };
    chart.setOption(option);
}

export function renderCandleChart(safeSym, data, gridLines, activeOrders = []) {
    const dom = document.getElementById(`chart-${safeSym}`);
    if(!dom) return;
    if (!data || data.length === 0) return;
    
    // Simplificació del cache: usem timestamp última espelma
    const lastTime = data[data.length-1][0];
    const cacheKey = `sig_${safeSym}_${lastTime}_${activeOrders.length}`;
    
    if (chartCache[cacheKey]) return;
    chartCache[cacheKey] = true;

    let chart = echarts.getInstanceByDom(dom);
    if (!chart) chart = echarts.init(dom);

    const priceData = data.map(i => [i[0], parseFloat(i[2])]); 
    
    // (Càlcul mínims i màxims simplificat per brevetat, mantenint lògica original)
    let allPrices = [];
    data.forEach(c => { if (!isNaN(parseFloat(c[3]))) allPrices.push(parseFloat(c[3])); if (!isNaN(parseFloat(c[4]))) allPrices.push(parseFloat(c[4])); });
    activeOrders.forEach(o => { if (!isNaN(parseFloat(o.price))) allPrices.push(parseFloat(o.price)); });
    gridLines.forEach(g => { if (!isNaN(parseFloat(g))) allPrices.push(parseFloat(g)); });

    let yMin = 0, yMax = 0;
    if (allPrices.length > 0) {
        yMin = Math.min(...allPrices); yMax = Math.max(...allPrices);
        const padding = (yMax - yMin) * 0.05; 
        yMin -= padding; yMax += padding;
    }

    const gridMarkLines = gridLines.map(p => ({ yAxis: parseFloat(p), lineStyle: { color: '#e5e7eb', type: 'dotted', width: 1 }, label: { show: false }, silent: true }));
    const orderMarkLines = activeOrders.map(o => ({
        yAxis: parseFloat(o.price),
        lineStyle: { color: o.side === 'buy' ? '#0ecb81' : '#f6465d', type: 'solid', width: 1.5 },
        label: { show: true, position: 'end', formatter: (o.side === 'buy' ? 'C' : 'V') + ' ' + fmtPrice(o.price), color: '#fff', backgroundColor: o.side === 'buy' ? '#0ecb81' : '#f6465d', padding: [3, 5], borderRadius: 3, fontSize: 10 }
    }));

    const option = { 
        animation: false, grid: { left: 10, right: 85, top: 10, bottom: 20, containLabel: true }, 
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, formatter: function (params) { if(!params.length) return ''; return `<b>${params[0].axisValue}</b><br/>Precio: ${fmtPrice(params[0].data[1])}`; } }, 
        xAxis: { type: 'category', data: data.map(i => i[0]), scale: true, boundaryGap: false, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { show: false } }, 
        yAxis: { type: 'value', position: 'right', min: yMin, max: yMax, splitLine: { show: true, lineStyle: { color: '#f3f4f6' } }, axisLabel: { formatter: (v) => fmtPrice(v), fontSize: 10 } }, 
        series: [{ type: 'line', data: priceData, showSymbol: false, lineStyle: { width: 2, color: '#3b82f6' }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(59, 130, 246, 0.3)' }, { offset: 1, color: 'rgba(59, 130, 246, 0)' }]) }, markLine: { symbol: 'none', data: [...gridMarkLines, ...orderMarkLines], silent: true, animation: false } }] 
    };
    chart.setOption(option);
}