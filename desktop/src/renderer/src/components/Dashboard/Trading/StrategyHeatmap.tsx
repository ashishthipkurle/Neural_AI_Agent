import React, { useEffect, useState, useCallback } from 'react';

// ── Types ────────────────────────────────────────────────────
interface StrategyRegimeStat {
    strategy: string;
    regime: string;
    total_trades: number;
    wins: number;
    losses: number;
    avg_pnl: number;
}

const API = 'http://localhost:8000';

const STRATEGIES = ['trend_following', 'mean_reversion', 'breakout', 'faiss_pattern'];
const REGIMES = ['TRENDING_VOLATILE', 'EXPANSION_BREAKOUT', 'MEAN_REVERTING', 'LOW_VOL_RANGE', 'QUIET'];

const STRATEGY_LABELS: Record<string, string> = {
    trend_following: 'Trend Following',
    mean_reversion: 'Mean Reversion',
    breakout: 'Breakout',
    faiss_pattern: 'FAISS Pattern',
};

const REGIME_LABELS: Record<string, string> = {
    TRENDING_VOLATILE: 'Trending',
    EXPANSION_BREAKOUT: 'Breakout',
    MEAN_REVERTING: 'Mean Rev',
    LOW_VOL_RANGE: 'Low Vol',
    QUIET: 'Quiet',
};

function getWinRateColor(winRate: number, trades: number): string {
    if (trades < 3) return 'bg-white/5 border-white/10';
    if (winRate >= 60) return 'bg-emerald-500/20 border-emerald-500/30';
    if (winRate >= 55) return 'bg-emerald-500/10 border-emerald-500/20';
    if (winRate >= 45) return 'bg-amber-500/10 border-amber-500/20';
    if (winRate >= 40) return 'bg-red-500/10 border-red-500/20';
    return 'bg-red-500/20 border-red-500/30';
}

function getWinRateTextColor(winRate: number, trades: number): string {
    if (trades < 3) return 'text-white/30';
    if (winRate >= 55) return 'text-emerald-400';
    if (winRate >= 45) return 'text-amber-400';
    return 'text-red-400';
}

// ── Component ────────────────────────────────────────────────
export default function StrategyHeatmap() {
    const [stats, setStats] = useState<StrategyRegimeStat[]>([]);
    const [tooltip, setTooltip] = useState<{ stat: StrategyRegimeStat; x: number; y: number } | null>(null);

    const fetchStats = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/trading/strategy-stats`);
            if (res.ok) {
                const json = await res.json();
                setStats(json.stats || []);
            }
        } catch (e) {
            console.error('Failed to fetch strategy stats:', e);
        }
    }, []);

    useEffect(() => {
        fetchStats();
        const interval = setInterval(fetchStats, 120000); // Refresh every 2 min
        return () => clearInterval(interval);
    }, [fetchStats]);

    const getStat = (strategy: string, regime: string): StrategyRegimeStat | null => {
        return stats.find(s => s.strategy === strategy && s.regime === regime) || null;
    };

    return (
        <div className="bg-[#0a0a0a] rounded-xl border border-[#222] overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-2 px-3 py-2 border-b border-[#222]">
                <div className="w-2 h-2 rounded-full bg-fuchsia-500" />
                <span className="text-[11px] font-bold tracking-wider text-white/80">STRATEGY x REGIME</span>
                <span className="text-[9px] text-white/30 font-mono ml-auto">{stats.length} entries</span>
            </div>

            {/* Heatmap Grid */}
            <div className="p-3 overflow-x-auto">
                <table className="w-full border-collapse">
                    <thead>
                        <tr>
                            <th className="text-[9px] font-mono text-white/40 text-left py-1 px-2 w-24"></th>
                            {REGIMES.map(regime => (
                                <th key={regime} className="text-[9px] font-mono text-white/50 text-center py-1 px-1 min-w-[80px]">
                                    {REGIME_LABELS[regime] || regime}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {STRATEGIES.map(strategy => (
                            <tr key={strategy}>
                                <td className="text-[10px] font-mono text-white/60 py-1 px-2 font-bold">
                                    {STRATEGY_LABELS[strategy] || strategy}
                                </td>
                                {REGIMES.map(regime => {
                                    const stat = getStat(strategy, regime);
                                    const total = stat?.total_trades || 0;
                                    const wins = stat?.wins || 0;
                                    const winRate = total > 0 ? (wins / total) * 100 : 0;

                                    return (
                                        <td key={regime} className="py-1 px-1">
                                            <div
                                                className={`rounded-lg border px-2 py-2 text-center cursor-default transition-all hover:scale-105 ${getWinRateColor(winRate, total)}`}
                                                onMouseEnter={(e) => {
                                                    if (stat && total > 0) {
                                                        const rect = e.currentTarget.getBoundingClientRect();
                                                        setTooltip({ stat, x: rect.left, y: rect.bottom + 4 });
                                                    }
                                                }}
                                                onMouseLeave={() => setTooltip(null)}
                                            >
                                                {total > 0 ? (
                                                    <>
                                                        <div className={`text-[11px] font-bold font-mono ${getWinRateTextColor(winRate, total)}`}>
                                                            {winRate.toFixed(0)}%
                                                        </div>
                                                        <div className="text-[8px] text-white/30 font-mono mt-0.5">
                                                            {wins}W / {total - wins}L
                                                        </div>
                                                    </>
                                                ) : (
                                                    <div className="text-[9px] text-white/15 font-mono">--</div>
                                                )}
                                            </div>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Tooltip */}
            {tooltip && (
                <div
                    className="fixed z-50 bg-[#1a1a2e] border border-[#444] rounded-lg px-3 py-2 shadow-2xl pointer-events-none"
                    style={{ left: tooltip.x, top: tooltip.y }}
                >
                    <div className="text-[10px] text-white/60 font-mono">
                        {STRATEGY_LABELS[tooltip.stat.strategy]} x {REGIME_LABELS[tooltip.stat.regime]}
                    </div>
                    <div className="text-[11px] text-white font-mono font-bold mt-1">
                        {tooltip.stat.total_trades} trades | {tooltip.stat.wins}W / {tooltip.stat.losses}L
                    </div>
                    <div className="text-[10px] text-white/50 font-mono">
                        Avg P&L: <span className={tooltip.stat.avg_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                            {(tooltip.stat.avg_pnl * 100).toFixed(2)}%
                        </span>
                    </div>
                </div>
            )}

            {/* Legend */}
            <div className="flex items-center justify-center gap-3 px-3 py-2 border-t border-[#222]">
                <div className="flex items-center gap-1">
                    <div className="w-3 h-2 rounded bg-emerald-500/20 border border-emerald-500/30" />
                    <span className="text-[8px] text-white/40 font-mono">&gt;55%</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-2 rounded bg-amber-500/10 border border-amber-500/20" />
                    <span className="text-[8px] text-white/40 font-mono">45-55%</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-2 rounded bg-red-500/20 border border-red-500/30" />
                    <span className="text-[8px] text-white/40 font-mono">&lt;40%</span>
                </div>
            </div>
        </div>
    );
}
