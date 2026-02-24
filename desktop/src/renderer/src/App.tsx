import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    Mic,
    MicOff,
    Send,
    Code,
    Search,
    FolderOpen,
    Settings,
    Eye,
    Cpu,
    Activity,
    Wifi,
    Clock,
    Sparkles,
    Maximize2,
    Minimize2,
    Paperclip,
    X,
    Plus,
    MessageSquare,
    Camera,
    Trash2,
    LineChart
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import AIGlobe from "./components/AIGlobe";
import CodeEditorView from "./components/CodeEditor/CodeEditorView";
import Dashboard from "./components/Dashboard/Dashboard";
import TradingView from "./components/Dashboard/TradingView";
import { api } from "./lib/api";

/* ================= TYPES ================= */

type AIState = "idle" | "listening" | "thinking" | "speaking";

interface Message {
    id: string;
    role: "user" | "assistant" | "system";
    content: string;
    image?: string;
    kind?: "trace" | "indicator" | "system";
}

/* ================= BACKGROUND ================= */

function GeometricBackground() {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current!;
        const ctx = canvas.getContext("2d")!;
        const resize = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        };
        resize();
        window.addEventListener("resize", resize);

        const nodes = Array.from({ length: 30 }).map(() => ({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.15,
            vy: (Math.random() - 0.5) * 0.15,
        }));

        let raf: number;
        const draw = () => {
            // Neutral black background
            ctx.fillStyle = "#050505";
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            nodes.forEach((n) => {
                n.x += n.vx;
                n.y += n.vy;
                if (n.x < 0 || n.x > canvas.width) n.vx *= -1;
                if (n.y < 0 || n.y > canvas.height) n.vy *= -1;
            });

            ctx.strokeStyle = "rgba(255,255,255,0.02)";
            for (let i = 0; i < nodes.length; i++) {
                for (let j = i + 1; j < nodes.length; j++) {
                    const dx = nodes[i].x - nodes[j].x;
                    const dy = nodes[i].y - nodes[j].y;
                    const d = Math.sqrt(dx * dx + dy * dy);
                    if (d < 180) {
                        ctx.beginPath();
                        ctx.moveTo(nodes[i].x, nodes[i].y);
                        ctx.lineTo(nodes[j].x, nodes[j].y);
                        ctx.stroke();
                    }
                }
            }

            nodes.forEach((n) => {
                ctx.beginPath();
                ctx.arc(n.x, n.y, 2, 0, Math.PI * 2);
                ctx.fillStyle = "rgba(255,255,255,0.06)";
                ctx.fill();
            });

            raf = requestAnimationFrame(draw);
        };

        draw();
        return () => {
            cancelAnimationFrame(raf);
            window.removeEventListener("resize", resize);
        };
    }, []);

    return <canvas ref={canvasRef} className="fixed inset-0 z-0" />;
}

/* ================= STATUS BAR ================= */

function StatusHUD({ aiState }: { aiState: AIState }) {
    const [time, setTime] = useState(new Date());
    useEffect(() => {
        const i = setInterval(() => setTime(new Date()), 1000);
        return () => clearInterval(i);
    }, []);

    return (
        <div className="fixed top-0 left-0 right-0 z-50 px-6 py-4 flex justify-between text-xs font-mono text-slate-300">
            <div className="flex gap-8">
                <span className="flex items-center gap-2">
                    <Cpu size={14} /> CPU: <b className="text-slate-100">26%</b>
                </span>
                <span className="flex items-center gap-2">
                    <Activity size={14} /> Status:{" "}
                    <b className="text-slate-100">{aiState.toUpperCase()}</b>
                </span>
            </div>
            <div className="flex gap-8">
                <span className="flex items-center gap-2">
                    <Wifi size={14} /> Latency: <b className="text-slate-100">0ms</b>
                </span>
                <span className="flex items-center gap-2">
                    <Clock size={14} />{" "}
                    {time.toLocaleTimeString("en-US", {
                        hour: "2-digit",
                        minute: "2-digit",
                    })}
                </span>
            </div>
        </div>
    );
}

/* ================= HISTORY PANEL ================= */

/* ================= HISTORY PANEL ================= */

interface Metrics {
    tps: number;
    contextUsed: number;
    ttft: number;
    totalLatency: number;
    vramUsage: number[];
}

interface Conversation {
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
}

interface HistoryPanelProps {
    metrics: Metrics;
    onSelectChat: (id: string) => void;
    onCreateChat: () => void;
    activeChatId: string | null;
    onDeleteActiveChat: () => void;
}

