import React, { useState, useRef, useEffect } from "react";
import { X, Send, MessageSquare, Cpu, Sparkles, Edit, Bot, Activity } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface AgentMessage {
    id: string;
    role: "user" | "agent" | "system";
    content: string;
    timestamp: number;
}

interface AgentConfig {
    name: string;
    displayName: string;
    description: string;
    icon: React.ComponentType<any>;
    color: string;       // text color class
    bgColor: string;     // background accent
    borderColor: string; // border accent
}

const AGENT_CONFIGS: Record<string, AgentConfig> = {
    general: {
        name: "general",
        displayName: "General Agent",
        description: "Conversation, Q&A, web search, and general assistance",
        icon: MessageSquare,
        color: "text-emerald-400",
        bgColor: "bg-emerald-500",
        borderColor: "border-emerald-500/30",
    },
    computer_control: {
        name: "computer_control",
        displayName: "Computer Control",
        description: "Desktop automation — open apps, click, type, take screenshots",
        icon: Cpu,
        color: "text-orange-400",
        bgColor: "bg-orange-500",
        borderColor: "border-orange-500/30",
    },
    workflow: {
        name: "workflow",
        displayName: "Workflow Agent",
        description: "Automate repetitive tasks with custom workflows and schedules",
        icon: Sparkles,
        color: "text-yellow-400",
        bgColor: "bg-yellow-500",
        borderColor: "border-yellow-500/30",
    },
    content_creator: {
        name: "content_creator",
        displayName: "Content Creator",
        description: "Generate social media posts, articles, video scripts, and image prompts",
        icon: Edit,
        color: "text-pink-400",
        bgColor: "bg-pink-500",
        borderColor: "border-pink-500/30",
    },
};

interface AgentChatViewProps {
    agentKey: string;
    onClose: () => void;
}

