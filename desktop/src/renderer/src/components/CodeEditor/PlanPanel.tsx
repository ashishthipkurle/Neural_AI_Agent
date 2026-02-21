import React, { useState } from 'react';
import type { ImplementationPlan } from './editor-core/types';

/* ── Inline Button shown in chat when a plan is ready ── */
export function PlanReadyButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="group relative w-full flex items-center gap-3 px-4 py-3 rounded-xl
                 bg-gradient-to-r from-indigo-600/20 via-violet-600/15 to-cyan-500/15
                 border border-indigo-500/30 hover:border-indigo-400/50
                 shadow-[0_0_20px_rgba(99,102,241,0.08)] hover:shadow-[0_0_30px_rgba(99,102,241,0.15)]
                 transition-all duration-300 text-left"
    >
      {/* Animated glow dot */}
      <div className="relative shrink-0">
        <span className="absolute inset-0 rounded-full bg-indigo-400 animate-ping opacity-40" style={{ width: 10, height: 10 }} />
        <span className="relative block w-2.5 h-2.5 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.6)]" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[12px] font-semibold text-indigo-300 group-hover:text-indigo-200 transition-colors">
          Implementation Plan Ready
        </div>
        <div className="text-[10px] text-gray-500 group-hover:text-gray-400 transition-colors mt-0.5">
          Click to review and approve the plan
        </div>
      </div>
      <span className="material-symbols-outlined text-[18px] text-indigo-400/60 group-hover:text-indigo-300 transition-colors group-hover:translate-x-0.5 transform duration-200">
        arrow_forward
      </span>
    </button>
  );
}

