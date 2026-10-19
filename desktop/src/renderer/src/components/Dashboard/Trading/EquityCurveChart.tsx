import React, { useRef, useEffect, useState, useCallback } from 'react';

// ── Types ────────────────────────────────────────────────────
interface EquityPoint {
    timestamp: number;
    equity: number;
    cash: number;
    drawdown_pct: number;
}

interface BenchmarkPoint {
    timestamp: number;
    value: number;
}

interface EquityCurveChartProps {
    className?: string;
}

type TimeRange = '1D' | '1W' | '1M' | '3M' | 'YTD' | 'ALL';

const API = 'http://localhost:8000';

// ── Component ────────────────────────────────────────────────
export default function EquityCurveChart({ className = '' }: EquityCurveChartProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [data, setData] = useState<EquityPoint[]>([]);
    const [benchmarkData, setBenchmarkData] = useState<BenchmarkPoint[]>([]);
    const [range, setRange] = useState<TimeRange>('ALL');
    const [showBenchmark, setShowBenchmark] = useState(false);
    const [tooltip, setTooltip] = useState<{ x: number; y: number; point: EquityPoint } | null>(null);
    const [loading, setLoading] = useState(false);

    // Fetch equity curve data
    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API}/api/trading/equity-curve?limit=500`);
            if (res.ok) {
                const json = await res.json();
                setData(json.data || []);
            }
            // Fetch SPY benchmark data
            try {
                const bRes = await fetch(`${API}/api/trading/benchmark?symbol=SPY&limit=500`);
                if (bRes.ok) {
                    const bJson = await bRes.json();
                    setBenchmarkData(bJson.data || []);
                }
            } catch { /* Benchmark optional */ }
        } catch (e) {
            console.error('Failed to fetch equity curve:', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60000); // Refresh every 60s
        return () => clearInterval(interval);
    }, [fetchData]);

    // Filter data by time range
    const filteredData = React.useMemo(() => {
        if (!data.length) return [];
        const now = Date.now() / 1000;
        const cutoffs: Record<TimeRange, number> = {
            '1D': now - 86400,
            '1W': now - 604800,
            '1M': now - 2592000,
            '3M': now - 7776000,
            'YTD': new Date(new Date().getFullYear(), 0, 1).getTime() / 1000,
            'ALL': 0,
        };
        const cutoff = cutoffs[range];
        return data.filter(d => d.timestamp >= cutoff);
    }, [data, range]);

    // Draw chart
    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !container || filteredData.length < 2) return;

        const rect = container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        canvas.style.width = `${rect.width}px`;
        canvas.style.height = `${rect.height}px`;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.scale(dpr, dpr);

        const W = rect.width;
        const H = rect.height;
        const PAD_TOP = 20;
        const PAD_BOTTOM = 40;
        const PAD_LEFT = 60;
        const PAD_RIGHT = 20;
        const chartW = W - PAD_LEFT - PAD_RIGHT;
        const chartH = H - PAD_TOP - PAD_BOTTOM;

        // Clear
        ctx.fillStyle = '#0a0a0a';
        ctx.fillRect(0, 0, W, H);

        const equities = filteredData.map(d => d.equity);
        const drawdowns = filteredData.map(d => d.drawdown_pct || 0);
        const minEq = Math.min(...equities) * 0.995;
        const maxEq = Math.max(...equities) * 1.005;
        const eqRange = maxEq - minEq || 1;

        const toX = (i: number) => PAD_LEFT + (i / (filteredData.length - 1)) * chartW;
        const toY = (eq: number) => PAD_TOP + (1 - (eq - minEq) / eqRange) * chartH;

        // Grid lines
        ctx.strokeStyle = '#1a1a1a';
        ctx.lineWidth = 0.5;
        for (let i = 0; i <= 4; i++) {
            const y = PAD_TOP + (i / 4) * chartH;
            ctx.beginPath();
            ctx.moveTo(PAD_LEFT, y);
            ctx.lineTo(W - PAD_RIGHT, y);
            ctx.stroke();

            const val = maxEq - (i / 4) * eqRange;
            ctx.fillStyle = '#555';
            ctx.font = '10px monospace';
            ctx.textAlign = 'right';
            ctx.fillText(`$${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, PAD_LEFT - 8, y + 3);
        }

        // Gradient fill
        const gradient = ctx.createLinearGradient(0, PAD_TOP, 0, PAD_TOP + chartH);
        gradient.addColorStop(0, 'rgba(0, 200, 83, 0.25)');
        gradient.addColorStop(1, 'rgba(0, 200, 83, 0.02)');

        ctx.beginPath();
        ctx.moveTo(toX(0), PAD_TOP + chartH);
        filteredData.forEach((d, i) => ctx.lineTo(toX(i), toY(d.equity)));
        ctx.lineTo(toX(filteredData.length - 1), PAD_TOP + chartH);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        // Equity line
        ctx.beginPath();
        filteredData.forEach((d, i) => {
            if (i === 0) ctx.moveTo(toX(i), toY(d.equity));
            else ctx.lineTo(toX(i), toY(d.equity));
        });
        ctx.strokeStyle = '#00c853';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Drawdown overlay (red fill at bottom)
        if (drawdowns.some(d => d > 0)) {
            const maxDD = Math.max(...drawdowns, 0.01);
            const ddH = chartH * 0.2; // Bottom 20% of chart

            ctx.globalAlpha = 0.4;
            ctx.beginPath();
            ctx.moveTo(toX(0), PAD_TOP + chartH);
            filteredData.forEach((d, i) => {
                const ddY = PAD_TOP + chartH - (d.drawdown_pct / maxDD) * ddH;
                ctx.lineTo(toX(i), ddY);
            });
            ctx.lineTo(toX(filteredData.length - 1), PAD_TOP + chartH);
            ctx.closePath();
            ctx.fillStyle = '#ff1744';
            ctx.fill();
            ctx.globalAlpha = 1;
        }

        // SPY benchmark line (dashed yellow)
        if (showBenchmark && benchmarkData.length >= 2 && filteredData.length >= 2) {
            const startEq = filteredData[0].equity;
            const startBench = benchmarkData[0]?.value || 1;
            ctx.save();
            ctx.setLineDash([6, 4]);
            ctx.strokeStyle = '#FFD600';
            ctx.lineWidth = 1.5;
            ctx.globalAlpha = 0.7;
            ctx.beginPath();
            const benchLen = Math.min(benchmarkData.length, filteredData.length);
            for (let i = 0; i < benchLen; i++) {
                const normalizedVal = startEq * (benchmarkData[i].value / startBench);
                const y = toY(normalizedVal);
                if (i === 0) ctx.moveTo(toX(i), y);
                else ctx.lineTo(toX(i), y);
            }
            ctx.stroke();
            ctx.restore();
        }

        // Time labels on X axis
        ctx.fillStyle = '#555';
        ctx.font = '10px monospace';
        ctx.textAlign = 'center';
        const labelCount = Math.min(6, filteredData.length);
        for (let i = 0; i < labelCount; i++) {
            const idx = Math.round((i / (labelCount - 1)) * (filteredData.length - 1));
            const d = new Date(filteredData[idx].timestamp * 1000);
            const label = `${d.getMonth() + 1}/${d.getDate()}`;
            ctx.fillText(label, toX(idx), H - 8);
        }

    }, [filteredData]);

    // Mouse hover for tooltip
    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !container || filteredData.length < 2) return;

        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const W = rect.width;
        const PAD_LEFT = 60;
        const PAD_RIGHT = 20;
        const chartW = W - PAD_LEFT - PAD_RIGHT;

        const ratio = (mx - PAD_LEFT) / chartW;
        const idx = Math.round(ratio * (filteredData.length - 1));
        if (idx >= 0 && idx < filteredData.length) {
            setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, point: filteredData[idx] });
        }
    }, [filteredData]);

    const handleMouseLeave = useCallback(() => setTooltip(null), []);

    return (
        <div className={`flex flex-col bg-[#0a0a0a] rounded-xl border border-[#222] overflow-hidden ${className}`}>
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-[#222]">
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="text-[11px] font-bold tracking-wider text-white/80">EQUITY CURVE</span>
                </div>
                <div className="flex gap-1">
                    {(['1D', '1W', '1M', '3M', 'YTD', 'ALL'] as TimeRange[]).map(r => (
                        <button
                            key={r}
                            onClick={() => setRange(r)}
                            className={`text-[9px] font-mono px-1.5 py-0.5 rounded transition-colors ${
                                range === r
                                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                    : 'text-white/40 hover:text-white/70 border border-transparent'
                            }`}
                        >
                            {r}
                        </button>
                    ))}
                    <div className="w-px bg-white/10 mx-1" />
                    <button
                        onClick={() => setShowBenchmark(!showBenchmark)}
                        className={`text-[9px] font-mono px-1.5 py-0.5 rounded transition-colors ${
                            showBenchmark
                                ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                                : 'text-white/40 hover:text-white/70 border border-transparent'
                        }`}
                        title="Toggle SPY buy-and-hold benchmark"
                    >
                        SPY
                    </button>
                </div>
            </div>

            {/* Chart */}
            <div ref={containerRef} className="flex-1 relative min-h-[200px]">
                {filteredData.length < 2 ? (
                    <div className="w-full h-full flex items-center justify-center">
                        <span className="text-white/30 text-xs font-mono">
                            {loading ? 'Loading...' : 'Insufficient equity data'}
                        </span>
                    </div>
                ) : (
                    <>
                        <canvas
                            ref={canvasRef}
                            className="w-full h-full"
                            onMouseMove={handleMouseMove}
                            onMouseLeave={handleMouseLeave}
                        />
                        {tooltip && (
                            <div
                                className="absolute pointer-events-none bg-[#1a1a2e]/95 border border-[#333] rounded-lg px-3 py-2 text-[10px] font-mono shadow-xl z-10"
                                style={{ left: tooltip.x + 12, top: tooltip.y - 60 }}
                            >
                                <div className="text-white/50">{new Date(tooltip.point.timestamp * 1000).toLocaleDateString()}</div>
                                <div className="text-emerald-400 font-bold">${tooltip.point.equity.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
                                <div className="text-red-400">DD: {(tooltip.point.drawdown_pct * 100).toFixed(2)}%</div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
