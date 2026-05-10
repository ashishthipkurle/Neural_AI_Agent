import React from 'react';
import { Cpu, Database, Wifi, WifiOff, Radio, Zap, Clock, AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';
import { SystemStatus, RiskState } from '../../../store/tradingStore';

interface Props {
    system: SystemStatus | null;
    risk: RiskState | null;
    lastUpdate: number;
}

const SystemHealth: React.FC<Props> = ({ system, risk, lastUpdate }) => {
    const timeSinceUpdate = lastUpdate ? Math.round((Date.now() - lastUpdate) / 1000) : 999;
    const isStale = timeSinceUpdate > 30;

    return (
        <div className="bg-[#0a0a0a] border border-[#222] rounded-xl p-3 space-y-2.5">
            <div className="flex items-center gap-2 border-b border-[#222] pb-2">
                <Cpu size={14} className="text-gray-400" />
                <span className="text-white text-xs font-bold tracking-wider">SYSTEM HEALTH</span>
                <div className={`ml-auto flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                    system?.running 
                        ? 'bg-emerald-900/40 text-emerald-400 border-emerald-500/30'
                        : 'bg-red-900/40 text-red-400 border-red-500/30'
                }`}>
                    <Radio size={8} className={system?.running ? 'animate-pulse' : ''} />
                    {system?.running ? 'ONLINE' : 'OFFLINE'}
                </div>
            </div>

            {/* Status Rows */}
            <StatusRow
                icon={<Zap size={11} />}
                label="Engine Mode"
                value={system?.mode?.toUpperCase() || 'UNKNOWN'}
                color={system?.mode === 'paper' ? '#42a5f5' : system?.mode === 'live' ? '#ff9800' : '#78909c'}
            />
            <StatusRow
                icon={risk?.broker_connected ? <Wifi size={11} /> : <WifiOff size={11} />}
                label="Broker"
                value={risk?.broker_connected ? 'CONNECTED' : 'DISCONNECTED'}
                color={risk?.broker_connected ? '#00e676' : '#ff5252'}
            />
            <StatusRow
                icon={<AlertTriangle size={11} />}
                label="Kill Switch"
                value={risk?.kill_switch_active ? 'ACTIVE' : 'SAFE'}
                color={risk?.kill_switch_active ? '#ff1744' : '#00e676'}
            />
            <StatusRow
                icon={<Database size={11} />}
                label="Circuit Breaker"
                value={risk?.circuit_breaker?.is_open ? `OPEN (${risk.circuit_breaker.failures} fails)` : 'CLOSED'}
                color={risk?.circuit_breaker?.is_open ? '#ff5252' : '#00e676'}
            />
            <StatusRow
                icon={<Clock size={11} />}
                label="Last Update"
                value={isStale ? `${timeSinceUpdate}s ago ⚠️` : `${timeSinceUpdate}s ago`}
                color={isStale ? '#ff9800' : '#78909c'}
            />

            {risk?.kill_switch_active && risk.kill_switch_reason && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="bg-red-900/30 border border-red-500/30 rounded-lg p-2 text-[10px] text-red-300 font-mono"
                >
                    ⚠ KILL SWITCH: {risk.kill_switch_reason}
                </motion.div>
            )}
        </div>
    );
};

const StatusRow: React.FC<{ icon: React.ReactNode; label: string; value: string; color: string }> = ({
    icon, label, value, color
}) => (
    <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
            <span className="text-slate-600">{icon}</span>
            {label}
        </div>
        <span className="text-[10px] font-mono font-bold" style={{ color }}>{value}</span>
    </div>
);

export default SystemHealth;
