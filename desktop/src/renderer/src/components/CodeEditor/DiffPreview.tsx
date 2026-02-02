
import React from 'react';
import { X, Check } from 'lucide-react';

interface DiffPreviewProps {
    open: boolean;
    diff: string;
    proposalId: string;
    onClose: () => void;
    onApply: (proposalId: string) => void;
}

export const DiffPreview: React.FC<DiffPreviewProps> = ({ open, diff, proposalId, onClose, onApply }) => {
    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[100000] flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-[#1e1e1e] border border-[#333] rounded-lg shadow-2xl w-4/5 max-h-[85vh] flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-[#333]">
                    <h3 className="text-white font-medium text-sm">Review Refactor Proposal</h3>
                    <button onClick={onClose} className="p-1 hover:bg-white/10 rounded text-white/60 hover:text-white">
                        <X size={16} />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto p-4 bg-[#111]">
                    <pre className="font-mono text-sm text-gray-300 whitespace-pre-wrap">
                        {diff}
                    </pre>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 px-4 py-3 border-t border-[#333] bg-[#252526]">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded text-sm font-medium text-red-400 hover:bg-red-500/10 border border-transparent transition-colors"
                    >
                        Reject
                    </button>
                    <button
                        onClick={() => onApply(proposalId)}
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
