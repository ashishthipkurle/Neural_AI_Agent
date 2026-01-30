"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
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
} from "lucide-react";
import AIGlobe from "./components/AIGlobe";
import CodeEditorView from "./components/CodeEditor/CodeEditorView";

/* ================= TYPES ================= */

type AIState = "idle" | "listening" | "thinking" | "speaking";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
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
            ctx.fillStyle = "#020a12";
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            nodes.forEach((n) => {
                n.x += n.vx;
                n.y += n.vy;
                if (n.x < 0 || n.x > canvas.width) n.vx *= -1;
                if (n.y < 0 || n.y > canvas.height) n.vy *= -1;
            });

            ctx.strokeStyle = "rgba(0,180,200,0.05)";
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
                ctx.fillStyle = "rgba(0,200,220,0.3)";
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
        <div className="fixed top-0 left-0 right-0 z-50 px-6 py-4 flex justify-between text-xs font-mono text-cyan-400">
            <div className="flex gap-8">
                <span className="flex items-center gap-2">
                    <Cpu size={14} /> CPU: <b className="text-cyan-300">26%</b>
                </span>
                <span className="flex items-center gap-2">
                    <Activity size={14} /> Status:{" "}
                    <b className="text-cyan-300">{aiState.toUpperCase()}</b>
                </span>
            </div>
            <div className="flex gap-8">
                <span className="flex items-center gap-2">
                    <Wifi size={14} /> Latency: <b className="text-cyan-300">0ms</b>
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

