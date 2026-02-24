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

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
        <div
            style={{
                background: 'rgba(15, 20, 30, 0.95)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px',
                display: 'flex',
                flexDirection: 'column',
                height: '400px',
                overflow: 'hidden',
            }}
        >
            {/* Header */}
            <div
                style={{
                    padding: '12px 14px',
                    borderBottom: '1px solid rgba(255,255,255,0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                }}
            >
                <Sparkles size={14} color="#7C4DFF" />
                <span style={{ color: '#B0BEC5', fontSize: '12px', fontWeight: 600, letterSpacing: '0.5px' }}>
                    TRADING COPILOT
                </span>
            </div>

            {/* Messages */}
            <div
                style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '10px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                }}
            >
                <AnimatePresence>
                    {messages.map((msg) => (
                        <motion.div
                            key={msg.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.2 }}
                            style={{
                                display: 'flex',
                                gap: '8px',
                                alignItems: 'flex-start',
                                flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                            }}
                        >
                            <div
                                style={{
                                    width: '24px',
                                    height: '24px',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    background: msg.role === 'user' ? 'rgba(33, 150, 243, 0.2)' : 'rgba(124, 77, 255, 0.2)',
                                    flexShrink: 0,
                                }}
                            >
                                {msg.role === 'user' ? (
                                    <User size={12} color="#2196F3" />
                                ) : (
                                    <Bot size={12} color="#7C4DFF" />
                                )}
                            </div>
                            <div
                                style={{
                                    background: msg.role === 'user' ? 'rgba(33, 150, 243, 0.1)' : 'rgba(255,255,255,0.04)',
                                    border: `1px solid ${msg.role === 'user' ? 'rgba(33, 150, 243, 0.2)' : 'rgba(255,255,255,0.06)'}`,
                                    borderRadius: '10px',
                                    padding: '8px 12px',
                                    maxWidth: '85%',
                                    fontSize: '12px',
                                    color: '#CFD8DC',
                                    lineHeight: 1.5,
                                    whiteSpace: 'pre-wrap',
                                    fontFamily: 'monospace',
                                }}
                            >
                                {msg.content}
                                {msg.source && msg.role === 'assistant' && (
                                    <div style={{ marginTop: '4px', fontSize: '9px', color: '#546E7A' }}>
                                        source: {msg.source}
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>
                {loading && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 8px' }}>
                        <Loader2 size={12} color="#7C4DFF" className="animate-spin" />
                        <span style={{ fontSize: '11px', color: '#546E7A' }}>Analyzing engine state...</span>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Quick Queries */}
            <div style={{ padding: '6px 10px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {quickQueries.map((q) => (
                    <button
                        key={q}
                        onClick={() => {
                            setInput(q);
                            setTimeout(() => handleSend(), 50);
                        }}
                        style={{
                            padding: '3px 10px',
                            borderRadius: '12px',
                            border: '1px solid rgba(124, 77, 255, 0.3)',
                            background: 'rgba(124, 77, 255, 0.08)',
                            color: '#B388FF',
                            fontSize: '10px',
                            cursor: 'pointer',
                            transition: 'all 0.15s',
                        }}
                        onMouseEnter={(e) => {
                            (e.target as HTMLButtonElement).style.background = 'rgba(124, 77, 255, 0.2)';
                        }}
                        onMouseLeave={(e) => {
                            (e.target as HTMLButtonElement).style.background = 'rgba(124, 77, 255, 0.08)';
                        }}
                    >
                        {q}
                    </button>
                ))}
            </div>

            {/* Input */}
            <div
                style={{
                    padding: '10px',
                    borderTop: '1px solid rgba(255,255,255,0.06)',
                    display: 'flex',
                    gap: '8px',
                }}
            >
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Ask about bias, confidence, regime..."
                    style={{
                        flex: 1,
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: '8px',
                        padding: '8px 12px',
                        color: '#CFD8DC',
                        fontSize: '12px',
                        outline: 'none',
                        fontFamily: 'monospace',
                    }}
                />
                <button
                    onClick={handleSend}
                    disabled={loading || !input.trim()}
                    style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '8px',
                        border: 'none',
                        background: loading ? 'rgba(124, 77, 255, 0.2)' : 'rgba(124, 77, 255, 0.4)',
                        color: '#B388FF',
                        cursor: loading ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    <Send size={14} />
                </button>
            </div>
        </div>
    );
};

export default TradingChat;
