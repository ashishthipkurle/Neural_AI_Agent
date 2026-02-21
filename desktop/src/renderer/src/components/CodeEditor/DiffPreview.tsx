
import React, { useMemo, useState } from 'react';
import { X, Check } from 'lucide-react';

interface DiffPreviewProps {
    open: boolean;
    patches: Array<{ filePath: string; diff: string; proposalId?: string; isNewFile?: boolean }>;
    onClose: () => void;
    onReject: () => void;
    onApply: (proposalIds: string[]) => void;
    onApplyOne: (filePath: string) => void;
}

export const DiffPreview: React.FC<DiffPreviewProps> = ({ open, patches, onClose, onReject, onApply, onApplyOne }) => {
    if (!open) return null;

    const [activeIndex, setActiveIndex] = useState(0);

    const safePatches = patches ?? [];
    const active = safePatches[Math.min(activeIndex, Math.max(0, safePatches.length - 1))];

    const proposalIds = useMemo(() => {
        return safePatches.map(p => p.proposalId).filter((x): x is string => !!x && x.trim().length > 0);
    }, [safePatches]);

    const hasNonProposed = safePatches.some(p => !p.proposalId);
    const canApplyCurrent = !!active && (!!active.proposalId || !!active.isNewFile);

    return (
        <div className="fixed inset-0 z-[100000] flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-[#1e1e1e] border border-[#333] rounded-lg shadow-2xl w-4/5 max-h-[85vh] flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-[#333]">
                    <div className="min-w-0">
                        <h3 className="text-white font-medium text-sm">Review Patch Set</h3>
                        <div className="text-[11px] text-white/50 truncate">
                            {safePatches.length} file(s)
                            {active?.filePath ? ` • ${active.filePath}` : ''}
                        </div>
                    </div>
                    <button onClick={onClose} className="p-1 hover:bg-white/10 rounded text-white/60 hover:text-white">
                        <X size={16} />
                    </button>
                </div>

                {/* Tabs */}
                {safePatches.length > 1 ? (
                    <div className="flex items-center gap-1 px-3 py-2 border-b border-[#333] bg-[#171717] overflow-x-auto">
                        {safePatches.map((p, idx) => {
                            const name = p.filePath.split(/[\\/]/).pop() || p.filePath;
                            const isActive = idx === activeIndex;
                            return (
                                <button
                                    key={p.filePath}
                                    onClick={() => setActiveIndex(idx)}
                                    className={`px-3 py-1.5 rounded text-[11px] font-mono border transition-colors whitespace-nowrap ${
                                        isActive
                                            ? 'bg-white/10 border-white/20 text-white'
                                            : 'bg-transparent border-transparent text-white/50 hover:text-white hover:bg-white/5'
                                    }`}
                                    title={p.filePath}
                                >
                                    {name}
                                </button>
                            );
                        })}
                    </div>
                ) : null}

                {/* Content */}
                <div className="flex-1 overflow-auto p-4 bg-[#111]">
                    {hasNonProposed ? (
                        <div className="mb-3 text-[11px] text-yellow-300/80 border border-yellow-500/20 bg-yellow-500/10 rounded px-3 py-2">
                            Some items are buffer-only (no backend proposal ID). They won’t be written to disk by “Accept & Apply”.
                        </div>
                    ) : null}
                    <pre className="font-mono text-sm text-gray-300 whitespace-pre-wrap">
                        {active?.diff || '(no diff)'}
                    </pre>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 px-4 py-3 border-t border-[#333] bg-[#252526]">
                    <button
                        onClick={onReject}
                        className="px-4 py-2 rounded text-sm font-medium text-red-400 hover:bg-red-500/10 border border-transparent transition-colors"
                    >
                        Reject All
                    </button>
                    <button
                        onClick={() => active?.filePath && onApplyOne(active.filePath)}
                        disabled={!canApplyCurrent}
                        className="px-4 py-2 rounded text-sm font-medium bg-white/10 hover:bg-white/15 text-white flex items-center gap-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        title={canApplyCurrent ? 'Apply only the currently selected file' : 'Current file has no apply action'}
                    >
                        Apply Current
                    </button>
                    <button
                        onClick={() => onApply(proposalIds)}
                        disabled={proposalIds.length === 0}
                        className="px-4 py-2 rounded text-sm font-medium bg-green-600 hover:bg-green-500 text-white flex items-center gap-2 transition-colors"
                    >
                        <Check size={16} />
                        Accept & Apply
                    </button>
                </div>
            </div>
        </div>
    );
};
