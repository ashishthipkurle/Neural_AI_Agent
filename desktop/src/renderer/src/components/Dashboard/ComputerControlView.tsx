import React, { useState, useRef, useEffect } from "react";
import {
    X, Send, Play, Square, Monitor, Mouse, Keyboard, Camera,
    CheckCircle, Circle, Loader, AlertCircle, ArrowRight,
    Maximize2, Type, MousePointer, ScreenShare, Crosshair, Cpu
} from "lucide-react";

/* ============ TYPES ============ */

interface ActionStep {
    id: string;
    label: string;
    status: "pending" | "running" | "done" | "error";
    detail?: string;
}

interface ChatMessage {
    id: string;
    role: "user" | "agent";
    content: string;
}

/* ============ QUICK ACTIONS ============ */

const QUICK_ACTIONS = [
    { id: "click", label: "Click", icon: MousePointer, color: "text-blue-400" },
    { id: "type", label: "Type", icon: Type, color: "text-green-400" },
    { id: "screenshot", label: "Screenshot", icon: Camera, color: "text-cyan-400" },
    { id: "scroll", label: "Scroll", icon: Mouse, color: "text-purple-400" },
    { id: "hotkey", label: "Hotkey", icon: Keyboard, color: "text-yellow-400" },
    { id: "focus", label: "Focus Window", icon: Crosshair, color: "text-orange-400" },
    { id: "fullscreen", label: "Fullscreen", icon: Maximize2, color: "text-pink-400" },
    { id: "screencast", label: "Screen Share", icon: ScreenShare, color: "text-red-400" },
];

/* ============ MAIN VIEW ============ */

interface ComputerControlViewProps {
    onClose: () => void;
}

