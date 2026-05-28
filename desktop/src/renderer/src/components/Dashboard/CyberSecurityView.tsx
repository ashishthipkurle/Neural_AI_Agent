import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useCyberStore } from '../../store/cyberStore';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
    X, ShieldAlert, Terminal, Send, ChevronRight, Globe, Wifi, Smartphone,
    MapPin, MessageCircle, Monitor, Server, Key, Bug, Radio, Search,
    Skull, Zap, Lock, Database, Eye
} from 'lucide-react';

interface Message {
    id: string;
    role: 'user' | 'phantom' | 'system';
    content: string;
}

interface CyberSecurityViewProps {
    onClose: () => void;
}

// ── Quick Ops Categories ──
const QUICK_OPS = [
    {
        category: 'WEBSITE HACKING', icon: <Globe size={14} />,
        actions: [
            { label: 'SQL Injection Attack', cmd: 'perform SQL injection on a web login form with sqlmap step by step' },
            { label: 'XSS Payload Generator', cmd: 'generate advanced XSS payloads to bypass WAF and CSP filters' },
            { label: 'Directory Bruteforce', cmd: 'bruteforce hidden directories and files on a website using gobuster and ffuf' },
            { label: 'Subdomain Enumeration', cmd: 'enumerate all subdomains of a target domain using multiple tools' },
            { label: 'WAF Bypass Techniques', cmd: 'how to identify and bypass web application firewalls' },
        ]
    },
    {
        category: 'WIFI HACKING', icon: <Wifi size={14} />,
        actions: [
            { label: 'Crack WPA2 Network', cmd: 'crack WPA2 wifi using aircrack-ng with deauth and handshake capture step by step' },
            { label: 'Evil Twin Attack', cmd: 'set up an evil twin access point to intercept wifi traffic' },
            { label: 'PMKID Attack', cmd: 'capture PMKID from wifi router without deauth using hcxdumptool' },
            { label: 'Scan All Networks', cmd: 'scan all wifi networks around me with signal strength and encryption type' },
            { label: 'Deauth Flood', cmd: 'how to perform deauthentication attack on a specific wifi client' },
        ]
    },
    {
        category: 'APP HACKING', icon: <Smartphone size={14} />,
        actions: [
            { label: 'APK Reverse Engineer', cmd: 'reverse engineer an Android APK file and find vulnerabilities' },
            { label: 'iOS App Exploit', cmd: 'exploit iOS application using Frida and objection framework' },
            { label: 'API Vulnerability Scan', cmd: 'find and exploit REST API vulnerabilities including IDOR and broken auth' },
            { label: 'Inject Payload in APK', cmd: 'inject meterpreter payload into an Android APK using msfvenom' },
        ]
    },
    {
        category: 'DEVICE CONTROL', icon: <Monitor size={14} />,
        actions: [
            { label: 'Remote Access Trojan', cmd: 'create a remote access trojan for windows with persistent backdoor and C2' },
            { label: 'Reverse Shell Generator', cmd: 'generate reverse shell payloads for bash python php powershell netcat' },
            { label: 'Keylogger Creation', cmd: 'create an undetectable keylogger for windows with exfiltration' },
            { label: 'Privilege Escalation', cmd: 'linux and windows privilege escalation from user to root/SYSTEM' },
            { label: 'Persistence Methods', cmd: 'establish persistence on a compromised windows and linux system' },
        ]
    },
    {
        category: 'WHATSAPP HACKING', icon: <MessageCircle size={14} />,
        actions: [
            { label: 'WhatsApp Clone', cmd: 'how to clone whatsapp using MAC spoofing and QR code interception' },
            { label: 'Message Interception', cmd: 'intercept whatsapp messages using man in the middle attack on same network' },
            { label: 'Social Engineering', cmd: 'social engineering techniques to gain access to someone whatsapp account' },
        ]
    },
    {
        category: 'LOCATION TRACKING', icon: <MapPin size={14} />,
        actions: [
            { label: 'IP Geolocation', cmd: 'track exact location from an IP address using multiple geolocation databases' },
            { label: 'Phone Number OSINT', cmd: 'perform OSINT on a phone number to find location and identity' },
            { label: 'GPS Spoofing', cmd: 'how to spoof GPS location on android and iOS devices' },
            { label: 'WiFi Triangulation', cmd: 'track device location using wifi access point triangulation' },
        ]
    },
    {
        category: 'NETWORK PENTEST', icon: <Server size={14} />,
        actions: [
            { label: 'Full Port Scan', cmd: 'nmap port scan 127.0.0.1 with service detection and OS fingerprinting' },
            { label: 'Man in the Middle', cmd: 'perform ARP spoofing MITM attack to intercept network traffic' },
            { label: 'Password Sniffing', cmd: 'capture and crack network passwords using wireshark and bettercap' },
            { label: 'Active Directory Attack', cmd: 'attack Active Directory with kerberoasting pass-the-hash and golden ticket' },
        ]
    },
    {
        category: 'OSINT & RECON', icon: <Search size={14} />,
        actions: [
            { label: 'Full OSINT Recon', cmd: 'perform complete OSINT investigation on a target person or organization' },
            { label: 'Email OSINT', cmd: 'find all accounts and breaches associated with an email address' },
            { label: 'Dark Web Search', cmd: 'search the dark web for leaked credentials and data breaches' },
        ]
    },
];

