import React from 'react';
import { useTradingStore, ActiveSignal } from '../../../store/tradingStore';

export default function DebugPanel() {
    const {
        lastSequenceNumber,
        lastSnapshotUtc,
        lastEventTimestampUtc,
        engineClockHash,
        activeSignals,
        systemHalted
    } = useTradingStore();

    const signalsList = Object.values(activeSignals);

    return (
        <div className="absolute top-4 left-4 z-50 bg-black/80 backdrop-blur border border-cyan-500/30 rounded px-3 py-2 font-mono text-[9px] text-cyan-400/80 shadow-[0_4px_20px_rgba(0,0,0,0.8)] pointer-events-none">
            <div className="flex items-center gap-2 border-b border-cyan-500/20 pb-1 mb-1">
                <div className={`w-1.5 h-1.5 rounded-full ${systemHalted ? 'bg-red-500' : 'bg-emerald-400 animate-pulse'}`} />
                <span className="font-bold text-white tracking-widest">
                    {systemHalted ? 'SYSTEM HALTED' : 'STATE SYNC'}
                </span>
            </div>

            <div className="space-y-0.5">
                <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Event Seq:</span>
                    <span>{lastSequenceNumber}</span>
                </div>
                <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Snapshot UTC:</span>
                    <span>{lastSnapshotUtc ? lastSnapshotUtc.toFixed(2) : 'N/A'}</span>
                </div>
                <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Event UTC:</span>
                    <span>{lastEventTimestampUtc ? lastEventTimestampUtc.toFixed(2) : 'N/A'}</span>
                </div>
                <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Clock Hash:</span>
                    <span>{engineClockHash ? Math.abs(Number(engineClockHash)).toString().substring(0, 8) : 'N/A'}</span>
                </div>
                <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Active Signals:</span>
                    <span>{signalsList.length}</span>
                </div>
            </div>

            {signalsList.length > 0 && (
                <div className="mt-2 pt-1 border-t border-cyan-500/20">
                    {signalsList.map(sig => (
                        <div key={sig.signal_id} className="flex justify-between gap-4 text-[8px]">
                            <span className="text-amber-400">{sig.asset.split('_')[1] || sig.asset}</span>
                            <span className={sig.state === 'ACTIVE' ? 'text-emerald-400' : 'text-slate-400'}>
                                {sig.state} v{sig.version_number}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
