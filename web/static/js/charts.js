import { fmtUSDC, fmtInt } from './utils.js';

// Cache para instancias de Lightweight Charts
let chartInstances = {};

// Mantenemos ECharts SOLO para los Donuts (Pie Charts)
let donutCache = {};
export function renderDonut(domId, data, isCurrency = false) {
    const dom = document.getElementById(domId);
    if (!dom) return;
    const chart = echarts.getInstanceByDom(dom) || echarts.init(dom);
    const chartData = (data && data.length > 0) ? data : [{value: 0, name: 'Sin Datos'}];
    
    const cacheKey = domId + JSON.stringify(chartData);
    if (donutCache[cacheKey]) return;
    donutCache[cacheKey] = true;

    chart.setOption({ 
        tooltip: { trigger: 'item', formatter: function(params) { const val = isCurrency ? fmtUSDC(params.value) : fmtInt(params.value); return `${params.name}: ${val} (${params.percent}%)`; } }, 
        legend: { orient: 'vertical', left: '0%', top: 'center', itemGap: 10, textStyle: { fontSize: 11, color: '#6b7280' } }, 
        series: [{ type: 'pie', radius: ['40%', '80%'], center: ['65%', '50%'], label: { show: false, position: 'center' }, emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } }, data: chartData }] 
    });
}

// Nueva implementación con Lightweight Charts (TradingView) para líneas de Balance
export function renderLineChart(domId, data, color) {
    if (typeof LightweightCharts === 'undefined') {
        console.error("LightweightCharts no está cargado. Revisa tu conexión.");
        return;
    }

    const dom = document.getElementById(domId);
    if (!dom) return;
    if (!data || data.length === 0) return;

    dom.style.position = 'relative';

    if (!chartInstances[domId]) {
        dom.innerHTML = ''; 
        const chart = LightweightCharts.createChart(dom, {
            layout: { background: { color: 'transparent' }, textColor: '#333' },
            grid: { vertLines: { color: '#f0f3fa' }, horzLines: { color: '#f0f3fa' } },
            rightPriceScale: { 
                borderVisible: false,
                scaleMargins: { top: 0.1, bottom: 0.1 } 
            },
            timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
            handleScroll: { mouseWheel: false, pressedMouseMove: false },
            handleScale: { axisPressedMouseMove: false, mouseWheel: false, pinch: false }
        });

        const series = chart.addAreaSeries({
            lineColor: color,
            topColor: color, 
            bottomColor: 'rgba(255, 255, 255, 0)',
            lineWidth: 2,
        });

        chartInstances[domId] = { chart, series };

        new ResizeObserver(entries => {
            if (entries.length === 0 || !entries[0].contentRect) return;
            const { width, height } = entries[0].contentRect;
            chart.applyOptions({ width, height });
            chart.timeScale().fitContent(); 
        }).observe(dom);
    }

    const formattedData = data.map(d => ({
        time: d[0] / 1000, 
        value: d[1]
    }));

    const uniqueData = [];
    const seenTimes = new Set();
    formattedData.sort((a, b) => a.time - b.time);
    
    formattedData.forEach(item => {
        if (!seenTimes.has(item.time)) {
            seenTimes.add(item.time);
            uniqueData.push(item);
        }
    });

    chartInstances[domId].series.setData(uniqueData);
    chartInstances[domId].chart.timeScale().fitContent();
}

