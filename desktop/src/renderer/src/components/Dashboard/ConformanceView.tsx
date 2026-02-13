import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck } from 'lucide-react';

interface Conformance {
    overall: string;
    counts: {
        implemented: number;
        partial: number;
        missing: number;
    };
    checks?: Array<{
        area: string;
        status: string;
    }>;
}

export default function ConformanceView() {
    const [data, setData] = useState<Conformance | null>(null);

    const fetchConformance = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/architecture/conformance');
            const body = await res.json();
            setData(body);
        } catch (e) {
            console.error('Failed to fetch architecture conformance', e);
        }
    };

    useEffect(() => {
        fetchConformance();
        const interval = setInterval(fetchConformance, 10000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="h-full p-6 flex flex-col gap-4">
            <div className="flex items-center justify-between">
                <h2 className="text-cyan-400 font-mono text-sm tracking-wider">ARCHITECTURE CONFORMANCE</h2>
                {data && (
                    <span className={`text-[10px] font-mono uppercase px-2 py-1 rounded border ${data.overall === 'implemented'
                        ? 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10'
                        : 'text-amber-300 border-amber-500/40 bg-amber-500/10'
                        }`}>
                        {data.overall}
                    </span>
                )}
            </div>

            <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-cyan-500/30 bg-cyan-950/20 p-5"
            >
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl border border-cyan-500/40 bg-cyan-500/10 flex items-center justify-center">
                        <ShieldCheck size={20} className="text-cyan-300" />
                    </div>
                    <div className="text-sm text-cyan-100">Live report from <span className="font-mono">/api/architecture/conformance</span></div>
                </div>

                {data ? (
                    <>
                        <div className="grid grid-cols-3 gap-3 text-xs font-mono mb-4">
                            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-emerald-300 text-center">
                                {data.counts.implemented} implemented
                            </div>
                            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-amber-300 text-center">
                                {data.counts.partial} partial
                            </div>
                            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-red-300 text-center">
                                {data.counts.missing} missing
                            </div>
                        </div>

                        <div className="space-y-2 max-h-[290px] overflow-y-auto custom-scrollbar pr-1">
                            {(data.checks || []).map((check) => (
                                <div
                                    key={check.area}
                                    className="flex items-center justify-between rounded-lg border border-slate-700/50 bg-black/20 px-3 py-2"
                                >
                                    <span className="text-cyan-100 text-sm">{check.area.replace(/_/g, ' ')}</span>
                                    <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${check.status === 'implemented'
                                        ? 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10'
                                        : check.status === 'partial'
                                            ? 'text-amber-300 border-amber-500/40 bg-amber-500/10'
                                            : 'text-red-300 border-red-500/40 bg-red-500/10'
                                        }`}>
                                        {check.status}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </>
                ) : (
                    <div className="text-slate-400 text-sm">Loading conformance report...</div>
                )}
            </motion.div>
        </div>
    );
}