/* ── Full-screen modal showing plan details ── */
export function PlanPanel(props: {
  plan: ImplementationPlan;
  onApprove: () => void;
  onReject: () => void;
  onClose: () => void;
  stageLabel?: string;
  isGenerating?: boolean;
}) {
  const { plan, onApprove, onReject, onClose, stageLabel, isGenerating } = props;
  const [hoveredSection, setHoveredSection] = useState<string | null>(null);

  const riskColor = plan.risk_level === 'high' ? 'text-red-400 bg-red-500/10 border-red-500/30'
    : plan.risk_level === 'medium' ? 'text-amber-400 bg-amber-500/10 border-amber-500/30'
    : 'text-green-400 bg-green-500/10 border-green-500/30';

  return (
    <div className="absolute inset-0 z-20 flex flex-col bg-[#0a0a0e] overflow-hidden animate-in fade-in">
      <div className="flex-1 flex flex-col min-h-0">
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800/60 bg-gradient-to-r from-[#0e0e12] to-[#111118] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/15 flex items-center justify-center border border-indigo-500/25">
              <span className="material-symbols-outlined text-indigo-400 text-[18px]">architecture</span>
            </div>
            <div>
              <h2 className="text-[14px] font-semibold text-gray-100">Implementation Plan</h2>
              {stageLabel && <div className="text-[10px] text-indigo-400/70 mt-0.5">{stageLabel}</div>}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors" title="Back to editor">
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        {/* ── Body ── */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 custom-scrollbar">
          {/* Objective */}
          <div className="rounded-xl border border-gray-800/50 bg-[#121218] p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="material-symbols-outlined text-[14px] text-indigo-400">target</span>
              <span className="text-[10px] uppercase tracking-wider text-indigo-400/80 font-semibold">Objective</span>
            </div>
            <p className="text-[13px] text-gray-200 leading-relaxed">{plan.objective}</p>
          </div>

          {/* Risk + Dependencies row */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-gray-800/50 bg-[#121218] p-4">
              <div className="text-[10px] uppercase tracking-wider text-gray-500 font-medium mb-2">Risk Level</div>
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${riskColor}`}>
                <span className="w-1.5 h-1.5 rounded-full bg-current" />
                {plan.risk_level || 'low'}
              </span>
            </div>
            <div className="rounded-xl border border-gray-800/50 bg-[#121218] p-4">
              <div className="text-[10px] uppercase tracking-wider text-gray-500 font-medium mb-2">Dependencies</div>
              <div className="text-[12px] text-gray-300">
                {(plan.dependencies_affected ?? []).length > 0
                  ? plan.dependencies_affected!.map((d, i) => (
                      <span key={i} className="inline-block mr-1.5 mb-1 px-2 py-0.5 rounded bg-gray-800/60 border border-gray-700/50 text-gray-400 text-[11px]">{d}</span>
                    ))
                  : <span className="text-gray-600 italic">None</span>}
              </div>
            </div>
          </div>

          {/* Files */}
          <div className="grid grid-cols-2 gap-3">
            <div
              className={`rounded-xl border bg-[#121218] p-4 transition-colors ${hoveredSection === 'modify' ? 'border-amber-500/30' : 'border-gray-800/50'}`}
              onMouseEnter={() => setHoveredSection('modify')}
              onMouseLeave={() => setHoveredSection(null)}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="material-symbols-outlined text-[14px] text-amber-400">edit_document</span>
                <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">Files to Modify</span>
                <span className="ml-auto text-[10px] text-gray-600 bg-gray-800/60 px-1.5 py-0.5 rounded-full">{(plan.files_to_modify ?? []).length}</span>
              </div>
              <div className="space-y-1 max-h-32 overflow-y-auto custom-scrollbar">
                {(plan.files_to_modify ?? []).length > 0
                  ? plan.files_to_modify!.map((f, i) => (
                      <div key={i} className="flex items-center gap-2 text-[11px] text-gray-300 py-0.5">
                        <span className="material-symbols-outlined text-[12px] text-gray-600">description</span>
                        <span className="truncate">{f}</span>
                      </div>
                    ))
                  : <span className="text-[11px] text-gray-600 italic">None</span>}
              </div>
            </div>

            <div
              className={`rounded-xl border bg-[#121218] p-4 transition-colors ${hoveredSection === 'new' ? 'border-green-500/30' : 'border-gray-800/50'}`}
              onMouseEnter={() => setHoveredSection('new')}
              onMouseLeave={() => setHoveredSection(null)}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="material-symbols-outlined text-[14px] text-green-400">note_add</span>
                <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">New Files</span>
                <span className="ml-auto text-[10px] text-gray-600 bg-gray-800/60 px-1.5 py-0.5 rounded-full">{(plan.new_files ?? []).length}</span>
              </div>
              <div className="space-y-1 max-h-32 overflow-y-auto custom-scrollbar">
                {(plan.new_files ?? []).length > 0
                  ? plan.new_files!.map((f, i) => (
                      <div key={i} className="flex items-center gap-2 text-[11px] text-emerald-300 py-0.5">
                        <span className="material-symbols-outlined text-[12px] text-green-600">add_circle</span>
                        <span className="truncate">{f}</span>
                      </div>
                    ))
                  : <span className="text-[11px] text-gray-600 italic">None</span>}
              </div>
            </div>
          </div>

          {/* Test Plan */}
          <div className="rounded-xl border border-gray-800/50 bg-[#121218] p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="material-symbols-outlined text-[14px] text-cyan-400">science</span>
              <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">Test Plan</span>
            </div>
            <p className="text-[12px] text-gray-300 leading-relaxed whitespace-pre-wrap">{plan.test_plan || 'Not specified'}</p>
          </div>

          {/* Rollback */}
          <div className="rounded-xl border border-gray-800/50 bg-[#121218] p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="material-symbols-outlined text-[14px] text-orange-400">undo</span>
              <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">Rollback Strategy</span>
            </div>
            <p className="text-[12px] text-gray-300 leading-relaxed whitespace-pre-wrap">{plan.rollback_strategy || 'Not specified'}</p>
          </div>
        </div>

        {/* ── Footer Actions ── */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-800/60 bg-[#0a0a0e] shrink-0">
          <button
            onClick={() => { onReject(); onClose(); }}
            disabled={isGenerating}
            className="px-4 py-2 rounded-lg text-[12px] font-medium text-red-400 hover:text-red-300
                       bg-red-500/5 hover:bg-red-500/15 border border-red-500/20 hover:border-red-500/40
                       transition-all duration-200 flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span className="material-symbols-outlined text-[16px]">close</span>
            Reject Plan
          </button>
          <button
            onClick={onApprove}
            disabled={isGenerating}
            className="px-5 py-2 rounded-lg text-[12px] font-semibold text-white
                       bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500
                       shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30
                       transition-all duration-200 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isGenerating ? (
              <>
                <span className="material-symbols-outlined text-[16px] animate-spin">sync</span>
                Generating Patch...
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[16px]">check_circle</span>
                Approve &amp; Generate Patch
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}