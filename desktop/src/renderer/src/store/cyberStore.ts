import { create } from 'zustand';

interface Message {
    id: string;
    role: 'user' | 'phantom' | 'system';
    content: string;
}

interface CyberState {
    messages: Message[];
    psOutput: string[];
    bashOutput: string[];
    cmdHistory: string[];
    sidebarW: number;
    terminalW: number;
    termSplitPct: number;
    expandedCat: string | null;
    
    // Actions
    setMessages: (messages: Message[] | ((prev: Message[]) => Message[])) => void;
    addMessage: (msg: Message) => void;
    setPsOutput: (output: string[] | ((prev: string[]) => string[])) => void;
    setBashOutput: (output: string[] | ((prev: string[]) => string[])) => void;
    setCmdHistory: (history: string[] | ((prev: string[]) => string[])) => void;
    setSidebarW: (w: number | ((prev: number) => number)) => void;
    setTerminalW: (w: number | ((prev: number) => number)) => void;
    setTermSplitPct: (pct: number | ((prev: number) => number)) => void;
    setExpandedCat: (cat: string | null) => void;
    clearMessages: () => void;
}

export const useCyberStore = create<CyberState>((set) => ({
    messages: [
        {
            id: 'boot',
            role: 'phantom',
            content: '**PHANTOM v5.0 Online.** All exploit modules loaded.\n\nAsk me anything — port scans, WiFi cracking, SQL injection, privilege escalation, reverse shells, OSINT, malware analysis. Use the **Quick Ops** panel on the left or type below.\n\n> I execute without hesitation. What\'s the target, operator?'
        }
    ],
    psOutput: ['Windows PowerShell', 'Copyright (C) Microsoft Corporation.', ''],
    bashOutput: ['GNU bash, version 5.2.26', ''],
    cmdHistory: [],
    sidebarW: 240,
    terminalW: 380,
    termSplitPct: 50,
    expandedCat: 'WEBSITE HACKING',

    setMessages: (update) => set((state) => ({
        messages: typeof update === 'function' ? update(state.messages) : update
    })),
    addMessage: (msg) => set((state) => ({
        messages: [...state.messages, msg]
    })),
    setPsOutput: (update) => set((state) => ({
        psOutput: typeof update === 'function' ? update(state.psOutput) : update
    })),
    setBashOutput: (update) => set((state) => ({
        bashOutput: typeof update === 'function' ? update(state.bashOutput) : update
    })),
    setCmdHistory: (update) => set((state) => ({
        cmdHistory: typeof update === 'function' ? update(state.cmdHistory) : update
    })),
    setSidebarW: (update) => set((state) => ({
        sidebarW: typeof update === 'function' ? update(state.sidebarW) : update
    })),
    setTerminalW: (update) => set((state) => ({
        terminalW: typeof update === 'function' ? update(state.terminalW) : update
    })),
    setTermSplitPct: (update) => set((state) => ({
        termSplitPct: typeof update === 'function' ? update(state.termSplitPct) : update
    })),
    setExpandedCat: (cat) => set({ expandedCat: cat }),
    clearMessages: () => set({ 
        messages: [{
            id: 'boot',
            role: 'phantom',
            content: '**PHANTOM v5.0 Online.** All exploit modules loaded.\n\nAsk me anything — port scans, WiFi cracking, SQL injection, privilege escalation, reverse shells, OSINT, malware analysis. Use the **Quick Ops** panel on the left or type below.\n\n> I execute without hesitation. What\'s the target, operator?'
        }]
    }),
}));
