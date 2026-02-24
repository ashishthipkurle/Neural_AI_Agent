import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Zap } from 'lucide-react';

interface TimeframeBias {
    timeframe: string;
    score: number;
    label: string;
}

interface BiasHUDProps {
    fusionScore: number;
    fusionLabel: string;
    htfScore: number;
    ltfScore: number;
    overrideActive: boolean;
    timeframes: TimeframeBias[];
    regime: string;
    regimeStable: boolean;
}

/**
 * Multi-Timeframe Bias HUD — displays directional bias across all timeframes
 * with fusion score, HTF/LTF split, and regime indicator.
 */
const BiasHUD: React.FC<BiasHUDProps> = ({
    fusionScore,
    fusionLabel,
    htfScore,
    ltfScore,
    overrideActive,
    timeframes,
    regime,
    regimeStable,
}) => {
    const getBiasColor = (score: number): string => {
        if (score >= 2.0) return '#00E676';
        if (score >= 0.5) return '#66BB6A';
        if (score > -0.5) return '#78909C';
        if (score > -2.0) return '#EF5350';
        return '#FF1744';
    };

    const getBiasIcon = (score: number) => {
        if (score >= 0.5) return <TrendingUp size={14} />;
        if (score <= -0.5) return <TrendingDown size={14} />;
        return <Minus size={14} />;
    };

    const getBarWidth = (score: number): number => {
        // Map -3..+3 to 0..100
        return Math.max(5, ((score + 3) / 6) * 100);
    };

    const regimeColors: Record<string, string> = {
        TRENDING_VOLATILE: '#FF9800',
        LOW_VOL_RANGE: '#42A5F5',
        MEAN_REVERTING: '#78909C',
        EXPANSION_BREAKOUT: '#00E676',
        QUIET: '#546E7A',
    };

    return (
        <div style={{
            background: 'rgba(15, 20, 30, 0.95)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '12px',
            padding: '14px',
            marginBottom: '10px',
        }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ color: '#90A4AE', fontSize: '11px', fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                    Multi-TF Bias
                </span>
                <div style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    padding: '2px 8px', borderRadius: '6px',
                    background: `${regimeColors[regime] || '#546E7A'}22`,
                    border: `1px solid ${regimeColors[regime] || '#546E7A'}44`,
                }}>
                    {!regimeStable && <AlertTriangle size={10} color="#FF9800" />}
                    <span style={{ fontSize: '9px', color: regimeColors[regime] || '#546E7A', fontWeight: 700 }}>
                        {regime}
                    </span>
                </div>
            </div>

            {/* Fusion Score */}
            <div style={{ textAlign: 'center', marginBottom: '12px' }}>
                <motion.div
                    key={fusionLabel}
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    style={{
                        fontSize: '28px',
                        fontWeight: 800,
                        color: getBiasColor(fusionScore),
                        fontFamily: 'monospace',
                    }}
                >
                    {fusionScore >= 0 ? '+' : ''}{fusionScore.toFixed(2)}
                </motion.div>
                <div style={{ fontSize: '11px', color: getBiasColor(fusionScore), fontWeight: 600, marginTop: '2px' }}>
                    {fusionLabel}
                </div>
            </div>

            {/* HTF / LTF Split */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                <div style={{
                    flex: 1, padding: '8px', borderRadius: '8px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.06)',
                }}>
                    <div style={{ fontSize: '9px', color: '#78909C', marginBottom: '4px' }}>HTF (60%)</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: getBiasColor(htfScore), fontFamily: 'monospace' }}>
                        {htfScore >= 0 ? '+' : ''}{htfScore.toFixed(2)}
                    </div>
                </div>
                <div style={{
                    flex: 1, padding: '8px', borderRadius: '8px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.06)',
                }}>
                    <div style={{ fontSize: '9px', color: '#78909C', marginBottom: '4px' }}>
                        LTF (40%) {overrideActive && <Zap size={10} color="#FF9800" style={{ display: 'inline' }} />}
                    </div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: getBiasColor(ltfScore), fontFamily: 'monospace' }}>
                        {ltfScore >= 0 ? '+' : ''}{ltfScore.toFixed(2)}
                    </div>
                </div>
            </div>

            {/* Override Warning */}
            {overrideActive && (
                <div style={{
                    padding: '6px 10px', marginBottom: '10px', borderRadius: '6px',
                    background: 'rgba(255, 152, 0, 0.1)',
                    border: '1px solid rgba(255, 152, 0, 0.3)',
                    fontSize: '10px', color: '#FF9800',
                    display: 'flex', alignItems: 'center', gap: '6px',
                }}>
                    <Zap size={12} /> HTF Override Active — LTF bias clamped
                </div>
            )}

            {/* Per-Timeframe Bars */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {timeframes.map((tf) => (
                    <div key={tf.timeframe} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '10px', color: '#78909C', width: '28px', fontFamily: 'monospace', textAlign: 'right' }}>
                            {tf.timeframe}
                        </span>
                        <div style={{
                            flex: 1, height: '6px', borderRadius: '3px',
                            background: 'rgba(255,255,255,0.06)',
                            overflow: 'hidden',
                            position: 'relative',
                        }}>
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${getBarWidth(tf.score)}%` }}
                                transition={{ duration: 0.5, ease: 'easeOut' }}
                                style={{
                                    height: '100%', borderRadius: '3px',
                                    background: getBiasColor(tf.score),
                                }}
                            />
                        </div>
                        <span style={{ fontSize: '10px', color: getBiasColor(tf.score), width: '36px', fontFamily: 'monospace' }}>
                            {tf.score >= 0 ? '+' : ''}{tf.score.toFixed(1)}
                        </span>
                        {getBiasIcon(tf.score)}
                    </div>
                ))}
            </div>
        </div>
    );
};

export default BiasHUD;