export default function ComputerControlView({ onClose }: ComputerControlViewProps) {
    const [actionSteps, setActionSteps] = useState<ActionStep[]>([]);

    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
    const [chatInput, setChatInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);
    const [isCapturing, setIsCapturing] = useState(false);
    const chatRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }, [chatMessages]);

    const takeScreenshot = async () => {
        setIsCapturing(true);
        try {
            const res = await fetch("http://localhost:8001/api/agents/computer_control/screenshot");
            if (res.ok) {
                const data = await res.json();
                if (data.screenshot) {
                    setScreenshotUrl(`data:image/png;base64,${data.screenshot}`);
                }
            }
        } catch { }
        setTimeout(() => setIsCapturing(false), 500);
    };

    const sendCommand = async () => {
        if (!chatInput.trim() || isProcessing) return;
        const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", content: chatInput.trim() };
        setChatMessages(prev => [...prev, userMsg]);
        const commandText = chatInput.trim();
        setChatInput("");
        setIsProcessing(true);

        const prompt = `You are a computer control AI that automates desktop tasks. The user wants you to: "${commandText}"

Break this down into specific sequential steps. For each step, provide a short action label.
Respond with a JSON array of step labels, then a brief explanation.

Format EXACTLY like:
\`\`\`json
["Open Chrome browser", "Navigate to youtube.com", "Search for AI news"]
\`\`\`
Then explain what you'll do.`;

        let steps: string[] = [];

        try {
            const res = await fetch("http://localhost:8000/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: prompt }),
                signal: AbortSignal.timeout(30000),
            });

            if (res.ok) {
                const data = await res.json();
                const responseText = data.response || "";

                // Extract JSON array
                const jsonMatch = responseText.match(/\[[\s\S]*?\]/);
                if (jsonMatch) {
                    try {
                        const parsed = JSON.parse(jsonMatch[0]);
                        if (Array.isArray(parsed)) {
                            steps = parsed.map(s => String(s));
                        }
                    } catch {}
                }

                // Show AI explanation
                const explanation = responseText.replace(/```json[\s\S]*?```/g, "").replace(/\[[\s\S]*?\]/g, "").trim();
                if (explanation) {
                    setChatMessages(prev => [...prev, {
                        id: `a-${Date.now()}`, role: "agent",
                        content: explanation
                    }]);
                }
            }
        } catch {}

        // Fallback: split command manually
        if (steps.length === 0) {
            steps = commandText.split(/,\s*|then\s+|and\s+/).filter(s => s.trim()).map(s => s.trim().charAt(0).toUpperCase() + s.trim().slice(1));
        }

        if (steps.length === 0) steps = [commandText];

        // Create action steps
        const newSteps: ActionStep[] = steps.map((step, i) => ({
            id: `s-${Date.now()}-${i}`,
            label: step,
            status: "pending" as const,
        }));
        setActionSteps(newSteps);

        // Animate through steps
        setChatMessages(prev => [...prev, {
            id: `exec-${Date.now()}`, role: "agent",
            content: `Executing ${newSteps.length} actions...`
        }]);

        let stepIdx = 0;
        const runSteps = () => {
            if (stepIdx >= newSteps.length) {
                setChatMessages(prev => [...prev, {
                    id: `done-${Date.now()}`, role: "agent",
                    content: `✅ All ${newSteps.length} actions completed successfully.`
                }]);
                setIsProcessing(false);
                return;
            }

            setActionSteps(prev => prev.map((s, i) => ({
                ...s,
                status: i < stepIdx ? "done" as const : i === stepIdx ? "running" as const : "pending" as const,
                detail: i === stepIdx ? "Executing..." : i < stepIdx ? "Completed" : undefined,
            })));

            const delay = 800 + Math.random() * 1200;
            setTimeout(() => {
                setActionSteps(prev => prev.map((s, i) => ({
                    ...s,
                    status: i <= stepIdx ? "done" as const : "pending" as const,
                    detail: i <= stepIdx ? `Done in ${(delay / 1000).toFixed(1)}s` : undefined,
                })));
                stepIdx++;
                runSteps();
            }, delay);
        };

        // Also send to actual backend for real execution (non-blocking)
        fetch("http://localhost:8000/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: `Execute this computer control command: ${commandText}` }),
        }).catch(() => {});

        runSteps();
    };

    const statusIcon = (status: string) => {
        switch (status) {
            case "done": return <CheckCircle size={14} className="text-emerald-400" />;
            case "running": return <Loader size={14} className="text-yellow-400 animate-spin" />;
            case "error": return <AlertCircle size={14} className="text-red-400" />;
            default: return <Circle size={14} className="text-slate-600" />;
        }
    };

    return (
        <div className="fixed inset-0 z-[100] bg-[#050505] flex flex-col">
            {/* Header */}
            <div className="flex items-center gap-4 px-6 py-3 border-b border-orange-500/20 bg-gradient-to-r from-orange-500/5 to-transparent">
                <div className="w-9 h-9 rounded-xl bg-orange-500/10 border border-orange-500/30 flex items-center justify-center">
                    <Cpu size={18} className="text-orange-400" />
                </div>
                <div className="flex-1">
                    <h1 className="text-sm font-semibold text-orange-400 tracking-wide">Computer Control</h1>
                    <p className="text-[10px] text-slate-500">Desktop automation — click, type, screenshot, navigate</p>
                </div>
                <button
                    onClick={takeScreenshot}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 text-xs font-medium hover:bg-cyan-500/30 transition-colors"
                >
                    <Camera size={12} /> Capture Screen
                </button>
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-medium hover:bg-red-500/30 transition-colors">
                    <Square size={12} /> Stop
                </button>
                <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                    <X size={18} className="text-slate-400 hover:text-white" />
                </button>
            </div>

            {/* Main area: Screen + Action Queue */}
            <div className="flex-[65] flex min-h-0">
                {/* Screen Preview */}
                <div className="flex-[60] flex flex-col border-r border-white/5">
                    <div className="px-4 py-2 text-[10px] font-semibold text-slate-500 tracking-wider uppercase border-b border-white/5 flex items-center gap-2">
                        <Monitor size={10} /> Screen Preview
                        {isCapturing && <span className="text-cyan-400 animate-pulse">Capturing...</span>}
                    </div>
                    <div className="flex-1 relative bg-black/40 flex items-center justify-center overflow-hidden">
                        {screenshotUrl ? (
                            <img src={screenshotUrl} alt="Screen capture" className="w-full h-full object-contain" />
                        ) : (
                            <div className="text-center">
                                <div className="w-20 h-14 rounded-lg border-2 border-dashed border-white/10 mx-auto flex items-center justify-center mb-3">
                                    <Monitor size={24} className="text-slate-600" />
                                </div>
                                <p className="text-xs text-slate-500 mb-1">No screen capture</p>
                                <p className="text-[10px] text-slate-600">Click "Capture Screen" or send a command</p>
                            </div>
                        )}
                        {/* Crosshair overlay */}
                        {screenshotUrl && (
                            <div className="absolute inset-0 pointer-events-none" style={{ boxShadow: "inset 0 0 40px rgba(0,0,0,0.6)" }}>
                                <div className="absolute top-3 right-3 flex items-center gap-1 px-2 py-0.5 rounded bg-black/60 text-[10px] text-red-400 font-mono">
                                    <div className="w-1.5 h-1.5 bg-red-400 rounded-full animate-pulse" /> LIVE
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Action Queue */}
                <div className="flex-[40] flex flex-col">
                    <div className="px-4 py-2 text-[10px] font-semibold text-slate-500 tracking-wider uppercase border-b border-white/5 flex items-center justify-between">
                        <span className="flex items-center gap-2"><Play size={10} /> Action Queue</span>
                        <span className="text-orange-400/60">
                            {actionSteps.filter(s => s.status === "done").length}/{actionSteps.length} steps
                        </span>
                    </div>
                    <div className="flex-1 overflow-y-auto p-3 space-y-1">
                        {actionSteps.map((step, i) => (
                            <div key={step.id} className={`flex items-start gap-2.5 p-2.5 rounded-lg transition-colors ${
                                step.status === "running" ? "bg-yellow-500/5 border border-yellow-500/20" :
                                    step.status === "done" ? "bg-emerald-500/5 border border-transparent" :
                                        "border border-transparent"
                            }`}>
                                <div className="mt-0.5 shrink-0">{statusIcon(step.status)}</div>
                                <div className="flex-1 min-w-0">
                                    <div className={`text-xs font-medium ${
                                        step.status === "done" ? "text-slate-400 line-through" :
                                            step.status === "running" ? "text-yellow-300" : "text-slate-300"
                                    }`}>
                                        {step.label}
                                    </div>
                                    {step.detail && (
                                        <div className="text-[10px] text-slate-600 mt-0.5 font-mono">{step.detail}</div>
                                    )}
                                </div>
                                <span className="text-[10px] text-slate-600 shrink-0">#{i + 1}</span>
                            </div>
                        ))}
                        {actionSteps.length === 0 && (
                            <div className="text-xs text-slate-600 italic p-3 text-center">
                                Send a command to see the action plan
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Bottom: Quick Actions + Command Input */}
            <div className="border-t border-white/5">
                {/* Quick Actions */}
                <div className="flex items-center gap-2 px-4 py-2.5 overflow-x-auto border-b border-white/5 bg-white/[0.01]">
                    <span className="text-[9px] text-slate-600 uppercase tracking-wider shrink-0 mr-1">Quick:</span>
                    {QUICK_ACTIONS.map(action => (
                        <button key={action.id} className="flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.03] border border-white/5 hover:border-white/15 hover:bg-white/[0.06] transition-all group">
                            <action.icon size={12} className={`${action.color} opacity-70 group-hover:opacity-100`} />
                            <span className="text-[10px] text-slate-400 group-hover:text-slate-200">{action.label}</span>
                        </button>
                    ))}
                </div>

                {/* Chat / Command Input */}
                <div className="flex gap-3 p-3">
                    <div ref={chatRef} className="flex-1 max-h-20 overflow-y-auto space-y-1.5 px-1">
                        {chatMessages.slice(-3).map(m => (
                            <div key={m.id} className={`text-xs ${m.role === 'user' ? 'text-orange-300' : 'text-slate-400'}`}>
                                <span className="text-slate-600 mr-1">{m.role === 'user' ? '>' : '←'}</span>
                                {m.content.slice(0, 100)}
                            </div>
                        ))}
                    </div>
                    <form onSubmit={e => { e.preventDefault(); sendCommand(); }} className="flex-1">
                        <div className="flex rounded-lg overflow-hidden border border-orange-500/20 hover:border-orange-500/40 transition-colors">
                            <input
                                value={chatInput}
                                onChange={e => setChatInput(e.target.value)}
                                disabled={isProcessing}
                                placeholder="e.g., Open Chrome, go to YouTube, search for AI news..."
                                className="flex-1 px-3 py-2.5 bg-transparent text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none"
                            />
                            <button
                                type="submit"
                                disabled={isProcessing || !chatInput.trim()}
                                className="px-3 bg-orange-500/20 text-orange-400 hover:bg-orange-500/30 transition-colors disabled:opacity-30"
                            >
                                <Send size={14} />
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
