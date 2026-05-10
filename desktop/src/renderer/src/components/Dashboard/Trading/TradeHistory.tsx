import React from 'react';
import { History, TrendingUp, TrendingDown } from 'lucide-react';
import { TradeRecord } from '../../../store/tradingStore';

interface Props {
    trades: TradeRecord[];
    stats: { total: number; wins: number; losses: number; win_rate: number; total_net_pnl: number; avg_r: number };
}

const TradeHistory: React.FC<Props> = ({ trades, stats }) => {
    return (
        <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-3 flex flex-col">
            {/* Header */}
            <div className="flex items-center gap-2 border-b border-[#222] pb-2 mb-2">
                <History size={14} className="text-gray-400" />
                <span className="text-white text-xs font-bold tracking-wider">TRADE HISTORY</span>
                <div className="ml-auto flex items-center gap-3 text-[10px] font-mono">
                    <span className="text-slate-400">{stats.total} trades</span>
                    <span className="text-emerald-400">{stats.win_rate}% WR</span>
                    <span className={stats.total_net_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                        {stats.total_net_pnl >= 0 ? '+' : ''}${stats.total_net_pnl.toFixed(2)}
                    </span>
                </div>
            </div>

            {/* Table */}
            {trades.length === 0 ? (
                <div className="text-center text-slate-600 text-xs py-6 font-mono">
                    No trades yet — engine scanning for signals...
                </div>
            ) : (
                <div className="overflow-y-auto max-h-[200px] custom-scrollbar">
                    <table className="w-full text-[10px] font-mono">
                        <thead>
                            <tr className="text-slate-600 border-b border-white/5">
                                <th className="text-left py-1.5 px-1">SYMBOL</th>
                                <th className="text-left py-1.5 px-1">SIDE</th>
                                <th className="text-right py-1.5 px-1">ENTRY</th>
                                <th className="text-right py-1.5 px-1">EXIT</th>
                                <th className="text-right py-1.5 px-1">P&L</th>
                                <th className="text-right py-1.5 px-1">R</th>
                            </tr>
                        </thead>
                        <tbody>
                            {trades.map((t) => {
                                const isWin = t.net_pnl >= 0;
                                return (
                                    <tr key={t.trade_id} className="border-b border-white/3 hover:bg-white/2">
                                        <td className="py-1.5 px-1 text-white">{t.symbol}</td>
                                        <td className="py-1.5 px-1">
                                            <span className={`flex items-center gap-1 ${t.direction === 'LONG' ? 'text-emerald-400' : 'text-red-400'}`}>
                                                {t.direction === 'LONG' ? <TrendingUp size={9} /> : <TrendingDown size={9} />}
                                                {t.direction}
                                            </span>
                                        </td>
                                        <td className="py-1.5 px-1 text-right text-slate-400">{t.entry_price.toFixed(2)}</td>
                                        <td className="py-1.5 px-1 text-right text-slate-400">{t.exit_price.toFixed(2)}</td>
                                        <td className={`py-1.5 px-1 text-right font-bold ${isWin ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {isWin ? '+' : ''}{t.net_pnl.toFixed(2)}
                                        </td>
                                        <td className={`py-1.5 px-1 text-right ${t.r_achieved >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {t.r_achieved.toFixed(2)}R
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default TradeHistory;