// Implementación DUAL OPTIMIZADA (Velas o Línea)
export function renderCandleChart(safeSym, data, gridLines, activeOrders = [], chartType = 'candles') {
    if (typeof LightweightCharts === 'undefined') return;

    const domId = `chart-${safeSym}`;
    const dom = document.getElementById(domId);
    if(!dom) return;
    if (!data || data.length === 0) return;

    dom.style.position = 'relative';

    // 1. Crear gráfico solo si no existe
    if (!chartInstances[domId]) {
        dom.innerHTML = '';
        const chart = LightweightCharts.createChart(dom, {
            layout: { background: { color: '#ffffff' }, textColor: '#333' },
            grid: { vertLines: { color: '#f0f3fa' }, horzLines: { color: '#f0f3fa' } },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            
            // CONFIGURACIÓ PER SEPARAR ETIQUETES
            leftPriceScale: {
                visible: true,
                borderColor: '#d1d4dc',
                scaleMargins: { top: 0.1, bottom: 0.1 }
            },
            rightPriceScale: {
                visible: true,
                borderColor: '#d1d4dc',
                textColor: 'rgba(255, 255, 255, 0)', // Text invisible
                scaleMargins: { top: 0.1, bottom: 0.1 }
            },
            timeScale: { 
                borderColor: '#d1d4dc', 
                timeVisible: true, 
                secondsVisible: false,
                rightOffset: 2, 
            },
        });

        const mainSeries = chart.addCandlestickSeries({
            upColor: '#0ecb81', downColor: '#f6465d',
            borderUpColor: '#0ecb81', borderDownColor: '#f6465d',
            wickUpColor: '#0ecb81', wickDownColor: '#f6465d',
            priceScaleId: 'right' 
        });

        const axisSeries = chart.addLineSeries({
            color: 'rgba(0,0,0,0)', 
            lineWidth: 1,
            priceScaleId: 'left',
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false
        });

        // ESTAT INICIAL
        chartInstances[domId] = { 
            chart, 
            mainSeries,
            axisSeries,
            activeType: 'candles',
            activeLines: [],
            initialZoomDone: false // BANDERA DE CONTROL DE ZOOM
        };

        new ResizeObserver(entries => {
            if (entries.length === 0 || !entries[0].contentRect) return;
            const { width, height } = entries[0].contentRect;
            chart.applyOptions({ width, height });
        }).observe(dom);
    }

    const { chart, axisSeries } = chartInstances[domId];

    // 2. Gestionar cambio de tipo
    if (chartInstances[domId].activeType !== chartType) {
        chart.removeSeries(chartInstances[domId].mainSeries);
        
        let newSeries;
        if (chartType === 'line') {
            newSeries = chart.addAreaSeries({
                lineColor: '#2962FF', topColor: 'rgba(41, 98, 255, 0.3)', bottomColor: 'rgba(41, 98, 255, 0)', lineWidth: 2,
                priceScaleId: 'right'
            });
        } else {
            newSeries = chart.addCandlestickSeries({
                upColor: '#0ecb81', downColor: '#f6465d', borderUpColor: '#0ecb81', borderDownColor: '#f6465d', wickUpColor: '#0ecb81', wickDownColor: '#f6465d',
                priceScaleId: 'right'
            });
        }
        
        chartInstances[domId].mainSeries = newSeries;
        chartInstances[domId].activeType = chartType;
        chartInstances[domId].activeLines = [];
    }

    const mainSeries = chartInstances[domId].mainSeries;

    // 3. Formatear datos
    const formattedData = data.map(d => {
        const dateParts = d[0].split(/[- :]/); 
        const dateObj = new Date(dateParts[0], dateParts[1]-1, dateParts[2], dateParts[3], dateParts[4]);
        const timeVal = dateObj.getTime() / 1000;
        return {
            time: timeVal,
            open: parseFloat(d[1]), high: parseFloat(d[4]), low: parseFloat(d[3]), close: parseFloat(d[2]),
            value: parseFloat(d[2]) 
        };
    });

    const uniqueData = [];
    const seenTimes = new Set();
    formattedData.sort((a, b) => a.time - b.time);
    formattedData.forEach(item => {
        if (!seenTimes.has(item.time)) {
            seenTimes.add(item.time);
            uniqueData.push(item);
        }
    });

    // 4. Actualizar datos
    mainSeries.setData(uniqueData);
    
    const lineData = uniqueData.map(d => ({ time: d.time, value: d.close }));
    axisSeries.setData(lineData);

    // 5. Gestionar Línies
    chartInstances[domId].activeLines.forEach(line => {
        mainSeries.removePriceLine(line);
    });
    chartInstances[domId].activeLines = [];

    // Pintar Órdenes Activas
    activeOrders.forEach(o => {
        const isBuy = o.side === 'buy';
        const line = mainSeries.createPriceLine({
            price: parseFloat(o.price),
            color: isBuy ? '#0ecb81' : '#f6465d',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            axisLabelVisible: true,
            title: (isBuy ? 'C' : 'V') + ` ${fmtInt(o.amount)}`,
        });
        chartInstances[domId].activeLines.push(line);
    });
    
    // 6. CONTROL DEL ZOOM (NOMÉS LA PRIMERA VEGADA O RESET)
    if (!chartInstances[domId].initialZoomDone) {
        const visibleRange = 100;
        const totalData = uniqueData.length;
        
        if (totalData > visibleRange) {
            chart.timeScale().setVisibleLogicalRange({
                from: totalData - visibleRange,
                to: totalData
            });
        } else {
            chart.timeScale().fitContent();
        }
        chartInstances[domId].initialZoomDone = true;
    }
}

// --- FUNCIÓ NOVA PER RESETEJAR ZOOM ---
export function resetChartZoom(safeSym) {
    const domId = `chart-${safeSym}`;
    if (chartInstances[domId]) {
        chartInstances[domId].initialZoomDone = false;
    }
}
