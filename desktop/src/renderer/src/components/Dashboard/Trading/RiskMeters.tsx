import React from 'react';
import { motion } from 'framer-motion';
import { Shield, ShieldAlert, ShieldOff, AlertTriangle, Activity } from 'lucide-react';

interface RiskData {
    mode?: string;
    r_multiplier?: number;
    rMultiplier?: number;
    signals_allowed?: boolean;
    signalsAllowed?: boolean;
    halted_reason?: string | null;
    haltedReason?: string | null;
    current_drawdown?: number;
    currentDrawdown?: number;
    max_drawdown?: number;
    maxDrawdown?: number;
    exposure_pct?: number;
    exposurePct?: number;
    confidence_avg?: number;
    confidenceAvg?: number;
    atr_percentile?: number;
    atrPercentile?: number;
    // Legacy fields from old TradingView
    drawdown?: string | number;
    risk_score?: number;
    regime?: string;
    volatility?: string | number;
}

interface RiskMetersProps {
    data?: RiskData;
    // Also accept individual props for direct usage
    mode?: string;
    rMultiplier?: number;
    signalsAllowed?: boolean;
    haltedReason?: string | null;
    currentDrawdown?: number;
    maxDrawdown?: number;
    exposurePct?: number;
    confidenceAvg?: number;
    atrPercentile?: number;
}

/**
 * Advanced Risk Meters — displays risk mode, drawdown, exposure, and system health.
 * Accepts both `data` prop (from TradingView) and individual props (direct usage).
 */