function HistoryPanel({ metrics, onSelectChat, onCreateChat, activeChatId, onDeleteActiveChat }: HistoryPanelProps) {
    const [activeTab, setActiveTab] = useState<'history' | 'analysis'>('history');
    const [searchQuery, setSearchQuery] = useState("");
    const [conversations, setConversations] = useState<Conversation[]>([]);

    const fetchConversations = () => {
        fetch('http://localhost:8000/api/conversations')
            .then(res => res.json())
            .then(data => {
                if (Array.isArray(data)) {
                    setConversations(data);
                } else {
                    console.error("Invalid history data:", data);
                    setConversations([]);
                }
            })
            .catch(err => {
                console.error("Failed to fetch history:", err);
                setConversations([]);
            });
    };

    // Fetch conversations on mount
    useEffect(() => {
        fetchConversations();
    }, []);

    // Refetch when switching TO the history tab, or when asked (via props if we could but here we can just expose refresh)
    useEffect(() => {
        if (activeTab === 'history') {
            fetchConversations();
        }
    }, [activeTab, conversations.length]); // Auto refresh if count changes locally (optimistic ui)

    const filteredHistory = conversations.filter(item =>
        item.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleDelete = async (id: string) => {
        try {
            await fetch(`http://localhost:8000/api/conversations/${id}`, {
                method: 'DELETE',
            });
            // Update local list instantly
            setConversations(prev => prev.filter(c => c.id !== id));

            // If deleting active chat, notify parent
            if (id === activeChatId) {
                onDeleteActiveChat();
            }
        } catch (e) {
            console.error("Delete chat error", e);
        }
    };

    return (
        <div
            className="w-full h-full rounded-2xl flex flex-col"
            style={{
                background: "rgba(0,0,0,0.55)",
                border: "1px solid rgba(255,255,255,0.08)",
                backdropFilter: "blur(10px)",
            }}
        >
            {/* Tab Header */}
            <div className="px-2 py-2 flex items-center gap-1 border-b border-white/10">
                <button
                    onClick={() => setActiveTab('history')}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'history'
                        ? 'bg-white/5 text-slate-100'
                        : 'text-slate-400/70 hover:text-slate-200 hover:bg-white/5'
                        }`}
                >
                    History
                </button>
                <button
                    onClick={() => setActiveTab('analysis')}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'analysis'
                        ? 'bg-white/5 text-slate-100'
                        : 'text-slate-400/70 hover:text-slate-200 hover:bg-white/5'
                        }`}
                >
                    Analysis
                </button>
            </div>

            {/* CONTENT AREA */}
            <div className="flex-1 overflow-hidden flex flex-col relative">

                {/* === HISTORY VIEW === */}
                {activeTab === 'history' && (
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="flex-1 flex flex-col min-h-0"
                    >
                        {/* Header & New Chat */}
                        <div className="px-4 py-3 flex items-center gap-2 justify-between">
                            <div className="flex items-center gap-2">
                                <span className="text-base font-medium text-white">Recent Chats</span>
                            </div>
                            <button
                                onClick={onCreateChat}
                                className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-200 transition-colors flex items-center gap-1 text-xs"
                            >
                                <Plus size={14} />
                                New Chat
                            </button>
                        </div>

                        {/* Search Box */}
                        <div className="px-4 pb-3">
                            <div className="flex rounded-lg overflow-hidden border border-white/10"
                                style={{ background: "rgba(255,255,255,0.03)" }}>
                                <Search size={14} className="ml-3 my-auto text-slate-300/60" />
                                <input
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder="Search history..."
                                    className="flex-1 px-2 py-2 bg-transparent text-slate-200 text-sm focus:outline-none placeholder:text-slate-500"
                                />
                            </div>
                        </div>

                        {/* History Items - Scrollable */}
                        <div className="flex-1 px-4 pb-4 space-y-2 overflow-y-auto">
                            {filteredHistory.map((item) => (
                                <div
                                    key={item.id}
                                    onClick={() => onSelectChat(item.id)}
                                    className={`group relative p-2.5 rounded-lg flex items-center gap-2.5 cursor-pointer transition-all border ${activeChatId === item.id
                                        ? 'bg-white/5 border-white/10'
                                        : 'bg-transparent border-transparent hover:bg-white/5'
                                        }`}
                                >
                                    <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center border border-white/10 text-slate-200">
                                        <MessageSquare size={14} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm text-slate-200 truncate">{item.title || "New Chat"}</div>
                                        <div className="text-xs text-slate-400/70">{new Date(item.updated_at).toLocaleString()}</div>
                                    </div>

                                    {/* Delete Button - Visible on Hover */}
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleDelete(item.id);
                                        }}
                                        className="opacity-0 group-hover:opacity-100 p-1.5 rounded-md hover:bg-red-500/20 text-red-400 transition-all absolute right-2"
                                        title="Delete Conversation"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}

                {/* === ANALYSIS VIEW === */}
                {activeTab === 'analysis' && (
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="flex-1 flex flex-col p-4 space-y-4 overflow-y-auto"
                    >
                        {/* Metric: Tokens Per Second */}
                        <div className="p-4 rounded-xl border border-white/10 bg-white/5">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-slate-300/70 text-xs font-mono tracking-wider">THROUGHPUT</span>
                                <Activity size={14} className="text-slate-200/70" />
                            </div>
                            <div className="flex items-end gap-2">
                                <span className="text-3xl font-bold text-white">{metrics.tps.toFixed(1)}</span>
                                <span className="text-sm text-slate-300/70 mb-1">t/s</span>
                            </div>
                            <div className="mt-3 h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-slate-200/70 rounded-full transition-all duration-500"
                                    style={{ width: `${Math.min(100, (metrics.tps / 100) * 100)}%` }}
                                />
                            </div>
                        </div>

                        {/* Metric: Context Window */}
                        <div className="p-4 rounded-xl border border-purple-500/20 bg-purple-900/10">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-purple-400/60 text-xs font-mono tracking-wider">CONTEXT USE</span>
                                <Cpu size={14} className="text-purple-400" />
                            </div>
                            <div className="flex items-end gap-2">
                                <span className="text-3xl font-bold text-white">{(metrics.contextUsed / 1000).toFixed(1)}</span>
                                <span className="text-sm text-purple-400/60 mb-1">k tokens</span>
                            </div>
                            <div className="mt-3 h-1.5 w-full bg-purple-900/40 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-purple-400 rounded-full shadow-[0_0_10px_rgba(180,100,255,0.5)] transition-all duration-500"
                                    style={{ width: `${Math.min(100, (metrics.contextUsed / 32000) * 100)}%` }}
                                />
                            </div>
                            <div className="mt-2 text-[10px] text-purple-400/40 text-right">Limit: 32k</div>
                        </div>

                        {/* Metric: Latency Grid */}
                        <div className="grid grid-cols-2 gap-3">
                            <div className="p-3 rounded-xl border border-white/10 bg-white/5">
                                <div className="text-[10px] text-slate-300/70 mb-1">TTFT</div>
                                <div className="text-xl font-bold text-white">{metrics.ttft.toFixed(2)}s</div>
                            </div>
                            <div className="p-3 rounded-xl border border-white/10 bg-white/5">
                                <div className="text-[10px] text-slate-300/70 mb-1">TOTAL</div>
                                <div className="text-xl font-bold text-white">{metrics.totalLatency.toFixed(2)}s</div>
                            </div>
                        </div>

                        {/* Mock Memory Graph */}
                        <div className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-900/10 flex-1 min-h-[120px] flex flex-col">
                            <div className="flex items-center justify-between mb-4">
                                <span className="text-emerald-500/60 text-xs font-mono tracking-wider">VRAM USAGE</span>
                                <div className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px]">SUCCESS</div>
                            </div>
                            <div className="flex-1 flex items-end gap-1 px-1">
                                {metrics.vramUsage.map((h, i) => (
                                    <div key={i} className="flex-1 bg-emerald-500/30 rounded-t-sm transition-all hover:bg-emerald-400" style={{ height: `${h}%` }} />
                                ))}
                            </div>
                        </div>

                    </motion.div>
                )}

            </div>
        </div>
    );
}

/* ================= FORMATTED MESSAGE ================= */