export default function CyberSecurityView({ onClose }: CyberSecurityViewProps) {
    const {
        messages, setMessages,
        psOutput, setPsOutput,
        bashOutput, setBashOutput,
        cmdHistory, setCmdHistory,
        sidebarW, setSidebarW,
        terminalW, setTerminalW,
        termSplitPct, setTermSplitPct,
        expandedCat, setExpandedCat,
        clearMessages
    } = useCyberStore();

    const [input, setInput] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);
    const [histIdx, setHistIdx] = useState(-1);
    const [psInput, setPsInput] = useState('');
    const [bashInput, setBashInput] = useState('');
    const termRef = useRef<HTMLDivElement>(null);
    const psRef = useRef<HTMLDivElement>(null);
    const bashRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const abortRef = useRef<AbortController | null>(null);



    const startDrag = useCallback((onMove: (e: MouseEvent) => void) => {
        const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); document.body.style.cursor = ''; document.body.style.userSelect = ''; };
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    }, []);

    // Focus input on mount
    useEffect(() => {
        setTimeout(() => inputRef.current?.focus(), 300);
    }, []);

    useEffect(() => {
        if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
    }, [messages]);

    useEffect(() => {
        if (psRef.current) psRef.current.scrollTop = psRef.current.scrollHeight;
    }, [psOutput]);

    useEffect(() => {
        if (bashRef.current) bashRef.current.scrollTop = bashRef.current.scrollHeight;
    }, [bashOutput]);

    // ── Real Shell execution via backend subprocess ──
    const runShellCmd = useCallback(async (cmd: string, shell: 'powershell' | 'bash'): Promise<string> => {
        if (!cmd.trim()) return '';
        const isPs = shell === 'powershell';
        const setOutput = isPs ? setPsOutput : setBashOutput;
        const setInp = isPs ? setPsInput : setBashInput;
        const prefix = isPs ? 'PS >' : '$';

        setOutput(p => [...p, `${prefix} ${cmd}`]);
        setInp('');

        try {
            const res = await fetch('http://localhost:8000/api/shell/exec', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: cmd, shell, timeout: 30 }),
                signal: abortRef.current?.signal
            });
            const body = await res.json().catch(() => null);
            const output = body?.output || '(no output)';
            const exitCode = body?.exit_code ?? -1;
            const lines = output.split('\n');
            setOutput(p => [
                ...p,
                ...lines,
                ...(exitCode !== 0 ? [`[exit code: ${exitCode}]`] : []),
            ]);
            return exitCode !== 0 ? `${output}\n[exit code: ${exitCode}]` : output;
        } catch (err: any) {
            if (err.name === 'AbortError') {
                setOutput(p => [...p, '[Execution Aborted]']);
                throw err; // Re-throw to stop loops
            }
            setOutput(p => [...p, 'Error: Could not reach backend.']);
            return 'Error: Could not reach backend.';
        }
    }, []);

    const runPsCmd = useCallback((cmd: string) => runShellCmd(cmd, 'powershell'), [runShellCmd]);
    const runBashCmd = useCallback((cmd: string) => runShellCmd(cmd, 'bash'), [runShellCmd]);

    // ── Extract code blocks from markdown response ──
    const extractCodeBlocks = useCallback((text: string): Array<{ lang: string; code: string }> => {
        const blocks: Array<{ lang: string; code: string }> = [];
        const regex = /```(\w+)?\s*\n([\s\S]*?)```/g;
        let match;
        while ((match = regex.exec(text)) !== null) {
            const lang = (match[1] || '').toLowerCase();
            const code = match[2].trim();
            if (code) blocks.push({ lang, code });
        }
        return blocks;
    }, []);

    // ── Auto-execute code blocks, show results in chat, and FEEDBACK LOOP ──
    const autoExecuteBlocks = useCallback(async (text: string, retryCount = 0): Promise<void> => {
        const blocks = extractCodeBlocks(text);
        const shellMap: Record<string, 'powershell' | 'bash'> = {
            'bash': 'bash', 'sh': 'bash', 'shell': 'bash', 'zsh': 'bash',
            'powershell': 'powershell', 'ps': 'powershell', 'ps1': 'powershell',
            'cmd': 'powershell', 'bat': 'powershell',
        };

        const successes: string[] = [];
        const failures: Array<{ cmd: string; shell: string; output: string }> = [];

        for (const block of blocks) {
            const shell = shellMap[block.lang];
            if (!shell) continue;

            const lines = block.code.split('\n').filter(l =>
                l.trim() && !l.trim().startsWith('#') && !l.trim().startsWith('//')
            );
            for (const line of lines) {
                if (abortRef.current?.signal.aborted) return;
                const output = await runShellCmd(line.trim(), shell);
                const trimmed = output.trim();

                // Detect failure: check exit code markers, error keywords
                const isError = trimmed.includes('[exit code:') ||
                    /command not found|not recognized|cannot be loaded|is not recognized|error|failed|denied|unable to|no such file/i.test(trimmed);

                if (isError && trimmed) {
                    failures.push({ cmd: line.trim(), shell, output: trimmed });
                } else if (trimmed && trimmed !== '(no output)') {
                    successes.push(`\`${line.trim()}\`\n\`\`\`\n${trimmed}\n\`\`\``);
                }
                if (abortRef.current?.signal.aborted) return;
                await new Promise(r => setTimeout(r, 300));
            }
        }

        // Post execution results to chat
        if (successes.length > 0) {
            setMessages(p => [...p, {
                id: `exec-${Date.now()}`,
                role: 'system' as const,
                content: `**⚡ EXECUTION OUTPUT:**\n\n${successes.join('\n\n')}`,
            }]);
        }

        // ── FEEDBACK LOOP: If commands failed, send errors back to PHANTOM ──
        if (failures.length > 0 && retryCount < 2) {
            const failureSummary = failures.map(f =>
                `Command: \`${f.cmd}\` (${f.shell})\nError:\n\`\`\`\n${f.output}\n\`\`\``
            ).join('\n\n');

            // Show failure notice in chat
            setMessages(p => [...p, {
                id: `fail-${Date.now()}`,
                role: 'system' as const,
                content: `**❌ ${failures.length} command(s) failed.** Sending errors back to PHANTOM for analysis...`,
            }]);

            // Send errors back to PHANTOM for diagnosis and fix
            setMessages(p => [...p, { id: 'retry-thinking', role: 'system', content: '🔄 PHANTOM analyzing errors and finding alternatives...' }]);

            try {
                const retryPrompt = (
                    `The following commands were just executed on the operator's WINDOWS machine and FAILED.\n\n` +
                    `FAILED COMMANDS:\n${failureSummary}\n\n` +
                    `IMPORTANT CONTEXT:\n` +
                    `- This is a WINDOWS machine (not Linux)\n` +
                    `- Git Bash may be available but has limited Linux tools\n` +
                    `- PowerShell is the primary shell\n` +
                    `- If a tool is not installed, tell me how to install it first, OR provide an alternative that works on Windows\n` +
                    `- Provide ONLY the fixed/alternative commands that will work\n` +
                    `- Use \`\`\`powershell for Windows commands\n\n` +
                    `Fix these errors. Provide working alternative commands for Windows.`
                );

                const res = await fetch('http://localhost:8000/api/phantom', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: retryPrompt }),
                });
                const body = await res.json().catch(() => null);
                const fixText = typeof body?.response === 'string' ? body.response.trim() : '';

                setMessages(p => {
                    const f = p.filter(m => m.id !== 'retry-thinking');
                    return [...f, {
                        id: `ph-fix-${Date.now()}`,
                        role: 'phantom' as const,
                        content: fixText || '⚠ Could not generate fix.',
                    }];
                });

                // Auto-execute the fix (with incremented retry count)
                if (fixText) {
                    await autoExecuteBlocks(fixText, retryCount + 1);
                }
            } catch {
                setMessages(p => {
                    const f = p.filter(m => m.id !== 'retry-thinking');
                    return [...f, { id: `e-${Date.now()}`, role: 'system' as const, content: '⚠ Could not reach PHANTOM for retry.' }];
                });
            }
        }
    }, [extractCodeBlocks, runShellCmd]);

    // ── Send to PHANTOM ──
    const sendCommand = useCallback(async (cmd: string) => {
        if (!cmd.trim() || isProcessing) return;
        setMessages(p => [...p, { id: `u-${Date.now()}`, role: 'user', content: cmd }]);
        setCmdHistory(p => [cmd, ...p.slice(0, 50)]);
        setHistIdx(-1);
        setInput('');
        setIsProcessing(true);
        setMessages(p => [...p, { id: 'thinking', role: 'system', content: '⏳ PHANTOM analyzing...' }]);

        try {
            const ctrl = new AbortController();
            abortRef.current = ctrl;
            const res = await fetch('http://localhost:8000/api/phantom', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: cmd }), signal: ctrl.signal,
            });
            const body = await res.json().catch(() => null);
            if (ctrl.signal.aborted) return; // Exit if aborted
            const text = typeof body?.response === 'string' ? body.response.trim() : '';
            setMessages(p => {
                const f = p.filter(m => m.id !== 'thinking');
                return [...f, { id: `ph-${Date.now()}`, role: 'phantom' as const, content: text || '⚠ No response.' }];
            });

            // ── AUTO-EXECUTE with feedback loop ──
            if (text) {
                await autoExecuteBlocks(text);
            }
        } catch (err: any) {
            setMessages(p => {
                const f = p.filter(m => m.id !== 'thinking');
                const msg = err.name === 'AbortError' ? '⏹ Aborted.' : `⚠ Error: ${err.message}`;
                return [...f, { id: `e-${Date.now()}`, role: 'system' as const, content: msg }];
            });
        } finally {
            setIsProcessing(false);
            abortRef.current = null;
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [isProcessing, autoExecuteBlocks]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'ArrowUp') { e.preventDefault(); const i = Math.min(histIdx + 1, cmdHistory.length - 1); setHistIdx(i); if (cmdHistory[i]) setInput(cmdHistory[i]); }
        else if (e.key === 'ArrowDown') { e.preventDefault(); if (histIdx > 0) { setHistIdx(histIdx - 1); setInput(cmdHistory[histIdx - 1]); } else { setHistIdx(-1); setInput(''); } }
        else if (e.key === 'c' && e.ctrlKey && isProcessing) { abortRef.current?.abort(); }
    };

    // ── Execute code from PHANTOM response in the appropriate terminal ──
    const executeCodeBlock = useCallback(async (code: string, lang: string) => {
        if (isProcessing) return;
        setIsProcessing(true);
        const ctrl = new AbortController();
        abortRef.current = ctrl;

        const shellLangs: Record<string, 'powershell' | 'bash'> = {
            'bash': 'bash', 'sh': 'bash', 'shell': 'bash', 'zsh': 'bash',
            'powershell': 'powershell', 'ps': 'powershell', 'ps1': 'powershell',
            'cmd': 'powershell', 'bat': 'powershell',
        };
        const shell = shellLangs[lang.toLowerCase()] || 'powershell';
        const lines = code.split('\n').filter(l => l.trim() && !l.trim().startsWith('#') && !l.trim().startsWith('//'));
        
        try {
            for (const line of lines) {
                if (ctrl.signal.aborted) break;
                await runShellCmd(line.trim(), shell);
                await new Promise(r => setTimeout(r, 200));
            }
        } catch (err: any) {
            console.error('Execution failed:', err);
        } finally {
            setIsProcessing(false);
            abortRef.current = null;
        }
    }, [isProcessing, runShellCmd]);

    // ── Markdown Renderer ──
    const renderPhantom = (content: string) => (
        <div className="text-[13px] leading-relaxed text-[#ccc]">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
                h1: ({ children }) => <h1 className="text-base font-bold text-white mt-3 mb-1">{children}</h1>,
                h2: ({ children }) => <h2 className="text-sm font-bold text-white mt-3 mb-1">{children}</h2>,
                h3: ({ children }) => <h3 className="text-sm font-semibold text-gray-200 mt-2 mb-1">{children}</h3>,
                p: ({ children }) => <p className="mb-2">{children}</p>,
                ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-0.5 pl-2">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-0.5 pl-2">{children}</ol>,
                li: ({ children }) => <li className="text-gray-300">{children}</li>,
                strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
                em: ({ children }) => <em className="italic text-gray-400">{children}</em>,
                a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">{children}</a>,
                code: ({ className, children, ...props }) => {
                    const langMatch = className?.match(/language-(\w+)/);
                    if (langMatch) {
                        const lang = langMatch[1];
                        const codeStr = String(children).replace(/\n$/, '');
                        const isShellLang = ['bash', 'sh', 'shell', 'zsh', 'powershell', 'ps', 'ps1', 'cmd', 'bat', 'python', 'py'].includes(lang.toLowerCase());
                        return (
                            <div className="my-2 rounded-lg overflow-hidden border border-[#333] bg-[#0a0a0a]">
                                <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-gray-500 border-b border-[#222] bg-[#111] flex justify-between items-center">
                                    <span>{lang}</span>
                                    <div className="flex gap-2">
                                        <button onClick={() => navigator.clipboard.writeText(codeStr)} className="text-gray-500 hover:text-white transition-colors">COPY</button>
                                        {isShellLang && (
                                            <button onClick={() => executeCodeBlock(codeStr, lang)}
                                                className="text-emerald-600 hover:text-emerald-400 transition-colors font-bold flex items-center gap-1">
                                                <Zap size={10} /> RUN
                                            </button>
                                        )}
                                    </div>
                                </div>
                                <pre className="p-3 overflow-x-auto text-xs"><code className="text-green-400 font-mono" {...props}>{children}</code></pre>
                            </div>
                        );
                    }
                    return <code className="px-1 py-0.5 rounded bg-[#222] text-orange-300 text-xs font-mono" {...props}>{children}</code>;
                },
                pre: ({ children }) => <>{children}</>,
                table: ({ children }) => <div className="my-2 overflow-x-auto rounded border border-[#333]"><table className="w-full text-xs">{children}</table></div>,
                thead: ({ children }) => <thead className="bg-[#111] text-gray-300">{children}</thead>,
                th: ({ children }) => <th className="px-2 py-1 text-left font-medium border-b border-[#333]">{children}</th>,
                td: ({ children }) => <td className="px-2 py-1 border-b border-[#1a1a1a] text-gray-400">{children}</td>,
                blockquote: ({ children }) => <blockquote className="border-l-2 border-gray-600 pl-3 my-2 text-gray-400 italic">{children}</blockquote>,
                hr: () => <hr className="my-3 border-[#333]" />,
            }}>{content}</ReactMarkdown>
        </div>
    );

    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[999] bg-[#000] flex flex-col overflow-hidden text-[#e0e0e0] font-sans">

            {/* ═══ TOP BAR ═══ */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-[#222] bg-[#0a0a0a] shrink-0">
                <div className="flex items-center gap-3">
                    <ShieldAlert size={16} className="text-red-500" />
                    <span className="text-sm font-bold tracking-wider text-white">PHANTOM OPS COMMAND</span>
                    <div className="h-4 w-px bg-white/10" />
                    <span className="text-[10px] px-2 py-0.5 rounded border border-[#333] bg-[#111] text-gray-400">OPSEC: SECURE</span>
                    <span className="text-[10px] px-2 py-0.5 rounded border border-[#333] bg-[#111] text-gray-400">MODE: OFFENSIVE</span>
                    {isProcessing && <span className="text-[10px] px-2 py-0.5 rounded border border-red-500/30 bg-red-900/20 text-red-400 animate-pulse">● EXECUTING</span>}
                </div>
                <div className="flex items-center gap-2">
                    {isProcessing && <button onClick={() => abortRef.current?.abort()} className="text-[10px] px-3 py-1 rounded border border-red-500/30 bg-red-900/20 text-red-400 hover:bg-red-900/40">ABORT</button>}
                    <button onClick={clearMessages} className="text-[10px] px-3 py-1 rounded border border-[#333] text-gray-500 hover:text-white hover:border-[#555] transition-colors">CLEAR</button>
                    <button onClick={onClose} className="p-1.5 rounded-lg border border-[#333] text-gray-500 hover:text-red-400 hover:border-red-500/30 transition-colors"><X size={14} /></button>
                </div>
            </div>

            {/* ═══ MAIN ═══ */}
            <div className="flex-1 flex min-h-0 overflow-hidden">

                {/* LEFT — Quick Ops */}
                <div style={{ width: sidebarW }} className="border-r border-[#222] bg-[#080808] flex flex-col shrink-0 overflow-hidden">
                    <div className="px-3 py-2 text-[10px] tracking-[0.15em] text-gray-500 border-b border-[#222] font-bold">QUICK OPS</div>
                    <div className="flex-1 overflow-y-auto custom-scrollbar">
                        {QUICK_OPS.map(cat => (
                            <div key={cat.category}>
                                <button
                                    onClick={() => setExpandedCat(expandedCat === cat.category ? null : cat.category)}
                                    className={`w-full text-left px-3 py-2.5 text-[11px] font-bold tracking-wider flex items-center gap-2 border-b border-[#1a1a1a] transition-colors ${expandedCat === cat.category ? 'bg-[#111] text-white' : 'text-gray-500 hover:bg-[#0d0d0d] hover:text-gray-300'}`}
                                >
                                    {cat.icon}
                                    <span className="flex-1">{cat.category}</span>
                                    <ChevronRight size={12} className={`transition-transform ${expandedCat === cat.category ? 'rotate-90' : ''}`} />
                                </button>
                                {expandedCat === cat.category && (
                                    <div className="bg-[#060606]">
                                        {cat.actions.map((a, i) => (
                                            <button key={i} onClick={() => sendCommand(a.cmd)} disabled={isProcessing}
                                                className="w-full text-left px-5 py-2 text-[11px] text-gray-400 hover:bg-[#111] hover:text-white border-b border-[#111] transition-colors disabled:opacity-30 truncate">
                                                {a.label}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* DRAG HANDLE: Sidebar ↔ Chat */}
                <div className="w-1 cursor-col-resize bg-[#222] hover:bg-[#555] active:bg-[#666] transition-colors shrink-0"
                    onMouseDown={() => startDrag((e) => setSidebarW(w => Math.max(160, Math.min(400, e.clientX))))} />

                {/* CENTER — PHANTOM Chat */}
                <div className="flex-1 flex flex-col min-w-0 min-h-0">
                    <div className="px-4 py-2 border-b border-[#222] bg-[#0a0a0a] flex items-center gap-2 shrink-0">
                        <ShieldAlert size={13} className="text-red-500" />
                        <span className="text-xs font-bold tracking-wider text-white">PHANTOM AGENT</span>
                        <span className="text-[10px] text-gray-600 ml-auto">All queries routed through PHANTOM persona</span>
                    </div>

                    <div ref={termRef} className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar bg-[#050505]">
                        {messages.map(msg => (
                            <div key={msg.id}>
                                {msg.role === 'user' ? (
                                    <div className="flex items-start gap-2 text-sm">
                                        <span className="text-gray-500 font-mono text-xs shrink-0 mt-0.5">YOU ›</span>
                                        <span className="text-white">{msg.content}</span>
                                    </div>
                                ) : msg.role === 'system' ? (
                                    msg.id.startsWith('exec-') ? (
                                        <div className="bg-[#080808] border border-emerald-900/30 rounded-lg p-4">
                                            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-emerald-900/20">
                                                <Zap size={12} className="text-emerald-400" />
                                                <span className="text-[10px] tracking-widest font-bold text-emerald-400">TERMINAL OUTPUT</span>
                                            </div>
                                            {renderPhantom(msg.content)}
                                        </div>
                                    ) : msg.id.startsWith('fail-') ? (
                                        <div className="bg-[#0a0505] border border-red-900/30 rounded-lg px-4 py-2 flex items-center gap-2">
                                            <Bug size={12} className="text-red-400 shrink-0" />
                                            <span className="text-xs text-red-400">{msg.content.replace(/\*\*/g, '')}</span>
                                        </div>
                                    ) : msg.content.includes('🔄') ? (
                                        <div className="text-xs text-amber-500 animate-pulse flex items-center gap-2 py-1">
                                            <div className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                                            {msg.content}
                                        </div>
                                    ) : msg.content.includes('⏳') ? (
                                        <div className="text-xs text-amber-500 animate-pulse">{msg.content}</div>
                                    ) : (
                                        <div className="text-xs text-gray-500">{msg.content}</div>
                                    )
                                ) : (
                                    <div className="bg-[#0a0a0a] border border-[#222] rounded-lg p-4">
                                        <div className="flex items-center gap-2 mb-2 pb-2 border-b border-[#1a1a1a]">
                                            <ShieldAlert size={12} className="text-red-500" />
                                            <span className="text-[10px] tracking-widest font-bold text-red-500">PHANTOM</span>
                                        </div>
                                        {renderPhantom(msg.content)}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>

                    {/* Command Input */}
                    <form onSubmit={e => { e.preventDefault(); sendCommand(input); }}
                        className="border-t border-[#222] bg-[#0a0a0a] px-4 py-4 flex items-center gap-3 shrink-0">
                        <span className="text-gray-500 text-sm font-mono shrink-0">PHANTOM ›</span>
                        <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown}
                            disabled={isProcessing} autoComplete="off" spellCheck={false}
                            className="flex-1 bg-[#111] border border-[#333] rounded-lg px-4 py-3 text-sm text-white placeholder:text-gray-600 outline-none focus:border-[#555] disabled:opacity-40 transition-colors"
                            placeholder={isProcessing ? 'Executing... (Ctrl+C to abort)' : 'Ask PHANTOM anything... hack wifi, exploit website, generate payload...'} />
                        <button type="submit" disabled={!input.trim() || isProcessing}
                            className="px-5 py-3 rounded-lg bg-[#222] border border-[#333] text-white hover:bg-[#333] disabled:opacity-20 transition-colors flex items-center gap-2 text-sm font-medium">
                            <Send size={14} /> EXEC
                        </button>
                    </form>
                </div>

                {/* DRAG HANDLE: Chat ↔ Terminals */}
                <div className="w-1 cursor-col-resize bg-[#222] hover:bg-[#555] active:bg-[#666] transition-colors shrink-0"
                    onMouseDown={() => startDrag((e) => setTerminalW(w => Math.max(250, Math.min(600, window.innerWidth - e.clientX))))} />

                {/* RIGHT — Terminals Stacked */}
                <div style={{ width: terminalW }} className="flex flex-col shrink-0">

                    {/* PowerShell Terminal */}
                    <div style={{ height: `${termSplitPct}%` }} className="flex flex-col border-b border-[#222] min-h-0">
                        <div className="px-3 py-2 border-b border-[#222] bg-[#0a0a0a] flex items-center gap-2 shrink-0">
                            <Terminal size={13} className="text-blue-400" />
                            <span className="text-[11px] font-bold tracking-wider text-white">POWERSHELL</span>
                            <div className="w-1.5 h-1.5 rounded-full bg-blue-400 ml-1" />
                            <button onClick={() => setPsOutput(['Windows PowerShell', ''])} className="ml-auto text-[10px] text-gray-600 hover:text-white transition-colors">Clear</button>
                        </div>
                        <div ref={psRef} className="flex-1 overflow-y-auto p-2 font-mono text-xs custom-scrollbar bg-[#050505]">
                            {psOutput.map((line, i) => (
                                <div key={i} className={`whitespace-pre-wrap ${line.startsWith('PS') ? 'text-blue-300' : line.startsWith('[exit') ? 'text-red-400' : line.startsWith('Error') ? 'text-red-400' : 'text-gray-300'}`}>{line}</div>
                            ))}
                        </div>
                        <form onSubmit={e => { e.preventDefault(); runPsCmd(psInput); }}
                            className="border-t border-[#222] bg-[#050505] px-3 py-1.5 flex items-center gap-1 shrink-0">
                            <span className="text-blue-400 text-xs font-mono">PS&gt;</span>
                            <input value={psInput} onChange={e => setPsInput(e.target.value)}
                                className="flex-1 bg-transparent text-xs text-white outline-none font-mono caret-blue-400"
                                autoComplete="off" spellCheck={false} autoFocus />
                        </form>
                    </div>

                    {/* DRAG HANDLE: PowerShell ↔ Bash */}
                    <div className="h-1 cursor-row-resize bg-[#222] hover:bg-[#555] active:bg-[#666] transition-colors shrink-0"
                        onMouseDown={(e) => {
                            const startY = e.clientY;
                            const startPct = termSplitPct;
                            const parent = (e.target as HTMLElement).parentElement;
                            const parentH = parent?.clientHeight || 600;
                            const onMove = (ev: MouseEvent) => {
                                const delta = ev.clientY - startY;
                                const newPct = startPct + (delta / parentH) * 100;
                                setTermSplitPct(Math.max(20, Math.min(80, newPct)));
                            };
                            const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); document.body.style.cursor = ''; document.body.style.userSelect = ''; };
                            document.addEventListener('mousemove', onMove);
                            document.addEventListener('mouseup', onUp);
                            document.body.style.cursor = 'row-resize';
                            document.body.style.userSelect = 'none';
                        }} />

                    {/* Bash Terminal */}
                    <div style={{ height: `${100 - termSplitPct}%` }} className="flex flex-col min-h-0">
                        <div className="px-3 py-2 border-b border-[#222] bg-[#0a0a0a] flex items-center gap-2 shrink-0">
                            <Terminal size={13} className="text-green-400" />
                            <span className="text-[11px] font-bold tracking-wider text-white">BASH</span>
                            <div className="w-1.5 h-1.5 rounded-full bg-green-400 ml-1" />
                            <button onClick={() => setBashOutput(['GNU bash', ''])} className="ml-auto text-[10px] text-gray-600 hover:text-white transition-colors">Clear</button>
                        </div>
                        <div ref={bashRef} className="flex-1 overflow-y-auto p-2 font-mono text-xs custom-scrollbar bg-[#050505]">
                            {bashOutput.map((line, i) => (
                                <div key={i} className={`whitespace-pre-wrap ${line.startsWith('$') ? 'text-green-300' : line.startsWith('[exit') ? 'text-red-400' : line.startsWith('Error') ? 'text-red-400' : 'text-gray-300'}`}>{line}</div>
                            ))}
                        </div>
                        <form onSubmit={e => { e.preventDefault(); runBashCmd(bashInput); }}
                            className="border-t border-[#222] bg-[#050505] px-3 py-1.5 flex items-center gap-1 shrink-0">
                            <span className="text-green-400 text-xs font-mono">$</span>
                            <input value={bashInput} onChange={e => setBashInput(e.target.value)}
                                className="flex-1 bg-transparent text-xs text-white outline-none font-mono caret-green-400"
                                autoComplete="off" spellCheck={false} />
                        </form>
                    </div>
                </div>
            </div>
        </motion.div>
    );
}

