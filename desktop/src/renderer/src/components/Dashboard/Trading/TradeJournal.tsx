import React, { useEffect, useState, useCallback } from 'react';
import { ChevronDown, ChevronRight, Filter } from 'lucide-react';

// ── Types ────────────────────────────────────────────────────
interface JournalEntry {
    trade_id: string;
    symbol: string;
    direction: string;
    strategy_name: string;
    entry_price: number;
    exit_price: number;
    net_pnl: number;
    pnl_pct: number;
    confidence: number;
    regime: string;
    exit_reason: string;
    closed_at: number;
    ta_conviction?: number;
    ml_agreed?: boolean;
    llm_review?: string;
}

interface Filters {
    symbol: string;
    strategy: string;
    result: 'ALL' | 'WIN' | 'LOSS';
}

const API = 'http://localhost:8000';

// ── Component ────────────────────────────────────────────────
export default function TradeJournal() {
    const [trades, setTrades] = useState<JournalEntry[]>([]);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [filters, setFilters] = useState<Filters>({ symbol: '', strategy: '', result: 'ALL' });
    const [showFilters, setShowFilters] = useState(false);
    const [sortKey, setSortKey] = useState<'closed_at' | 'net_pnl' | 'symbol'>('closed_at');
    const [sortAsc, setSortAsc] = useState(false);

    const fetchTrades = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/trading/trades?limit=200`);
            if (res.ok) {
                const json = await res.json();
                setTrades(json.trades || []);
            }
        } catch (e) {
            console.error('Failed to fetch trades:', e);
        }
    }, []);

    useEffect(() => {
        fetchTrades();
        const interval = setInterval(fetchTrades, 30000);
        return () => clearInterval(interval);
    }, [fetchTrades]);

    // Filter + Sort
    const filteredTrades = React.useMemo(() => {
        let result = [...trades];

        if (filters.symbol) {
            result = result.filter(t => t.symbol.includes(filters.symbol.toUpperCase()));
        }
        if (filters.strategy) {
            result = result.filter(t => t.strategy_name === filters.strategy);
        }
        if (filters.result === 'WIN') {
            result = result.filter(t => t.net_pnl > 0);
        } else if (filters.result === 'LOSS') {
            result = result.filter(t => t.net_pnl <= 0);
        }

        result.sort((a, b) => {
            const va = a[sortKey] ?? 0;
            const vb = b[sortKey] ?? 0;
            return sortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
        });

        return result;
    }, [trades, filters, sortKey, sortAsc]);

    const handleSort = (key: typeof sortKey) => {
        if (sortKey === key) setSortAsc(!sortAsc);
        else { setSortKey(key); setSortAsc(false); }
    };

    const uniqueStrategies = [...new Set(trades.map(t => t.strategy_name))];

    return (
        <div className="bg-[#0a0a0a] rounded-xl border border-[#222] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-[#222]">
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-blue-500" />
                    <span className="text-[11px] font-bold tracking-wider text-white/80">TRADE JOURNAL</span>
                    <span className="text-[9px] text-white/30 font-mono">{filteredTrades.length} trades</span>
                </div>
                <button
                    onClick={() => setShowFilters(!showFilters)}
                    className={`p-1 rounded border transition-colors ${showFilters ? 'bg-blue-500/20 border-blue-500/30 text-blue-400' : 'border-[#333] text-white/40 hover:text-white/70'}`}
                >
                    <Filter size={12} />
                </button>
            </div>

            {/* Filters */}
            {showFilters && (
                <div className="flex items-center gap-2 px-3 py-2 border-b border-[#222] bg-[#111]">
                    <input
                        type="text"
                        placeholder="Symbol..."
                        value={filters.symbol}
                        onChange={e => setFilters({ ...filters, symbol: e.target.value })}
                        className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[10px] font-mono text-white/70 w-20 focus:outline-none focus:border-blue-500/50"
                    />
                    <select
                        value={filters.strategy}
                        onChange={e => setFilters({ ...filters, strategy: e.target.value })}
                        className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[10px] font-mono text-white/70 focus:outline-none focus:border-blue-500/50"
                    >
                        <option value="">All Strategies</option>
                        {uniqueStrategies.map(s => (
                            <option key={s} value={s}>{s}</option>
                        ))}
                    </select>
                    <div className="flex gap-1">
                        {(['ALL', 'WIN', 'LOSS'] as const).map(r => (
                            <button
                                key={r}
                                onClick={() => setFilters({ ...filters, result: r })}
                                className={`text-[9px] font-mono px-1.5 py-0.5 rounded border transition-colors ${
                                    filters.result === r
                                        ? r === 'WIN' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                                        : r === 'LOSS' ? 'bg-red-500/20 text-red-400 border-red-500/30'
                                        : 'bg-white/10 text-white/70 border-white/20'
                                        : 'text-white/30 border-transparent'
                                }`}
                            >
                                {r}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Table */}
            <div className="flex-1 overflow-y-auto custom-scrollbar">
                <table className="w-full text-[10px] font-mono">
                    <thead className="sticky top-0 bg-[#0f0f0f] z-10">
                        <tr className="border-b border-[#222]">
                            <th className="py-1.5 px-2 text-left text-white/40 font-normal w-5"></th>
                            <th onClick={() => handleSort('closed_at')} className="py-1.5 px-2 text-left text-white/40 font-normal cursor-pointer hover:text-white/70">Date</th>
                            <th onClick={() => handleSort('symbol')} className="py-1.5 px-2 text-left text-white/40 font-normal cursor-pointer hover:text-white/70">Symbol</th>
                            <th className="py-1.5 px-2 text-left text-white/40 font-normal">Dir</th>
                            <th className="py-1.5 px-2 text-left text-white/40 font-normal">Strategy</th>
                            <th className="py-1.5 px-2 text-right text-white/40 font-normal">Entry</th>
                            <th className="py-1.5 px-2 text-right text-white/40 font-normal">Exit</th>
                            <th onClick={() => handleSort('net_pnl')} className="py-1.5 px-2 text-right text-white/40 font-normal cursor-pointer hover:text-white/70">P&L</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredTrades.length === 0 ? (
                            <tr>
                                <td colSpan={8} className="text-center py-8 text-white/20">No trades recorded yet</td>
                            </tr>
                        ) : (
                            filteredTrades.map(trade => (
                                <React.Fragment key={trade.trade_id}>
                                    <tr
                                        onClick={() => setExpandedId(expandedId === trade.trade_id ? null : trade.trade_id)}
                                        className={`border-b border-[#1a1a1a] cursor-pointer transition-colors hover:bg-white/[0.02] ${
                                            trade.net_pnl > 0 ? 'hover:bg-emerald-500/[0.03]' : 'hover:bg-red-500/[0.03]'
                                        }`}
                                    >
                                        <td className="py-1.5 px-2 text-white/20">
                                            {expandedId === trade.trade_id ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                                        </td>
                                        <td className="py-1.5 px-2 text-white/50">
                                            {new Date(trade.closed_at * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                                        </td>
                                        <td className="py-1.5 px-2 text-white font-bold">{trade.symbol}</td>
                                        <td className="py-1.5 px-2">
                                            <span className={trade.direction === 'LONG' ? 'text-emerald-400' : 'text-red-400'}>
                                                {trade.direction}
                                            </span>
                                        </td>
                                        <td className="py-1.5 px-2 text-white/40">{trade.strategy_name}</td>
                                        <td className="py-1.5 px-2 text-right text-white/60">${trade.entry_price?.toFixed(2)}</td>
                                        <td className="py-1.5 px-2 text-right text-white/60">${trade.exit_price?.toFixed(2)}</td>
                                        <td className={`py-1.5 px-2 text-right font-bold ${trade.net_pnl > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {trade.net_pnl > 0 ? '+' : ''}${trade.net_pnl?.toFixed(2)}
                                        </td>
                                    </tr>

                                    {/* Expanded Detail Row */}
                                    {expandedId === trade.trade_id && (
                                        <tr className="bg-[#111]">
                                            <td colSpan={8} className="px-4 py-3">
                                                <div className="grid grid-cols-4 gap-3">
                                                    <div>
                                                        <div className="text-[9px] text-white/30 mb-0.5">Confidence</div>
                                                        <div className="text-[11px] text-cyan-400 font-bold">{(trade.confidence * 100).toFixed(0)}%</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-[9px] text-white/30 mb-0.5">Regime</div>
                                                        <div className="text-[11px] text-white/60">{trade.regime || '--'}</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-[9px] text-white/30 mb-0.5">TA Conviction</div>
                                                        <div className="text-[11px] text-blue-400">{trade.ta_conviction ? `${(trade.ta_conviction * 100).toFixed(0)}%` : '--'}</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-[9px] text-white/30 mb-0.5">Exit Reason</div>
                                                        <div className="text-[11px] text-white/60">{trade.exit_reason || '--'}</div>
                                                    </div>
                                                </div>
                                                {trade.llm_review && (
                                                    <div className="mt-2 px-2 py-1.5 bg-violet-500/5 border border-violet-500/10 rounded text-[10px] text-violet-300/70 italic">
                                                        LLM Review: {trade.llm_review}
                                                    </div>
                                                )}
                                            </td>
                                        </tr>
                                    )}
                                </React.Fragment>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
