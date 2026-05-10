import React, { useEffect, useRef, useCallback } from 'react';
import { createChart, IChartApi, CandlestickData, HistogramData, ColorType, CandlestickSeries, HistogramSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';
import { useTradingStore, CandleData } from '../../../store/tradingStore';

interface CandlestickChartProps {
    candles: CandleData[];
    indicators?: any;
    signals?: any[];
    height?: number;
}

const CandlestickChart: React.FC<CandlestickChartProps> = ({ candles, indicators, signals, height = 420 }) => {
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
            time: c.time as any,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }));

        const volumeData: HistogramData[] = candles.map(c => ({
            time: c.time as any,
            value: c.volume,
            color: c.close >= c.open ? 'rgba(0, 230, 118, 0.15)' : 'rgba(255, 82, 82, 0.15)',
        }));

        candleSeriesRef.current.setData(candleData);
        volumeSeriesRef.current.setData(volumeData);

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
        // UNIFIED SIGNAL MARKERS (BB crossovers) — BOTH US & INDIA
        // ═══════════════════════════════════════════════════════════
        const allMarkers: any[] = [];
        let lastAutoDir: 'LONG' | 'SHORT' | null = null;
        let lastAutoPrice: number = 0;

        if (indicators?.bollinger && candles.length > 2 && markersPluginRef.current) {
            const { upper, middle, lower } = indicators.bollinger;
            const len = Math.min(upper?.length || 0, candles.length);
            const candleOffset = candles.length - len;
            const indOffset = (upper?.length || 0) - len;

            if (len > 2 && upper && lower && middle) {
                for (let i = 1; i < len; i++) {
                    const c = candles[candleOffset + i];
                    const prevC = candles[candleOffset + i - 1];
                    const u = upper[indOffset + i];
                    const l = lower[indOffset + i];
                    const prevU = upper[indOffset + i - 1];
                    const prevL = lower[indOffset + i - 1];

                    if (!u || !l || !prevU || !prevL || u === 0 || l === 0) continue;

                    // BUY signal: price crosses UP from below the lower band
                    if (prevC.close <= prevL && c.close > l) {
                        allMarkers.push({
                            time: c.time as any,
                            position: 'belowBar' as const,
                            color: '#00e676',
                            shape: 'arrowUp' as const,
                            text: 'BUY Signal',
                        });
                        lastAutoDir = 'LONG';
                        lastAutoPrice = c.close;
                    }

                    // SELL signal: price crosses DOWN from above the upper band
                    if (prevC.close >= prevU && c.close < u) {
                        allMarkers.push({
                            time: c.time as any,
                            position: 'aboveBar' as const,
                            color: '#ff5252',
                            shape: 'arrowDown' as const,
                            text: 'SELL Signal',
                        });
                        lastAutoDir = 'SHORT';
                        lastAutoPrice = c.close;
                    }
                }
            }
        }

        // ═══════════════════════════════════════════════════════════
        // ACTIVE TRADE SIGNAL markers + Entry/Stop/Target price lines
        // ═══════════════════════════════════════════════════════════
        if (signals && signals.length > 0 && candles.length > 0 && candleSeriesRef.current) {
            for (const sig of signals) {
                // Find the closest candle to signal's created_at time
                let closestCandle = candles[candles.length - 1];
                let minDiff = Infinity;
                const sigTime = sig.created_at || (Date.now() / 1000);
                for (const c of candles) {
                    const diff = Math.abs((c.time as number) - sigTime);
                    if (diff < minDiff) { minDiff = diff; closestCandle = c; }
                }

                // Trade entry arrow marker
                allMarkers.push({
                    time: closestCandle.time as any,
                    position: sig.direction === 'LONG' ? 'belowBar' as const : 'aboveBar' as const,
                    color: sig.direction === 'LONG' ? '#4cff91' : '#ff6b6b',
                    shape: sig.direction === 'LONG' ? 'arrowUp' as const : 'arrowDown' as const,
                    text: `${sig.direction} @ ${sig.entry_price?.toFixed(2) || 'Market'}`,
                });

                // ── Dynamic Target & Stop Loss price lines ──
                // Check if current price has surpassed target or stop loss
                const lastClose = candles[candles.length - 1].close;
                let currentStop = sig.stop_price || 0;
                let currentTarget = sig.target_price || 0;
                const entryPrice = sig.entry_price || 0;

                if (entryPrice > 0) {
                    const range = Math.abs(currentTarget - entryPrice) || entryPrice * 0.01;

                    // If price surpassed the target, set new extended target & trail the stop
                    if (sig.direction === 'LONG' && currentTarget > 0 && lastClose > currentTarget) {
                        currentTarget = lastClose + range;
                        currentStop = Math.max(currentStop, entryPrice); // trail stop to entry (breakeven)
                    } else if (sig.direction === 'SHORT' && currentTarget > 0 && lastClose < currentTarget) {
                        currentTarget = lastClose - range;
                        currentStop = Math.min(currentStop, entryPrice);
                    }

                    // If price hit stop loss, show invalidated level
                    if (sig.direction === 'LONG' && currentStop > 0 && lastClose < currentStop) {
                        currentStop = lastClose - range * 0.5;
                        currentTarget = lastClose + range;
                    } else if (sig.direction === 'SHORT' && currentStop > 0 && lastClose > currentStop) {
                        currentStop = lastClose + range * 0.5;
                        currentTarget = lastClose - range;
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

                // Stop Loss price line
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

                // Target price line
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
        // AUTO-GENERATE Target/Stop from BB for charts WITHOUT signals
        // ═══════════════════════════════════════════════════════════
        if ((!signals || signals.length === 0) && indicators?.bollinger && candles.length > 0 && candleSeriesRef.current) {
            const { upper, lower } = indicators.bollinger;
            if (upper && lower && upper.length > 0 && lastAutoDir) {
                const lastUpper = upper[upper.length - 1];
                const lastLower = lower[lower.length - 1];
                
                if (lastUpper > 0 && lastLower > 0 && lastAutoPrice > 0) {
                    // Entry Price Line based on the last auto signal
                    const entryPl = candleSeriesRef.current.createPriceLine({
                        price: lastAutoPrice,
                        color: lastAutoDir === 'LONG' ? '#00e676' : '#ff5252',
                        lineWidth: 1, lineStyle: 0,
                        axisLabelVisible: true, title: `${lastAutoDir} Entry`,
                    });
                    priceLinesRef.current.push(entryPl);

                    // Set Target and Stop correctly based on trade direction
                    const targetPrice = lastAutoDir === 'LONG' ? lastUpper : lastLower;
                    const stopPrice = lastAutoDir === 'LONG' ? lastLower : lastUpper;

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

    return (
        <div
            ref={chartContainerRef}
            style={{
                width: '100%',
                height: '100%',
                minHeight: '300px',
                borderRadius: '8px',
                overflow: 'hidden',
                border: '1px solid #1a1a1a',
            }}
        />
    );
};

export default CandlestickChart;
