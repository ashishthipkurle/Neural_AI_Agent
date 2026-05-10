import React, { useEffect, useRef, useState } from 'react';
import { X, RefreshCw, Zap, Crosshair, PencilLine, AlignEndHorizontal, Type, Ruler, Trash2, List, LayoutList, Layers } from 'lucide-react';
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

interface TradingTerminalProps {
    onClose: () => void;
}

export default function TradingTerminal({ onClose }: TradingTerminalProps) {
    const [activeTab, setActiveTab] = React.useState<'WATCHLIST' | 'POSITIONS' | 'ORDERS' | 'SYSTEM' | 'CHAT' | 'HISTORY'>('SYSTEM');
    const {
        portfolio, candles, indicators, activeSignals, tradeHistory, recentOrders, tradeStats,
        riskState, systemStatus, selectedSymbol, selectedTimeframe, symbols, setSymbol,
        market, setMarket,
        lastUpdate, loading, error, fetchAll, fetchCandles,
        connectWebSocket, disconnectWebSocket, wsConnected
    } = useTradingStore();

    // Connect WebSocket on mount
    useEffect(() => {
        connectWebSocket();
        return () => {
            disconnectWebSocket();
        };
    }, []);

    const handleRefresh = () => {
        fetchAll();
    };

    const handleDrawingClick = () => {
        window.alert("Drawing tools are not supported in Lightweight Charts. Pro version with TradingView required.");
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

            {/* ═══ MAIN CONTENT ═══ */}
            <div className="flex-1 flex gap-3 px-4 pb-3 min-h-0 overflow-hidden">
                {/* LEFT TOOLBAR (GROWW STYLE) */}
                <div className="w-10 flex flex-col gap-3 items-center pt-2">
                    <button onClick={handleDrawingClick} className="p-2 rounded-lg hover:bg-[#222] text-gray-500 hover:text-white transition-colors" title="Crosshair">
                        <Crosshair size={16} />
                    </button>
                    <button onClick={handleDrawingClick} className="p-2 rounded-lg hover:bg-[#222] text-gray-500 hover:text-white transition-colors" title="Trend Line">
                        <PencilLine size={16} />
                    </button>
                    <button onClick={handleDrawingClick} className="p-2 rounded-lg hover:bg-[#222] text-gray-500 hover:text-white transition-colors" title="Fibonacci">
                        <AlignEndHorizontal size={16} />
                    </button>
                    <button onClick={handleDrawingClick} className="p-2 rounded-lg hover:bg-[#222] text-gray-500 hover:text-white transition-colors" title="Text">
                        <Type size={16} />
                    </button>
                    <button onClick={handleDrawingClick} className="p-2 rounded-lg hover:bg-[#222] text-gray-500 hover:text-white transition-colors" title="Measure">
                        <Ruler size={16} />
                    </button>
                    <button onClick={handleDrawingClick} className="p-2 rounded-lg hover:bg-[#222] text-gray-500 hover:text-red-400 transition-colors mt-auto mb-2" title="Delete Drawings">
                        <Trash2 size={16} />
                    </button>
                </div>

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
                        <CandlestickChart
                            candles={candles}
                            indicators={indicators}
                            signals={activeSignals.filter(s => s.asset === selectedSymbol)}
                        />
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
