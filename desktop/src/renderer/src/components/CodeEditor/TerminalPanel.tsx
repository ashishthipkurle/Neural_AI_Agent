"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Terminal as XTerm } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import { ChevronUp, ChevronDown, Plus, X, Terminal as TerminalIcon, Lock, Unlock } from "lucide-react";
import "xterm/css/xterm.css";
import { api } from "../../lib/api";

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
    cwd?: string;
    hideHeader?: boolean;
}

const DEFAULT_CWD = "D:\\All Projects\\My AI Agent\\generated";

export default function TerminalPanel({ isOpen, onToggle, cwd, hideHeader = false }: TerminalPanelProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [tabs, setTabs] = useState<TerminalTab[]>([]);
    const [activeTabId, setActiveTabId] = useState<string | null>(null);
    const [restoreAttempted, setRestoreAttempted] = useState(false);
    const termInstances = useRef<Map<string, { term: XTerm; fit: FitAddon; cleanup: () => void }>>(new Map());

    /* =========================== CREATE TAB ============================ */

    const createTab = useCallback((shell: ShellType = "powershell") => {
        const id = crypto.randomUUID();
        // Use provided cwd or fallback to default
        const effectiveCwd = cwd || DEFAULT_CWD;

        const newTab: TerminalTab = {
            id,
            name: shell === "powershell" ? "PowerShell" : "CMD",
            shell,
            cwd: effectiveCwd,
            aiWritable: true,
        };

        setTabs((prev) => [...prev, newTab]);
        setActiveTabId(id);

        // Create PTY session
        api.terminal.create({
            id,
            cwd: effectiveCwd,
            shell,
        });
    }, [cwd]);

    useEffect(() => {
        console.log("DEBUG: TerminalPanel mounted. API:", api);
        if (!api?.terminal) console.error("CRITICAL: Electron API not available!");
        else console.log("DEBUG: Terminal API found:", api.terminal);
    }, []);

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
                        api.terminal.create({
                            id: tab.id,
                            cwd: tab.cwd,
                            shell: tab.shell,
                        });
                    });
                }
            } catch (e) {
                console.error("Failed to restore terminal sessions:", e);
            }
        }

        setRestoreAttempted(true);
    }, []);

    // If opened and no restored tabs exist, create a default PowerShell tab so the terminal is usable.
    useEffect(() => {
        if (!isOpen) return;
        if (!restoreAttempted) return;
        if (tabs.length > 0) return;

        // Avoid auto-creating if the API isn't available.
        if (!api?.terminal) return;

        createTab("powershell");
    }, [isOpen, restoreAttempted, tabs.length, createTab]);

    // Save tabs to localStorage whenever they change
    useEffect(() => {
        const tabData = tabs.map(({ id, name, shell, cwd, aiWritable }) => ({
            id, name, shell, cwd, aiWritable
        }));
        localStorage.setItem("terminal-tabs", JSON.stringify(tabData));
    }, [tabs]);

    /* ============================ CLOSE TAB ============================ */

    const closeTab = useCallback((tabId: string) => {
        // Kill PTY session
        // Kill PTY session
        api.terminal.kill(tabId);

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
                background: "#08080a",
                foreground: "#d1d5db",
                cursor: "#d1d5db",
                cursorAccent: "#08080a",
                black: "#08080a",
                red: "#ef4444",
                green: "#22c55e",
                yellow: "#eab308",
                blue: "#60a5fa",
                magenta: "#a78bfa",
                cyan: "#22d3ee",
                white: "#f3f4f6",
            },
        });

        const fit = new FitAddon();
        term.loadAddon(fit);
        term.open(containerRef.current);
        fit.fit();
        term.focus();

        // Subscribe to PTY data

        // Subscribe to PTY data
        let cleanupData = () => { };
        let cleanupExit = () => { };

        cleanupData = api.terminal.onData(activeTabId, (data: string) => {
            term.write(data);
        });

        cleanupExit = api.terminal.onExit(activeTabId, (code: number) => {
            term.write(`\r\n\x1b[31m[Process exited with code ${code}]\x1b[0m\r\n`);
        });

        // Handle user input - respects AI permission
        term.onData((data) => {
            const currentTab = tabs.find((t) => t.id === activeTabId);
            if (!currentTab?.aiWritable) {
                // Show lock indicator if AI tries to write when locked
                return;
            }
            api.terminal.input({ id: activeTabId, data });
        });

        // Handle resize
        const handleResize = () => {
            fit.fit();
            if (api.terminal) {
                api.terminal.resize({
                    id: activeTabId,
                    cols: term.cols,
                    rows: term.rows,
                });
            }
        };

        window.addEventListener("resize", handleResize);
        handleResize();

        const observer = new ResizeObserver(() => {
            handleResize();
        });

        if (containerRef.current) observer.observe(containerRef.current);

        // Store instance
        const cleanup = () => {
            window.removeEventListener("resize", handleResize);
            observer.disconnect();
            cleanupData();
            cleanupExit();
        };

        termInstances.current.set(activeTabId, { term, fit, cleanup });

        return () => {
            window.removeEventListener("resize", handleResize);
            observer.disconnect();
        };
    }, [activeTabId, isOpen, tabs]);

    /* ================================ UI ================================ */

    if (!isOpen) {
        return (
            <div
                onClick={onToggle}
                className="h-8 bg-[#08080a] border-t border-gray-800 flex items-center px-3 cursor-pointer hover:bg-white/5 transition-colors"
            >
                <TerminalIcon size={14} className="text-gray-300 mr-2" />
                <span className="text-xs text-gray-300 font-medium">Terminal</span>
                <span className="ml-2 text-xs text-gray-500">({tabs.length} tabs)</span>
                <ChevronUp className="ml-auto text-gray-300" size={14} />
            </div>
        );
    }

    return (
        <div className={`flex flex-col h-full ${hideHeader ? 'bg-transparent' : 'bg-[#08080a] border-t border-gray-800'}`}>
            {/* Tab Bar */}
            {!hideHeader && (
                <div className="h-8 bg-[#0a0a0c] flex items-center px-2 border-b border-gray-800/60 overflow-x-auto shrink-0">
                    {tabs.map((tab) => (
                        <div
                            key={tab.id}
                            className={`flex items-center gap-1.5 px-2 py-1 mr-1 rounded text-xs cursor-pointer group ${activeTabId === tab.id
                                ? "bg-white/5 text-gray-200"
                                : "text-gray-500 hover:bg-white/5 hover:text-gray-200"
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
                            className="p-1 rounded hover:bg-white/5 text-gray-300"
                            title="New PowerShell"
                        >
                            <Plus size={14} />
                        </button>
                        <button
                            onClick={() => createTab("cmd")}
                            className="px-2 py-0.5 rounded hover:bg-white/5 text-gray-300 text-[10px]"
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
            )}

            {/* Terminal Container */}
            {tabs.length === 0 ? (
                <div className={`flex-1 min-h-0 flex items-center justify-center text-gray-500 ${hideHeader ? '' : ''}`}>
                    <div className="text-center">
                        <TerminalIcon size={32} className="mx-auto mb-2 opacity-40" />
                        <p className="text-sm">No terminals open</p>
                        <button
                            onClick={() => createTab("powershell")}
                            className="mt-2 px-3 py-1 bg-white/5 rounded text-gray-200 text-sm hover:bg-white/10"
                        >
                            New Terminal
                        </button>
                    </div>
                </div>
            ) : (
                <div ref={containerRef} className="flex-1 min-h-0 w-full" />
            )}
        </div>
    );
}
