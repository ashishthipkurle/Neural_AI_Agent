import React, { useState, useRef, useEffect } from "react";
import {
    X, Send, Copy, Download, RefreshCw, CheckCircle,
    Instagram, Linkedin, Youtube, FileText, Mail, Hash,
    Image, Type, AlignLeft, Sparkles, Edit, Palette,
    ChevronDown, Globe, PenTool
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/* ============ TYPES ============ */

interface Platform {
    id: string;
    label: string;
    icon: React.ComponentType<any>;
    color: string;
    bgColor: string;
    maxChars?: number;
}

interface GeneratedContent {
    text: string;
    hashtags?: string[];
    imagePrompt?: string;
    platform: string;
    timestamp: number;
}

interface ChatMessage {
    id: string;
    role: "user" | "agent";
    content: string;
}

/* ============ PLATFORMS ============ */

const PLATFORMS: Platform[] = [
    { id: "instagram", label: "Instagram", icon: Instagram, color: "text-pink-400", bgColor: "bg-pink-500", maxChars: 2200 },
    { id: "linkedin", label: "LinkedIn", icon: Linkedin, color: "text-blue-400", bgColor: "bg-blue-500", maxChars: 3000 },
    { id: "youtube", label: "YouTube", icon: Youtube, color: "text-red-400", bgColor: "bg-red-500" },
    { id: "blog", label: "Blog Post", icon: FileText, color: "text-emerald-400", bgColor: "bg-emerald-500" },
    { id: "twitter", label: "Twitter/X", icon: Globe, color: "text-cyan-400", bgColor: "bg-cyan-500", maxChars: 280 },
    { id: "email", label: "Email", icon: Mail, color: "text-yellow-400", bgColor: "bg-yellow-500" },
];

/* ============ MAIN VIEW ============ */

interface ContentCreatorViewProps {
    onClose: () => void;
}

export default function ContentCreatorView({ onClose }: ContentCreatorViewProps) {
    const [selectedPlatform, setSelectedPlatform] = useState<Platform>(PLATFORMS[0]);
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
    const [chatInput, setChatInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [generatedContent, setGeneratedContent] = useState<GeneratedContent | null>(null);
    const [history, setHistory] = useState<GeneratedContent[]>([]);
    const [copied, setCopied] = useState(false);
    const chatRef = useRef<HTMLDivElement>(null);

    // Settings
    const [tone, setTone] = useState("Professional");
    const [length, setLength] = useState("Medium");
    const [style, setStyle] = useState("Engaging");

    const tones = ["Professional", "Casual", "Humorous", "Inspirational", "Educational", "Provocative"];
    const lengths = ["Short", "Medium", "Long", "Thread"];
    const styles = ["Engaging", "Storytelling", "Listicle", "How-to", "Opinion", "News"];

    useEffect(() => {
        if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }, [chatMessages]);

    // ── LOCAL CONTENT GENERATION ──
    function generateLocalContent(topic: string, platform: string, toneSetting: string, lengthSetting: string, styleSetting: string): { text: string; hashtags: string[]; imagePrompt: string } {
        const topicCap = topic.charAt(0).toUpperCase() + topic.slice(1);
        const emoji: Record<string, string> = { instagram: "📸✨", linkedin: "💼🚀", youtube: "🎬📹", blog: "📝💡", twitter: "🔥💬", email: "📧✉️" };
        const e = emoji[platform] || "✨";

        const toneMap: Record<string, string> = {
            Professional: "In today's rapidly evolving landscape",
            Casual: "Hey everyone! So I've been thinking about",
            Humorous: "Okay, hear me out on this one 😂",
            Inspirational: "Imagine a world where",
            Educational: "Here's something most people don't know about",
            Provocative: "Unpopular opinion:"
        };

        const opener = toneMap[toneSetting] || toneMap.Professional;

        const bodies: Record<string, string> = {
            instagram: `${e} ${opener} ${topicCap}.\n\nThis is something that's been on my mind lately, and I think it's worth sharing with all of you.\n\n💡 Here's why ${topicCap} matters:\n\n1️⃣ It's changing the way we think about innovation\n2️⃣ The impact on daily life is already visible\n3️⃣ Early adopters are seeing incredible results\n\n${toneSetting === "Casual" ? "What do you think? Drop your thoughts below! 👇" : "I'd love to hear your perspective on this. Share your thoughts in the comments."}\n\n📌 Save this post for later!`,

            linkedin: `${opener} ${topicCap}.\n\nAs professionals, we need to pay attention to this shift. Here's my take:\n\n📊 The data speaks for itself — ${topicCap} is not just a trend, it's a transformation.\n\n**Key Takeaways:**\n• Organizations embracing ${topicCap} are seeing 3x better outcomes\n• The skills gap in this area is widening\n• Now is the time to invest in understanding this space\n\nI've spent the last few weeks diving deep into this topic, and the insights are compelling.\n\nWhat's your experience with ${topicCap}? Are you seeing similar patterns in your industry?\n\n#ThoughtLeadership #Innovation #FutureOfWork`,

            youtube: `🎬 **VIDEO SCRIPT: ${topicCap}**\n\n**[HOOK - 0:00-0:15]**\nDid you know that ${topicCap} is completely changing the game? In this video, I'm going to break down everything you need to know.\n\n**[INTRO - 0:15-0:45]**\nHey everyone, welcome back to the channel! Today we're diving deep into ${topicCap}. If you find this valuable, smash that like button!\n\n**[MAIN CONTENT - 0:45-5:00]**\nLet's start with the basics...\n- Point 1: What ${topicCap} actually means\n- Point 2: Why it matters right now\n- Point 3: How you can get started\n\n**[CTA - 5:00-5:30]**\nIf you enjoyed this video, subscribe and hit the bell! See you in the next one!`,

            blog: `# ${topicCap}: A Complete Guide\n\n${opener} ${topicCap}. Whether you're a beginner or an expert, this comprehensive guide will provide valuable insights.\n\n## What is ${topicCap}?\n\n${topicCap} has emerged as one of the most significant developments in recent years. Understanding its implications is crucial for anyone looking to stay ahead.\n\n## Why Does ${topicCap} Matter?\n\nThe importance of ${topicCap} cannot be overstated. Here are the key reasons:\n\n1. **Innovation Driver**: ${topicCap} is pushing boundaries in ways we haven't seen before\n2. **Practical Applications**: From daily life to enterprise solutions\n3. **Future Potential**: The possibilities are virtually limitless\n\n## Getting Started\n\nIf you're new to ${topicCap}, here's how to begin:\n- Start with the fundamentals\n- Join communities and forums\n- Practice with real projects\n\n## Conclusion\n\n${topicCap} is here to stay. The sooner you embrace it, the better positioned you'll be for the future.`,

            twitter: `${toneSetting === "Provocative" ? "Unpopular opinion: " : ""}${topicCap} is about to change everything.\n\nHere's why 🧵👇`,

            email: `Subject: ${topicCap} — What You Need to Know\n\nHi there,\n\n${opener} ${topicCap}, and I wanted to share some thoughts with you.\n\n${topicCap} is gaining significant momentum, and here's why it should be on your radar:\n\n• The market is shifting rapidly\n• Early movers are gaining competitive advantages\n• The technology is finally mature enough for mainstream adoption\n\nI'd love to discuss this further. Would you be available for a quick call this week?\n\nBest regards,\nINDRA AI`
        };

        const text = bodies[platform] || bodies.instagram;
        
        // Shorten for "Short" length
        const finalText = lengthSetting === "Short" ? text.split("\n\n").slice(0, 2).join("\n\n") :
            lengthSetting === "Long" ? text + `\n\n---\n\n💬 This topic deserves a deeper conversation. What aspects of ${topicCap} are you most interested in? Let's discuss!` :
            text;

        const hashtags = [
            `#${topic.replace(/\s+/g, "")}`,
            "#AI", "#Innovation", "#Technology",
            `#${platform.charAt(0).toUpperCase() + platform.slice(1)}`,
            "#FutureReady", "#DigitalTransformation"
        ];

        const imagePrompt = `A stunning, high-quality ${toneSetting.toLowerCase()} photo representing ${topicCap}. Modern, clean composition with dramatic lighting. Perfect for ${platform} — professional, eye-catching, 4K quality.`;

        return { text: finalText, hashtags, imagePrompt };
    }

    const sendMessage = async () => {
        if (!chatInput.trim() || isProcessing) return;
        const topic = chatInput.trim();
        const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", content: topic };
        setChatMessages(prev => [...prev, userMsg]);
        setChatInput("");
        setIsProcessing(true);

        const prompt = `You are a professional social media content creator. Generate ${selectedPlatform.label} content with these settings:
- Platform: ${selectedPlatform.label}
- Tone: ${tone}
- Length: ${length}
- Style: ${style}
- Topic/Request: ${topic}
${selectedPlatform.maxChars ? `- Max characters: ${selectedPlatform.maxChars}` : ""}

Generate the actual content text that would be posted. Include relevant emojis, formatting, and hashtags appropriate for ${selectedPlatform.label}. 
For YouTube: Write a video script with timestamps.
For Blog: Write with markdown headings and sections.
For Email: Write a complete email with subject line.
For Twitter/X: Keep it under 280 characters.

IMPORTANT: Write the ACTUAL content, not instructions about content. Make it ready to post.`;

        let contentText = "";
        
        try {
            const res = await fetch("http://localhost:8000/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: prompt }),
                signal: AbortSignal.timeout(30000),
            });

            if (res.ok) {
                const data = await res.json();
                contentText = (data.response || "").trim();
            }
        } catch {}

        // Fallback to local generation if AI returned nothing
        if (!contentText || contentText.length < 20) {
            const localGen = generateLocalContent(topic, selectedPlatform.id, tone, length, style);
            contentText = localGen.text;
        }

        const hashtagMatch = contentText.match(/#\w+/g);
        const generated: GeneratedContent = {
            text: contentText,
            hashtags: hashtagMatch || [`#${topic.replace(/\s+/g, "")}`, "#AI", "#Innovation"],
            imagePrompt: `A stunning, high-quality ${tone.toLowerCase()} photo representing ${topic}. Modern, clean composition with dramatic lighting. Perfect for ${selectedPlatform.label} — professional, eye-catching, 4K quality.`,
            platform: selectedPlatform.id,
            timestamp: Date.now(),
        };
        setGeneratedContent(generated);
        setHistory(prev => [generated, ...prev].slice(0, 10));
        setChatMessages(prev => [...prev, {
            id: `a-${Date.now()}`, role: "agent",
            content: `${selectedPlatform.label} content generated! Check the preview panel.`
        }]);
        setIsProcessing(false);
    };

    const copyContent = () => {
        if (generatedContent) {
            navigator.clipboard.writeText(generatedContent.text);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const PlatformIcon = selectedPlatform.icon;

    return (
        <div className="fixed inset-0 z-[100] bg-[#050505] flex flex-col">
            {/* Header */}
            <div className="flex items-center gap-4 px-6 py-3 border-b border-pink-500/20 bg-gradient-to-r from-pink-500/5 to-transparent">
                <div className="w-9 h-9 rounded-xl bg-pink-500/10 border border-pink-500/30 flex items-center justify-center">
                    <PenTool size={18} className="text-pink-400" />
                </div>
                <div className="flex-1">
                    <h1 className="text-sm font-semibold text-pink-400 tracking-wide">Content Creator</h1>
                    <p className="text-[10px] text-slate-500">Generate posts, articles, scripts, and image prompts</p>
                </div>
                <button
                    onClick={() => { if (generatedContent) sendMessage(); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-500/20 border border-purple-500/30 text-purple-400 text-xs font-medium hover:bg-purple-500/30 transition-colors"
                >
                    <RefreshCw size={12} /> Regenerate
                </button>
                <button
                    onClick={copyContent}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-400 text-xs font-medium hover:bg-white/10 transition-colors"
                >
                    {copied ? <CheckCircle size={12} className="text-emerald-400" /> : <Copy size={12} />}
                    {copied ? "Copied!" : "Copy"}
                </button>
                <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                    <X size={18} className="text-slate-400 hover:text-white" />
                </button>
            </div>

            {/* Main: Settings + Preview */}
            <div className="flex-1 flex min-h-0">
                {/* Left: Platform + Settings */}
                <div className="w-[260px] flex flex-col border-r border-white/5">
                    {/* Platform Selector */}
                    <div className="p-4 border-b border-white/5">
                        <div className="text-[10px] font-semibold text-slate-500 tracking-wider uppercase mb-2.5">Platform</div>
                        <div className="grid grid-cols-2 gap-1.5">
                            {PLATFORMS.map(p => {
                                const Icon = p.icon;
                                const isActive = selectedPlatform.id === p.id;
                                return (
                                    <button
                                        key={p.id}
                                        onClick={() => setSelectedPlatform(p)}
                                        className={`flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs transition-all ${
                                            isActive
                                                ? `${p.bgColor}/20 border border-current ${p.color}`
                                                : 'bg-white/[0.02] border border-white/5 text-slate-400 hover:bg-white/5'
                                        }`}
                                    >
                                        <Icon size={14} />
                                        <span className="font-medium">{p.label}</span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Tone */}
                    <div className="p-4 border-b border-white/5">
                        <div className="text-[10px] font-semibold text-slate-500 tracking-wider uppercase mb-2">Tone</div>
                        <div className="flex flex-wrap gap-1">
                            {tones.map(t => (
                                <button
                                    key={t}
                                    onClick={() => setTone(t)}
                                    className={`px-2 py-1 rounded-md text-[10px] transition-colors ${
                                        tone === t ? 'bg-pink-500/20 text-pink-400 border border-pink-500/30' : 'bg-white/[0.03] text-slate-500 border border-white/5 hover:text-slate-300'
                                    }`}
                                >
                                    {t}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Length */}
                    <div className="p-4 border-b border-white/5">
                        <div className="text-[10px] font-semibold text-slate-500 tracking-wider uppercase mb-2">Length</div>
                        <div className="flex gap-1">
                            {lengths.map(l => (
                                <button
                                    key={l}
                                    onClick={() => setLength(l)}
                                    className={`px-2.5 py-1 rounded-md text-[10px] flex-1 transition-colors ${
                                        length === l ? 'bg-pink-500/20 text-pink-400 border border-pink-500/30' : 'bg-white/[0.03] text-slate-500 border border-white/5 hover:text-slate-300'
                                    }`}
                                >
                                    {l}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Style */}
                    <div className="p-4 border-b border-white/5">
                        <div className="text-[10px] font-semibold text-slate-500 tracking-wider uppercase mb-2">Style</div>
                        <div className="flex flex-wrap gap-1">
                            {styles.map(s => (
                                <button
                                    key={s}
                                    onClick={() => setStyle(s)}
                                    className={`px-2 py-1 rounded-md text-[10px] transition-colors ${
                                        style === s ? 'bg-pink-500/20 text-pink-400 border border-pink-500/30' : 'bg-white/[0.03] text-slate-500 border border-white/5 hover:text-slate-300'
                                    }`}
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Recent History */}
                    <div className="flex-1 overflow-y-auto p-4">
                        <div className="text-[10px] font-semibold text-slate-500 tracking-wider uppercase mb-2">Recent</div>
                        {history.length === 0 ? (
                            <p className="text-[10px] text-slate-600 italic">No generations yet</p>
                        ) : (
                            <div className="space-y-1.5">
                                {history.map((h, i) => {
                                    const plat = PLATFORMS.find(p => p.id === h.platform);
                                    const PIcon = plat?.icon || FileText;
                                    return (
                                        <button
                                            key={i}
                                            onClick={() => setGeneratedContent(h)}
                                            className="w-full flex items-center gap-2 p-2 rounded-lg bg-white/[0.02] hover:bg-white/5 transition-colors text-left"
                                        >
                                            <PIcon size={12} className={plat?.color || "text-slate-400"} />
                                            <span className="text-[10px] text-slate-400 truncate flex-1">
                                                {h.text.slice(0, 40)}...
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>

                {/* Center: Content Preview */}
                <div className="flex-1 flex flex-col">
                    <div className="px-4 py-2 text-[10px] font-semibold text-slate-500 tracking-wider uppercase border-b border-white/5 flex items-center gap-2">
                        <PlatformIcon size={10} className={selectedPlatform.color} />
                        {selectedPlatform.label} Preview
                        {generatedContent && selectedPlatform.maxChars && (
                            <span className={`ml-auto ${generatedContent.text.length > selectedPlatform.maxChars ? 'text-red-400' : 'text-emerald-400/50'}`}>
                                {generatedContent.text.length}/{selectedPlatform.maxChars}
                            </span>
                        )}
                    </div>

                    <div className="flex-1 overflow-y-auto p-6">
                        {generatedContent ? (
                            <div className="max-w-lg mx-auto">
                                {/* Platform card */}
                                <div className={`rounded-2xl border ${selectedPlatform.color.replace('text-', 'border-')}/20 bg-white/[0.02] p-6`}>
                                    {/* Platform header */}
                                    <div className="flex items-center gap-2 mb-4 pb-3 border-b border-white/5">
                                        <div className={`w-8 h-8 rounded-full ${selectedPlatform.bgColor}/20 flex items-center justify-center`}>
                                            <PlatformIcon size={14} className={selectedPlatform.color} />
                                        </div>
                                        <div>
                                            <div className="text-xs font-medium text-slate-200">INDRA AI</div>
                                            <div className="text-[10px] text-slate-500">Just now</div>
                                        </div>
                                    </div>

                                    {/* Content */}
                                    <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap mb-4">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}
                                            components={{
                                                p: ({children}) => <p className="mb-2">{children}</p>,
                                                strong: ({children}) => <strong className="text-white font-semibold">{children}</strong>,
                                            }}
                                        >
                                            {generatedContent.text}
                                        </ReactMarkdown>
                                    </div>

                                    {/* Hashtags */}
                                    {generatedContent.hashtags && generatedContent.hashtags.length > 0 && (
                                        <div className="flex flex-wrap gap-1 pt-3 border-t border-white/5">
                                            {generatedContent.hashtags.map((tag, i) => (
                                                <span key={i} className={`text-[11px] ${selectedPlatform.color} opacity-70`}>{tag}</span>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Image Prompt */}
                                {generatedContent.imagePrompt && (
                                    <div className="mt-4 p-4 rounded-xl bg-white/[0.02] border border-white/5">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Image size={12} className="text-purple-400" />
                                            <span className="text-[10px] font-semibold text-purple-400/60 uppercase tracking-wider">Image Prompt</span>
                                        </div>
                                        <p className="text-xs text-slate-400 italic">{generatedContent.imagePrompt}</p>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full text-center opacity-40">
                                <div className="w-20 h-20 rounded-2xl bg-pink-500/5 border border-pink-500/20 flex items-center justify-center mb-4">
                                    <PenTool size={32} className="text-pink-500/30" />
                                </div>
                                <p className="text-sm text-slate-400 mb-1">No content generated yet</p>
                                <p className="text-xs text-slate-600">Select a platform and describe what you want to create</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Bottom: Chat Input */}
            <div className="border-t border-white/5">
                <div className="flex gap-3 p-3 items-center">
                    <div ref={chatRef} className="flex-shrink-0 max-w-[300px] max-h-16 overflow-y-auto space-y-1 px-1">
                        {chatMessages.slice(-2).map(m => (
                            <div key={m.id} className={`text-[10px] ${m.role === 'user' ? 'text-pink-300' : 'text-slate-500'} truncate`}>
                                {m.role === 'user' ? '> ' : '← '}{m.content.slice(0, 60)}
                            </div>
                        ))}
                    </div>
                    <form onSubmit={e => { e.preventDefault(); sendMessage(); }} className="flex-1">
                        <div className="flex rounded-lg overflow-hidden border border-pink-500/20 hover:border-pink-500/40 transition-colors">
                            <input
                                value={chatInput}
                                onChange={e => setChatInput(e.target.value)}
                                disabled={isProcessing}
                                placeholder={`Create ${selectedPlatform.label} content about...`}
                                className="flex-1 px-3 py-2.5 bg-transparent text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none"
                            />
                            <button
                                type="submit"
                                disabled={isProcessing || !chatInput.trim()}
                                className="px-3 bg-pink-500/20 text-pink-400 hover:bg-pink-500/30 transition-colors disabled:opacity-30"
                            >
                                {isProcessing ? <RefreshCw size={14} className="animate-spin" /> : <Send size={14} />}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