function HistoryPanel() {
    const [searchQuery, setSearchQuery] = useState("");
    const [historyItems] = useState([
        { id: '1', title: 'System initialization', time: '2 min ago', type: 'system' },
        { id: '2', title: 'Voice command activated', time: '5 min ago', type: 'voice' },
        { id: '3', title: 'File search completed', time: '12 min ago', type: 'search' },
        { id: '4', title: 'Code analysis finished', time: '25 min ago', type: 'code' },
        { id: '5', title: 'Settings updated', time: '1 hour ago', type: 'settings' },
    ]);

    const filteredHistory = historyItems.filter(item =>
        item.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div
            className="w-full h-full rounded-2xl flex flex-col"
            style={{
                background: "rgba(5,20,30,0.65)",
                border: "1px solid rgba(0,180,200,0.2)",
                backdropFilter: "blur(10px)",
            }}
        >
            <div className="px-4 py-3 flex items-center gap-2">
                <div className="w-2.5 h-2.5 bg-emerald-400 rounded-full" />
                <span className="text-base font-medium text-white">History</span>
                <Clock size={16} className="ml-auto text-cyan-500/40" />
            </div>

            {/* Search Box */}
            <div className="px-4 pb-3">
                <div className="flex rounded-lg overflow-hidden border border-cyan-500/30"
                    style={{ background: "rgba(0,30,45,0.5)" }}>
                    <Search size={14} className="ml-3 my-auto text-cyan-500/50" />
                    <input
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search..."
                        className="flex-1 px-2 py-2 bg-transparent text-cyan-100 text-sm focus:outline-none"
                    />
                </div>
            </div>

            {/* History Items - Scrollable */}
            <div className="flex-1 px-4 pb-4 space-y-2 overflow-y-auto">
                {filteredHistory.map((item) => (
                    <div
                        key={item.id}
                        className="p-2.5 rounded-lg flex items-center gap-2.5 cursor-pointer hover:bg-cyan-500/10 transition-colors"
                        style={{
                            background: "rgba(0,30,45,0.3)",
                        }}
                    >
                        <div className={`w-2 h-2 rounded-full ${item.type === 'system' ? 'bg-cyan-400' :
                            item.type === 'voice' ? 'bg-green-400' :
                                item.type === 'search' ? 'bg-yellow-400' :
                                    item.type === 'code' ? 'bg-purple-400' :
                                        'bg-gray-400'
                            }`} />
                        <div className="flex-1 min-w-0">
                            <div className="text-sm text-cyan-100 truncate">{item.title}</div>
                            <div className="text-xs text-cyan-500/50">{item.time}</div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

/* ================= COMMAND FEED ================= */


interface CommandFeedProps {
    messages: Message[];
    onSend: (t: string) => void;
    isProcessing?: boolean;
}

function CommandFeed({
    messages,
    onSend,
    isProcessing = false
}: CommandFeedProps) {
    const [input, setInput] = useState("");
    const listRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        if (listRef.current) {
            listRef.current.scrollTop = listRef.current.scrollHeight;
        }
    }, [messages]);

    return (
        <div
            className="w-full rounded-2xl flex flex-col shadow-2xl shadow-cyan-900/20"
            style={{
                background: "rgba(5,20,30,0.85)",
                border: "1px solid rgba(0,180,200,0.3)",
                backdropFilter: "blur(20px)",
                maxHeight: "500px" // prevent total component growth
            }}
        >
            <div className="px-5 py-4 flex items-center gap-3 border-b border-cyan-500/10">
                <div className={`w-3 h-3 rounded-full ${isProcessing ? 'animate-pulse bg-amber-400' : 'bg-cyan-400'}`} />
                <span className="text-lg font-medium text-white tracking-wide">
                    {isProcessing ? 'Processing...' : 'Command Feed'}
                </span>
                <Sparkles size={18} className="ml-auto text-cyan-500/40" />
            </div>

            <div
                ref={listRef}
                className="flex-1 px-5 py-4 space-y-4 text-base text-cyan-100/90 overflow-y-auto min-h-[150px]"
            >
                {messages.map((m) => (
                    <div
                        key={m.id}
                        className={`p-4 rounded-xl ${m.role === 'assistant'
                            ? 'bg-cyan-900/20 border-l-4 border-cyan-500/40'
                            : 'bg-slate-800/40 border-l-4 border-slate-500/40 ml-8'
                            }`}
                    >
                        {m.content}
                    </div>
                ))}
            </div>

            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    if (!input.trim() || isProcessing) return;
                    onSend(input);
                    setInput("");
                }}
                className="p-4 border-t border-cyan-500/10"
            >
                <div className={`flex rounded-xl overflow-hidden border transition-colors ${isProcessing ? 'border-slate-700 opacity-50 cursor-not-allowed' : 'border-cyan-500/30 hover:border-cyan-500/50'
                    }`}>
                    <input
                        disabled={isProcessing}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder={isProcessing ? "Wait for response..." : "Type a command..."}
                        className="flex-1 px-4 py-3 bg-black/20 text-cyan-100 text-base focus:outline-none placeholder-cyan-500/30 disabled:cursor-not-allowed"
                    />
                    <button
                        disabled={isProcessing}
                        className={`px-4 text-black transition-colors ${isProcessing ? 'bg-slate-600' : 'bg-cyan-400 hover:bg-cyan-300'
                            }`}
                    >
                        <Send size={18} />
                    </button>
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
                background: "rgba(0,25,40,0.7)",
                border: "1px solid rgba(0,200,220,0.35)",
                boxShadow: active
                    ? "0 0 20px rgba(0,200,220,0.5)"
                    : "none",
                backdropFilter: "blur(6px)",
            }}
            whileHover={{ scale: 1.1 }}
        >
            <Icon size={18} className="text-cyan-300" />
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
                background: "rgba(5,20,30,0.65)",
                border: "1px solid rgba(0,180,200,0.2)",
                backdropFilter: "blur(10px)",
            }}
        >
            <div className="px-4 py-3 flex items-center gap-2 border-b border-cyan-500/10">
                <div className={`w-2.5 h-2.5 rounded-full ${mode === 'idle' ? 'bg-gray-500' : 'bg-red-500 animate-pulse'}`} />
                <span className="text-base font-medium text-white">
                    {mode === 'camera' ? 'Camera Feed' : mode === 'cctv' ? 'Surveillance' : 'System Vision'}
                </span>
                <div className="ml-auto flex items-center gap-2">
                    <button
                        onClick={toggleFullscreen}
                        className="p-1.5 rounded-lg hover:bg-cyan-500/20 transition-colors"
                        title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
                    >
                        {isFullscreen ? (
                            <Minimize2 size={16} className="text-cyan-500/60 hover:text-cyan-400" />
                        ) : (
                            <Maximize2 size={16} className="text-cyan-500/60 hover:text-cyan-400" />
                        )}
                    </button>
                    <Activity size={16} className="text-cyan-500/40" />
                </div>
            </div>

            <div className="flex-1 relative bg-black/40 flex items-center justify-center overflow-hidden">
                {mode === 'idle' && (
                    <div className="text-center p-6">
                        <div className="w-16 h-16 rounded-full border-2 border-dashed border-cyan-500/20 mx-auto flex items-center justify-center mb-4">
                            <Eye size={24} className="text-cyan-500/40" />
                        </div>
                        <div className="text-cyan-500/40 text-sm font-mono tracking-widest">NO ACTIVE FEED</div>
                    </div>
                )}

                {mode === 'camera' && (
                    <div className="absolute inset-0 bg-[#020a12] flex flex-col">
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
                                <div className="absolute top-4 right-4 text-cyan-500 font-mono text-xs">LIVE</div>
                                <div className="absolute bottom-4 left-4 text-cyan-500/50 font-mono text-[10px]">
                                    {error ? "OFFLINE" : "SIGNAL: STRONG"}
                                </div>
                            </div>
                        </div>

                        <div className="p-3 border-t border-cyan-500/20 bg-cyan-900/10 flex justify-between text-xs font-mono text-cyan-400/60">
                            <span>CAM-01</span>
                            <span className={!error ? "text-red-400 animate-pulse" : ""}>{!error ? "REC ●" : "ERR"}</span>
                        </div>
                    </div>
                )}

                {mode === 'cctv' && (
                    <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-[1px] bg-cyan-900/20">
                        {/* CAM-01: Live Stream */}
                        <div className="relative bg-[#05101a] overflow-hidden border border-cyan-500/10">
                            <div className="absolute top-2 left-2 z-10 text-[10px] font-mono text-cyan-500/80 bg-black/50 px-1">CAM-01 • LIVE</div>
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
                            <div key={i} className="relative bg-[#05101a] flex items-center justify-center border border-cyan-500/10">
                                <div className="absolute top-2 left-2 text-[10px] font-mono text-cyan-500/40">CAM-0{i}</div>
                                <div className="w-8 h-8 rounded-full border border-cyan-500/20 flex items-center justify-center">
                                    <div className="w-1 h-1 bg-cyan-500/40 rounded-full" />
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
    const [messages, setMessages] = useState<Message[]>([
        {
            id: "1",
            role: "assistant",
            content: "Neural interface initialized. How may I assist you today?",
        },
    ]);
    const [listening, setListening] = useState(false);
    const [showCodeEditor, setShowCodeEditor] = useState(false);
    const [audioAnalyzer, setAudioAnalyzer] = useState<AnalyserNode | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const streamRef = useRef<MediaStream | null>(null);

    // Video Ref lifted to parent for capture
    const videoRef = useRef<HTMLVideoElement>(null);

    // Capture frame from video element
    const captureFrame = (): string | null => {
        if (!videoRef.current) {
            console.error("CAPTURE ERROR: videoRef.current is null");
            return null;
        }
        if (liveFeedMode !== 'camera') {
            console.error("CAPTURE ERROR: liveFeedMode is not 'camera'");
            return null;
        }

        const video = videoRef.current;
        if (video.videoWidth === 0 || video.videoHeight === 0) {
            console.error("CAPTURE ERROR: Video dimensions are 0 (stream not ready?)");
            return null;
        }

        try {
            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext("2d");
            if (ctx) {
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataUrl = canvas.toDataURL("image/jpeg");
                console.log(`CAPTURE SUCCESS: Generated frame (${dataUrl.length} chars)`);
                return dataUrl.split(",")[1];
            }
        } catch (e) {
            console.error("CAPTURE EXCEPTION:", e);
        }
        return null;
    };

    // Command handler with Backend Integration
    const handleCommand = async (text: string) => {
        // 1. Update UI with user message immediately
        const userMsgId = Date.now().toString();
        setMessages((p) => [...p, { id: userMsgId, role: "user", content: text }]);

        const lower = text.toLowerCase();

        // 2. Local UI overrides for immediate feedback (Visuals)
        if (lower.includes("scan") || (lower.includes("camera") && !lower.includes("tell me") && !lower.includes("what is"))) {
            setLiveFeedMode("camera");
            setTimeout(() => setMessages(p => [...p, { id: Date.now().toString(), role: "assistant", content: "Activating visual scanner..." }]), 500);
            return;
        } else if (lower.includes("cctv") || lower.includes("surveillance")) {
            setLiveFeedMode("cctv");
            // Don't return! Let the backend process "Start Surveillance" to launch native window
            setTimeout(() => setMessages(p => [...p, { id: Date.now().toString(), role: "assistant", content: "Initializing neural surveillance grid..." }]), 500);
        } else if (lower === "stop" || lower === "close" || lower.includes("stop visual")) {
            setLiveFeedMode("idle");
            setTimeout(() => setMessages(p => [...p, { id: Date.now().toString(), role: "assistant", content: "Visual feed terminated." }]), 500);
            return;
        }

        // 3. Send to Backend API
        try {
            // Show a "thinking" message temporarily
            const processingId = (Date.now() + 1).toString();
            setMessages(p => [...p, { id: processingId, role: "assistant", content: "Thinking..." }]);

            // CAPTURE IMAGE logic
            let imageData: string | null = null;

            // Check if user is asking visual question but camera is OFF
            const isVisualQuery = lower.includes("what") || lower.includes("see") || lower.includes("describe") || lower.includes("holding");

            if (isVisualQuery && liveFeedMode !== 'camera') {
                setMessages(p => [...p, { id: Date.now().toString(), role: "assistant", content: "Please open the camera first (click the Eye icon)!" }]);
                return;
            }

            if (liveFeedMode === 'camera') {
                imageData = captureFrame();
                if (!imageData) {
                    console.warn("Camera is open but failed to capture frame. Check console for details.");
                    // Inform user of error
                    setMessages(p => p.map(m => m.id === processingId ? { ...m, content: "⚠️ Error: Camera active but could not capture image. Try refreshing." } : m));
                    return;
                }
            }

            console.log("Sending request to backend...");

            const payload: any = { message: text };
            if (imageData) {
                payload.image = imageData;
            }

            const response = await fetch('http://localhost:8000/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            console.log("Received response:", data);

            // 4. Update Assistant Response (Replace "Thinking...")
            setMessages(p => p.map(m =>
                m.id === processingId
                    ? { ...m, content: data.response }
                    : m
            ));

        } catch (error) {
            console.error("Agent interaction failed:", error);
            // Fallback error message in chat
            setMessages(p => [...p, {
                id: (Date.now() + 2).toString(),
                role: "assistant",
                content: "⚠️ I'm having trouble connecting to my backend brain. Please ensure the Python server (port 8000) is running."
            }]);
        }
    };

    useEffect(() => {
        setAiState(listening ? "listening" : "idle");
    }, [listening]);

    const toggleListening = async () => {
        if (listening) {
            streamRef.current?.getTracks().forEach(t => t.stop());
            audioContextRef.current?.close();
            setListening(false);
            setAudioAnalyzer(null);
        } else {
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
                setListening(true);
            } catch (err) {
                console.error('Audio error:', err);
            }
        }
    };

    return (
        <>
            {showCodeEditor && <CodeEditorView onClose={() => setShowCodeEditor(false)} />}
            <div className="min-h-screen relative overflow-hidden bg-[#020a12]">
                <GeometricBackground />
                <StatusHUD aiState={aiState} />

                {/* LEFT EDGE - History Panel (full height) */}
                <div className="fixed left-0 top-14 bottom-0 z-20 w-[280px] p-4">
                    <div className="h-full">
                        <HistoryPanel />
                    </div>
                </div>

                {/* BOTTOM - Command Feed (next to history) */}
                <div className="fixed left-[300px] bottom-6 z-20 w-[400px]">
                    <CommandFeed
                        messages={messages}
                        onSend={handleCommand}
                        isProcessing={messages.some(m => m.content === "Thinking...")}
                    />
                </div>

                {/* RIGHT EDGE - Live Feed Panel (Medium Width) */}
                <div className="fixed right-0 top-14 bottom-0 z-20 w-[480px] p-4">
                    <div className="h-full">
                        <LiveFeedPanel mode={liveFeedMode} videoRef={videoRef} />
                    </div>
                </div>

                {/* CENTER - Globe (Buttons and Globe together) */}
                <div className="relative z-10 min-h-screen flex items-center justify-center pl-[480px] pr-[320px]">
                    <div className="relative w-[700px] h-[700px]">
                        {/* Globe Container - No Ring */}
                        <div className="absolute inset-0 rounded-full overflow-hidden">
                            <AIGlobe audioAnalyzer={audioAnalyzer} />
                        </div>

                        {/* Orbiting Buttons - Closer to globe */}
                        <OrbitButton icon={Code} angle={-90} radius={300} onClick={() => setShowCodeEditor(true)} />
                        <OrbitButton icon={Settings} angle={-150} radius={300} />
                        <OrbitButton icon={Mic} angle={-210} radius={300} active={listening} onClick={toggleListening} />
                        <OrbitButton icon={Search} angle={-30} radius={300} onClick={() => setLiveFeedMode(p => p === 'cctv' ? 'idle' : 'cctv')} />
                        <OrbitButton icon={FolderOpen} angle={30} radius={300} />
                        <OrbitButton icon={Eye} angle={90} radius={300} onClick={() => setLiveFeedMode(p => p === 'camera' ? 'idle' : 'camera')} />
                    </div>
                </div>

                <div className="fixed bottom-6 left-1/2 -translate-x-1/2 text-xs tracking-[0.4em] text-cyan-500/50 font-mono">
                    NEURAL INTERFACE V2.0
                </div>
            </div>
        </>
    );
}
