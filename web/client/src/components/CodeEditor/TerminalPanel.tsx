"use client";

import React, { useEffect, useRef, useState } from "react";
import { Terminal as XTerm } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import {
    ChevronUp,
    ChevronDown,
    X,
    Terminal as TerminalIcon,
    Play,
    Plus,
} from "lucide-react";
import "xterm/css/xterm.css";

type ShellType = "powershell" | "cmd";

interface TerminalInstance {
    id: string;
    name: string;
    type: ShellType;
    term?: XTerm;
    fitAddon?: FitAddon;
    cwd: string;
    buffer: string;
    history: string[];
    historyIndex: number;
}

const DEFAULT_CWD = "D:\\All Projects\\My AI Agent\\generated";

export default function TerminalPanel({
    isOpen,
    onToggle,
    currentFile,
    workingDirectory,
}: {
    isOpen: boolean;
    onToggle: () => void;
    currentFile?: string;
    workingDirectory?: string;
}) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [terms, setTerms] = useState<TerminalInstance[]>([]);
    const [activeId, setActiveId] = useState<string | null>(null);

    /* ---------------------------------- PROMPT ---------------------------------- */

    const prompt = (t: TerminalInstance) =>
        t.type === "powershell"
            ? `\x1b[36mPS\x1b[0m \x1b[33m${t.cwd}\x1b[0m\x1b[36m>\x1b[0m `
            : `\x1b[33m${t.cwd}\x1b[0m\x1b[32m>\x1b[0m `;

    /* ----------------------------- CREATE TERMINAL ------------------------------ */

    const createTerminal = (type: ShellType) => {
        const id = `term-${Date.now()}`;
        setTerms((prev) => [
            ...prev,
            {
                id,
                name: type,
                type,
                cwd: workingDirectory || DEFAULT_CWD,
                buffer: "",
                history: [],
                historyIndex: -1,
            },
        ]);
        setActiveId(id);
    };

    useEffect(() => {
        if (isOpen && terms.length === 0) createTerminal("powershell");
    }, [isOpen]);

    /* ------------------------------ INIT XTERM ---------------------------------- */

    useEffect(() => {
        if (!isOpen || !containerRef.current || !activeId) return;

        const t = terms.find((x) => x.id === activeId);
        if (!t || t.term) return;

        containerRef.current.innerHTML = "";

        const term = new XTerm({
            fontFamily: "JetBrains Mono, Consolas, monospace",
            fontSize: 13,
            cursorBlink: true,
            cursorStyle: "bar",
            theme: {
                background: "#0a0f1a",
                foreground: "#e0e0e0",
                cursor: "#00c8d4",
            },
        });

        const fit = new FitAddon();
        term.loadAddon(fit);
        term.open(containerRef.current);
        fit.fit();

        term.writeln("\x1b[36mNeural Code Editor Terminal\x1b[0m\n");
        term.write(prompt(t));

        term.onKey(({ key, domEvent }) => {
            handleKey(term, t, key, domEvent);
        });

        // Handle paste (Ctrl+V)
        term.attachCustomKeyEventHandler((event) => {
            if (event.ctrlKey && event.key === "v") {
                navigator.clipboard.readText().then((text) => {
                    if (text) {
                        t.buffer += text;
                        term.write(text);
                    }
                }).catch(() => { });
                return false;
            }
            return true;
        });

        setTerms((prev) =>
            prev.map((x) =>
                x.id === t.id ? { ...x, term, fitAddon: fit } : x
            )
        );

        const resize = () => fit.fit();
        window.addEventListener("resize", resize);
        return () => window.removeEventListener("resize", resize);
    }, [isOpen, activeId, terms]);

    /* ------------------------------ KEY HANDLING -------------------------------- */

    const handleKey = (
        term: XTerm,
        t: TerminalInstance,
        key: string,
        e: KeyboardEvent
    ) => {
        if (e.key === "Enter") {
            term.write("\r\n");
            execute(t, term);
            return;
        }

        if (e.key === "Backspace") {
            if (t.buffer.length > 0) {
                t.buffer = t.buffer.slice(0, -1);
                term.write("\b \b");
            }
            return;
        }

        if (e.key === "ArrowUp") {
            if (t.history.length === 0) return;
            t.historyIndex = Math.max(0, t.historyIndex - 1);
            replaceLine(term, t, t.history[t.historyIndex]);
            return;
        }

        if (e.key === "ArrowDown") {
            t.historyIndex = Math.min(
                t.history.length,
                t.historyIndex + 1
            );
            replaceLine(
                term,
                t,
                t.history[t.historyIndex] || ""
            );
            return;
        }

        if (key.length === 1) {
            t.buffer += key;
            term.write(key);
        }
    };

    const replaceLine = (term: XTerm, t: TerminalInstance, value: string) => {
        term.write("\x1b[2K\r");
        term.write(prompt(t));
        term.write(value);
        t.buffer = value;
    };

    /* ------------------------------ EXECUTION ----------------------------------- */

    const execute = async (t: TerminalInstance, term: XTerm) => {
        const cmd = t.buffer.trim();
        t.buffer = "";
        t.history.push(cmd);
        t.historyIndex = t.history.length;

        if (!cmd) {
            term.write(prompt(t));
            return;
        }

        if (cmd === "cls" || cmd === "clear") {
            term.clear();
            term.write(prompt(t));
            return;
        }

        if (cmd.startsWith("cd ")) {
            const path = cmd.slice(3).replace(/"/g, "");
            t.cwd = path.includes(":") ? path : `${t.cwd}\\${path}`;
            term.write(prompt(t));
            return;
        }

        try {
            const res = await fetch("http://localhost:8000/api/terminal", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    command: cmd,
                    cwd: t.cwd,
                    shell: t.type,
                }),
            });
            const data = await res.json();

            // Write output line by line for proper formatting
            if (data.output) {
                const lines = data.output.split('\n');
                lines.forEach((line: string) => {
                    term.write('\r\n' + line);
                });
            }
            if (data.error) {
                const errorLines = data.error.split('\n');
                errorLines.forEach((line: string) => {
                    term.write('\r\n\x1b[31m' + line + '\x1b[0m');
                });
            }
        } catch {
            term.write("\r\n\x1b[31mBackend unavailable\x1b[0m");
        }

        term.write('\r\n');
        term.write(prompt(t));
    };

    /* ---------------------------------- UI ------------------------------------- */

    if (!isOpen)
        return (
            <div
                onClick={onToggle}
                className="h-8 bg-[#0a0f1a] border-t border-cyan-500/20 flex items-center px-3 cursor-pointer"
            >
                <TerminalIcon size={14} className="text-cyan-500 mr-2" />
                <span className="text-xs text-cyan-500">Terminal</span>
                <ChevronUp className="ml-auto text-cyan-500" size={14} />
            </div>
        );

    return (
        <div className="flex flex-col bg-[#0a0f1a] border-t border-cyan-500/20">
            <div className="h-8 bg-[#0c1624] flex items-center px-2">
                {terms.map((t) => (
                    <button
                        key={t.id}
                        onClick={() => setActiveId(t.id)}
                        className={`text-xs px-2 py-1 rounded mr-1 ${activeId === t.id
                            ? "bg-cyan-500/20 text-cyan-400"
                            : "text-white/60"
                            }`}
                    >
                        {t.name}
                    </button>
                ))}
                <button
                    onClick={() => createTerminal("powershell")}
                    className="ml-auto text-cyan-400"
                >
                    <Plus size={14} />
                </button>
                <button onClick={onToggle} className="ml-2 text-white/60">
                    <ChevronDown size={14} />
                </button>
            </div>

            <div ref={containerRef} className="h-48 p-2" />
        </div>
    );
}
