"use client";

import React, { useEffect, useRef } from "react";
import { Terminal as XTerm } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import { ChevronUp, ChevronDown, Terminal as TerminalIcon } from "lucide-react";
import "xterm/css/xterm.css";

interface TerminalPanelProps {
    isOpen: boolean;
    onToggle: () => void;
}

export default function TerminalPanel({ isOpen, onToggle }: TerminalPanelProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const termRef = useRef<XTerm | null>(null);
    const fitRef = useRef<FitAddon | null>(null);
    const socketRef = useRef<WebSocket | null>(null);

    /* --------------------------- INIT TERMINAL --------------------------- */
    useEffect(() => {
        if (!isOpen || !containerRef.current) return;
        if (termRef.current) return;

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

        termRef.current = term;
        fitRef.current = fit;

        /* ------------------------ WEBSOCKET CONNECT ------------------------ */
        const socket = new WebSocket("ws://localhost:8765");
        socketRef.current = socket;

        socket.onopen = () => {
            term.write("\x1b[32m[Connected to terminal]\x1b[0m\r\n");
            // Send initial resize
            const dims = fit.proposeDimensions();
            if (dims) {
                socket.send(`RESIZE:${dims.cols}:${dims.rows}`);
            }
        };

        socket.onmessage = (event) => {
            term.write(event.data);
        };

        socket.onclose = () => {
            term.write("\r\n\x1b[31m[Terminal disconnected]\x1b[0m");
        };

        socket.onerror = (err) => {
            term.write("\r\n\x1b[31m[Connection error - is the app running?]\x1b[0m");
        };

        /* --------------------------- INPUT PIPE ---------------------------- */
        term.onData((data) => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.send(data);
            }
        });

        /* --------------------------- RESIZE HANDLER ------------------------ */
        const handleResize = () => {
            fit.fit();
            const dims = fit.proposeDimensions();
            if (dims && socket.readyState === WebSocket.OPEN) {
                socket.send(`RESIZE:${dims.cols}:${dims.rows}`);
            }
        };
        window.addEventListener("resize", handleResize);

        return () => {
            window.removeEventListener("resize", handleResize);
            socket.close();
            term.dispose();
            termRef.current = null;
            socketRef.current = null;
        };
    }, [isOpen]);

    /* ------------------------------- UI -------------------------------- */
    if (!isOpen) {
        return (
            <div
                onClick={onToggle}
                className="h-8 bg-[#0a0f1a] border-t border-cyan-500/20 flex items-center px-3 cursor-pointer hover:bg-[#0c1624] transition-colors"
            >
                <TerminalIcon size={14} className="text-cyan-500 mr-2" />
                <span className="text-xs text-cyan-500 font-medium">Terminal</span>
                <ChevronUp className="ml-auto text-cyan-500" size={14} />
            </div>
        );
    }

    return (
        <div className="flex flex-col bg-[#0a0f1a] border-t border-cyan-500/20">
            <div className="h-8 bg-[#0c1624] flex items-center px-3 border-b border-cyan-500/10">
                <TerminalIcon size={12} className="text-cyan-400 mr-2" />
                <span className="text-xs text-cyan-400 font-medium">PowerShell</span>
                <button
                    onClick={onToggle}
                    className="ml-auto text-white/60 hover:text-white transition-colors"
                >
                    <ChevronDown size={14} />
                </button>
            </div>
            <div ref={containerRef} className="h-64 w-full" />
        </div>
    );
}
