import React, { useEffect, useRef, useState } from 'react';
import { X, RefreshCw, Zap, Crosshair, PencilLine, AlignEndHorizontal, Type, Ruler, Trash2, List, LayoutList, Layers, Columns, Rows } from 'lucide-react';
import { motion } from 'framer-motion';
import { useTradingStore } from '../../store/tradingStore';
import CandlestickChart from './Trading/CandlestickChart';
import SymbolSelector from './Trading/SymbolSelector';
import PortfolioDashboard from './Trading/PortfolioDashboard';
import ActiveSignals from './Trading/ActiveSignals';
import RiskMeters from './Trading/RiskMeters';
import SystemHealth from './Trading/SystemHealth';
import TradeHistory from './Trading/TradeHistory';
import TradingChat from './Trading/TradingChat';
import DrawingToolbar from './Trading/DrawingToolbar';
import EquityCurveChart from './Trading/EquityCurveChart';
import StrategyHeatmap from './Trading/StrategyHeatmap';
import TradeJournal from './Trading/TradeJournal';
import IntelligencePanel from './Trading/IntelligencePanel';

interface TradingTerminalProps {
    onClose: () => void;
}

// ── Upstox Connection Status Badge ──
function UpstoxStatus() {
    const [status, setStatus] = React.useState<{ connected: boolean; login_url?: string | null } | null>(null);

    React.useEffect(() => {
        fetch('http://localhost:8000/api/upstox/status')
            .then(r => r.json())
            .then(data => setStatus(data))
            .catch(() => setStatus(null));
    }, []);

    if (!status) return null;

    if (status.connected) {
        return (
            <span
                className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border bg-emerald-900/30 text-emerald-400 border-emerald-500/30"
                title="Upstox connected — real-time Indian market data active"
            >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                UPSTOX
            </span>
        );
    }

    return (
        <a
            href={status.login_url || '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border bg-amber-900/30 text-amber-400 border-amber-500/30 hover:bg-amber-800/40 transition-colors cursor-pointer"
            title="Click to login to Upstox for real-time Indian data"
        >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            LOGIN UPSTOX
        </a>
    );
}

export default function TradingTerminal({ onClose }: TradingTerminalProps) {
    const [activeTab, setActiveTab] = React.useState<'WATCHLIST' | 'POSITIONS' | 'ORDERS' | 'SYSTEM' | 'CHAT' | 'HISTORY' | 'PERFORMANCE' | 'JOURNAL' | 'INTELLIGENCE'>('SYSTEM');
    const {
        portfolio, candles, indicators, activeSignals, tradeHistory, recentOrders, tradeStats,
        riskState, systemStatus, selectedSymbol, selectedTimeframe, symbols, setSymbol,
        market, setMarket,
        lastUpdate, loading, error, fetchAll, fetchCandles, fetchIndicators,
        connectWebSocket, disconnectWebSocket, wsConnected
    } = useTradingStore();

    // Connect WebSocket on mount
    useEffect(() => {
        connectWebSocket();
        return () => {
            disconnectWebSocket();
        };
    }, []);

    const handleRefresh = async () => {
        await fetchAll();
        await fetchCandles();
        await fetchIndicators();
    };

    const [activeTool, setActiveTool] = useState<string | null>(null);
    const [chartLayout, setChartLayout] = useState<'stacked' | 'split'>('split');

    const handleDrawingClick = (toolName: string) => {
        if (toolName === 'trash') {
            setActiveTool('clear_drawings');
            setTimeout(() => setActiveTool(null), 100);
            return;
        }
        setActiveTool(prev => prev === toolName ? null : toolName);
    };

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[999] bg-[#000000] flex flex-col overflow-hidden text-[#e0e0e0]"
        >
            {/* ═══ TOP BAR ═══ */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-[#222] bg-[#0a0a0a]">
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-white text-sm font-bold tracking-wider">TRADING TERMINAL PRO</span>
                    </div>
                    <div className="h-4 w-px bg-white/10" />
                    <SymbolSelector />
                    <div className="h-4 w-px bg-white/10" />
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${portfolio?.mode === 'PAPER'
                        ? 'bg-[#222] text-gray-300 border-[#333]'
                        : portfolio?.mode === 'LIVE'
                            ? 'bg-amber-900/30 text-amber-400 border-amber-500/30'
                            : 'bg-slate-800/30 text-slate-400 border-slate-500/30'
                        }`}>
                        {portfolio?.mode || 'OFFLINE'}
                    </span>
                    <div className="h-4 w-px bg-white/10" />
                    <button
                        onClick={() => setMarket(market === 'USA' ? 'IND' : 'USA')}
                        className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors ${market === 'USA'
                            ? 'bg-[#222] text-white/80 border-[#444] hover:bg-[#333]'
                            : 'bg-[#222] text-white/80 border-[#444] hover:bg-[#333]'
                            }`}
                        title="Toggle between US Equities and Indian Equities"
                    >
                        {market === 'USA' ? '🇺🇸 USA' : '🇮🇳 IND'}
                    </button>
                    {/* Upstox Connection Status (visible in IND mode) */}
                    {market === 'IND' && (
                        <UpstoxStatus />
                    )}
                    <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]' : 'bg-red-500'}`} title={wsConnected ? 'Live Data Connected' : 'Live Data Disconnected'} />
                </div>

                <div className="flex items-center gap-2">
                    {error && (
                        <span className="text-[10px] text-red-400 font-mono">{error}</span>
                    )}
                    <button
                        onClick={handleRefresh}
                        className="p-1.5 rounded-lg border border-[#222] text-white/50 hover:text-white/90 
                                   hover:border-[#444] hover:bg-[#222] transition-colors"
                        title="Refresh all data"
                    >
                        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                    </button>
                    <button
                        onClick={() => setChartLayout(prev => prev === 'stacked' ? 'split' : 'stacked')}
                        className="p-1.5 rounded-lg border border-[#222] text-white/50 hover:text-white/90 
                                   hover:border-[#444] hover:bg-[#222] transition-colors ml-2"
                        title={chartLayout === 'stacked' ? "Switch to Side-by-Side View" : "Switch to Stacked View"}
                    >
                        {chartLayout === 'stacked' ? <Columns size={14} /> : <Rows size={14} />}
                    </button>
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg border border-[#222] text-white/50 hover:text-red-400 
                                   hover:border-red-500/30 hover:bg-red-500/10 transition-colors"
                    >
                        <X size={14} />
                    </button>
                </div>
            </div>



            {/* ═══ PORTFOLIO METRICS BAR ═══ */}
            <div className="px-4 pt-3">
                <PortfolioDashboard portfolio={portfolio} market={market} />
            </div>

            {/* ═══ ML PREDICTION BADGE ═══ */}
            {indicators?.ml_prediction && indicators.ml_prediction.confidence > 0.55 && (
                <div className="px-4 pt-1">
                    <div className={`flex items-center gap-3 px-3 py-1.5 rounded-lg border text-[11px] font-mono ${
                        indicators.ml_prediction.direction === 'UP'
                            ? 'bg-cyan-900/20 border-cyan-500/30 text-cyan-400'
                            : 'bg-fuchsia-900/20 border-fuchsia-500/30 text-fuchsia-400'
                    }`}>
                        <span className="font-bold">🤖 AI PREDICTION</span>
                        <span className={`px-1.5 py-0.5 rounded font-bold ${
                            indicators.ml_prediction.direction === 'UP' ? 'bg-cyan-500/20' : 'bg-fuchsia-500/20'
                        }`}>
                            {indicators.ml_prediction.direction === 'UP' ? '▲ BULLISH' : '▼ BEARISH'}
                        </span>
                        <span className="text-white/50">Confidence:</span>
                        <span className="font-bold">{(indicators.ml_prediction.confidence * 100).toFixed(0)}%</span>
                        <span className="text-white/50">|</span>
                        <span className="text-white/50">Accuracy:</span>
                        <span className="font-bold">{(indicators.ml_prediction.model_accuracy * 100).toFixed(0)}%</span>
                        <span className="text-white/50">|</span>
                        <span className="text-white/50">Entry:</span>
                        <span className="text-white">{indicators.ml_prediction.entry_price.toFixed(2)}</span>
                        <span className="text-white/50">Target:</span>
                        <span className="text-emerald-400">{indicators.ml_prediction.target_price.toFixed(2)}</span>
                        <span className="text-white/50">Stop:</span>
                        <span className="text-red-400">{indicators.ml_prediction.stop_price.toFixed(2)}</span>
                    </div>
                </div>
            )}

            {/* ═══ MAIN CONTENT ═══ */}
            <div className="flex-1 flex gap-3 px-4 pb-3 min-h-0 overflow-hidden">
                {/* LEFT TOOLBAR (TRADINGVIEW STYLE) */}
                <DrawingToolbar activeTool={activeTool} setActiveTool={setActiveTool} />

                {/* CENTER: Chart */}
                <div className="flex-1 flex flex-col min-w-0 border-l border-[#222] pl-3 relative bg-[#000]">
                    {candles.length === 0 ? (
                        <div className="w-full h-full flex items-center justify-center bg-[#0a0a0a] rounded-xl border border-[#222]">
                            <div className="text-center">
                                <Zap size={24} className="text-[#333] mx-auto mb-2" />
                                <div className="text-slate-500 text-xs font-mono">
                                    {loading ? 'Loading chart data...' : `No data for ${selectedSymbol} / ${selectedTimeframe}`}
                                </div>
                                <div className="text-slate-600 text-[10px] font-mono mt-1">
                                    Configure symbols in .env or check broker connection
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className={`flex-1 flex gap-2 min-h-0 ${chartLayout === 'split' ? 'flex-row' : 'flex-col'}`}>
                            {/* AI PREDICTION CHART */}
                            <div className="flex-1 min-h-0 relative border border-[#222] rounded overflow-hidden">
                                <CandlestickChart
                                    candles={candles}
                                    indicators={indicators}
                                    signals={activeSignals.filter(s => s.asset === selectedSymbol)}
                                    activeTool={activeTool}
                                    mode="AI"
                                    title="AI Machine Learning"
                                />
                            </div>
                            
                            {/* BOLLINGER BANDS CHART */}
                            <div className="flex-1 min-h-0 relative border border-[#222] rounded overflow-hidden">
                                <CandlestickChart
                                    candles={candles}
                                    indicators={indicators}
                                    signals={[]} // Don't duplicate trade lines on bottom chart
                                    activeTool={activeTool}
                                    mode="BB"
                                    title="Bollinger Bands"
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* RIGHT SIDEBAR (TABBED - GROWW STYLE) */}
                <div className="w-[320px] flex flex-col gap-3 border-l border-[#222] pl-3">

                    {/* TABS HEADER */}
                    <div className="flex flex-wrap items-center gap-1 border-b border-[#222] pb-2">
                        {[
                            { id: 'WATCHLIST', label: 'Watchlist', icon: <List size={14} /> },
                            { id: 'POSITIONS', label: 'Positions', icon: <Layers size={14} /> },
                            { id: 'ORDERS', label: 'Orders', icon: <LayoutList size={14} /> },
                            { id: 'HISTORY', label: 'History', icon: <List size={14} /> },
                            { id: 'PERFORMANCE', label: 'Perf', icon: <AlignEndHorizontal size={14} /> },
                            { id: 'JOURNAL', label: 'Journal', icon: <Ruler size={14} /> },
                            { id: 'INTELLIGENCE', label: 'Intel', icon: <Crosshair size={14} /> },
                            { id: 'CHAT', label: 'AI Chat', icon: <Type size={14} /> },
                            { id: 'SYSTEM', label: 'System', icon: <Zap size={14} /> }
                        ].map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id as any)}
                                className={`flex items-center gap-1.5 px-2 py-1.5 rounded-md text-[10px] font-bold tracking-wider transition-colors whitespace-nowrap ${activeTab === tab.id
                                    ? 'bg-[#222] text-white'
                                    : 'text-gray-500 hover:bg-[#111] hover:text-gray-300'
                                    }`}
                            >
                                {tab.icon}
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* TAB CONTENT */}
                    <div className="flex-1 overflow-y-auto custom-scrollbar pr-1 flex flex-col gap-3">
                        {activeTab === 'WATCHLIST' && (
                            <div className="flex flex-col gap-2">
                                {symbols && symbols.length > 0 ? (
                                    symbols.map((sym: string) => (
                                        <button
                                            key={sym}
                                            onClick={() => setSymbol(sym)}
                                            className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${selectedSymbol === sym
                                                ? 'bg-[#111] border-[#444] text-white'
                                                : 'bg-[#0a0a0a] border-[#222] text-slate-300 hover:bg-[#111]'
                                                }`}
                                        >
                                            <span className="font-bold tracking-widest">{sym}</span>
                                            {selectedSymbol === sym && <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />}
                                        </button>
                                    ))
                                ) : (
                                    <div className="text-sm text-gray-500 p-4 text-center border border-[#222] rounded-lg bg-[#0a0a0a]">
                                        No symbols monitored
                                    </div>
                                )}
                            </div>
                        )}
                        {activeTab === 'POSITIONS' && (
                            <ActiveSignals data={activeSignals} refreshData={handleRefresh} />
                        )}
                        {activeTab === 'ORDERS' && (
                            <div className="flex flex-col gap-2">
                                {recentOrders && recentOrders.length > 0 ? (
                                    recentOrders.map((order: any) => (
                                        <div key={order.order_id || Math.random().toString()} className="bg-[#0a0a0a] border border-[#222] rounded-lg p-3 shadow-inner">
                                            <div className="flex justify-between items-center mb-1">
                                                <span className={`font-bold ${order.side === 'LONG' ? 'text-emerald-400' : 'text-red-400'}`}>
                                                    {order.side === 'LONG' ? 'BUY' : 'SELL'} {order.symbol}
                                                </span>
                                                <span className="text-[10px] font-mono text-slate-400 bg-black/50 px-1.5 py-0.5 rounded">
                                                    {new Date(order.created_at * 1000).toLocaleTimeString()}
                                                </span>
                                            </div>
                                            <div className="flex justify-between items-center text-xs text-gray-400">
                                                <span>Qty: {order.quantity}</span>
                                                <span>@ ${order.price?.toFixed(2) || 'MKT'}</span>
                                            </div>
                                            <div className="mt-2 text-right">
                                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${order.status === 'FILLED' ? 'bg-emerald-500/20 text-emerald-400' :
                                                    order.status === 'REJECTED' || order.status === 'CANCELED' ? 'bg-red-500/20 text-red-400' :
                                                        'bg-amber-500/20 text-amber-400'
                                                    }`}>
                                                    {order.status}
                                                </span>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-sm text-gray-500 p-4 text-center border border-[#222] rounded-lg bg-[#0a0a0a]">
                                        No recent orders
                                    </div>
                                )}
                            </div>
                        )}
                        {activeTab === 'HISTORY' && (
                            <TradeHistory trades={tradeHistory} stats={tradeStats} />
                        )}
                        {activeTab === 'PERFORMANCE' && (
                            <>
                                <EquityCurveChart className="h-[280px]" />
                                <StrategyHeatmap />
                            </>
                        )}
                        {activeTab === 'JOURNAL' && (
                            <TradeJournal />
                        )}
                        {activeTab === 'INTELLIGENCE' && (
                            <IntelligencePanel />
                        )}
                        {activeTab === 'CHAT' && (
                            <TradingChat />
                        )}
                        {activeTab === 'SYSTEM' && (
                            <>
                                <RiskMeters data={riskState ? {
                                    mode: riskState.mode,
                                    current_drawdown: riskState.drawdown_pct,
                                    max_drawdown: 0.20,
                                    signals_allowed: !riskState.kill_switch_active,
                                    halted_reason: riskState.kill_switch_reason,
                                } : undefined} />
                                <SystemHealth
                                    system={systemStatus}
                                    risk={riskState}
                                    lastUpdate={lastUpdate}
                                />
                            </>
                        )}
                    </div>
                </div>
            </div>
        </motion.div>
    );
}
