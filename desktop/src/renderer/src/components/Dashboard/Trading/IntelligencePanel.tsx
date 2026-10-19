import React, { useEffect, useState, useCallback } from 'react';

// ── Types ────────────────────────────────────────────────────
interface ConfidenceBreakdown {
    scores: {
        technical: number;
        ta_conviction: number;
        ml_model: number;
        historical: number;
    };
    weights: {
        technical: number;
        ta_conviction: number;
        ml_model: number;
        historical: number;
    };
    confidence: number;
    action: string;
    direction: string;
}

interface LLMBudget {
    daily_limit: number;
    daily_spent: number;
    daily_remaining: number;
}

const API = 'http://localhost:8000';

const SOURCE_LABELS: Record<string, string> = {
    technical: 'Technical Signal',
    ta_conviction: 'TradingAgents AI',
    ml_model: 'ML Predictor',
    historical: 'Historical Win Rate',
};

const SOURCE_COLORS: Record<string, string> = {
    technical: '#00c853',
    ta_conviction: '#448aff',
    ml_model: '#e040fb',
    historical: '#ff9100',
};

function getActionStyle(action: string) {
    switch (action) {
        case 'ALLOW': return { bg: 'bg-emerald-500/15', border: 'border-emerald-500/30', text: 'text-emerald-400', glow: 'shadow-[0_0_12px_rgba(16,185,129,0.3)]' };
        case 'REDUCE': return { bg: 'bg-amber-500/15', border: 'border-amber-500/30', text: 'text-amber-400', glow: 'shadow-[0_0_12px_rgba(245,158,11,0.3)]' };
        case 'BLOCK': return { bg: 'bg-red-500/15', border: 'border-red-500/30', text: 'text-red-400', glow: 'shadow-[0_0_12px_rgba(239,68,68,0.3)]' };
        default: return { bg: 'bg-white/5', border: 'border-white/10', text: 'text-white/50', glow: '' };
    }
}

