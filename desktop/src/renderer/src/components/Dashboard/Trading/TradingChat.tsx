import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Bot, User, Loader2, Sparkles } from 'lucide-react';

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    source?: string;
    timestamp: number;
}

interface TradingChatProps {
    apiBase?: string;
}

/**
 * Trading Chat Copilot Panel.
 * Queries the deterministic engine state via /api/trading/chat.
 * Never fabricates numbers — all responses are grounded in engine outputs.
 */
const TradingChat: React.FC<TradingChatProps> = ({ apiBase = 'http://localhost:8000' }) => {
    const [messages, setMessages] = useState<ChatMessage[]>([
        {
            id: 'welcome',
            role: 'assistant',
            content: 'Trading Intelligence Copilot ready. Ask me about **bias**, **confidence**, **regime**, **sizing**, **risk**, **screener**, or request a full **summary**.',
            source: 'system',
            timestamp: Date.now(),
        },
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const chatContainerRef = useRef<HTMLDivElement>(null);
    const [userScrolledUp, setUserScrolledUp] = useState(false);

    const handleScroll = () => {
        if (chatContainerRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
            const isNearBottom = scrollHeight - scrollTop - clientHeight < 50;
            setUserScrolledUp(!isNearBottom);
        }
    };

    const scrollToBottom = () => {
        if (!userScrolledUp) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        const query = input.trim();
        if (!query || loading) return;

        const userMsg: ChatMessage = {
            id: `user-${Date.now()}`,
            role: 'user',
            content: query,
            timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            const res = await fetch(`${apiBase}/api/trading/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
            });
            const data = await res.json();

            const botMsg: ChatMessage = {
                id: `bot-${Date.now()}`,
                role: 'assistant',
                content: data.response || 'No response received.',
                source: data.source,
                timestamp: Date.now(),
            };

            setMessages((prev) => [...prev, botMsg]);
        } catch (err) {
            setMessages((prev) => [
                ...prev,
                {
                    id: `err-${Date.now()}`,
                    role: 'assistant',
                    content: 'Failed to reach trading engine. Is the backend running?',
                    source: 'error',
                    timestamp: Date.now(),
                },
            ]);
        } finally {
            setLoading(false);
        }
    };

    const quickQueries = ['What\'s the bias?', 'Risk mode?', 'Confidence?', 'Summary'];

    return (
        <div className="flex-1 flex flex-col bg-[#0a0a0a] border border-[#222] rounded-lg overflow-hidden">
            {/* Header */}
            <div className="p-3 border-b border-[#222] flex items-center gap-2">
                <Sparkles size={14} className="text-emerald-400" />
                <span className="text-gray-400 text-xs font-bold tracking-wider">
                    TRADING COPILOT
                </span>
            </div>

            {/* Messages */}
            <div 
                ref={chatContainerRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto custom-scrollbar p-3 flex flex-col gap-3"
            >
                <AnimatePresence>
                    {messages.map((msg) => (
                        <motion.div
                            key={msg.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.2 }}
                            className={`flex gap-2 items-start ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                        >
                            <div className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-[#222] text-gray-300'}`}>
                                {msg.role === 'user' ? <User size={12} /> : <Bot size={12} />}
                            </div>
                            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed font-mono whitespace-pre-wrap border ${
                                msg.role === 'user' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-50' : 'bg-[#1a1a1a] border-[#333] text-gray-300'
                            }`}>
                                {msg.content}
                                {msg.source && msg.role === 'assistant' && (
                                    <div className="mt-1 text-[9px] text-gray-500">
                                        source: {msg.source}
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>
                {loading && (
                    <div className="flex items-center gap-2 px-2 py-1">
                        <Loader2 size={12} className="text-emerald-400 animate-spin" />
                        <span className="text-[11px] text-gray-500">Analyzing engine state...</span>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Quick Queries */}
            <div className="px-3 py-1.5 flex gap-1.5 flex-wrap">
                {quickQueries.map((q) => (
                    <button
                        key={q}
                        onClick={() => {
                            setInput(q);
                            setTimeout(() => handleSend(), 50);
                        }}
                        className="px-2.5 py-1 rounded-md border border-[#333] bg-[#111] hover:bg-[#222] hover:border-[#444] text-gray-400 text-[10px] transition-colors cursor-pointer"
                    >
                        {q}
                    </button>
                ))}
            </div>

            {/* Input */}
            <div className="p-3 border-t border-[#222] bg-[#0a0a0a]">
                <div className="relative flex items-center">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        placeholder="Command the AI..."
                        className="w-full bg-[#1a1a1a] border border-[#444] rounded-lg pl-3 pr-10 py-2.5 text-xs text-white placeholder-gray-400 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50 transition-all shadow-inner font-mono"
                    />
                    <button
                        onClick={handleSend}
                        disabled={loading || !input.trim()}
                        className={`absolute right-1 w-8 h-8 rounded-md flex items-center justify-center transition-colors ${
                            loading || !input.trim() 
                                ? 'text-gray-500 bg-transparent cursor-not-allowed' 
                                : 'text-emerald-400 hover:text-white hover:bg-emerald-500/20 cursor-pointer'
                        }`}
                    >
                        <Send size={14} />
                    </button>
                </div>
            </div>
        </div>
    );
};

export default TradingChat;
