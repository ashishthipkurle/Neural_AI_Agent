import React, { useEffect, useRef, useCallback } from 'react';
import { createChart, IChartApi, CandlestickData, HistogramData, ColorType, CandlestickSeries, HistogramSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';
import { useTradingStore, CandleData } from '../../../store/tradingStore';

interface CandlestickChartProps {
    candles: CandleData[];
    indicators?: any;
    signals?: any[];
    height?: number;
    activeTool?: string | null;
    mode?: 'AI' | 'BB' | 'COMBINED';
    title?: string;
}

const CandlestickChart: React.FC<CandlestickChartProps> = ({ candles, indicators, signals, height = 420, activeTool = null, mode = 'COMBINED', title }) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const candleSeriesRef = useRef<any>(null);
    const volumeSeriesRef = useRef<any>(null);
    const bbUpperSeriesRef = useRef<any>(null);
    const bbMiddleSeriesRef = useRef<any>(null);
    const bbLowerSeriesRef = useRef<any>(null);
    const markersPluginRef = useRef<any>(null);

    // Create chart once
    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
            layout: {
                background: { type: ColorType.Solid, color: '#000000' },
                textColor: '#888888',
                fontSize: 11,
                fontFamily: "'Inter', 'JetBrains Mono', sans-serif",
            },
            grid: {
                vertLines: { color: '#1a1a1a' },
                horzLines: { color: '#1a1a1a' },
            },
            crosshair: {
                mode: 0,
                vertLine: { color: 'rgba(255, 255, 255, 0.2)', width: 1, style: 2 },
                horzLine: { color: 'rgba(255, 255, 255, 0.2)', width: 1, style: 2 },
            },
            rightPriceScale: {
                borderColor: '#222222',
                scaleMargins: { top: 0.05, bottom: 0.2 },
            },
            timeScale: {
                borderColor: '#222222',
                timeVisible: true,
                secondsVisible: false,
            },
        });

        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#00e676',
            downColor: '#ff5252',
            borderDownColor: '#ff5252',
            borderUpColor: '#00e676',
            wickDownColor: '#ff5252',
            wickUpColor: '#00e676',
        });

        const volumeSeries = chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' },
            priceScaleId: '',
        });
        volumeSeries.priceScale().applyOptions({
            scaleMargins: { top: 0.85, bottom: 0 },
        });

        const bbUpperSeries = chart.addSeries(LineSeries, { color: 'rgba(255, 255, 255, 0.3)', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false });
        const bbMiddleSeries = chart.addSeries(LineSeries, { color: 'rgba(255, 165, 0, 0.5)', lineWidth: 1, crosshairMarkerVisible: false });
        const bbLowerSeries = chart.addSeries(LineSeries, { color: 'rgba(255, 255, 255, 0.3)', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false });

        chartRef.current = chart;
        candleSeriesRef.current = candleSeries;
        volumeSeriesRef.current = volumeSeries;
        bbUpperSeriesRef.current = bbUpperSeries;
        bbMiddleSeriesRef.current = bbMiddleSeries;
        bbLowerSeriesRef.current = bbLowerSeries;

        // Initialize markers plugin
        markersPluginRef.current = createSeriesMarkers(candleSeries, []);


        // Handle resize
        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: chartContainerRef.current.clientHeight
                });
            }
        };
        const observer = new ResizeObserver(handleResize);
        observer.observe(chartContainerRef.current);

        return () => {
            observer.disconnect();
            chart.remove();
            chartRef.current = null;
        };
    }, [height]);

    // Track previous candle count for smart update detection
    const prevCandleCountRef = useRef(0);
    // Track previous first/last timestamps to detect dataset changes
    const prevFirstTimeRef = useRef<number>(0);
    const prevLastTimeRef = useRef<number>(0);
    // Track initial render for fitting content
    const hasFittedContent = useRef(false);
    // Track created price lines so we can remove them on re-render
    const priceLinesRef = useRef<any[]>([]);

    // Update data when candles change
    useEffect(() => {
        if (!candleSeriesRef.current || !volumeSeriesRef.current || !candles.length) return;

        // Remove old price lines before adding new ones
        for (const pl of priceLinesRef.current) {
            try { candleSeriesRef.current.removePriceLine(pl); } catch (_) { /* ignore */ }
        }
        priceLinesRef.current = [];

        const candleData: CandlestickData[] = candles.map(c => ({
            time: (typeof c.time === 'number' ? c.time : Number(c.time)) as any,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }));

        const volumeData: HistogramData[] = candles.map(c => ({
            time: (typeof c.time === 'number' ? c.time : Number(c.time)) as any,
            value: c.volume,
            color: c.close >= c.open ? 'rgba(0, 230, 118, 0.15)' : 'rgba(255, 82, 82, 0.15)',
        }));

        const prevCount = prevCandleCountRef.current;
        const curFirstTime = candleData[0]?.time as number || 0;
        const curLastTime = candleData[candleData.length - 1]?.time as number || 0;

        // Detect if this is truly a live tick update vs a dataset change
        const sameDataset = prevFirstTimeRef.current === curFirstTime;
        const isLiveTick = prevCount > 0 && sameDataset && Math.abs(candles.length - prevCount) <= 1;

        if (isLiveTick) {
            // Smart update: only update the last candle(s) to preserve scroll/zoom
            try {
                const lastCandle = candleData[candleData.length - 1];
                const lastVolume = volumeData[volumeData.length - 1];
                candleSeriesRef.current.update(lastCandle);
                volumeSeriesRef.current.update(lastVolume);
                // If a new candle was added (count increased), also add the previous one
                if (candles.length > prevCount && candleData.length >= 2) {
                    candleSeriesRef.current.update(candleData[candleData.length - 2]);
                    volumeSeriesRef.current.update(volumeData[volumeData.length - 2]);
                }
            } catch (updateErr) {
                // Fallback to full reload if update fails
                candleSeriesRef.current.setData(candleData);
                volumeSeriesRef.current.setData(volumeData);
            }
        } else {
            // Full reload: first load, symbol/timeframe changed, or dataset shifted
            candleSeriesRef.current.setData(candleData);
            volumeSeriesRef.current.setData(volumeData);
        }

        prevCandleCountRef.current = candles.length;
        prevFirstTimeRef.current = curFirstTime;
        prevLastTimeRef.current = curLastTime;

        // Add Bollinger Bands data if available
        if (indicators?.bollinger && bbUpperSeriesRef.current) {
            const { upper, middle, lower } = indicators.bollinger;
            if (upper && upper.length > 0 && candles.length > 0) {
                // Align from the end (most recent data) when lengths differ
                const len = Math.min(upper.length, candles.length);
                const candleOffset = candles.length - len;
                const indOffset = upper.length - len;

                const upperData = [];
                const middleData = [];
                const lowerData = [];

                for (let i = 0; i < len; i++) {
                    const time = candles[candleOffset + i].time as any;
                    const uVal = upper[indOffset + i];
                    const mVal = middle[indOffset + i];
                    const lVal = lower[indOffset + i];

                    if (!isNaN(uVal) && uVal !== 0) upperData.push({ time, value: uVal });
                    if (!isNaN(mVal) && mVal !== 0) middleData.push({ time, value: mVal });
                    if (!isNaN(lVal) && lVal !== 0) lowerData.push({ time, value: lVal });
                }

                bbUpperSeriesRef.current.setData(upperData);
                bbMiddleSeriesRef.current.setData(middleData);
                bbLowerSeriesRef.current.setData(lowerData);
            }
        }
        // ═══════════════════════════════════════════════════════════
        // UNIFIED SIGNAL MARKERS — Bollinger + Momentum + RSI Divergence
        // ═══════════════════════════════════════════════════════════
        const allMarkers: any[] = [];
        let lastAutoDir: 'LONG' | 'SHORT' | null = null;
        let lastAutoPrice: number = 0;
        let lastAutoIndex: number = -1;
        let signalInvalidated = false;

        if ((mode === 'BB' || mode === 'COMBINED') && indicators?.bollinger && candles.length > 2 && markersPluginRef.current) {
            const { upper, middle, lower } = indicators.bollinger;
            const rsiData = indicators?.rsi || [];
            const len = Math.min(upper?.length || 0, candles.length);
            const candleOffset = candles.length - len;
            const indOffset = (upper?.length || 0) - len;
            const rsiOffset = rsiData.length - len;

            if (len > 2 && upper && lower && middle) {
                for (let i = 1; i < len; i++) {
                    const c = candles[candleOffset + i];
                    const prevC = candles[candleOffset + i - 1];
                    const u = upper[indOffset + i];
                    const l = lower[indOffset + i];
                    const prevU = upper[indOffset + i - 1];
                    const prevL = lower[indOffset + i - 1];
                    const m = middle[indOffset + i];

                    if (!u || !l || !prevU || !prevL || u === 0 || l === 0) continue;

                    // Get RSI value if available
                    const rsi = rsiOffset >= 0 && rsiData[rsiOffset + i] ? rsiData[rsiOffset + i] : 50;
                    const prevRsi = rsiOffset >= 0 && rsiData[rsiOffset + i - 1] ? rsiData[rsiOffset + i - 1] : 50;

                    // Volume spike detection (current volume > 1.5x average of last 10 bars)
                    let volumeSpike = false;
                    if (i >= 10) {
                        const avgVol = candles.slice(candleOffset + i - 10, candleOffset + i)
                            .reduce((sum: number, cc: any) => sum + (cc.volume || 0), 0) / 10;
                        volumeSpike = c.volume > avgVol * 1.5;
                    }

                    // ── BUY signal: Bollinger bounce + RSI confirmation ──
                    // Price was below lower band and crossed back up, with RSI turning up from oversold
                    const bbBuySignal = prevC.close <= prevL && c.close > l;
                    const rsiBullishDiv = rsi > prevRsi && rsi < 40; // RSI turning up from low level
                    const momentumBuy = c.close > prevC.close && prevC.close < candles[candleOffset + Math.max(0, i - 2)]?.close;

                    if (bbBuySignal || (rsiBullishDiv && momentumBuy && c.close < m)) {
                        const signalType = bbBuySignal ? 'BUY Signal' : '📈 Momentum Buy';
                        allMarkers.push({
                            time: c.time as any,
                            position: 'belowBar' as const,
                            color: '#00e676',
                            shape: 'arrowUp' as const,
                            text: signalType,
                        });
                        lastAutoDir = 'LONG';
                        lastAutoPrice = c.close;
                        lastAutoIndex = candleOffset + i;
                        signalInvalidated = false;
                    }

                    // ── SELL signal: Bollinger rejection + RSI confirmation ──
                    const bbSellSignal = prevC.close >= prevU && c.close < u;
                    const rsiBearishDiv = rsi < prevRsi && rsi > 60; // RSI turning down from high level
                    const momentumSell = c.close < prevC.close && prevC.close > candles[candleOffset + Math.max(0, i - 2)]?.close;

                    if (bbSellSignal || (rsiBearishDiv && momentumSell && c.close > m)) {
                        const signalType = bbSellSignal ? 'SELL Signal' : '📉 Momentum Sell';
                        allMarkers.push({
                            time: c.time as any,
                            position: 'aboveBar' as const,
                            color: '#ff5252',
                            shape: 'arrowDown' as const,
                            text: signalType,
                        });
                        lastAutoDir = 'SHORT';
                        lastAutoPrice = c.close;
                        lastAutoIndex = candleOffset + i;
                        signalInvalidated = false;
                    }
                }
            }
        }

        // ═══════════════════════════════════════════════════════════
        // ACTIVE TRADE SIGNAL markers + Entry/Stop/Target price lines
        // ═══════════════════════════════════════════════════════════
        if (signals && signals.length > 0 && candles.length > 0 && candleSeriesRef.current) {
            for (const sig of signals) {
                let closestCandle = candles[candles.length - 1];
                let minDiff = Infinity;
                const sigTime = sig.created_at || (Date.now() / 1000);
                for (const c of candles) {
                    const diff = Math.abs((c.time as number) - sigTime);
                    if (diff < minDiff) { minDiff = diff; closestCandle = c; }
                }

                const lastClose = candles[candles.length - 1].close;
                const entryPrice = sig.entry_price || 0;
                let currentStop = sig.stop_price || 0;
                let currentTarget = sig.target_price || 0;

                // ── Check if signal has been INVALIDATED (stop loss breached) ──
                let isInvalidated = false;
                if (entryPrice > 0 && currentStop > 0) {
                    if (sig.direction === 'LONG' && lastClose < currentStop) {
                        isInvalidated = true;
                    } else if (sig.direction === 'SHORT' && lastClose > currentStop) {
                        isInvalidated = true;
                    }
                }

                if (isInvalidated) {
                    // Show the stopped-out marker instead of the original signal
                    allMarkers.push({
                        time: candles[candles.length - 1].time as any,
                        position: 'aboveBar' as const,
                        color: '#ffa726',
                        shape: 'circle' as const,
                        text: `⛔ STOPPED OUT`,
                    });
                    // Don't draw stale entry/stop/target lines for invalidated signals
                    continue;
                }

                // Trade entry arrow marker
                allMarkers.push({
                    time: closestCandle.time as any,
                    position: sig.direction === 'LONG' ? 'belowBar' as const : 'aboveBar' as const,
                    color: sig.direction === 'LONG' ? '#4cff91' : '#ff6b6b',
                    shape: sig.direction === 'LONG' ? 'arrowUp' as const : 'arrowDown' as const,
                    text: `${sig.direction} @ ${sig.entry_price?.toFixed(2) || 'Market'}`,
                });

                // ── Dynamic Trailing Stop & Extended Target ──
                if (entryPrice > 0) {
                    const range = Math.abs(currentTarget - entryPrice) || entryPrice * 0.01;

                    // Trail stop loss when price moves in favor
                    if (sig.direction === 'LONG' && currentTarget > 0 && lastClose > currentTarget) {
                        currentTarget = lastClose + range;
                        currentStop = Math.max(currentStop, entryPrice);
                    } else if (sig.direction === 'SHORT' && currentTarget > 0 && lastClose < currentTarget) {
                        currentTarget = lastClose - range;
                        currentStop = Math.min(currentStop, entryPrice);
                    }
                }

                // Entry price line
                if (entryPrice > 0) {
                    const pl = candleSeriesRef.current.createPriceLine({
                        price: entryPrice,
                        color: sig.direction === 'LONG' ? '#00e676' : '#ff5252',
                        lineWidth: 1, lineStyle: 0,
                        axisLabelVisible: true,
                        title: `${sig.direction} Entry`,
                    });
                    priceLinesRef.current.push(pl);
                }

                if (currentStop > 0) {
                    const pl = candleSeriesRef.current.createPriceLine({
                        price: currentStop,
                        color: '#ff5252',
                        lineWidth: 1, lineStyle: 2,
                        axisLabelVisible: true,
                        title: 'Stop Loss',
                    });
                    priceLinesRef.current.push(pl);
                }

                if (currentTarget > 0) {
                    const pl = candleSeriesRef.current.createPriceLine({
                        price: currentTarget,
                        color: '#00e676',
                        lineWidth: 1, lineStyle: 2,
                        axisLabelVisible: true,
                        title: 'Target',
                    });
                    priceLinesRef.current.push(pl);
                }
            }
        }



        // ═══════════════════════════════════════════════════════════
        // BOLLINGER TARGET/STOP LINES (if mode is BB or COMBINED)
        // ═══════════════════════════════════════════════════════════
        if ((mode === 'BB' || mode === 'COMBINED') && (!signals || signals.length === 0) && indicators?.bollinger && candles.length > 0 && candleSeriesRef.current) {
            const { upper, lower } = indicators.bollinger;
            const lastClose = candles[candles.length - 1].close;

            if (upper && lower && upper.length > 0 && lastAutoDir && !signalInvalidated) {
                const lastUpper = upper[upper.length - 1];
                const lastLower = lower[lower.length - 1];

                if (lastUpper > 0 && lastLower > 0 && lastAutoPrice > 0) {
                    const bbWidth = lastUpper - lastLower;
                    const atrEstimate = bbWidth / 4; 

                    let targetPrice = lastAutoDir === 'LONG' ? lastUpper : lastLower;
                    let stopPrice = lastAutoDir === 'LONG' ? lastLower : lastUpper;

                    const stopBreached = (lastAutoDir === 'LONG' && lastClose < stopPrice) ||
                                        (lastAutoDir === 'SHORT' && lastClose > stopPrice);

                    if (stopBreached) {
                        signalInvalidated = true;
                    } else {
                        if (lastAutoDir === 'LONG' && lastClose > lastAutoPrice + atrEstimate) {
                            stopPrice = Math.max(stopPrice, lastAutoPrice);
                        } else if (lastAutoDir === 'SHORT' && lastClose < lastAutoPrice - atrEstimate) {
                            stopPrice = Math.min(stopPrice, lastAutoPrice);
                        }

                        const entryPl = candleSeriesRef.current.createPriceLine({
                            price: lastAutoPrice,
                            color: lastAutoDir === 'LONG' ? '#00e676' : '#ff5252',
                            lineWidth: 1, lineStyle: 0,
                            axisLabelVisible: true, title: `${lastAutoDir} Entry`,
                        });
                        priceLinesRef.current.push(entryPl);

                        const plTarget = candleSeriesRef.current.createPriceLine({
                            price: targetPrice,
                            color: '#00e676', lineWidth: 1, lineStyle: 2,
                            axisLabelVisible: true, title: 'Target',
                        });
                        priceLinesRef.current.push(plTarget);

                        const plStop = candleSeriesRef.current.createPriceLine({
                            price: stopPrice,
                            color: '#ff5252', lineWidth: 1, lineStyle: 2,
                            axisLabelVisible: true, title: 'Stop Loss',
                        });
                        priceLinesRef.current.push(plStop);
                    }
                }
            }
        }

        // ═══════════════════════════════════════════════════════════
        // ML PREDICTION — Forward-looking AI signal (if mode is AI or COMBINED)
        // ═══════════════════════════════════════════════════════════
        if ((mode === 'AI' || mode === 'COMBINED') && indicators?.ml_prediction && candles.length > 0 && candleSeriesRef.current) {
            const ml = indicators.ml_prediction;
            if (ml.confidence > 0.55) { // Only show if confidence > 55%
                const lastCandle = candles[candles.length - 1];

                // Prediction arrow marker on the LAST candle
                allMarkers.push({
                    time: lastCandle.time as any,
                    position: ml.direction === 'UP' ? 'belowBar' as const : 'aboveBar' as const,
                    color: ml.direction === 'UP' ? '#00bcd4' : '#e040fb',
                    shape: ml.direction === 'UP' ? 'arrowUp' as const : 'arrowDown' as const,
                    text: `🤖 AI ${ml.direction} (${(ml.confidence * 100).toFixed(0)}%)`,
                });

                // ML Entry price line
                if (ml.entry_price > 0) {
                    const pl = candleSeriesRef.current.createPriceLine({
                        price: ml.entry_price,
                        color: ml.direction === 'UP' ? '#00bcd4' : '#e040fb',
                        lineWidth: 2, lineStyle: 1, // dashed
                        axisLabelVisible: true,
                        title: `AI ${ml.direction === 'UP' ? 'LONG' : 'SHORT'} Entry`,
                    });
                    priceLinesRef.current.push(pl);
                }

                // ML Stop Loss
                if (ml.stop_price > 0) {
                    const pl = candleSeriesRef.current.createPriceLine({
                        price: ml.stop_price,
                        color: '#ff1744',
                        lineWidth: 1, lineStyle: 3, // dotted
                        axisLabelVisible: true,
                        title: 'AI Stop',
                    });
                    priceLinesRef.current.push(pl);
                }

                // ML Target
                if (ml.target_price > 0) {
                    const pl = candleSeriesRef.current.createPriceLine({
                        price: ml.target_price,
                        color: '#00e5ff',
                        lineWidth: 1, lineStyle: 3, // dotted
                        axisLabelVisible: true,
                        title: 'AI Target',
                    });
                    priceLinesRef.current.push(pl);
                }
            }
        }

        // Set all markers (sorted by time)
        if (markersPluginRef.current) {
            allMarkers.sort((a, b) => (a.time as number) - (b.time as number));
            markersPluginRef.current.setMarkers(allMarkers);
        }

        // Only fit content on the very first data load
        if (!hasFittedContent.current && chartRef.current) {
            chartRef.current.timeScale().fitContent();
            hasFittedContent.current = true;
        }
    }, [candles, signals, indicators]);

    // --- Drawing Tool State ---
    const [drawings, setDrawings] = React.useState<{ x1: number, y1: number, x2: number, y2: number }[]>([]);
    const [currentDrawing, setCurrentDrawing] = React.useState<{ x1: number, y1: number, x2: number, y2: number } | null>(null);

    // Handle clear
    useEffect(() => {
        if (activeTool === 'clear_drawings') {
            setDrawings([]);
        }
    }, [activeTool]);

    const handleMouseDown = (e: React.MouseEvent) => {
        // Only allow drawing for specific line-based tools for now
        const supportedDrawingTools = ['trendline', 'hline', 'vline', 'ray', 'brush', 'rectangle'];
        if (!activeTool || !supportedDrawingTools.includes(activeTool)) return;

        const rect = e.currentTarget.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        setCurrentDrawing({ x1: x, y1: y, x2: x, y2: y });
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!currentDrawing) return;

        const rect = e.currentTarget.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        setCurrentDrawing(prev => prev ? { ...prev, x2: x, y2: y } : null);
    };

    const handleMouseUp = () => {
        if (currentDrawing) {
            setDrawings(prev => [...prev, currentDrawing]);
            setCurrentDrawing(null);
        }
    };

    return (
        <div
            style={{ width: '100%', height: '100%', position: 'relative' }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
        >
            <style>{`
                /* Hide TradingView watermark/logo injected by lightweight-charts */
                #tv-attr-logo,
                a[href*="tradingview.com"] {
                    display: none !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                    visibility: hidden !important;
                }
            `}</style>

            {title && (
                <div style={{
                    position: 'absolute',
                    top: '8px',
                    left: '8px',
                    zIndex: 10,
                    padding: '4px 8px',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(17, 17, 17, 0.8)',
                    border: '1px solid #333',
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    pointerEvents: 'none',
                    backdropFilter: 'blur(4px)'
                }}>
                    {title}
                </div>
            )}
            <div
                ref={chartContainerRef}
                style={{
                    width: '100%',
                    height: '100%',
                    minHeight: '300px',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    border: '1px solid #1a1a1a',
                    pointerEvents: activeTool && ['trendline', 'hline', 'vline', 'ray', 'brush', 'rectangle'].includes(activeTool) ? 'none' : 'auto'
                }}
            />

            {/* Drawing Overlay */}
            <svg
                style={{
                    position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                    pointerEvents: 'none', zIndex: 10
                }}
            >
                {drawings.map((d, i) => (
                    <line key={i} x1={d.x1} y1={d.y1} x2={d.x2} y2={d.y2} stroke="#00e676" strokeWidth={2} />
                ))}
                {currentDrawing && (
                    <line x1={currentDrawing.x1} y1={currentDrawing.y1} x2={currentDrawing.x2} y2={currentDrawing.y2} stroke="#00e676" strokeWidth={2} strokeDasharray="4" />
                )}
            </svg>
        </div>
    );
};

export default CandlestickChart;
