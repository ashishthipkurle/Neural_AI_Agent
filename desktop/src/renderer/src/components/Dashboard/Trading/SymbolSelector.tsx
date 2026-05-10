import React from 'react';
import { ChevronDown, Clock } from 'lucide-react';
import { useTradingStore } from '../../../store/tradingStore';

const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '1d'];

const SymbolSelector: React.FC = () => {
    const { selectedSymbol, selectedTimeframe, symbols, setSymbol, setTimeframe } = useTradingStore();

    return (
        <div className="flex items-center gap-3">
            {/* Symbol Dropdown */}
            <div className="relative">
                <select
                    value={selectedSymbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="appearance-none bg-[#111] border border-[#222] text-white/90 text-xs font-mono 
                               px-3 py-1.5 pr-7 rounded-lg cursor-pointer hover:border-[#444] 
                               focus:outline-none focus:border-[#666] transition-colors"
                >
                    {symbols.length > 0 ? (
                        symbols.map((s) => (
                            <option key={s} value={s} className="bg-[#111]">{s}</option>
                        ))
                    ) : (
                        <option value={selectedSymbol} className="bg-[#111]">{selectedSymbol}</option>
                    )}
                </select>
                <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-white/50 pointer-events-none" />
            </div>

            {/* Timeframe Pills */}
            <div className="flex items-center gap-1 bg-[#111] rounded-lg p-0.5 border border-[#222]">
                {TIMEFRAMES.map((tf) => (
                    <button
                        key={tf}
                        onClick={() => setTimeframe(tf)}
                        className={`px-2 py-1 text-[10px] font-mono rounded-md transition-all ${
                            selectedTimeframe === tf
                                ? 'bg-[#333] text-white border border-[#444]'
                                : 'text-white/50 hover:text-white/80 border border-transparent hover:bg-[#222]'
                        }`}
                    >
                        {tf}
                    </button>
                ))}
            </div>
        </div>
    );
};

export default SymbolSelector;
