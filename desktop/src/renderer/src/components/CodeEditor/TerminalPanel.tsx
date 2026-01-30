"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Terminal as XTerm } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import { ChevronUp, ChevronDown, Plus, X, Terminal as TerminalIcon, Lock, Unlock } from "lucide-react";
import "xterm/css/xterm.css";

type ShellType = "powershell" | "cmd";

interface TerminalTab {
    id: string;
    name: string;
    shell: ShellType;
    cwd: string;
    aiWritable: boolean;
}

interface TerminalPanelProps {
    isOpen: boolean;
    onToggle: () => void;
}

const DEFAULT_CWD = "D:\\All Projects\\My AI Agent\\generated";

// Declare terminalAPI type
declare global {
    interface Window {
        terminalAPI: {
            create: (data: { id: string; cwd: string; shell: ShellType }) => Promise<any>;
            input: (data: { id: string; data: string }) => Promise<any>;
            resize: (data: { id: string; cols: number; rows: number }) => Promise<any>;
            kill: (id: string) => Promise<any>;
            list: () => Promise<string[]>;
            onData: (id: string, callback: (data: string) => void) => () => void;
            onExit: (id: string, callback: (code: number) => void) => () => void;
        };
    }
}

export default function TerminalPanel({ isOpen, onToggle }: TerminalPanelProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [tabs, setTabs] = useState<TerminalTab[]>([]);
    const [activeTabId, setActiveTabId] = useState<string | null>(null);
    const termInstances = useRef<Map<string, { term: XTerm; fit: FitAddon; cleanup: () => void }>>(new Map());

    /* ========================= SESSION RESTORE ========================= */

    useEffect(() => {
        const saved = localStorage.getItem("terminal-tabs");
        if (saved) {
            try {
                const parsed: TerminalTab[] = JSON.parse(saved);
                if (parsed.length > 0) {
                    setTabs(parsed);
                    setActiveTabId(parsed[0].id);
                    // Recreate PTY sessions for restored tabs
                    parsed.forEach((tab) => {
                        if (window.terminalAPI) {
                            window.terminalAPI.create({
                                id: tab.id,
                                cwd: tab.cwd,
                                shell: tab.shell,
                            });
                        }
                    });
                }
            } catch (e) {
                console.error("Failed to restore terminal sessions:", e);
            }
        }
    }, []);

    // Save tabs to localStorage whenever they change
    useEffect(() => {
        const tabData = tabs.map(({ id, name, shell, cwd, aiWritable }) => ({
            id, name, shell, cwd, aiWritable
        }));
        localStorage.setItem("terminal-tabs", JSON.stringify(tabData));
    }, [tabs]);

    /* =========================== CREATE TAB ============================ */

    const createTab = useCallback((shell: ShellType = "powershell") => {
        const id = crypto.randomUUID();
        const newTab: TerminalTab = {
            id,
            name: shell === "powershell" ? "PowerShell" : "CMD",
            shell,
            cwd: DEFAULT_CWD,
            aiWritable: true,
        };

        setTabs((prev) => [...prev, newTab]);
        setActiveTabId(id);

        // Create PTY session
        if (window.terminalAPI) {
            window.terminalAPI.create({
                id,
                cwd: DEFAULT_CWD,
                shell,
            });
        }
    }, []);

    /* ============================ CLOSE TAB ============================ */

    const closeTab = useCallback((tabId: string) => {
        // Kill PTY session
        if (window.terminalAPI) {
            window.terminalAPI.kill(tabId);
        }

        // Dispose xterm instance
        const instance = termInstances.current.get(tabId);
        if (instance) {
            instance.cleanup();
            instance.term.dispose();
            termInstances.current.delete(tabId);
        }

        setTabs((prev) => {
            const remaining = prev.filter((t) => t.id !== tabId);
            if (activeTabId === tabId && remaining.length > 0) {
                setActiveTabId(remaining[remaining.length - 1].id);
            } else if (remaining.length === 0) {
                setActiveTabId(null);
            }
            return remaining;
        });
    }, [activeTabId]);

    /* ======================= TOGGLE AI PERMISSION ====================== */

    const toggleAiPermission = useCallback((tabId: string) => {
        setTabs((prev) =>
            prev.map((t) =>
                t.id === tabId ? { ...t, aiWritable: !t.aiWritable } : t
            )
        );
    }, []);

    /* ======================== INITIALIZE TERMINAL ====================== */

    useEffect(() => {
        if (!isOpen || !containerRef.current || !activeTabId) return;

        const tab = tabs.find((t) => t.id === activeTabId);
        if (!tab) return;

        // Check if already initialized
        if (termInstances.current.has(activeTabId)) {
            // Just show the existing terminal
            const instance = termInstances.current.get(activeTabId)!;
            containerRef.current.innerHTML = "";
            instance.term.open(containerRef.current);
            instance.fit.fit();
            return;
        }

        // Clear container
        containerRef.current.innerHTML = "";

        // Create new xterm instance
        const term = new XTerm({
            fontFamily: "JetBrains Mono, Consolas, monospace",
            fontSize: 13,
            cursorBlink: true,
            cursorStyle: "block",
            theme: {
                background: "#0a0f1a",
                foreground: "#e0e0e0",
                cursor: "#00c8d4",
                cursorAccent: "#0a0f1a",
                black: "#0a0f1a",
                red: "#ff5555",
                green: "#50fa7b",
                yellow: "#f1fa8c",
                blue: "#6272a4",
                magenta: "#ff79c6",
                cyan: "#00c8d4",
                white: "#f8f8f2",
            },
        });

        const fit = new FitAddon();
        term.loadAddon(fit);
        term.open(containerRef.current);
        fit.fit();

        // Subscribe to PTY data
        let cleanupData = () => { };
        let cleanupExit = () => { };

        if (window.terminalAPI) {
            cleanupData = window.terminalAPI.onData(activeTabId, (data: string) => {
                term.write(data);
            });

            cleanupExit = window.terminalAPI.onExit(activeTabId, (code: number) => {
                term.write(`\r\n\x1b[31m[Process exited with code ${code}]\x1b[0m\r\n`);
            });
        }

        // Handle user input - respects AI permission
        term.onData((data) => {
            const currentTab = tabs.find((t) => t.id === activeTabId);
            if (!currentTab?.aiWritable) {
                // Show lock indicator if AI tries to write when locked
                return;
            }
            if (window.terminalAPI) {
                window.terminalAPI.input({ id: activeTabId, data });
            }
        });

        // Handle resize
        const handleResize = () => {
            fit.fit();
            if (window.terminalAPI) {
                window.terminalAPI.resize({
                    id: activeTabId,
                    cols: term.cols,
                    rows: term.rows,
                });
            }
        };

        window.addEventListener("resize", handleResize);
        handleResize();

        // Store instance
        const cleanup = () => {
            window.removeEventListener("resize", handleResize);
            cleanupData();
            cleanupExit();
        };

        termInstances.current.set(activeTabId, { term, fit, cleanup });

        return () => {
            window.removeEventListener("resize", handleResize);
        };
    }, [activeTabId, isOpen, tabs]);

    /* ================================ UI ================================ */

    if (!isOpen) {
        return (
            <div
                onClick={onToggle}
                className="h-8 bg-[#0a0f1a] border-t border-cyan-500/20 flex items-center px-3 cursor-pointer hover:bg-[#0c1624] transition-colors"
            >
                <TerminalIcon size={14} className="text-cyan-500 mr-2" />
                <span className="text-xs text-cyan-500 font-medium">Terminal</span>
                <span className="ml-2 text-xs text-cyan-500/50">({tabs.length} tabs)</span>
                <ChevronUp className="ml-auto text-cyan-500" size={14} />
            </div>
        );
    }

    return (
        <div className="flex flex-col bg-[#0a0f1a] border-t border-cyan-500/20">
            {/* Tab Bar */}
            <div className="h-8 bg-[#0c1624] flex items-center px-2 border-b border-cyan-500/10 overflow-x-auto">
                {tabs.map((tab) => (
                    <div
                        key={tab.id}
                        className={`flex items-center gap-1.5 px-2 py-1 mr-1 rounded text-xs cursor-pointer group ${activeTabId === tab.id
                                ? "bg-cyan-500/20 text-cyan-400"
                                : "text-white/60 hover:bg-white/5"
                            }`}
                        onClick={() => setActiveTabId(tab.id)}
                    >
                        <TerminalIcon size={12} />
                        <span>{tab.name}</span>
                        {/* AI Permission Indicator */}
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                toggleAiPermission(tab.id);
                            }}
                            className="ml-1 opacity-60 hover:opacity-100"
                            title={tab.aiWritable ? "AI can type (click to lock)" : "AI locked (click to unlock)"}
                        >
                            {tab.aiWritable ? (
                                <Unlock size={10} className="text-green-400" />
                            ) : (
                                <Lock size={10} className="text-red-400" />
                            )}
                        </button>
                        {/* Close Button */}
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                closeTab(tab.id);
                            }}
                            className="ml-1 opacity-0 group-hover:opacity-60 hover:opacity-100"
                        >
                            <X size={12} />
                        </button>
                    </div>
                ))}

                {/* New Tab Buttons */}
                <div className="ml-auto flex items-center gap-1">
                    <button
                        onClick={() => createTab("powershell")}
                        className="p-1 rounded hover:bg-cyan-500/20 text-cyan-400"
                        title="New PowerShell"
                    >
                        <Plus size={14} />
                    </button>
                    <button
                        onClick={() => createTab("cmd")}
                        className="px-2 py-0.5 rounded hover:bg-cyan-500/20 text-cyan-400 text-[10px]"
                        title="New CMD"
                    >
                        CMD
                    </button>
                    <button
                        onClick={onToggle}
                        className="ml-2 text-white/60 hover:text-white"
                    >
                        <ChevronDown size={14} />
                    </button>
                </div>
            </div>

            {/* Terminal Container */}
            {tabs.length === 0 ? (
                <div className="h-64 flex items-center justify-center text-cyan-500/50">
                    <div className="text-center">
                        <TerminalIcon size={32} className="mx-auto mb-2 opacity-50" />
                        <p className="text-sm">No terminals open</p>
                        <button
                            onClick={() => createTab("powershell")}
                            className="mt-2 px-3 py-1 bg-cyan-500/20 rounded text-cyan-400 text-sm hover:bg-cyan-500/30"
                        >
                            New Terminal
                        </button>
                    </div>
                </div>
            ) : (
                <div ref={containerRef} className="h-64 w-full" />
            )}
        </div>
    );
}
