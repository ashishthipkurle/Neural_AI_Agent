import React from 'react';
import { Target, Clock, TrendingUp, TrendingDown, ShieldAlert, Crosshair, Zap } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function ActiveSignals({ data, refreshData }: { data: any[], refreshData: () => void }) {
    const formatPrice = (price: number | undefined) => {
        if (!price || price === 0) return '--';
        return price.toLocaleString('en-IN', { maximumFractionDigits: 2 });
    };

    return (
        <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-4 flex-1 flex flex-col min-h-0 relative shadow-inner">
            <div className="flex items-center gap-2 mb-4 border-b border-[#222] pb-2">
                <Target size={16} className="text-gray-400" />
                <h3 className="text-white text-sm font-bold tracking-wider">ACTIVE POSITIONS</h3>
                <div className="ml-auto flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-900/50 text-emerald-400 text-[10px] font-mono border border-emerald-500/30">
                    <Zap size={10} className="animate-pulse" />
                    AUTONOMOUS MODE
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-3 pr-2">
                <AnimatePresence>
                    {data.map((sig) => {
                        const isBuy = sig.direction === 'LONG';
                        const accentColor = isBuy ? 'emerald' : 'red';
                        const isProfitable = sig.current_r > 0;

                        return (
                            <motion.div
                                key={sig.signal_id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, x: -20, transition: { duration: 0.2 } }}
                                className={`border rounded-lg p-3 flex flex-col gap-2.5 group transition-colors
                                    ${isBuy
                                        ? 'bg-emerald-950/30 border-emerald-500/20'
                                        : 'bg-red-950/30 border-red-500/20'
                                    }`}
                            >
                                {/* Header: Direction + Asset */}
                                <div className="flex justify-between items-center">
                                    <div className="flex items-center gap-2">
                                        {isBuy
                                            ? <TrendingUp size={16} className="text-emerald-400" />
                                            : <TrendingDown size={16} className="text-red-400" />
                                        }
                                        <span className={`text-lg font-black ${isBuy ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {isBuy ? 'BUY' : 'SELL'}
                                        </span>
                                        <span className="text-white font-bold text-sm">{sig.asset}</span>
                                    </div>
                                    <div className={`text-[10px] font-mono px-2 py-0.5 rounded ${isProfitable ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                                        R: {sig.current_r ? sig.current_r.toFixed(2) : '0.00'}
                                    </div>
                                </div>

                                {/* Price Slots Grid */}
                                <div className="grid grid-cols-3 gap-2 text-center">
                                    {/* Entry Price */}
                                    <div className="bg-black/30 rounded-lg p-2 border border-white/5">
                                        <div className="text-[9px] text-slate-500 font-mono mb-1 flex items-center justify-center gap-1">
                                            <Crosshair size={9} />
                                            ENTRY
                                        </div>
                                        <div className={`text-sm font-bold ${isBuy ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {formatPrice(sig.entry_price)}
                                        </div>
                                    </div>
                                    {/* Stop Loss */}
                                    <div className="bg-black/30 rounded-lg p-2 border border-white/5">
                                        <div className="text-[9px] text-slate-500 font-mono mb-1 flex items-center justify-center gap-1">
                                            <ShieldAlert size={9} />
                                            STOP LOSS
                                        </div>
                                        <div className="text-sm font-bold text-amber-400">
                                            {formatPrice(sig.stop_price || sig.stop_loss)}
                                        </div>
                                    </div>
                                    <div className="bg-black/30 rounded-lg p-2 border border-white/5">
                                        <div className="text-[9px] text-slate-500 font-mono mb-1 flex items-center justify-center gap-1">
                                            <Target size={9} />
                                            TARGET
                                        </div>
                                        <div className="text-sm font-bold text-white/80">
                                            {formatPrice(sig.target_price)}
                                        </div>
                                    </div>
                                </div>

                                {/* Signal Details */}
                                <div className="grid grid-cols-2 gap-2 text-[10px] font-mono mt-2">
                                    <div className="bg-[#111] p-1.5 rounded">
                                        <span className="text-white/40 uppercase">DIR:</span>{' '}
                                        <span className={sig.direction === 'LONG' ? 'text-emerald-400' : 'text-red-400'}>{sig.direction}</span>
                                    </div>
                                    <div className="bg-[#111] p-1.5 rounded">
                                        <span className="text-white/40 uppercase">STATE:</span>{' '}
                                        <span className="text-white/80 font-bold">{sig.state || 'ACTIVE'}</span>
                                    </div>
                                    <div className="bg-[#111] p-1.5 rounded col-span-2">
                                        <span className="text-white/40 uppercase">TIMEFRAME:</span>{' '}
                                        <span className="text-white/80">{sig.timeframe || '15m'}</span>
                                    </div>
                                </div>
                            </motion.div>
                        );
                    })}
                    {data.length === 0 && (
                        <div className="text-center text-slate-500 text-xs py-8 font-mono border border-dashed border-white/10 rounded-lg">
                            SCANNING CHART FOR SIGNALS...
                        </div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}