const RiskMeters: React.FC<RiskMetersProps> = (props) => {
    // Merge: individual props override data props
    const d = props.data || {};

    const mode = props.mode || d.mode || 'NORMAL';
    const rMultiplier = props.rMultiplier ?? d.rMultiplier ?? d.r_multiplier ?? 1.0;
    const signalsAllowed = props.signalsAllowed ?? d.signalsAllowed ?? d.signals_allowed ?? true;
    const haltedReason = props.haltedReason || d.haltedReason || d.halted_reason || null;
    const currentDrawdown = props.currentDrawdown ?? d.currentDrawdown ?? d.current_drawdown ?? parseFloat(String(d.drawdown || '0')) / 100 ?? 0;
    const maxDrawdown = props.maxDrawdown ?? d.maxDrawdown ?? d.max_drawdown ?? 0.20;
    const exposurePct = props.exposurePct ?? d.exposurePct ?? d.exposure_pct ?? 0;
    const confidenceAvg = props.confidenceAvg ?? d.confidenceAvg ?? d.confidence_avg ?? 0.5;
    const atrPercentile = props.atrPercentile ?? d.atrPercentile ?? d.atr_percentile ?? 50;

    const modeConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
        NORMAL: { color: '#00E676', icon: <Shield size={16} />, label: 'NORMAL' },
        DEFENSIVE: { color: '#FF9800', icon: <ShieldAlert size={16} />, label: 'DEFENSIVE' },
        CRITICAL: { color: '#FF5252', icon: <AlertTriangle size={16} />, label: 'CRITICAL' },
        HALTED: { color: '#FF1744', icon: <ShieldOff size={16} />, label: 'HALTED' },
    };

    const config = modeConfig[mode] || modeConfig.NORMAL;

    const GaugeBar: React.FC<{ value: number; max: number; label: string; color: string; suffix?: string }> = ({
        value,
        max,
        label,
        color,
        suffix = '%',
    }) => {
        const safeVal = typeof value === 'number' && isFinite(value) ? value : 0;
        const safeMax = typeof max === 'number' && max > 0 ? max : 1;
        const pct = Math.min(safeVal / safeMax, 1.0) * 100;
        return (
            <div style={{ marginBottom: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                    <span style={{ fontSize: '10px', color: '#78909C' }}>{label}</span>
                    <span style={{ fontSize: '10px', color, fontFamily: 'monospace', fontWeight: 600 }}>
                        {(safeVal * 100).toFixed(1)}{suffix}
                    </span>
                </div>
                <div style={{ height: '4px', borderRadius: '2px', background: 'rgba(255,255,255,0.06)' }}>
                    <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ duration: 0.5 }}
                        style={{
                            height: '100%',
                            borderRadius: '2px',
                            background: color,
                        }}
                    />
                </div>
            </div>
        );
    };

    const safeRMult = typeof rMultiplier === 'number' && isFinite(rMultiplier) ? rMultiplier : 1.0;

    return (
        <div
            style={{
                background: 'rgba(15, 20, 30, 0.95)',
                border: `1px solid ${config.color}22`,
                borderRadius: '12px',
                padding: '14px',
                marginBottom: '10px',
            }}
        >
            {/* Mode Badge */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <span style={{ color: '#90A4AE', fontSize: '11px', fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                    Risk Engine
                </span>
                <motion.div
                    key={mode}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 12px',
                        borderRadius: '8px',
                        background: `${config.color}18`,
                        border: `1px solid ${config.color}44`,
                        color: config.color,
                    }}
                >
                    {config.icon}
                    <span style={{ fontSize: '11px', fontWeight: 700, fontFamily: 'monospace' }}>{config.label}</span>
                </motion.div>
            </div>

            {/* R Multiplier */}
            <div style={{
                textAlign: 'center',
                marginBottom: '14px',
                padding: '8px',
                borderRadius: '8px',
                background: 'rgba(255,255,255,0.02)',
            }}>
                <div style={{ fontSize: '9px', color: '#546E7A', marginBottom: '2px' }}>R MULTIPLIER</div>
                <div style={{
                    fontSize: '24px',
                    fontWeight: 800,
                    fontFamily: 'monospace',
                    color: safeRMult >= 0.8 ? '#00E676' : safeRMult >= 0.4 ? '#FF9800' : '#FF5252',
                }}>
                    {safeRMult.toFixed(2)}R
                </div>
            </div>

            {/* Halted Warning */}
            {!signalsAllowed && (
                <div
                    style={{
                        padding: '8px 12px',
                        marginBottom: '10px',
                        borderRadius: '8px',
                        background: 'rgba(255, 23, 68, 0.1)',
                        border: '1px solid rgba(255, 23, 68, 0.3)',
                        fontSize: '10px',
                        color: '#FF1744',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                    }}
                >
                    <ShieldOff size={14} />
                    <div>
                        <div style={{ fontWeight: 700 }}>SIGNALS BLOCKED</div>
                        {haltedReason && <div style={{ marginTop: '2px', opacity: 0.7 }}>{haltedReason}</div>}
                    </div>
                </div>
            )}

            {/* Gauges */}
            <GaugeBar
                value={currentDrawdown}
                max={maxDrawdown}
                label="Drawdown"
                color={currentDrawdown > maxDrawdown * 0.7 ? '#FF5252' : currentDrawdown > maxDrawdown * 0.4 ? '#FF9800' : '#00E676'}
            />
            <GaugeBar
                value={exposurePct}
                max={1.0}
                label="Total Exposure"
                color={exposurePct > 0.8 ? '#FF5252' : exposurePct > 0.5 ? '#FF9800' : '#42A5F5'}
            />
            <GaugeBar
                value={confidenceAvg}
                max={1.0}
                label="Avg Confidence"
                color={confidenceAvg >= 0.6 ? '#00E676' : confidenceAvg >= 0.45 ? '#FF9800' : '#FF5252'}
            />

            {/* ATR Volatility */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '6px 0',
                borderTop: '1px solid rgba(255,255,255,0.04)',
                marginTop: '6px',
            }}>
                <span style={{ fontSize: '10px', color: '#78909C' }}>
                    <Activity size={10} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />
                    Volatility (ATR%)
                </span>
                <span style={{
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    fontWeight: 600,
                    color: atrPercentile > 80 ? '#FF5252' : atrPercentile > 50 ? '#FF9800' : '#42A5F5',
                }}>
                    {typeof atrPercentile === 'number' ? atrPercentile.toFixed(0) : '50'}th
                </span>
            </div>
        </div>
    );
};

export default RiskMeters;
