import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { MessageCircle, Shield, Wifi } from 'lucide-react';

export default function TelegramView() {
    const [status, setStatus] = useState<any>({ connected: false });
    const [loading, setLoading] = useState(true);

    const fetchStatus = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/telegram/status');
            const data = await res.json();
            setStatus(data);
        } catch (e) {
            console.error("Failed to fetch telegram status", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 10000); // Check every 10s
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex flex-col items-center justify-center p-8 space-y-6 h-full">
            <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className={`w-32 h-32 rounded-full flex items-center justify-center border-4 ${status.connected ? 'border-blue-500/50 bg-blue-500/10' : 'border-slate-600/50 bg-slate-700/10'
                    }`}
            >
                <MessageCircle size={64} className={status.connected ? 'text-blue-400' : 'text-slate-500'} />
            </motion.div>

            <div className="text-center">
                <h3 className="text-xl font-medium text-white mb-1">
                    Telegram Integration
                </h3>
                <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono border ${status.connected
                        ? 'bg-blue-500/20 border-blue-500/40 text-blue-300'
                        : 'bg-red-500/20 border-red-500/40 text-red-300'
                    }`}>
                    <div className={`w-2 h-2 rounded-full ${status.connected ? 'bg-blue-400 animate-pulse' : 'bg-red-400'}`} />
                    {status.connected ? 'CONNECTED' : 'DISCONNECTED'}
                </div>
            </div>

            {status.connected && (
                <div className="w-full max-w-xs bg-black/30 p-4 rounded-xl border border-blue-500/20 space-y-3">
                    <div className="flex justify-between text-sm">
                        <span className="text-slate-400">Bot Name</span>
                        <span className="text-white font-medium">{status.bot_name}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                        <span className="text-slate-400">Status</span>
                        <span className="text-emerald-400 font-mono uppercase">{status.status}</span>
                    </div>
                </div>
            )}

            <p className="text-center text-xs text-slate-500 max-w-sm">
                Use Telegram to remotely control the agent, receive alerts, and monitor long-running tasks.
            </p>
        </div>
    );
}
