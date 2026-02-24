import React, { useState } from 'react';
import { Target, CheckCircle, Clock, TrendingUp, TrendingDown, ShieldAlert, Crosshair } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function ActiveSignals({ data, refreshData }: { data: any[], refreshData: () => void }) {
    const [executing, setExecuting] = useState<string | null>(null);

    const handleExecute = async (signalId: string) => {
        setExecuting(signalId);
        try {
            const res = await fetch('http://localhost:8000/api/trading/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    signal_id: signalId,
                    confirmation_string: 'CONFIRM TRADE'
                })
            });
            if (res.ok) {
                setTimeout(() => refreshData(), 1000);
            }
        } catch (e) {
            console.error("Execution failed", e);
        } finally {
            setExecuting(null);
        }
    };

    const formatPrice = (price: number | undefined) => {
        if (!price || price === 0) return '--';
        return price.toLocaleString('en-IN', { maximumFractionDigits: 2 });
    };

    return (
        <div className="bg-[#03121a] border border-cyan-500/20 rounded-xl p-4 flex-1 flex flex-col min-h-0 relative shadow-inner">
            <div className="flex items-center gap-2 mb-4 border-b border-cyan-500/20 pb-2">
                <Target size={16} className="text-cyan-400" />
                <h3 className="text-cyan-300 text-sm font-medium tracking-wider">STAGED SIGNALS</h3>
                <div className="ml-auto px-2 py-0.5 rounded-full bg-cyan-900/50 text-cyan-400 text-[10px] font-mono border border-cyan-500/30">
                    AWAITING CONFIRMATION
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-3 pr-2">
                <AnimatePresence>
                    {data.map((sig) => {
                        const isBuy = sig.direction === 'LONG';
                        const accentColor = isBuy ? 'emerald' : 'red';

                        return (
                            <motion.div
                                key={sig.signal_id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, x: -20, transition: { duration: 0.2 } }}
                                className={`border rounded-lg p-3 flex flex-col gap-2.5 group transition-colors
                                    ${isBuy
                                        ? 'bg-emerald-950/30 border-emerald-500/20 hover:border-emerald-500/40'
                                        : 'bg-red-950/30 border-red-500/20 hover:border-red-500/40'
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
                                    <div className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${isBuy ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>
                                        {(sig.confidence * 100).toFixed(0)}%
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
                                            {formatPrice(sig.stop_loss)}
                                        </div>
                                    </div>
                                    {/* Target */}
                                    <div className="bg-black/30 rounded-lg p-2 border border-white/5">
                                        <div className="text-[9px] text-slate-500 font-mono mb-1 flex items-center justify-center gap-1">
                                            <Target size={9} />
                                            TARGET
                                        </div>
                                        <div className="text-sm font-bold text-cyan-400">
                                            {formatPrice(sig.target_price)}
                                        </div>
                                    </div>
                                </div>

                                {/* Reason */}
                                <div className="text-[10px] text-slate-400 bg-black/20 px-2 py-1.5 rounded border border-white/5 font-mono">
                                    <span className="text-cyan-500/60">REASON:</span> {sig.reason}
                                </div>

                                {/* Confirm Button */}
                                <button
                                    onClick={() => handleExecute(sig.signal_id)}
                                    disabled={executing === sig.signal_id}
                                    className={`w-full py-2 rounded-lg text-xs font-bold tracking-wider uppercase transition-all flex items-center justify-center gap-2 ${executing === sig.signal_id
                                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/50 cursor-wait'
                                        : isBuy
                                            ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500 hover:text-white shadow-[0_0_10px_rgba(16,185,129,0.1)] hover:shadow-[0_0_15px_rgba(16,185,129,0.4)]'
                                            : 'bg-red-500/10 text-red-300 border border-red-500/30 hover:bg-red-500 hover:text-white shadow-[0_0_10px_rgba(239,68,68,0.1)] hover:shadow-[0_0_15px_rgba(239,68,68,0.4)]'
                                        }`}
                                >
                                    {executing === sig.signal_id ? (
                                        <>EXECUTING...</>
                                    ) : (
                                        <>
                                            <CheckCircle size={14} />
                                            CONFIRM TRADE
                                        </>
                                    )}
                                </button>
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
