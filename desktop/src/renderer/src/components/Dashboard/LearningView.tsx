import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Brain, Database, Layers, Zap, Activity } from 'lucide-react';

interface LearningStats {
    total_skills: number;
    experiences_logged: number;
    patterns_identified: number;
    strategies_optimized: number;
    efficiency_score: number;
}

export default function LearningView() {
    const [stats, setStats] = useState<LearningStats>({
        total_skills: 0,
        experiences_logged: 0,
        patterns_identified: 0,
        strategies_optimized: 0,
        efficiency_score: 0.0
    });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await fetch('http://localhost:8000/api/learning/stats');
                const data = await res.json();
                setStats(data);
            } catch (e) {
                console.error("Failed to fetch learning stats", e);
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
        // Poll every 5 seconds
        const interval = setInterval(fetchStats, 5000);
        return () => clearInterval(interval);
    }, []);

    const container = {
        hidden: { opacity: 0 },
        show: {
            opacity: 1,
            transition: {
                staggerChildren: 0.1
            }
        }
    };

    const item = {
        hidden: { y: 20, opacity: 0 },
        show: { y: 0, opacity: 1 }
    };

    return (
        <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="grid grid-cols-2 lg:grid-cols-4 gap-4 p-4"
        >
            {/* Efficiency Score */}
            <motion.div variants={item} className="col-span-2 lg:col-span-4 p-6 rounded-2xl bg-gradient-to-r from-cyan-900/40 to-blue-900/40 border border-cyan-500/30">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-cyan-400 text-sm font-mono mb-1">SYSTEM EFFICIENCY</h3>
                        <div className="text-4xl font-bold text-white flex items-end gap-2">
                            {(stats.efficiency_score * 100).toFixed(1)}%
                            <span className="text-sm text-cyan-500/60 mb-1 font-normal">optimization rate</span>
                        </div>
                    </div>
                    <div className="p-4 rounded-full bg-cyan-500/10 text-cyan-400">
                        <Zap size={32} />
                    </div>
                </div>
                <div className="mt-4 h-2 bg-cyan-900/30 rounded-full overflow-hidden">
                    <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${stats.efficiency_score * 100}%` }}
                        transition={{ duration: 1, ease: "easeOut" }}
                        className="h-full bg-cyan-400 rounded-full shadow-[0_0_15px_rgba(0,255,255,0.5)]"
                    />
                </div>
            </motion.div>

            {/* Stat Cards */}
            <StatCard
                icon={Brain}
                label="ACTIVE SKILLS"
                value={stats.total_skills}
                color="text-purple-400"
                bg="bg-purple-900/20"
                border="border-purple-500/30"
            />
            <StatCard
                icon={Database}
                label="EXPERIENCES"
                value={stats.experiences_logged}
                color="text-emerald-400"
                bg="bg-emerald-900/20"
                border="border-emerald-500/30"
            />
            <StatCard
                icon={Layers}
                label="PATTERNS"
                value={stats.patterns_identified}
                color="text-amber-400"
                bg="bg-amber-900/20"
                border="border-amber-500/30"
            />
            <StatCard
                icon={Activity}
                label="STRATEGIES"
                value={stats.strategies_optimized}
                color="text-pink-400"
                bg="bg-pink-900/20"
                border="border-pink-500/30"
            />
        </motion.div>
    );
}

function StatCard({ icon: Icon, label, value, color, bg, border }: any) {
    return (
        <motion.div
            className={`p-4 rounded-xl border ${border} ${bg} backdrop-blur-sm relative overflow-hidden group`}
            whileHover={{ scale: 1.02 }}
        >
            <div className={`absolute -right-4 -bottom-4 opacity-10 group-hover:opacity-20 transition-opacity ${color}`}>
                <Icon size={80} />
            </div>
            <div className="relative z-10">
                <div className="flex items-center gap-2 mb-2">
                    <Icon size={16} className={color} />
                    <span className={`text-xs font-mono font-bold ${color} opacity-80`}>{label}</span>
                </div>
                <div className="text-2xl font-bold text-white">{value}</div>
            </div>
        </motion.div>
    );
}