function FormattedMessage({ content, role }: { content: string; role: string }) {
    if (role === "user") {
        return <span style={{ whiteSpace: "pre-wrap" }}>{content}</span>;
    }

    return (
        <div className="markdown-body">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    h1: ({ children }) => <h1 className="text-lg font-bold text-slate-100 mt-3 mb-2">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-base font-semibold text-slate-200 mt-3 mb-1.5">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-sm font-semibold text-slate-200 mt-2 mb-1">{children}</h3>,
                    p: ({ children }) => <p className="mb-2 leading-relaxed">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1 pl-2">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1 pl-2">{children}</ol>,
                    li: ({ children }) => <li className="text-slate-300">{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold text-slate-100">{children}</strong>,
                    em: ({ children }) => <em className="italic text-slate-300">{children}</em>,
                    a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300 underline underline-offset-2">
                            {children}
                        </a>
                    ),
                    code: ({ className, children, ...props }) => {
                        const isBlock = className?.startsWith("language-");
                        if (isBlock) {
                            return (
                                <div className="my-2 rounded-lg overflow-hidden bg-black/40 border border-white/10">
                                    <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider text-slate-400 border-b border-white/10 bg-white/5">
                                        {className?.replace("language-", "") || "code"}
                                    </div>
                                    <pre className="p-3 overflow-x-auto text-xs">
                                        <code className="text-emerald-300 font-mono" {...props}>{children}</code>
                                    </pre>
                                </div>
                            );
                        }
                        return (
                            <code className="px-1.5 py-0.5 rounded bg-white/10 text-cyan-300 text-xs font-mono" {...props}>
                                {children}
                            </code>
                        );
                    },
                    pre: ({ children }) => <>{children}</>,
                    table: ({ children }) => (
                        <div className="my-2 overflow-x-auto rounded-lg border border-white/10">
                            <table className="w-full text-xs">{children}</table>
                        </div>
                    ),
                    thead: ({ children }) => <thead className="bg-white/5 text-slate-300">{children}</thead>,
                    th: ({ children }) => <th className="px-3 py-2 text-left font-medium border-b border-white/10">{children}</th>,
                    td: ({ children }) => <td className="px-3 py-2 border-b border-white/5 text-slate-400">{children}</td>,
                    hr: () => <hr className="my-3 border-white/10" />,
                    blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-cyan-500/40 pl-3 my-2 text-slate-400 italic">
                            {children}
                        </blockquote>
                    ),
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}

/* ================= COMMAND FEED ================= */


interface CommandFeedProps {
    messages: Message[];
    onSend: (t: string, image?: string | null) => void;
    isProcessing?: boolean;
    onStop?: () => void;
    onToggleMute: () => void;
    isMuted: boolean;
    onToggleCode: () => void;
    onToggleCamera: () => void;
    onToggleCCTV: () => void;
    onToggleDashboard: () => void;
    onToggleTrading: () => void;

    liveFeedMode: "idle" | "camera" | "cctv";
}