// ── Component ────────────────────────────────────────────────
export default function IntelligencePanel() {
    const [insights, setInsights] = useState<string[]>([]);
    const [budget, setBudget] = useState<LLMBudget | null>(null);
    const [debateSummary, setDebateSummary] = useState<{
        conviction: number; direction: string; debate_summary: string;
        risk_assessment: string; cached_at: string | null;
    } | null>(null);
    const [loading, setLoading] = useState(false);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [insightsRes, budgetRes] = await Promise.all([
                fetch(`${API}/api/trading/insights`).catch(() => null),
                fetch(`${API}/api/trading/llm-budget`).catch(() => null),
            ]);

            if (insightsRes?.ok) {
                const json = await insightsRes.json();
                setInsights(json.insights || []);
            }
            if (budgetRes?.ok) {
                const json = await budgetRes.json();
                setBudget(json.budget || null);
            }

            // Fetch debate summary for the first watchlist symbol
            try {
                const debateRes = await fetch(`${API}/api/trading/debate-summary/SPY`);
                if (debateRes?.ok) {
                    const json = await debateRes.json();
                    setDebateSummary(json);
                }
            } catch { /* optional */ }
        } catch (e) {
            console.error('Intelligence panel fetch error:', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60000);
        return () => clearInterval(interval);
    }, [fetchData]);

    return (
        <div className="flex flex-col gap-3">
            {/* Confidence Breakdown (static placeholder until live signal) */}
            <div className="bg-[#0a0a0a] rounded-xl border border-[#222] overflow-hidden">
                <div className="flex items-center gap-2 px-3 py-2 border-b border-[#222]">
                    <div className="w-2 h-2 rounded-full bg-cyan-500" />
                    <span className="text-[11px] font-bold tracking-wider text-white/80">CONFIDENCE SOURCES</span>
                </div>

                <div className="p-3 space-y-3">
                    {Object.entries(SOURCE_LABELS).map(([key, label]) => {
                        const color = SOURCE_COLORS[key];
                        const weight = key === 'technical' ? 0.25 : key === 'ta_conviction' ? 0.30 : key === 'ml_model' ? 0.20 : 0.25;

                        return (
                            <div key={key} className="space-y-1">
                                <div className="flex items-center justify-between">
                                    <span className="text-[10px] font-mono text-white/60">{label}</span>
                                    <span className="text-[9px] font-mono text-white/30">{(weight * 100).toFixed(0)}% weight</span>
                                </div>
                                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                                    <div
                                        className="h-full rounded-full transition-all duration-500"
                                        style={{
                                            width: '50%', // Neutral when no live signal
                                            backgroundColor: color,
                                            opacity: 0.6,
                                        }}
                                    />
                                </div>
                            </div>
                        );
                    })}

                    <div className="flex items-center justify-between pt-2 border-t border-[#222]">
                        <span className="text-[10px] font-mono text-white/40">Aggregated Score</span>
                        <div className="flex items-center gap-2">
                            <span className="text-lg font-bold text-white/60 font-mono">--</span>
                            <span className="text-[9px] px-2 py-0.5 rounded border bg-white/5 border-white/10 text-white/30 font-mono">
                                WAITING
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* TradingAgents Debate Summary */}
            {debateSummary && (
                <div className="bg-[#0a0a0a] rounded-xl border border-[#222] overflow-hidden">
                    <div className="flex items-center justify-between px-3 py-2 border-b border-[#222]">
                        <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-blue-500" />
                            <span className="text-[11px] font-bold tracking-wider text-white/80">TA DEBATE</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded ${
                                debateSummary.direction === 'BUY' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' :
                                debateSummary.direction === 'SELL' ? 'bg-red-500/15 text-red-400 border border-red-500/30' :
                                'bg-white/5 text-white/40 border border-white/10'
                            }`}>
                                {debateSummary.direction}
                            </span>
                            <span className="text-[10px] font-mono text-white/50">
                                {(debateSummary.conviction * 100).toFixed(0)}%
                            </span>
                        </div>
                    </div>

                    <div className="p-3 space-y-2">
                        <div className="text-[10px] font-mono text-white/60 leading-relaxed max-h-[120px] overflow-y-auto custom-scrollbar">
                            {debateSummary.debate_summary || 'No debate data available.'}
                        </div>
                        {debateSummary.risk_assessment && (
                            <div className="text-[9px] font-mono text-amber-400/50 border-t border-[#222] pt-2">
                                Risk: {debateSummary.risk_assessment}
                            </div>
                        )}
                        {debateSummary.cached_at && (
                            <div className="text-[8px] font-mono text-white/20 text-right">
                                Updated: {new Date(debateSummary.cached_at).toLocaleTimeString()}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Learning Insights */}
            <div className="bg-[#0a0a0a] rounded-xl border border-[#222] overflow-hidden">
                <div className="flex items-center gap-2 px-3 py-2 border-b border-[#222]">
                    <div className="w-2 h-2 rounded-full bg-amber-500" />
                    <span className="text-[11px] font-bold tracking-wider text-white/80">LEARNING INSIGHTS</span>
                </div>

                <div className="p-3 space-y-2 max-h-[200px] overflow-y-auto custom-scrollbar">
                    {insights.length > 0 ? (
                        insights.map((insight, i) => (
                            <div key={i} className="flex gap-2 text-[10px] font-mono text-white/60 leading-relaxed">
                                <span className="text-amber-500/60 shrink-0">*</span>
                                <span>{insight}</span>
                            </div>
                        ))
                    ) : (
                        <div className="text-[10px] font-mono text-white/20 text-center py-4">
                            {loading ? 'Loading insights...' : 'No insights yet. Complete more trades.'}
                        </div>
                    )}
                </div>
            </div>

            {/* LLM Budget */}
            {budget && (
                <div className="bg-[#0a0a0a] rounded-xl border border-[#222] overflow-hidden">
                    <div className="flex items-center gap-2 px-3 py-2 border-b border-[#222]">
                        <div className="w-2 h-2 rounded-full bg-violet-500" />
                        <span className="text-[11px] font-bold tracking-wider text-white/80">LLM BUDGET</span>
                    </div>

                    <div className="p-3">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[10px] font-mono text-white/40">Daily Spend</span>
                            <span className="text-[11px] font-mono text-white/70">
                                ${budget.daily_spent.toFixed(4)} / ${budget.daily_limit.toFixed(2)}
                            </span>
                        </div>
                        <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                            <div
                                className="h-full rounded-full transition-all duration-500"
                                style={{
                                    width: `${Math.min(100, (budget.daily_spent / budget.daily_limit) * 100)}%`,
                                    backgroundColor: budget.daily_spent > budget.daily_limit * 0.8 ? '#ff5252' : '#7c4dff',
                                }}
                            />
                        </div>
                        <div className="flex items-center justify-between mt-1">
                            <span className="text-[9px] font-mono text-white/30">Remaining: ${budget.daily_remaining.toFixed(4)}</span>
                            <span className={`text-[9px] font-mono ${budget.daily_remaining > 0 ? 'text-emerald-400/60' : 'text-red-400/60'}`}>
                                {budget.daily_remaining > 0 ? 'ACTIVE' : 'EXHAUSTED'}
                            </span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