export default function AgentChatView({ agentKey, onClose }: AgentChatViewProps) {
    const config = AGENT_CONFIGS[agentKey];
    const [messages, setMessages] = useState<AgentMessage[]>([]);
    const [input, setInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [agentStatus, setAgentStatus] = useState<string>("idle");
    const [memoryStats, setMemoryStats] = useState<any>(null);
    const listRef = useRef<HTMLDivElement>(null);
    const Icon = config?.icon || Bot;

    // Auto-scroll
    useEffect(() => {
        if (listRef.current) {
            listRef.current.scrollTop = listRef.current.scrollHeight;
        }
    }, [messages]);

    // Fetch agent status on mount
    useEffect(() => {
        fetch(`http://localhost:8001/api/agents/${config?.name}`)
            .then(res => res.json())
            .then(data => {
                if (data.status) setAgentStatus(data.status);
                if (data.memory) setMemoryStats(data.memory);
            })
            .catch(() => {});
    }, [config?.name]);

    const sendMessage = async () => {
        if (!input.trim() || isProcessing) return;

        const userMsg: AgentMessage = {
            id: `user-${Date.now()}`,
            role: "user",
            content: input.trim(),
            timestamp: Date.now(),
        };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setIsProcessing(true);

        try {
            // Send to agent via INDRA command API
            const res = await fetch("http://localhost:8001/api/indra/command", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    command: userMsg.content,
                    target_agent: config.name,
                }),
            });

            if (res.ok) {
                const data = await res.json();
                const agentMsg: AgentMessage = {
                    id: `agent-${Date.now()}`,
                    role: "agent",
                    content: data.result || data.response || data.message || "Task received. Processing...",
                    timestamp: Date.now(),
                };
                setMessages(prev => [...prev, agentMsg]);
            } else {
                setMessages(prev => [...prev, {
                    id: `err-${Date.now()}`,
                    role: "system",
                    content: "Agent is not responding. Make sure the Python backend is running.",
                    timestamp: Date.now(),
                }]);
            }
        } catch (err) {
            setMessages(prev => [...prev, {
                id: `err-${Date.now()}`,
                role: "system",
                content: "Cannot connect to INDRA backend (port 8001). Start the Python server first.",
                timestamp: Date.now(),
            }]);
        } finally {
            setIsProcessing(false);
        }
    };

    if (!config) return null;

    return (
        <div className="fixed inset-0 z-[100] flex">
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />

            {/* Panel */}
            <div className="relative ml-auto w-full max-w-2xl h-full flex flex-col bg-[#0a0a0a] border-l border-white/10 shadow-2xl">

                {/* Header */}
                <div className={`px-6 py-4 flex items-center gap-4 border-b ${config.borderColor} bg-gradient-to-r from-white/[0.03] to-transparent`}>
                    <div className={`w-10 h-10 rounded-xl ${config.bgColor}/20 flex items-center justify-center border ${config.borderColor}`}>
                        <Icon size={20} className={config.color} />
                    </div>
                    <div className="flex-1">
                        <h2 className={`text-base font-semibold ${config.color}`}>{config.displayName}</h2>
                        <p className="text-xs text-slate-500">{config.description}</p>
                    </div>
                    <div className="flex items-center gap-3">
                        {/* Status badge */}
                        <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-white/5 border border-white/10">
                            <div className={`w-2 h-2 rounded-full ${agentStatus === 'idle' ? 'bg-emerald-400' : agentStatus === 'working' ? 'bg-yellow-400 animate-pulse' : 'bg-red-400'}`} />
                            <span className="text-[10px] text-slate-400 font-mono uppercase">{agentStatus}</span>
                        </div>
                        <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                            <X size={18} className="text-slate-400 hover:text-white" />
                        </button>
                    </div>
                </div>

                {/* Memory Stats Bar */}
                {memoryStats && (
                    <div className="px-6 py-2 flex items-center gap-4 text-[10px] font-mono text-slate-500 border-b border-white/5 bg-white/[0.02]">
                        <span>HOT: {memoryStats.hot_pages || 0} pages</span>
                        <span>WARM: {memoryStats.warm_pages || 0}</span>
                        <span>TOKENS: {memoryStats.hot_tokens || 0}</span>
                        <span className="ml-auto flex items-center gap-1">
                            <Activity size={10} />
                            KV CACHE ACTIVE
                        </span>
                    </div>
                )}

                {/* Messages */}
                <div ref={listRef} className="flex-1 overflow-y-auto p-6 space-y-4">
                    {messages.length === 0 && (
                        <div className="flex flex-col items-center justify-center h-full text-center opacity-40">
                            <div className={`w-16 h-16 rounded-2xl ${config.bgColor}/10 flex items-center justify-center mb-4 border ${config.borderColor}`}>
                                <Icon size={28} className={config.color} />
                            </div>
                            <p className="text-sm text-slate-400 mb-1">Start a conversation with {config.displayName}</p>
                            <p className="text-xs text-slate-600">Type a command below to get started</p>
                        </div>
                    )}

                    {messages.map(m => (
                        <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                                m.role === 'user'
                                    ? 'bg-white/10 text-slate-200 rounded-br-md'
                                    : m.role === 'system'
                                        ? 'bg-red-500/10 border border-red-500/20 text-red-300 rounded-bl-md'
                                        : `bg-white/[0.04] border ${config.borderColor} text-slate-300 rounded-bl-md`
                            }`}>
                                {m.role === 'agent' ? (
                                    <div className="markdown-body">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}
                                            components={{
                                                p: ({children}) => <p className="mb-2 leading-relaxed">{children}</p>,
                                                code: ({className, children, ...props}) => {
                                                    const isBlock = className?.startsWith("language-");
                                                    if (isBlock) {
                                                        return (
                                                            <div className="my-2 rounded-lg overflow-hidden bg-black/40 border border-white/10">
                                                                <pre className="p-3 overflow-x-auto text-xs">
                                                                    <code className="text-emerald-300 font-mono" {...props}>{children}</code>
                                                                </pre>
                                                            </div>
                                                        );
                                                    }
                                                    return <code className="px-1.5 py-0.5 rounded bg-white/10 text-cyan-300 text-xs font-mono" {...props}>{children}</code>;
                                                },
                                                pre: ({children}) => <>{children}</>,
                                                strong: ({children}) => <strong className="font-semibold text-slate-100">{children}</strong>,
                                                ul: ({children}) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                                                ol: ({children}) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                                            }}
                                        >
                                            {m.content}
                                        </ReactMarkdown>
                                    </div>
                                ) : (
                                    <span style={{ whiteSpace: "pre-wrap" }}>{m.content}</span>
                                )}
                                <div className="text-[10px] text-slate-600 mt-1 text-right">
                                    {new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </div>
                            </div>
                        </div>
                    ))}

                    {/* Thinking indicator */}
                    {isProcessing && (
                        <div className="flex justify-start">
                            <div className={`rounded-2xl rounded-bl-md px-4 py-3 bg-white/[0.04] border ${config.borderColor}`}>
                                <div className="flex items-center gap-2">
                                    <span className={`text-sm ${config.color}`}>{config.displayName} is thinking</span>
                                    <span className="flex gap-1">
                                        <span className={`w-1.5 h-1.5 ${config.bgColor} rounded-full animate-bounce`} style={{ animationDelay: '0ms' }} />
                                        <span className={`w-1.5 h-1.5 ${config.bgColor} rounded-full animate-bounce`} style={{ animationDelay: '150ms' }} />
                                        <span className={`w-1.5 h-1.5 ${config.bgColor} rounded-full animate-bounce`} style={{ animationDelay: '300ms' }} />
                                    </span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Input */}
                <form
                    onSubmit={(e) => { e.preventDefault(); sendMessage(); }}
                    className="p-4 border-t border-white/10"
                >
                    <div className={`flex rounded-xl overflow-hidden border ${isProcessing ? 'border-slate-700 opacity-50' : config.borderColor + ' hover:border-opacity-60'} transition-colors`}>
                        <input
                            disabled={isProcessing}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder={isProcessing ? "Waiting for response..." : `Ask ${config.displayName}...`}
                            className="flex-1 px-4 py-3 bg-black/20 text-slate-200 text-sm focus:outline-none placeholder:text-slate-600 disabled:cursor-not-allowed"
                        />
                        <button
                            type="submit"
                            disabled={isProcessing || !input.trim()}
                            className={`px-4 transition-colors ${isProcessing || !input.trim() ? 'bg-slate-800 text-slate-600' : `${config.bgColor} text-black hover:opacity-90`}`}
                        >
                            <Send size={16} />
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
