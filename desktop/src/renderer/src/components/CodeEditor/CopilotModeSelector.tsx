
import React from 'react';
import { Sparkles, HelpCircle, Hammer } from 'lucide-react';

export type CopilotMode = 'suggest' | 'explain' | 'refactor';

interface CopilotModeSelectorProps {
    mode: CopilotMode;
    onChange: (mode: CopilotMode) => void;
}

export const CopilotModeSelector: React.FC<CopilotModeSelectorProps> = ({ mode, onChange }) => {
    return (
        <div className="flex items-center bg-[#0a0f1a] rounded-lg p-0.5 border border-[#333]">
            <button
                onClick={() => onChange('suggest')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs transition-colors ${mode === 'suggest'
                        ? 'bg-[#1e3320] text-green-400 font-medium'
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                    }`}
                title="Inline Suggestions (Auto-complete)"
            >
                <Sparkles size={12} />
                Suggest
            </button>

            <div className="w-px h-3 bg-[#333] mx-0.5" />

            <button
                onClick={() => onChange('explain')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs transition-colors ${mode === 'explain'
                        ? 'bg-[#1a2e3b] text-cyan-400 font-medium'
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                    }`}
                title="Explain Code (Read Only)"
            >
                <HelpCircle size={12} />
                Explain
            </button>

            <div className="w-px h-3 bg-[#333] mx-0.5" />

            <button
                onClick={() => onChange('refactor')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs transition-colors ${mode === 'refactor'
                        ? 'bg-[#3b1a1a] text-red-400 font-medium'
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                    }`}
                title="Refactor Code (Diff Review)"
            >
                <Hammer size={12} />
                Refactor
            </button>
        </div>
    );
};