function CommandFeed({
    messages,
    onSend,
    isProcessing = false,
    onStop,
    onToggleMute,
    isMuted,
    onToggleCode,
    onToggleCamera,
    onToggleCCTV,
    onToggleDashboard,
    onToggleTrading,
    liveFeedMode
}: CommandFeedProps) {
    const [input, setInput] = useState("");
    const [attachedImage, setAttachedImage] = useState<string | null>(null);
    const [imagePreview, setImagePreview] = useState<string | null>(null);
    const listRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        if (listRef.current) {
            listRef.current.scrollTop = listRef.current.scrollHeight;
        }
    }, [messages]);

    return (
        <div
            className="w-full rounded-2xl flex flex-col shadow-2xl shadow-black/30"
            style={{
                background: "rgba(0,0,0,0.62)",
                border: "1px solid rgba(255,255,255,0.08)",
                backdropFilter: "blur(20px)",
                maxHeight: "350px" // prevent covering the globe
            }}
        >
            <div className="px-5 py-4 flex items-center justify-between border-b border-white/10">
                <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${isProcessing ? 'animate-pulse bg-amber-400' : 'bg-slate-300/70'}`} />
                    <span className="text-lg font-medium text-white tracking-wide">
                        {isProcessing ? 'Processing...' : 'Command Feed'}
                    </span>
                </div>

                {/* Integrated Controls */}
                <div className="flex items-center gap-2">
                    <button onClick={onToggleCode} className="p-2 rounded-lg hover:bg-white/5 text-slate-300 hover:text-slate-100 transition-colors" title="Code Editor">
                        <Code size={18} />
                    </button>
                    <button onClick={onToggleCamera} className={`p-2 rounded-lg hover:bg-white/5 transition-colors ${liveFeedMode === 'camera' ? 'text-slate-100 bg-white/5' : 'text-slate-300'}`} title="Camera Mode">
                        <Eye size={18} />
                    </button>
                    <button onClick={onToggleCCTV} className={`p-2 rounded-lg hover:bg-white/5 transition-colors ${liveFeedMode === 'cctv' ? 'text-red-400 bg-red-500/20' : 'text-slate-300'}`} title="Surveillance">
                        <Camera size={18} />
                    </button>
                    <button onClick={onToggleMute} className={`p-2 rounded-lg hover:bg-white/5 transition-colors ${isMuted ? 'text-red-400' : 'text-slate-300'}`} title="Toggle Mic">
                        {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
                    </button>
                    <button className="p-2 rounded-lg hover:bg-white/5 text-slate-300 hover:text-slate-100 transition-colors" title="Files">
                        <FolderOpen size={18} />
                    </button>
                    <button
                        onClick={onToggleDashboard}
                        className="px-3 py-2 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-slate-100 transition-colors flex items-center gap-2"
                        title="Open Dashboard"
                    >
                        <Settings size={16} />
                        <span className="text-xs font-mono tracking-wide">Dashboard</span>
                    </button>
                    <button
                        onClick={onToggleTrading}
                        className="px-3 py-2 rounded-lg border border-cyan-500/30 bg-cyan-900/20 hover:bg-cyan-900/40 text-cyan-300 transition-colors flex items-center gap-2"
                        title="Open Trading Terminal"
                    >
                        <LineChart size={16} />
                        <span className="text-xs font-mono tracking-wide">Trading</span>
                    </button>
                </div>
            </div>

            <div
                ref={listRef}
                className="flex-1 px-5 py-4 space-y-4 text-base text-slate-200/90 overflow-y-auto min-h-[150px]"
            >
                {messages.map((m) => (
                    <div
                        key={m.id}
                        className={`p-3 rounded-xl text-sm ${m.id === 'step-progress'
                            ? 'bg-teal-900/20 border-l-4 border-teal-400/50 text-teal-200/90 font-mono text-xs'
                            : m.role === 'assistant'
                                ? 'bg-white/5 border-l-4 border-white/10'
                                : m.role === 'system'
                                    ? 'bg-amber-900/10 border-l-4 border-amber-500/40 italic text-slate-300/70 text-xs'
                                    : 'bg-slate-800/40 border-l-4 border-slate-500/40 ml-8'
                            }`}
                    >
                        {m.image && (
                            <div className="mb-2">
                                <img src={`data:image/png;base64,${m.image}`} alt="Sent content" className="max-w-full h-auto rounded-lg border border-white/10 max-h-60 object-contain" />
                            </div>
                        )}
                        {m.id === 'step-progress' ? (
                            <div className="space-y-1">
                                <div className="text-teal-300/60 text-[10px] uppercase tracking-widest mb-2 flex items-center gap-2">
                                    <span className="w-2 h-2 bg-teal-400 rounded-full animate-pulse" />
                                    Agent Progress
                                </div>
                                {m.content.split('\n').map((line: string, i: number) => (
                                    <div key={i} className="flex items-center gap-2">
                                        <span className="text-teal-400">{line.startsWith('✓') ? '✓' : '⏳'}</span>
                                        <span>{line.startsWith('✓') ? line.slice(2) : line}</span>
                                    </div>
                                ))}
                            </div>
                        ) : <FormattedMessage content={m.content} role={m.role} />}
                    </div>
                ))}
                {/* Thinking Indicator */}
                {isProcessing && !messages.some(m => m.id === "step-progress") && (
                    <div className="p-3 rounded-xl text-sm bg-purple-900/20 border-l-4 border-purple-500/40 flex items-center gap-2">
                        <span className="text-purple-300">Agent is thinking</span>
                        <span className="flex gap-1">
                            <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        </span>
                    </div>
                )}
            </div>

            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    if ((!input.trim() && !attachedImage) || isProcessing) return;
                    onSend(input, attachedImage);
                    setInput("");
                    setAttachedImage(null);
                    setImagePreview(null);
                    if (fileInputRef.current) fileInputRef.current.value = ""; // Reset file input
                }}
                className="p-4 border-t border-white/10 flex flex-col gap-2"
            >
                {/* Image Preview - Inside the box now */}
                {imagePreview && (
                    <div className="relative inline-block self-start">
                        <img
                            src={imagePreview}
                            alt="Attached"
                            className="h-16 rounded border border-white/10 object-contain bg-black/40"
                        />
                        <button
                            type="button"
                            onClick={() => {
                                setAttachedImage(null);
                                setImagePreview(null);
                                if (fileInputRef.current) fileInputRef.current.value = ""; // Reset file input
                            }}
                            className="absolute -top-2 -right-2 w-5 h-5 bg-red-500/80 hover:bg-red-500 rounded-full flex items-center justify-center transition-colors border border-white/10"
                        >
                            <X size={12} className="text-white" />
                        </button>
                    </div>
                )}

                <div className={`flex rounded-xl overflow-hidden border transition-colors ${isProcessing ? 'border-slate-700 opacity-50 cursor-not-allowed' : 'border-white/10 hover:border-white/20'
                    }`}>
                    {/* Hidden File Input */}
                    <input
                        type="file"
                        ref={fileInputRef}
                        accept="image/*"
                        className="hidden"
                        onClick={(e) => (e.currentTarget.value = "")} // Allow selecting same file again
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                                const reader = new FileReader();
                                reader.onload = (event) => {
                                    const base64 = (event.target?.result as string)?.split(',')[1];
                                    setAttachedImage(base64);
                                    setImagePreview(event.target?.result as string);
                                };
                                reader.readAsDataURL(file);
                            }
                        }}
                    />
                    {/* Attach Button */}
                    <button
                        type="button"
                        disabled={isProcessing}
                        onClick={() => fileInputRef.current?.click()}
                        className={`px-3 flex items-center justify-center transition-colors ${isProcessing ? 'text-slate-600' : 'text-slate-300/70 hover:text-slate-100 hover:bg-white/5'}`}
                        title="Attach image (chart screenshot)"
                    >
                        <Paperclip size={18} />
                    </button>
                    <input
                        disabled={isProcessing}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder={isProcessing ? "Wait for response..." : "Type a command..."}
                        className="flex-1 px-4 py-3 bg-black/20 text-slate-200 text-base focus:outline-none placeholder:text-slate-500 disabled:cursor-not-allowed"
                    />
                    {isProcessing && onStop ? (
                        <button
                            type="button"
                            onClick={onStop}
                            className="px-4 bg-red-500/80 hover:bg-red-500 text-white transition-colors flex items-center gap-1.5"
                            title="Stop agent"
                        >
                            <X size={16} />
                            <span className="text-xs font-medium">Stop</span>
                        </button>
                    ) : (
                        <button
                            disabled={isProcessing}
                            className={`px-4 text-black transition-colors ${isProcessing ? 'bg-slate-600' : 'bg-slate-200 hover:bg-slate-100'}`}
                        >
                            <Send size={18} />
                        </button>
                    )}
                </div>
            </form>
        </div>
    );
}

/* ================= ORBIT BUTTON ================= */

function OrbitButton({
    icon: Icon,
    angle,
    radius,
    active,
    onClick,
}: any) {
    const x = Math.cos((angle * Math.PI) / 180) * radius;
    const y = Math.sin((angle * Math.PI) / 180) * radius;

    return (
        <motion.button
            onClick={onClick}
            className="absolute w-14 h-14 rounded-xl flex items-center justify-center"
            style={{
                left: `calc(50% + ${x}px - 28px)`,
                top: `calc(50% + ${y}px - 28px)`,
                background: "rgba(0,0,0,0.55)",
                border: "1px solid rgba(255,255,255,0.10)",
                boxShadow: active
                    ? "0 0 20px rgba(255,255,255,0.12)"
                    : "none",
                backdropFilter: "blur(6px)",
            }}
            whileHover={{ scale: 1.1 }}
        >
            <Icon size={18} className="text-slate-200" />
        </motion.button>
    );
}

/* ================= LIVE FEED PANEL ================= */

interface LiveFeedPanelProps {
    mode: "idle" | "camera" | "cctv";
    videoRef: React.RefObject<HTMLVideoElement>;
}

function LiveFeedPanel({ mode = "idle", videoRef }: LiveFeedPanelProps) {
    const [error, setError] = useState<string | null>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);

    const toggleFullscreen = () => {
        if (!panelRef.current) return;

        if (!isFullscreen) {
            if (panelRef.current.requestFullscreen) {
                panelRef.current.requestFullscreen();
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            }
        }
        setIsFullscreen(!isFullscreen);
    };

    useEffect(() => {
        const handleFullscreenChange = () => {
            setIsFullscreen(!!document.fullscreenElement);
        };
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
    }, []);

    useEffect(() => {
        let stream: MediaStream | null = null;

        const startCamera = async () => {
            if (mode !== 'camera') return;
            setError(null);

            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: true });
                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                }
            } catch (err) {
                console.error("Camera access failed:", err);
                setError("Camera access denied or unavailable.");
            }
        };

        const stopCamera = () => {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                stream = null;
            }
            if (videoRef.current) {
                videoRef.current.srcObject = null;
            }
        };

        if (mode === 'camera') {
            startCamera();
        } else {
            stopCamera();
        }

        return () => {
            stopCamera();
        };
    }, [mode, videoRef]);

    return (
        <div
            ref={panelRef}
            className={`w-full h-full rounded-2xl flex flex-col overflow-hidden ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}
            style={{
                background: "rgba(0,0,0,0.55)",
                border: "1px solid rgba(255,255,255,0.08)",
                backdropFilter: "blur(10px)",
            }}
        >
            <div className="px-4 py-3 flex items-center gap-2 border-b border-white/10">
                <div className={`w-2.5 h-2.5 rounded-full ${mode === 'idle' ? 'bg-gray-500' : 'bg-red-500 animate-pulse'}`} />
                <span className="text-base font-medium text-white">
                    {mode === 'camera' ? 'Camera Feed' : mode === 'cctv' ? 'Surveillance' : 'System Vision'}
                </span>
                <div className="ml-auto flex items-center gap-2">
                    <button
                        onClick={toggleFullscreen}
                        className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                        title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
                    >
                        {isFullscreen ? (
                            <Minimize2 size={16} className="text-slate-300/70 hover:text-slate-100" />
                        ) : (
                            <Maximize2 size={16} className="text-slate-300/70 hover:text-slate-100" />
                        )}
                    </button>
                    <Activity size={16} className="text-slate-300/40" />
                </div>
            </div>

            <div className="flex-1 relative bg-black/40 flex items-center justify-center overflow-hidden">
                {mode === 'idle' && (
                    <div className="text-center p-6">
                        <div className="w-16 h-16 rounded-full border-2 border-dashed border-white/10 mx-auto flex items-center justify-center mb-4">
                            <Eye size={24} className="text-slate-300/40" />
                        </div>
                        <div className="text-slate-300/40 text-sm font-mono tracking-widest">NO ACTIVE FEED</div>
                    </div>
                )}

                {mode === 'camera' && (
                    <div className="absolute inset-0 bg-[#050505] flex flex-col">
                        <div className="flex-1 relative overflow-hidden">
                            {error ? (
                                <div className="absolute inset-0 flex items-center justify-center text-red-400 font-mono text-xs">
                                    {error}
                                </div>
                            ) : (
                                <video
                                    ref={videoRef}
                                    autoPlay
                                    playsInline
                                    muted
                                    className="w-full h-full object-cover opacity-80"
                                />
                            )}

                            {/* HUD Overlay */}
                            <div className="absolute inset-0 pointer-events-none"
                                style={{
                                    boxShadow: "inset 0 0 50px rgba(0,0,0,0.8)"
                                }}
                            >
                                <div className="absolute top-4 right-4 text-slate-200/80 font-mono text-xs">LIVE</div>
                                <div className="absolute bottom-4 left-4 text-slate-200/50 font-mono text-[10px]">
                                    {error ? "OFFLINE" : "SIGNAL: STRONG"}
                                </div>
                            </div>
                        </div>

                        <div className="p-3 border-t border-white/10 bg-white/5 flex justify-between text-xs font-mono text-slate-300/70">
                            <span>CAM-01</span>
                            <span className={!error ? "text-red-400 animate-pulse" : ""}>{!error ? "REC ●" : "ERR"}</span>
                        </div>
                    </div>
                )}

                {mode === 'cctv' && (
                    <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-[1px] bg-white/5">
                        {/* CAM-01: Live Stream */}
                        <div className="relative bg-[#0b141a] overflow-hidden border border-white/10">
                            <div className="absolute top-2 left-2 z-10 text-[10px] font-mono text-slate-200/70 bg-black/40 px-1">CAM-01 • LIVE</div>
                            <img
                                src="http://localhost:8000/api/video_feed"
                                alt="Live Feed"
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                    (e.target as HTMLImageElement).style.display = 'none';
                                }}
                            />
                            <div className="absolute bottom-2 right-2 text-[10px] font-mono text-red-400 animate-pulse">● REC</div>
                        </div>
                        {/* CAM-02, 03, 04: Placeholders */}
                        {[2, 3, 4].map(i => (
                            <div key={i} className="relative bg-[#0b141a] flex items-center justify-center border border-white/10">
                                <div className="absolute top-2 left-2 text-[10px] font-mono text-slate-300/40">CAM-0{i}</div>
                                <div className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center">
                                    <div className="w-1 h-1 bg-slate-300/40 rounded-full" />
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

/* ================= MAIN ================= */

export default function NeuralInterface() {
    const [aiState, setAiState] = useState<AIState>("idle");
    const [liveFeedMode, setLiveFeedMode] = useState<"idle" | "camera" | "cctv">("idle"); // State for live feed
    const [showTradingPanel, setShowTradingPanel] = useState(false);

    const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([
        {
            id: "1",
            role: "assistant",
            content: "Neural interface initialized. How may I assist you today?",
        },
    ]);
    const [isMuted, setIsMuted] = useState(false); // Mute toggle for mic button
    const [showCodeEditor, setShowCodeEditor] = useState(false);
    const [codeEditorProjectPath, setCodeEditorProjectPath] = useState<string | null>(null);
    const [showDashboard, setShowDashboard] = useState(false);
    const [audioAnalyzer, setAudioAnalyzer] = useState<AnalyserNode | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const chatAbortRef = useRef<AbortController | null>(null);

    useEffect(() => {
        // Ensure Code Editor can always be opened even if the on-screen controls are not visible.
        window.electronAPI?.menu?.onToggleCodeEditor?.(() => {
            setShowCodeEditor((prev) => !prev);
        });
    }, []);

    // Metrics State (Dynamic)
    const [metrics, setMetrics] = useState<Metrics>({
        tps: 0,
        contextUsed: 0,
        ttft: 0,
        totalLatency: 0,
        vramUsage: [30, 40, 35, 50, 45, 60, 55, 70, 65, 50, 40, 30] // Initial dummy data
    });

    // Simulated Metrics Update (Replace with real event listener later)
    useEffect(() => {
        const interval = setInterval(() => {
            setMetrics(prev => {
                // Simulate fluctuation
                const newTps = 45 + Math.random() * 10;
                const newContext = Math.min(32000, prev.contextUsed + (Math.random() > 0.8 ? 500 : 0)); // Occasional jump
                const newVram = [...prev.vramUsage.slice(1), 30 + Math.random() * 50];

                return {
                    ...prev,
                    tps: newTps,
                    contextUsed: newContext,
                    ttft: 0.3 + Math.random() * 0.2, // 0.3 - 0.5s
                    totalLatency: 1.0 + Math.random() * 0.5, // 1.0 - 1.5s
                    vramUsage: newVram
                };
            });
        }, 2000); // Update every 2 seconds

        return () => clearInterval(interval);
    }, []);

    // Load initial chat on mount if needed
    useEffect(() => {
        // Here we could fetch the latest conversation, or just start fresh
    }, []);

    const createChat = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/conversations', { method: 'POST' });
            const data = await res.json();
            setActiveConversationId(data.id);
            setMessages([]); // Start fresh
        } catch (e) {
            console.error("Create chat error", e);
        }
    };

    const loadChat = async (id: string) => {
        try {
            setActiveConversationId(id);
            const res = await fetch('http://localhost:8000/api/conversations/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ conversation_id: id })
            });
            const data = await res.json();
            if (data.messages) {
                setMessages(data.messages);
            }
        } catch (e) {
            console.error("Load chat error", e);
        }
    };



    // Auto-start audio analyzer on mount for globe visualization
    useEffect(() => {
        const startAudio = async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                streamRef.current = stream;
                const audioContext = new AudioContext();
                if (audioContext.state === 'suspended') await audioContext.resume();
                const analyzer = audioContext.createAnalyser();
                audioContext.createMediaStreamSource(stream).connect(analyzer);
                analyzer.fftSize = 256;
                audioContextRef.current = audioContext;
                setAudioAnalyzer(analyzer);
                console.log('🎙️ Audio analyzer started automatically');
            } catch (err) {
                console.error('Audio auto-start error:', err);
            }
        };
        startAudio();

        return () => {
            streamRef.current?.getTracks().forEach(t => t.stop());
            audioContextRef.current?.close();
        };
    }, []);

    // Video Ref lifted to parent for capture
    const videoRef = useRef<HTMLVideoElement>(null);

    const extractProjectPathFromText = (value: string): string | null => {
        if (!value) return null;

        const cleanCandidate = (candidate: string): string => {
            let cleaned = candidate.trim();
            cleaned = cleaned.replace(/^['"]+/, '').replace(/['"]+$/, '');
            cleaned = cleaned.replace(/[\s.,;:!?]+$/, '');
            return cleaned;
        };

        const toLikelyProjectRoot = (candidate: string): string => {
            const normalized = candidate.replace(/\//g, '\\');
            const lower = normalized.toLowerCase();

            const stopMarkers = ['\\src\\', '\\node_modules\\', '\\components\\'];
            for (const marker of stopMarkers) {
                const idx = lower.indexOf(marker);
                if (idx > 2) {
                    return normalized.slice(0, idx);
                }
            }

            const parts = normalized.split('\\');
            const last = parts[parts.length - 1] || '';
            if (/\.[a-z0-9]+$/i.test(last)) {
                return parts.slice(0, -1).join('\\');
            }

            return normalized;
        };

        const explicitProjectPath = value.match(/project_path['"]?\s*[:=]\s*['"]([A-Za-z]:\\[^'"\r\n,]+)['"]/i);
        if (explicitProjectPath?.[1]) {
            return cleanCandidate(explicitProjectPath[1]);
        }

        const windowsMatches = value.match(/[A-Za-z]:\\[^,\n\r'"<>|?*]+/g) || [];
        const normalizedCandidates = windowsMatches
            .map(cleanCandidate)
            .map(toLikelyProjectRoot)
            .filter(Boolean);

        if (normalizedCandidates.length > 0) {
            const scored = normalizedCandidates.map((candidate) => {
                const lower = candidate.toLowerCase();
                const parts = candidate.split('\\');
                const last = parts[parts.length - 1] || '';
                const hasExtension = /\.[a-z0-9]+$/i.test(last);

                let score = 0;
                if (!hasExtension) score += 4;
                if (lower.includes('\\generated\\')) score += 3;
                if (!lower.includes('\\src\\')) score += 2;
                if (lower.includes('\\node_modules\\')) score -= 6;
                score -= candidate.length * 0.001;

                return { candidate, score };
            });

            scored.sort((a, b) => b.score - a.score);
            return scored[0]?.candidate || null;
        }

        const unixMatch = value.match(/\/(?:[^\s:]+\/)*[^\s:]+/);
        if (unixMatch?.[0] && !value.includes('http://') && !value.includes('https://')) {
            return cleanCandidate(unixMatch[0]);
        }

        return null;
    };

    // NEW: Listen for Synchronized Events from Backend (WebSocket + IPC)
    useEffect(() => {
        const handleSync = (data: any) => {
            console.log("Sync Event Received:", data);

            const { type, role, text, timestamp, partial } = data;
            const messageId = timestamp || Date.now().toString();

            // Handle UI-specific logic based on text content
            const lowerText = text?.toLowerCase() || "";
            if (!partial && (type === "status" || type === "assistant")) {
                if (lowerText.includes("cctv") || lowerText.includes("surveillance")) {
                    setLiveFeedMode("cctv");
                } else if (lowerText.includes("visual scanner") || lowerText.includes("camera feed")) {
                    setLiveFeedMode("camera");
                } else if (lowerText.includes("visual feed terminated")) {
                    setLiveFeedMode("idle");
                }
            }

            // Update AI State based on event type
            if (type === "stt") setAiState("listening");
            if (type === "status" && lowerText.includes("listening")) setAiState("listening");
            if (type === "status" && lowerText.includes("processing")) setAiState("thinking");
            if (type === "status" && lowerText.includes("muted")) setAiState("idle");  // Muted = idle
            if (type === "assistant") setAiState("speaking");
            if (type === "action") setAiState("thinking");
            if (type === "status" && text === "Done") setAiState("idle");

            // Fallback: long-running missions can be triggered remotely (e.g., Telegram) and may not emit
            // a local-only "Done" status via the pipeline. If we detect mission completion/failure in any
            // event text, force idle to clear the UI processing state.
            if (!partial) {
                const isMissionTerminal =
                    lowerText.includes("mission complete") ||
                    lowerText.includes("mission completed") ||
                    lowerText.includes("mission failed") ||
                    lowerText.includes("mission aborted") ||
                    lowerText.includes("mission ended");

                if (isMissionTerminal) setAiState("idle");
            }

            const detectedProjectPath = extractProjectPathFromText(text || "");
            if (detectedProjectPath) {
                setCodeEditorProjectPath(detectedProjectPath);
            }

            // Auto-open in-app code editor for visible coding workflow.
            const isCodingWorkflowSignal =
                (type === "action" || type === "status") &&
                (
                    lowerText.includes("scaffold") ||
                    lowerText.includes("npm run dev") ||
                    lowerText.includes("dev server") ||
                    lowerText.includes("code generation") ||
                    lowerText.includes("refactor") ||
                    lowerText.includes("coding skill")
                );

            const isNonCodingMissionSignal =
                lowerText.includes("mission complete") ||
                lowerText.includes("research complete") ||
                lowerText.includes("report saved") ||
                lowerText.includes("delivered via telegram") ||
                lowerText.includes("telegram") ||
                lowerText.includes("generated/") ||
                lowerText.includes(".md");

            if (isCodingWorkflowSignal && !isNonCodingMissionSignal) {
                setShowCodeEditor(true);
            }

            // Handle wake event - clear partial STT messages
            if (type === "wake") {
                setMessages(prev => prev.filter(m => m.id !== "partial-stt"));
                return; // Don't add wake event to chat
            }

            // Sync Chat history strictly from events
            if (type === "stt" || type === "assistant" || type === "status" || type === "error" || type === "action") {
                setMessages((prev) => {
                    // PARTIAL STT HANDLING
                    if (type === "stt" && partial) {
                        if (!text || !text.trim()) return prev;

                        const lastMsg = prev[prev.length - 1];
                        // If last message is already a partial user message, update it
                        if (lastMsg && lastMsg.role === "user" && lastMsg.id === "partial-stt") {
                            return [...prev.slice(0, -1), { ...lastMsg, content: text }];
                        }
                        // Otherwise, add a new partial message
                        return [...prev, { id: "partial-stt", role: "user", content: text }];
                    }

                    // FINAL STT HANDLING
                    if (type === "stt" && !partial) {
                        // Remove any existing partial placeholder
                        const filtered = prev.filter(m => m.id !== "partial-stt");
                        // Only add if not duplicate (prevent race conditions with typed input)
                        if (filtered.length > 0 && filtered[filtered.length - 1].content === text) {
                            return filtered;
                        }
                        return [...filtered, { id: messageId, role: "user", content: text }];
                    }

                    // STEP PROGRESS: Accumulate graph node progress into a single live indicator
                    if (type === "step") {
                        // Remove old loading indicator since steps provide better feedback
                        const withoutLoading = prev.filter(m => m.id !== "loading-indicator");

                        // Find existing step progress message or create one
                        const existingIdx = withoutLoading.findIndex(m => m.id === "step-progress");
                        const existingContent = existingIdx >= 0 ? withoutLoading[existingIdx].content : "";

                        // Append new step to the progress
                        const updatedContent = existingContent
                            ? `${existingContent}\n${text}`
                            : text;

                        const stepMsg: Message = {
                            id: "step-progress",
                            role: "system" as const,
                            content: updatedContent,
                            kind: "indicator"
                        };

                        if (existingIdx >= 0) {
                            const updated = [...withoutLoading];
                            updated[existingIdx] = stepMsg;
                            return updated;
                        }
                        return [...withoutLoading, stepMsg];
                    }

                    // ASSISTANT / SYSTEM HANDLING - Filter out internal status messages
                    if (type === "status") {
                        const statusLower = text?.toLowerCase() || "";

                        // Handle "Processing..." as a loading indicator
                        if (statusLower.includes("processing")) {
                            const withoutLoading = prev.filter(m => m.id !== "loading-indicator" && m.id !== "partial-stt" && m.id !== "listening-indicator");
                            return [...withoutLoading, {
                                id: "loading-indicator",
                                role: "system",
                                content: "Processing...",
                                kind: "indicator"
                            }];
                        }

                        // Handle "Listening..." as a loading indicator (User Request)
                        if (statusLower.includes("listening")) {
                            const withoutListening = prev.filter(m => m.id !== "listening-indicator");
                            return [...withoutListening, {
                                id: "listening-indicator",
                                role: "system",
                                content: "Listening...",
                                kind: "indicator"
                            }];
                        }

                        // CLEAR INDICATORS ON MUTE
                        if (statusLower.includes("microphone muted")) {
                            const cleaned = prev.filter(m => m.id !== "listening-indicator" && m.id !== "loading-indicator" && m.id !== "partial-stt");
                            return cleaned;
                        }

                        // Skip these statuses from appearing in chat
                        if (
                            text === "Done" ||
                            statusLower.includes("executing") ||
                            statusLower.includes("microphone muted") ||
                            statusLower.includes("microphone active") ||
                            statusLower.includes("got it") ||
                            statusLower.includes("understood") ||
                            statusLower.includes("on it") ||
                            statusLower.includes("alright") ||
                            statusLower.includes("sure thing")
                        ) {
                            // On "Done", clear step-progress tracker too
                            if (text === "Done") {
                                return prev.filter(m => m.id !== "step-progress" && m.id !== "loading-indicator");
                            }
                            return prev;
                        }

                        // If role is "assistant" (from speak()), treat it as an assistant message
                        // This handles greetings/responses that come through on_status
                        if (role === "assistant") {
                            const withoutLoading = prev.filter(m => m.id !== "loading-indicator" && m.id !== "listening-indicator");

                            // Duplicate check
                            if (withoutLoading.length > 0) {
                                const lastMsg = withoutLoading[withoutLoading.length - 1];
                                if (lastMsg.content === text) {
                                    return withoutLoading;
                                }
                            }

                            return [...withoutLoading, {
                                id: messageId,
                                role: "assistant",
                                content: text
                            }];
                        }

                        // For other system status messages, skip adding them to chat
                        // (e.g., "Opening notepad", etc. are just status updates)
                        return prev;
                    }

                    // For assistant messages, prevent duplicates and remove loading
                    if (type === "assistant") {
                        // Remove loading/listening/step indicators when assistant replies
                        const withoutLoading = prev.filter(m => m.id !== "loading-indicator" && m.id !== "listening-indicator" && m.id !== "step-progress");

                        // SMART DUPLICATE CHECK: 
                        // sometimes the same message comes twice with slightly different timestamps.
                        // We check if the last message has the same content, regardless of role (system vs assistant).
                        if (withoutLoading.length > 0) {
                            const lastMsg = withoutLoading[withoutLoading.length - 1];
                            if (lastMsg.content === text) {
                                return withoutLoading; // Ignore duplicate content
                            }
                        }

                        return [...withoutLoading, {
                            id: messageId,
                            role: "assistant",
                            content: text
                        }];
                    }

                    // ACTION EVENT: always show in command feed as live operation trace.
                    if (type === "action") {
                        if (!text || !text.trim()) return prev;
                        if (prev.length > 0 && prev[prev.length - 1].content === text) return prev;
                        return [...prev, {
                            id: messageId,
                            role: "system",
                            content: text,
                            kind: "trace"
                        }];
                    }

                    // Default: add as system message (for errors, etc.)
                    return [...prev, {
                        id: messageId,
                        role: "system",
                        content: text,
                        kind: "system"
                    }];
                });
            }
        };

        // IPC fallback (Electron API)
        // Now using safe adapter that works in both Web (no-op) and Desktop
        const ipcCleanup = api.agent.onSync(handleSync);

        // WebSocket connection to Python backend
        let ws: WebSocket | null = null;
        let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

        const connectWebSocket = () => {
            try {
                ws = new WebSocket("ws://localhost:8000/api/ws");

                ws.onopen = () => {
                    console.log("✅ WebSocket connected to Python backend");
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        handleSync(data);
                    } catch (e) {
                        console.error("WebSocket parse error:", e);
                    }
                };

                ws.onclose = () => {
                    console.log("WebSocket disconnected, reconnecting in 3s...");
                    reconnectTimeout = setTimeout(connectWebSocket, 3000);
                };

                ws.onerror = (error) => {
                    console.error("WebSocket error:", error);
                };
            } catch (e) {
                console.error("WebSocket connection failed:", e);
                reconnectTimeout = setTimeout(connectWebSocket, 3000);
            }
        };

        connectWebSocket();

        return () => {
            if (ipcCleanup) ipcCleanup();
            if (ws) ws.close();
            if (reconnectTimeout) clearTimeout(reconnectTimeout);
        };
    }, []);

    // Capture frame from video element
    const captureFrame = (): string | null => {
        if (!videoRef.current) return null;
        if (liveFeedMode !== 'camera') return null;

        const video = videoRef.current;
        if (video.videoWidth === 0 || video.videoHeight === 0) return null;

        try {
            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext("2d");
            if (ctx) {
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                return canvas.toDataURL("image/jpeg").split(",")[1];
            }
        } catch (e) {
            console.error("Capture failed:", e);
        }
        return null;
    };

    // Command handler - Pure Sender
    const handleCommand = async (text: string, attachedImage?: string | null) => {
        // We explicitly add the user message here if they TYPED it.
        // If it comes from voice, it will come back via 'stt' sync.
        const userMsgId = Date.now().toString();
        const displayContent = attachedImage ? `${text}` : text;

        const newMessage: Message = {
            id: userMsgId,
            role: "user",
            content: displayContent
        };

        if (attachedImage) {
            newMessage.image = attachedImage;
        }

        setMessages((p) => [...p, newMessage]);

        // Immediate UI feedback - Set state to thinking
        setAiState("thinking");

        try {
            // Use attached image or capture from camera
            let imageData: string | null = attachedImage || null;
            if (!imageData && liveFeedMode === 'camera') {
                imageData = captureFrame();
            }

            // Send to Backend
            const payload: any = { message: text };
            if (imageData) payload.image = imageData;

            const controller = new AbortController();
            chatAbortRef.current = controller;

            // Trigger command via backend API
            const httpResponse = await fetch('http://localhost:8000/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: controller.signal,
            });

            // Fallback completion path: if websocket completion events are delayed/missed,
            // use HTTP response body to unblock UI and show result.
            const body = await httpResponse.json().catch(() => null);
            const responseText = typeof body?.response === 'string' ? body.response.trim() : '';
            if (responseText) {
                setMessages((prev) => {
                    const withoutIndicators = prev.filter(
                        (m) => m.id !== 'loading-indicator' && m.id !== 'listening-indicator' && m.id !== 'partial-stt'
                    );
                    if (withoutIndicators.length > 0) {
                        const last = withoutIndicators[withoutIndicators.length - 1];
                        if (last.role === 'assistant' && last.content === responseText) {
                            return withoutIndicators;
                        }
                    }
                    return [
                        ...withoutIndicators,
                        {
                            id: `${Date.now()}-http-fallback`,
                            role: 'assistant',
                            content: responseText
                        }
                    ];
                });
            }

            setAiState('idle');
            chatAbortRef.current = null;

        } catch (error: any) {
            chatAbortRef.current = null;
            if (error.name === 'AbortError') {
                setMessages(p => [...p, {
                    id: Date.now().toString(),
                    role: "system",
                    content: "⏹ Agent stopped by user."
                }]);
                setAiState('idle');
                return;
            }
            console.error("Sync interaction failed:", error);
            setMessages(p => [...p, {
                id: Date.now().toString(),
                role: "system",
                content: "⚠️ Connection lost to Python brain. Terminal interface only."
            }]);
            setAiState('idle');
        }
    };

    const handleStopChat = () => {
        if (chatAbortRef.current) {
            chatAbortRef.current.abort();
            chatAbortRef.current = null;
        }
        setAiState('idle');
    };

    // Toggle mute via backend API
    const toggleMute = async () => {
        const newMutedState = !isMuted;
        try {
            await fetch('http://localhost:8000/api/mute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ muted: newMutedState })
            });
            setIsMuted(newMutedState);
            console.log(`🎤 Mic ${newMutedState ? 'MUTED' : 'UNMUTED'}`);
        } catch (err) {
            console.error('Mute toggle error:', err);
        }
    };

    return (
        <>
            {showCodeEditor && (
                <CodeEditorView
                    onClose={() => setShowCodeEditor(false)}
                    initialProjectPath={codeEditorProjectPath}
                />
            )}

            {/* TRADING FULL-SCREEN OVERLAY */}
            {showTradingPanel && (
                <TradingView onClose={() => setShowTradingPanel(false)} />
            )}

            <Dashboard isOpen={showDashboard} onClose={() => setShowDashboard(false)} />
            <div className="min-h-screen relative overflow-hidden bg-[#050505]">
                <GeometricBackground />
                <StatusHUD aiState={aiState} />

                {/* LEFT EDGE - History Panel (full height) */}
                <div className="fixed left-0 top-14 bottom-0 z-20 w-[480px] p-4">
                    <div className="h-full">
                        <HistoryPanel
                            metrics={metrics}
                            activeChatId={activeConversationId}
                            onSelectChat={loadChat}
                            onCreateChat={createChat}
                            onDeleteActiveChat={() => {
                                setActiveConversationId(null);
                                setMessages([]);
                            }}
                        />
                    </div>
                </div>

                {/* BOTTOM - Command Feed (Expanded) */}
                <div className="fixed bottom-4 left-[480px] right-[480px] z-30 px-6 flex justify-center">
                    <div className="w-full max-w-3xl">
                        {(() => {
                            const isBusy = aiState === "thinking" || aiState === "speaking" || aiState === "listening";
                            const visibleMessages = isBusy
                                ? messages
                                : messages.filter((m) => m.kind !== "trace" && m.kind !== "indicator");

                            return (
                                <CommandFeed
                                    messages={visibleMessages}
                                    onSend={handleCommand}
                                    isProcessing={aiState === "thinking" || aiState === "speaking"}
                                    onStop={handleStopChat}
                                    onToggleMute={toggleMute}
                                    isMuted={isMuted}
                                    onToggleCode={() => setShowCodeEditor(true)}
                                    onToggleCamera={() => setLiveFeedMode(p => p === 'camera' ? 'idle' : 'camera')}
                                    onToggleCCTV={() => setLiveFeedMode(p => p === 'cctv' ? 'idle' : 'cctv')}
                                    liveFeedMode={liveFeedMode}
                                    onToggleDashboard={() => setShowDashboard(true)}
                                    onToggleTrading={() => setShowTradingPanel(p => !p)}
                                />
                            );
                        })()}
                    </div>
                </div>

                {/* RIGHT EDGE - Live Feed Panel or Trading Panel (Medium Width) */}
                <div className="fixed right-0 top-14 bottom-0 z-20 w-[480px] p-4">
                    <div className="h-full">
                        <LiveFeedPanel mode={liveFeedMode} videoRef={videoRef} />
                    </div>
                </div>

                {/* CENTER - Globe (Buttons and Globe together) */}
                <div className="relative z-10 min-h-screen flex items-center justify-center -translate-y-32">
                    <div className="relative w-[700px] h-[700px]">
                        {/* Globe Container - No Ring */}
                        <div className="absolute inset-0 rounded-full overflow-hidden">
                            <AIGlobe audioAnalyzer={audioAnalyzer} aiState={aiState} isMuted={isMuted} />
                        </div>

                        {/* Orbiting Buttons - Side Flanks */}
                        {/* Buttons moved to Command Feed */}
                    </div>
                </div>

                <div className="fixed bottom-3 left-1/2 -translate-x-1/2 text-xs tracking-[0.4em] text-slate-300/40 font-mono">
                    NEURAL INTERFACE V2.0
                </div>
            </div>
        </>
    );
}
