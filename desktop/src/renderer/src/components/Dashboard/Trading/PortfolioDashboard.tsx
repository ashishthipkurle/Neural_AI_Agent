import React from 'react';
import { DollarSign, TrendingUp, TrendingDown, Activity, Wallet, BarChart3, Shield } from 'lucide-react';
import { motion } from 'framer-motion';
import { PortfolioState } from '../../../store/tradingStore';

interface Props {
    portfolio: PortfolioState | null;
    market: string;
}

const PortfolioDashboard: React.FC<Props> = ({ portfolio, market }) => {
    if (!portfolio) {
        return (
            <div className="grid grid-cols-4 gap-2 mb-3">
                {[...Array(4)].map((_, i) => (
                    <div key={i} className="bg-[#0a0a0a] rounded-lg p-3 border border-[#222] animate-pulse">
                        <div className="h-3 w-16 bg-[#222] rounded mb-2" />
                        <div className="h-5 w-20 bg-[#222] rounded" />
                    </div>
                ))}
            </div>
        );
    }

    const metrics = [
        {
            label: 'EQUITY',
            value: portfolio.total_equity,
            format: 'currency',
            icon: <DollarSign size={12} />,
            color: '#00e676',
        },
        {
            label: 'CASH',
            value: portfolio.cash_balance,
            format: 'currency',
            icon: <Wallet size={12} />,
            color: '#42a5f5',
        },
        {
            label: 'TOTAL P&L',
            value: portfolio.total_pnl,
            format: 'currency_signed',
            icon: portfolio.total_pnl >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />,
            color: portfolio.total_pnl >= 0 ? '#00e676' : '#ff5252',
        },
        {
            label: 'DRAWDOWN',
            value: portfolio.drawdown_pct * 100,
            format: 'percent',
            icon: <Activity size={12} />,
            color: portfolio.drawdown_pct > 0.1 ? '#ff5252' : portfolio.drawdown_pct > 0.05 ? '#ff9800' : '#00e676',
        },
        {
            label: 'POSITIONS',
            value: portfolio.open_positions,
            format: 'int',
            icon: <BarChart3 size={12} />,
            color: '#ce93d8',
        },
        {
            label: 'RISK MODE',
            value: portfolio.risk_mode,
            format: 'text',
            icon: <Shield size={12} />,
            color: portfolio.risk_mode === 'NORMAL' ? '#00e676' : '#ff5252',
        },
    ];

    const formatValue = (val: any, fmt: string): string => {
        const sym = market === 'IND' ? '₹' : '$';
        if (fmt === 'currency') return `${sym}${Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (fmt === 'currency_signed') {
            const n = Number(val);
            const prefix = n >= 0 ? `+${sym}` : `-${sym}`;
            return `${prefix}${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
        if (fmt === 'percent') return `${Number(val).toFixed(2)}%`;
        if (fmt === 'int') return String(Math.round(Number(val)));
        return String(val);
    };

    return (
        <div className="grid grid-cols-6 gap-2 mb-3">
            {metrics.map((m, i) => (
                <motion.div
                    key={m.label}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="bg-[#0a0a0a] rounded-lg p-2.5 border border-[#222] hover:border-[#444] transition-colors"
                >
                    <div className="flex items-center gap-1.5 mb-1.5">
                        <span style={{ color: m.color, opacity: 0.7 }}>{m.icon}</span>
                        <span className="text-[9px] text-slate-500 font-mono tracking-wider">{m.label}</span>
                    </div>
                    <div
                        className="text-sm font-bold font-mono"
                        style={{ color: m.color }}
                    >
                        {formatValue(m.value, m.format)}
                    </div>
                </motion.div>
            ))}
        </div>
    );
};

export default PortfolioDashboard;
