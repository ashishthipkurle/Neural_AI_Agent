import React, { useState, useRef, useEffect, useCallback } from "react";
import {
    X, Send, Play, Save, Trash2, Plus, Activity, Clock,
    Mail, FileText, Calendar, Database, Globe, Bell,
    Zap, GitBranch, ArrowRight, CheckCircle, Circle,
    AlertCircle, Loader, ChevronDown, Sparkles, GripVertical,
    FolderOpen, Settings, Timer, List, RefreshCw, ChevronRight
} from "lucide-react";

/* ============ TYPES ============ */

interface NodeConfig {
    [key: string]: any;
}

interface WorkflowNode {
    id: string;
    type: "trigger" | "agent" | "action" | "condition";
    label: string;
    icon: string;
    tool_id: string;  // maps to executor in the backend
    x: number;
    y: number;
    color: string;
    status?: "idle" | "running" | "done" | "error";
    config?: NodeConfig;
}

interface WorkflowEdge {
    id: string;
    from: string;
    to: string;
}

interface LogEntry {
    timestamp: string;
    level: "info" | "success" | "error" | "warn";
    message: string;
}

interface ChatMessage {
    id: string;
    role: "user" | "agent";
    content: string;
}

interface SavedWorkflow {
    id: string;
    name: string;
    description: string;
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
    config: any;
    created_at: string;
    updated_at: string;
    schedule?: {
        cron_expression: string;
        is_active: boolean;
        last_run?: string;
        next_run?: string;
    } | null;
}

interface WorkflowRun {
    id: string;
    workflow_id: string;
    status: string;
    trigger_type: string;
    started_at: string;
    finished_at: string | null;
    node_results: Record<string, any>;
    logs: Array<{ node_id: string; label: string; status: string; output: string; elapsed_seconds?: number }>;
    error_message: string | null;
}

/* ============ BACKEND API ============ */

const API_BASE = "http://localhost:8000";

const workflowAPI = {
    async create(name: string, nodes: WorkflowNode[], edges: WorkflowEdge[], description = "", config = {}) {
        const res = await fetch(`${API_BASE}/api/workflow`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, nodes, edges, description, config }),
        });
        return res.json();
    },

    async list(): Promise<{ workflows: SavedWorkflow[] }> {
        const res = await fetch(`${API_BASE}/api/workflow`);
        return res.json();
    },

    async get(id: string): Promise<{ workflow: SavedWorkflow }> {
        const res = await fetch(`${API_BASE}/api/workflow/${id}`);
        return res.json();
    },

    async update(id: string, name: string, nodes: WorkflowNode[], edges: WorkflowEdge[], description = "", config = {}) {
        const res = await fetch(`${API_BASE}/api/workflow/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, nodes, edges, description, config }),
        });
        return res.json();
    },

    async delete(id: string) {
        const res = await fetch(`${API_BASE}/api/workflow/${id}`, { method: "DELETE" });
        return res.json();
    },

    async run(id: string, triggerData = {}) {
        const res = await fetch(`${API_BASE}/api/workflow/${id}/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ trigger_data: triggerData }),
        });
        return res.json();
    },

    async runInline(nodes: WorkflowNode[], edges: WorkflowEdge[], config = {}) {
        const res = await fetch(`${API_BASE}/api/workflow/run-inline`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nodes, edges, config }),
        });
        return res.json();
    },

    async getRuns(id: string): Promise<{ runs: WorkflowRun[] }> {
        const res = await fetch(`${API_BASE}/api/workflow/${id}/runs`);
        return res.json();
    },

    async setSchedule(id: string, cronExpression: string) {
        const res = await fetch(`${API_BASE}/api/workflow/${id}/schedule`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cron_expression: cronExpression }),
        });
        return res.json();
    },

    async removeSchedule(id: string) {
        const res = await fetch(`${API_BASE}/api/workflow/${id}/schedule`, { method: "DELETE" });
        return res.json();
    },
};

/* ============ TOOL CARDS DATA ============ */

const TOOL_CARDS = [
    { id: "trigger_cron", label: "Schedule", icon: "Clock", color: "amber", type: "trigger" as const, category: "Triggers" },
    { id: "trigger_event", label: "On Event", icon: "Zap", color: "amber", type: "trigger" as const, category: "Triggers" },
    { id: "email_read", label: "Read Emails", icon: "Mail", color: "blue", type: "action" as const, category: "Email" },
    { id: "email_send", label: "Send Email", icon: "Mail", color: "blue", type: "action" as const, category: "Email" },
    { id: "task_create", label: "Create Task", icon: "FileText", color: "green", type: "action" as const, category: "Tasks" },
    { id: "task_update", label: "Update Task", icon: "FileText", color: "green", type: "action" as const, category: "Tasks" },
    { id: "calendar_event", label: "Create Event", icon: "Calendar", color: "purple", type: "action" as const, category: "Calendar" },
    { id: "calendar_check", label: "Check Schedule", icon: "Calendar", color: "purple", type: "action" as const, category: "Calendar" },
    { id: "web_search", label: "Web Search", icon: "Globe", color: "cyan", type: "action" as const, category: "Web" },
    { id: "web_scrape", label: "Scrape Page", icon: "Globe", color: "cyan", type: "action" as const, category: "Web" },
    { id: "file_read", label: "Read File", icon: "Database", color: "orange", type: "action" as const, category: "Files" },
    { id: "file_write", label: "Write File", icon: "Database", color: "orange", type: "action" as const, category: "Files" },
    { id: "notify", label: "Send Alert", icon: "Bell", color: "red", type: "action" as const, category: "Notify" },
    { id: "condition", label: "If/Else", icon: "GitBranch", color: "yellow", type: "condition" as const, category: "Logic" },
    { id: "delay", label: "Wait/Delay", icon: "Clock", color: "slate", type: "action" as const, category: "Logic" },
    { id: "agent_general", label: "General Agent", icon: "Sparkles", color: "emerald", type: "agent" as const, category: "Agents" },
    { id: "agent_coder", label: "Coding Agent", icon: "FileText", color: "purple", type: "agent" as const, category: "Agents" },
    { id: "agent_trader", label: "Trading Agent", icon: "Zap", color: "cyan", type: "agent" as const, category: "Agents" },
];

const ICON_MAP: Record<string, React.ComponentType<any>> = {
    Mail, FileText, Calendar, Database, Globe, Bell, Clock, GitBranch, Zap, Sparkles
};

const COLOR_MAP: Record<string, { bg: string; border: string; text: string; glow: string }> = {
    amber: { bg: "bg-amber-500/10", border: "border-amber-500/40", text: "text-amber-400", glow: "shadow-amber-500/20" },
    blue: { bg: "bg-blue-500/10", border: "border-blue-500/40", text: "text-blue-400", glow: "shadow-blue-500/20" },
    green: { bg: "bg-emerald-500/10", border: "border-emerald-500/40", text: "text-emerald-400", glow: "shadow-emerald-500/20" },
    emerald: { bg: "bg-emerald-500/10", border: "border-emerald-500/40", text: "text-emerald-400", glow: "shadow-emerald-500/20" },
    red: { bg: "bg-red-500/10", border: "border-red-500/40", text: "text-red-400", glow: "shadow-red-500/20" },
    purple: { bg: "bg-purple-500/10", border: "border-purple-500/40", text: "text-purple-400", glow: "shadow-purple-500/20" },
    yellow: { bg: "bg-yellow-500/10", border: "border-yellow-500/40", text: "text-yellow-400", glow: "shadow-yellow-500/20" },
    cyan: { bg: "bg-cyan-500/10", border: "border-cyan-500/40", text: "text-cyan-400", glow: "shadow-cyan-500/20" },
    orange: { bg: "bg-orange-500/10", border: "border-orange-500/40", text: "text-orange-400", glow: "shadow-orange-500/20" },
    slate: { bg: "bg-slate-500/10", border: "border-slate-500/40", text: "text-slate-400", glow: "shadow-slate-500/20" },
};

/* ============ NODE CONFIG DEFINITIONS ============ */

const NODE_CONFIG_FIELDS: Record<string, Array<{ key: string; label: string; type: "text" | "number" | "select" | "textarea"; placeholder?: string; options?: string[] }>> = {
    trigger_cron: [
        { key: "cron_expression", label: "Cron Expression", type: "text", placeholder: "0 9 * * *  (daily at 9am)" },
    ],
    trigger_event: [
        { key: "event_type", label: "Event Type", type: "select", options: ["manual", "webhook", "file_change"] },
    ],
    email_read: [
        { key: "folder", label: "Folder", type: "text", placeholder: "INBOX" },
        { key: "max_emails", label: "Max Emails", type: "number", placeholder: "5" },
    ],
    email_send: [
        { key: "to", label: "To Email", type: "text", placeholder: "user@example.com" },
        { key: "subject", label: "Subject", type: "text", placeholder: "Workflow Notification" },
        { key: "body", label: "Body", type: "textarea", placeholder: "Use {{variable}} for dynamic content" },
    ],
    task_create: [
        { key: "title", label: "Task Title", type: "text", placeholder: "New task from workflow" },
        { key: "description", label: "Description", type: "textarea", placeholder: "Task description" },
        { key: "priority", label: "Priority", type: "select", options: ["low", "medium", "high", "critical"] },
    ],
    task_update: [
        { key: "task_id", label: "Task ID", type: "number", placeholder: "ID from previous step" },
        { key: "status", label: "New Status", type: "select", options: ["pending", "in_progress", "completed", "cancelled"] },
    ],
    calendar_event: [
        { key: "title", label: "Event Title", type: "text", placeholder: "Meeting" },
        { key: "date", label: "Date (YYYY-MM-DD)", type: "text", placeholder: "2025-01-15" },
        { key: "time", label: "Time (HH:MM)", type: "text", placeholder: "09:00" },
        { key: "duration_minutes", label: "Duration (min)", type: "number", placeholder: "60" },
    ],
    calendar_check: [],
    web_search: [
        { key: "query", label: "Search Query", type: "text", placeholder: "What to search for" },
    ],
    web_scrape: [
        { key: "url", label: "URL to Scrape", type: "text", placeholder: "https://example.com" },
    ],
    file_read: [
        { key: "path", label: "File Path", type: "text", placeholder: "C:\\path\\to\\file.txt" },
    ],
    file_write: [
        { key: "path", label: "File Path", type: "text", placeholder: "Leave empty for auto-generated" },
        { key: "content", label: "Content", type: "textarea", placeholder: "Content to write (or uses input from previous node)" },
    ],
    notify: [
        { key: "title", label: "Alert Title", type: "text", placeholder: "Workflow Alert" },
        { key: "message", label: "Message", type: "textarea", placeholder: "Notification message" },
        { key: "send_telegram", label: "Send Telegram", type: "select", options: ["true", "false"] },
    ],
    condition: [
        { key: "field", label: "Field to Check", type: "text", placeholder: "success" },
        { key: "operator", label: "Operator", type: "select", options: ["equals", "not_equals", "contains", "not_empty", "greater_than"] },
        { key: "value", label: "Expected Value", type: "text", placeholder: "true" },
    ],
    delay: [
        { key: "seconds", label: "Wait Seconds", type: "number", placeholder: "5" },
    ],
    agent_general: [
        { key: "prompt", label: "Prompt", type: "textarea", placeholder: "What should the AI agent do?" },
        { key: "system_instruction", label: "System Instruction", type: "textarea", placeholder: "Optional: set agent role/personality" },
    ],
    agent_coder: [
        { key: "prompt", label: "Coding Task", type: "textarea", placeholder: "Describe the coding task" },
    ],
    agent_trader: [
        { key: "symbol", label: "Stock Symbol", type: "text", placeholder: "AAPL" },
        { key: "action", label: "Action", type: "select", options: ["analyze", "buy_signal", "sell_signal", "portfolio_review"] },
    ],
};

/* ============ DRAGGABLE NODE ============ */

function DraggableNode({
    node,
    onDragStart,
    onConnectStart,
    isSelected,
    onSelect,
}: {
    node: WorkflowNode;
    onDragStart: (nodeId: string, e: React.MouseEvent) => void;
    onConnectStart: (nodeId: string, side: "out" | "in", e: React.MouseEvent) => void;
    isSelected: boolean;
    onSelect: (nodeId: string) => void;
}) {
    const c = COLOR_MAP[node.color] || COLOR_MAP.slate;
    const IconComp = ICON_MAP[node.icon] || Zap;

    const statusIcon = node.status === "done"
        ? <CheckCircle size={10} className="text-emerald-400" />
        : node.status === "running"
            ? <Loader size={10} className="text-yellow-400 animate-spin" />
            : node.status === "error"
                ? <AlertCircle size={10} className="text-red-400" />
                : null;

    const hasConfig = node.config && Object.keys(node.config).length > 0;

    return (
        <div
            className="absolute select-none group"
            style={{ left: node.x, top: node.y, zIndex: isSelected ? 50 : 10 }}
            onMouseDown={(e) => {
                e.stopPropagation();
                onSelect(node.id);
                onDragStart(node.id, e);
            }}
        >
            {/* Input connector (left) */}
            <div
                className={`absolute -left-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full ${c.border} border-2 bg-[#0a0a0a] cursor-crosshair z-20 opacity-0 group-hover:opacity-100 hover:scale-150 transition-all flex items-center justify-center`}
                onMouseDown={(e) => { e.stopPropagation(); onConnectStart(node.id, "in", e); }}
            >
                <div className={`w-1.5 h-1.5 rounded-full ${c.bg}`} />
            </div>

            {/* Output connector (right) */}
            <div
                className={`absolute -right-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full ${c.border} border-2 bg-[#0a0a0a] cursor-crosshair z-20 opacity-0 group-hover:opacity-100 hover:scale-150 transition-all flex items-center justify-center`}
                onMouseDown={(e) => { e.stopPropagation(); onConnectStart(node.id, "out", e); }}
            >
                <div className={`w-1.5 h-1.5 rounded-full ${c.bg}`} />
            </div>

            {/* Node card */}
            <div className={`relative px-3.5 py-2.5 rounded-xl ${c.bg} border-2 ${isSelected ? 'border-white/40 shadow-lg' : c.border} backdrop-blur-sm min-w-[120px] cursor-grab active:cursor-grabbing transition-shadow hover:shadow-lg ${c.glow}`}>
                {statusIcon && <div className="absolute -top-1.5 -right-1.5">{statusIcon}</div>}
                {hasConfig && <div className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-emerald-500/30 border border-emerald-500/50 flex items-center justify-center"><Settings size={6} className="text-emerald-400" /></div>}

                <div className={`text-[8px] uppercase tracking-wider ${c.text} opacity-50 mb-1`}>
                    {node.type}
                </div>

                <div className="flex items-center gap-2">
                    <div className={`w-7 h-7 rounded-lg ${c.bg} border ${c.border} flex items-center justify-center shrink-0`}>
                        <IconComp size={14} className={c.text} />
                    </div>
                    <div className={`text-[11px] font-medium ${c.text} whitespace-pre-line leading-tight`}>
                        {node.label}
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ============ CANVAS ============ */

function WorkflowCanvas({
    nodes, edges, selectedNode,
    onNodeDragStart, onConnectStart, onSelectNode,
    onCanvasClick, onDrop,
    connectingFrom, mousePos,
}: {
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
    selectedNode: string | null;
    onNodeDragStart: (nodeId: string, e: React.MouseEvent) => void;
    onConnectStart: (nodeId: string, side: "out" | "in", e: React.MouseEvent) => void;
    onSelectNode: (nodeId: string) => void;
    onCanvasClick: () => void;
    onDrop: (e: React.DragEvent) => void;
    connectingFrom: { nodeId: string; side: string } | null;
    mousePos: { x: number; y: number };
}) {
    const canvasRef = useRef<HTMLDivElement>(null);
    const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

    return (
        <div
            ref={canvasRef}
            className="relative w-full h-full overflow-auto"
            style={{
                background: "#080808",
                backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)",
                backgroundSize: "20px 20px"
            }}
            onClick={onCanvasClick}
            onDragOver={(e) => e.preventDefault()}
            onDrop={onDrop}
        >
            {/* SVG Edges */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ minWidth: "100%", minHeight: "100%" }}>
                <defs>
                    <marker id="wf-arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                        <polygon points="0 0, 8 3, 0 6" fill="rgba(255,255,255,0.25)" />
                    </marker>
                </defs>

                {edges.map((edge) => {
                    const from = nodeMap[edge.from];
                    const to = nodeMap[edge.to];
                    if (!from || !to) return null;

                    const x1 = from.x + 140;
                    const y1 = from.y + 28;
                    const x2 = to.x;
                    const y2 = to.y + 28;
                    const cx1 = x1 + Math.abs(x2 - x1) * 0.5;
                    const cx2 = x2 - Math.abs(x2 - x1) * 0.5;
                    const isActive = from.status === "done" || from.status === "running";

                    return (
                        <g key={edge.id}>
                            <path
                                d={`M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`}
                                fill="none"
                                stroke={isActive ? "rgba(250,204,21,0.5)" : "rgba(255,255,255,0.1)"}
                                strokeWidth={isActive ? 2 : 1.5}
                                strokeDasharray={isActive ? "none" : "6 4"}
                                markerEnd="url(#wf-arrow)"
                            />
                            {isActive && (
                                <circle r="3" fill="#facc15">
                                    <animateMotion
                                        dur="2s" repeatCount="indefinite"
                                        path={`M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`}
                                    />
                                </circle>
                            )}
                        </g>
                    );
                })}

                {/* Live connection line while dragging */}
                {connectingFrom && (() => {
                    const fromNode = nodeMap[connectingFrom.nodeId];
                    if (!fromNode) return null;
                    const x1 = connectingFrom.side === "out" ? fromNode.x + 140 : fromNode.x;
                    const y1 = fromNode.y + 28;
                    return (
                        <line
                            x1={x1} y1={y1} x2={mousePos.x} y2={mousePos.y}
                            stroke="rgba(250,204,21,0.6)" strokeWidth={2} strokeDasharray="4 4"
                        />
                    );
                })()}
            </svg>

            {/* Nodes */}
            {nodes.map(node => (
                <DraggableNode
                    key={node.id}
                    node={node}
                    onDragStart={onNodeDragStart}
                    onConnectStart={onConnectStart}
                    isSelected={selectedNode === node.id}
                    onSelect={onSelectNode}
                />
            ))}

            {/* Empty state */}
            {nodes.length === 0 && (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                    <div className="w-20 h-20 rounded-2xl bg-yellow-500/5 border border-yellow-500/20 flex items-center justify-center mb-4">
                        <Sparkles size={32} className="text-yellow-500/20" />
                    </div>
                    <p className="text-sm text-slate-500 mb-1">Empty Canvas</p>
                    <p className="text-xs text-slate-600">Drag tools from below or describe a workflow in the chat</p>
                </div>
            )}
        </div>
    );
}

/* ============ NODE CONFIG PANEL ============ */

function NodeConfigPanel({
    node, onUpdateConfig, onClose
}: {
    node: WorkflowNode;
    onUpdateConfig: (nodeId: string, config: NodeConfig) => void;
    onClose: () => void;
}) {
    const fields = NODE_CONFIG_FIELDS[node.tool_id] || [];
    const [localConfig, setLocalConfig] = useState<NodeConfig>(node.config || {});

    const updateField = (key: string, value: string) => {
        const newConfig = { ...localConfig, [key]: value };
        setLocalConfig(newConfig);
        onUpdateConfig(node.id, newConfig);
    };

    const c = COLOR_MAP[node.color] || COLOR_MAP.slate;

    return (
        <div className="absolute right-0 top-0 bottom-0 w-72 bg-[#0d0d0d] border-l border-white/10 z-50 flex flex-col overflow-hidden">
            {/* Header */}
            <div className={`px-4 py-3 border-b border-white/10 flex items-center gap-3 ${c.bg}`}>
                <div className={`w-8 h-8 rounded-lg ${c.bg} border ${c.border} flex items-center justify-center`}>
                    {React.createElement(ICON_MAP[node.icon] || Zap, { size: 14, className: c.text })}
                </div>
                <div className="flex-1 min-w-0">
                    <div className={`text-xs font-semibold ${c.text}`}>{node.label}</div>
                    <div className="text-[9px] text-slate-500 uppercase tracking-wider">{node.type} · {node.tool_id}</div>
                </div>
                <button onClick={onClose} className="p-1 rounded hover:bg-white/10 transition-colors">
                    <X size={14} className="text-slate-400" />
                </button>
            </div>

            {/* Config fields */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {fields.length === 0 ? (
                    <div className="text-xs text-slate-600 text-center py-4 italic">No configuration needed for this node</div>
                ) : (
                    fields.map(field => (
                        <div key={field.key}>
                            <label className="block text-[10px] text-slate-400 uppercase tracking-wider mb-1.5 font-medium">
                                {field.label}
                            </label>
                            {field.type === "textarea" ? (
                                <textarea
                                    value={localConfig[field.key] || ""}
                                    onChange={e => updateField(field.key, e.target.value)}
                                    placeholder={field.placeholder}
                                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-yellow-500/40 resize-none"
                                    rows={3}
                                />
                            ) : field.type === "select" ? (
                                <select
                                    value={localConfig[field.key] || field.options?.[0] || ""}
                                    onChange={e => updateField(field.key, e.target.value)}
                                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-yellow-500/40"
                                >
                                    {field.options?.map(opt => (
                                        <option key={opt} value={opt} className="bg-[#0d0d0d]">{opt}</option>
                                    ))}
                                </select>
                            ) : (
                                <input
                                    type={field.type}
                                    value={localConfig[field.key] || ""}
                                    onChange={e => updateField(field.key, e.target.value)}
                                    placeholder={field.placeholder}
                                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-yellow-500/40"
                                />
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

/* ============ SAVED WORKFLOWS PANEL ============ */

function SavedWorkflowsPanel({
    workflows, onLoad, onDelete, onClose, currentId
}: {
    workflows: SavedWorkflow[];
    onLoad: (wf: SavedWorkflow) => void;
    onDelete: (id: string) => void;
    onClose: () => void;
    currentId: string | null;
}) {
    return (
        <div className="absolute left-0 top-0 bottom-0 w-64 bg-[#0d0d0d] border-r border-white/10 z-50 flex flex-col">
            <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <FolderOpen size={14} className="text-yellow-400" />
                    <span className="text-xs font-semibold text-yellow-400">Saved Workflows</span>
                </div>
                <button onClick={onClose} className="p-1 rounded hover:bg-white/10"><X size={14} className="text-slate-400" /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {workflows.length === 0 ? (
                    <div className="text-xs text-slate-600 text-center py-8 italic">No saved workflows yet</div>
                ) : (
                    workflows.map(wf => (
                        <div
                            key={wf.id}
                            className={`p-3 rounded-lg border transition-all cursor-pointer ${currentId === wf.id ? 'bg-yellow-500/10 border-yellow-500/30' : 'bg-white/[0.02] border-white/5 hover:border-yellow-500/20 hover:bg-white/[0.04]'}`}
                            onClick={() => onLoad(wf)}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-[11px] font-medium text-slate-200 truncate">{wf.name}</span>
                                <button
                                    onClick={(e) => { e.stopPropagation(); onDelete(wf.id); }}
                                    className="p-0.5 rounded hover:bg-red-500/20 transition-colors opacity-0 group-hover:opacity-100"
                                >
                                    <Trash2 size={10} className="text-red-400" />
                                </button>
                            </div>
                            <div className="flex items-center gap-2 text-[9px] text-slate-500">
                                <span>{wf.nodes?.length || 0} nodes</span>
                                <span>·</span>
                                <span>{new Date(wf.updated_at).toLocaleDateString()}</span>
                                {wf.schedule && <span className="text-amber-400">⏰ scheduled</span>}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

/* ============ MAIN VIEW ============ */

interface WorkflowBuilderViewProps {
    onClose: () => void;
}

export default function WorkflowBuilderView({ onClose }: WorkflowBuilderViewProps) {
    const [nodes, setNodes] = useState<WorkflowNode[]>([]);
    const [edges, setEdges] = useState<WorkflowEdge[]>([]);
    const [selectedNode, setSelectedNode] = useState<string | null>(null);
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
    const [chatInput, setChatInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [activeCategory, setActiveCategory] = useState<string | null>(null);
    const chatRef = useRef<HTMLDivElement>(null);
    const canvasContainerRef = useRef<HTMLDivElement>(null);

    // Workflow state
    const [workflowId, setWorkflowId] = useState<string | null>(null);
    const [workflowName, setWorkflowName] = useState("Untitled Workflow");
    const [isRunning, setIsRunning] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    // Panels
    const [showSavedPanel, setShowSavedPanel] = useState(false);
    const [showConfigPanel, setShowConfigPanel] = useState(false);
    const [savedWorkflows, setSavedWorkflows] = useState<SavedWorkflow[]>([]);

    // Schedule modal
    const [showScheduleModal, setShowScheduleModal] = useState(false);
    const [cronInput, setCronInput] = useState("0 9 * * *");

    // Drag state
    const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
    const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

    // Connection state
    const [connectingFrom, setConnectingFrom] = useState<{ nodeId: string; side: string } | null>(null);
    const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

    const [logs, setLogs] = useState<LogEntry[]>([
        { timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }), level: "info", message: "Workflow Agent ready" },
        { timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }), level: "success", message: "Drag tools onto the canvas to build workflows" },
    ]);

    // ── WEBSOCKET LISTENER for real-time node status ──
    useEffect(() => {
        let ws: WebSocket | null = null;
        let reconnectTimer: NodeJS.Timeout;

        function connect() {
            try {
                ws = new WebSocket("ws://127.0.0.1:8000/api/ws");

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);

                        if (data.type === "workflow_node_status") {
                            setNodes(prev => prev.map(n =>
                                n.id === data.node_id ? { ...n, status: data.status as any } : n
                            ));
                            if (data.output) {
                                addLog(
                                    data.status === "error" ? "error" : data.status === "done" ? "success" : "info",
                                    `[${data.label || data.node_id}] ${data.output}`
                                );
                            }
                        }

                        if (data.type === "workflow_run_start") {
                            setIsRunning(true);
                            addLog("info", `▶ Workflow execution started (${data.node_count} nodes)`);
                        }

                        if (data.type === "workflow_run_complete") {
                            setIsRunning(false);
                            addLog(
                                data.status === "completed" ? "success" : "error",
                                `■ Workflow ${data.status} (${data.node_count} nodes)`
                            );
                        }
                    } catch { /* ignore parse errors from non-workflow events */ }
                };

                ws.onclose = () => {
                    reconnectTimer = setTimeout(connect, 5000);
                };

                ws.onerror = () => {
                    ws?.close();
                };
            } catch {
                reconnectTimer = setTimeout(connect, 5000);
            }
        }

        connect();

        return () => {
            ws?.close();
            clearTimeout(reconnectTimer);
        };
    }, []);

    // ── LOAD SAVED WORKFLOWS ──
    useEffect(() => {
        loadSavedWorkflows();
    }, []);

    const loadSavedWorkflows = async () => {
        try {
            const data = await workflowAPI.list();
            setSavedWorkflows(data.workflows || []);
        } catch {
            // Backend not running — OK
        }
    };

    useEffect(() => {
        if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }, [chatMessages]);

    const categories = [...new Set(TOOL_CARDS.map(t => t.category))];
    const filteredTools = activeCategory
        ? TOOL_CARDS.filter(t => t.category === activeCategory)
        : TOOL_CARDS;

    // ── NODE DRAGGING ──
    const handleNodeDragStart = useCallback((nodeId: string, e: React.MouseEvent) => {
        const node = nodes.find(n => n.id === nodeId);
        if (!node) return;
        setDraggingNodeId(nodeId);
        setDragOffset({ x: e.clientX - node.x, y: e.clientY - node.y });
    }, [nodes]);

    useEffect(() => {
        if (!draggingNodeId) return;

        const handleMouseMove = (e: MouseEvent) => {
            const containerRect = canvasContainerRef.current?.getBoundingClientRect();
            const offsetY = containerRect?.top || 0;

            setNodes(prev => prev.map(n =>
                n.id === draggingNodeId
                    ? { ...n, x: Math.max(0, e.clientX - dragOffset.x), y: Math.max(0, e.clientY - dragOffset.y - offsetY + (canvasContainerRef.current?.scrollTop || 0)) }
                    : n
            ));
        };

        const handleMouseUp = () => {
            setDraggingNodeId(null);
        };

        window.addEventListener("mousemove", handleMouseMove);
        window.addEventListener("mouseup", handleMouseUp);
        return () => {
            window.removeEventListener("mousemove", handleMouseMove);
            window.removeEventListener("mouseup", handleMouseUp);
        };
    }, [draggingNodeId, dragOffset]);

    // ── CONNECTION DRAGGING ──
    const handleConnectStart = useCallback((nodeId: string, side: "out" | "in", e: React.MouseEvent) => {
        setConnectingFrom({ nodeId, side });
        setMousePos({ x: e.clientX, y: e.clientY });
    }, []);

    useEffect(() => {
        if (!connectingFrom) return;

        const handleMouseMove = (e: MouseEvent) => {
            const containerRect = canvasContainerRef.current?.getBoundingClientRect();
            setMousePos({
                x: e.clientX - (containerRect?.left || 0),
                y: e.clientY - (containerRect?.top || 0)
            });
        };

        const handleMouseUp = (e: MouseEvent) => {
            const containerRect = canvasContainerRef.current?.getBoundingClientRect();
            const dropX = e.clientX - (containerRect?.left || 0);
            const dropY = e.clientY - (containerRect?.top || 0);

            const targetNode = nodes.find(n =>
                n.id !== connectingFrom.nodeId &&
                dropX >= n.x - 10 && dropX <= n.x + 160 &&
                dropY >= n.y - 10 && dropY <= n.y + 70
            );

            if (targetNode) {
                const fromId = connectingFrom.side === "out" ? connectingFrom.nodeId : targetNode.id;
                const toId = connectingFrom.side === "out" ? targetNode.id : connectingFrom.nodeId;

                const exists = edges.some(e => e.from === fromId && e.to === toId);
                if (!exists && fromId !== toId) {
                    setEdges(prev => [...prev, { id: `e-${Date.now()}`, from: fromId, to: toId }]);
                    addLog("success", `Connected nodes`);
                }
            }
            setConnectingFrom(null);
        };

        window.addEventListener("mousemove", handleMouseMove);
        window.addEventListener("mouseup", handleMouseUp);
        return () => {
            window.removeEventListener("mousemove", handleMouseMove);
            window.removeEventListener("mouseup", handleMouseUp);
        };
    }, [connectingFrom, nodes, edges]);

    // ── DROP FROM TOOL CARDS ──
    const handleCanvasDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        const toolId = e.dataTransfer.getData("tool-id");
        const tool = TOOL_CARDS.find(t => t.id === toolId);
        if (!tool) return;

        const containerRect = canvasContainerRef.current?.getBoundingClientRect();
        const x = e.clientX - (containerRect?.left || 0) - 60;
        const y = e.clientY - (containerRect?.top || 0) - 20;

        const newNode: WorkflowNode = {
            id: `node-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            type: tool.type,
            label: tool.label,
            icon: tool.icon,
            tool_id: tool.id,
            x: Math.max(10, x),
            y: Math.max(10, y),
            color: tool.color,
            status: "idle",
            config: {},
        };
        setNodes(prev => [...prev, newNode]);
        addLog("info", `Added "${tool.label}" node`);
    }, []);

    // ── DELETE SELECTED ──
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.key === "Delete" || e.key === "Backspace") && selectedNode) {
                // Don't delete if focus is in an input/textarea
                const active = document.activeElement;
                if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.tagName === "SELECT")) return;

                setNodes(prev => prev.filter(n => n.id !== selectedNode));
                setEdges(prev => prev.filter(ed => ed.from !== selectedNode && ed.to !== selectedNode));
                setSelectedNode(null);
                setShowConfigPanel(false);
                addLog("warn", "Node deleted");
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [selectedNode]);

    const addLog = (level: LogEntry["level"], message: string) => {
        setLogs(prev => [...prev, {
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
            level, message,
        }]);
    };

    // ── UPDATE NODE CONFIG ──
    const handleUpdateNodeConfig = (nodeId: string, config: NodeConfig) => {
        setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, config } : n));
    };

    // ── SAVE WORKFLOW ──
    const saveWorkflow = async () => {
        if (nodes.length === 0) return;
        setIsSaving(true);
        addLog("info", "Saving workflow...");

        try {
            if (workflowId) {
                await workflowAPI.update(workflowId, workflowName, nodes, edges);
                addLog("success", `Workflow updated: ${workflowName}`);
            } else {
                const data = await workflowAPI.create(workflowName, nodes, edges);
                setWorkflowId(data.workflow.id);
                addLog("success", `Workflow saved: ${workflowName} (id: ${data.workflow.id})`);
            }
            loadSavedWorkflows();
        } catch (e) {
            addLog("error", `Save failed: ${e}`);
        }
        setIsSaving(false);
    };

    // ── RUN WORKFLOW (REAL BACKEND EXECUTION) ──
    const runWorkflow = async () => {
        if (nodes.length === 0 || isRunning) return;

        // Reset all node statuses
        setNodes(prev => prev.map(n => ({ ...n, status: "idle" as const })));
        addLog("info", "Executing workflow...");

        try {
            if (workflowId) {
                // Save first, then run the saved version
                await workflowAPI.update(workflowId, workflowName, nodes, edges);
                await workflowAPI.run(workflowId);
            } else {
                // Run inline without saving
                await workflowAPI.runInline(nodes, edges);
            }
            // Status updates come via WebSocket
        } catch (e) {
            addLog("error", `Execution failed: ${e}. Is the Python backend running?`);
            setIsRunning(false);
        }
    };

    // ── LOAD WORKFLOW ──
    const loadWorkflow = (wf: SavedWorkflow) => {
        setNodes(wf.nodes || []);
        setEdges(wf.edges || []);
        setWorkflowId(wf.id);
        setWorkflowName(wf.name);
        setShowSavedPanel(false);
        addLog("info", `Loaded workflow: ${wf.name}`);
    };

    // ── DELETE WORKFLOW ──
    const deleteWorkflow = async (id: string) => {
        try {
            await workflowAPI.delete(id);
            if (workflowId === id) {
                setWorkflowId(null);
                setWorkflowName("Untitled Workflow");
            }
            loadSavedWorkflows();
            addLog("warn", "Workflow deleted");
        } catch (e) {
            addLog("error", `Delete failed: ${e}`);
        }
    };

    // ── SCHEDULE WORKFLOW ──
    const scheduleWorkflow = async () => {
        if (!workflowId) {
            addLog("error", "Save the workflow first before scheduling");
            return;
        }
        try {
            await workflowAPI.setSchedule(workflowId, cronInput);
            addLog("success", `Scheduled with cron: ${cronInput}`);
            setShowScheduleModal(false);
            loadSavedWorkflows();
        } catch (e) {
            addLog("error", `Schedule failed: ${e}`);
        }
    };

    // ── OPEN NODE CONFIG ──
    const handleSelectNode = (nodeId: string) => {
        setSelectedNode(nodeId);
        setShowConfigPanel(true);
    };

    // ── LOCAL WORKFLOW PARSER ──
    const KEYWORD_NODES: { keywords: string[]; tool: typeof TOOL_CARDS[0] }[] = [
        { keywords: ["schedule", "every", "morning", "daily", "cron", "hourly", "weekly", "timer", "repeat"], tool: TOOL_CARDS[0] },
        { keywords: ["event", "trigger", "when", "on"], tool: TOOL_CARDS[1] },
        { keywords: ["read email", "check email", "inbox", "check mail", "read mail", "get email"], tool: TOOL_CARDS[2] },
        { keywords: ["send email", "reply", "compose", "mail to", "email to", "forward"], tool: TOOL_CARDS[3] },
        { keywords: ["create task", "add task", "todo", "to-do", "task from", "make task"], tool: TOOL_CARDS[4] },
        { keywords: ["update task", "edit task", "modify task", "mark task", "complete task"], tool: TOOL_CARDS[5] },
        { keywords: ["create event", "add event", "schedule meeting", "calendar event", "book meeting"], tool: TOOL_CARDS[6] },
        { keywords: ["check schedule", "check calendar", "free time", "availability", "what's on"], tool: TOOL_CARDS[7] },
        { keywords: ["web search", "search for", "google", "look up", "find online", "search the web"], tool: TOOL_CARDS[8] },
        { keywords: ["scrape", "extract", "crawl", "parse page", "get data from"], tool: TOOL_CARDS[9] },
        { keywords: ["read file", "open file", "load file", "get file"], tool: TOOL_CARDS[10] },
        { keywords: ["write file", "save file", "create file", "export"], tool: TOOL_CARDS[11] },
        { keywords: ["notify", "alert", "notification", "send alert", "warn", "remind"], tool: TOOL_CARDS[12] },
        { keywords: ["if", "condition", "check if", "when", "decide"], tool: TOOL_CARDS[13] },
        { keywords: ["wait", "delay", "pause", "sleep"], tool: TOOL_CARDS[14] },
        { keywords: ["summarize", "analyze", "process", "think", "ai", "agent"], tool: TOOL_CARDS[15] },
    ];

    function parseWorkflowFromText(text: string): { newNodes: WorkflowNode[]; newEdges: WorkflowEdge[]; description: string } {
        const lower = text.toLowerCase();
        const matched: typeof TOOL_CARDS[0][] = [];

        const hasTrigger = ["every", "daily", "morning", "hourly", "weekly", "schedule", "cron", "at"].some(k => lower.includes(k));
        if (hasTrigger) matched.push(TOOL_CARDS[0]);

        for (const entry of KEYWORD_NODES) {
            if (entry.tool === TOOL_CARDS[0] && hasTrigger) continue;
            const found = entry.keywords.some(kw => lower.includes(kw));
            if (found && !matched.includes(entry.tool)) matched.push(entry.tool);
        }

        if (matched.length === 0) matched.push(TOOL_CARDS[15]);
        if (matched.length > 0 && !matched.some(m => m.type === "trigger")) matched.unshift(TOOL_CARDS[1]);
        if (!matched.some(m => m.id === "notify")) matched.push(TOOL_CARDS[12]);

        const startX = 60, startY = 60, spacingX = 220, spacingY = 100;
        const cols = Math.min(matched.length, 4);

        const newNodes: WorkflowNode[] = matched.map((tool, i) => ({
            id: `auto-${Date.now()}-${i}`,
            type: tool.type,
            label: tool.label,
            icon: tool.icon,
            tool_id: tool.id,
            x: startX + (i % cols) * spacingX,
            y: startY + Math.floor(i / cols) * spacingY,
            color: tool.color,
            status: "idle",
            config: {},
        }));

        const newEdges: WorkflowEdge[] = [];
        for (let i = 0; i < newNodes.length - 1; i++) {
            newEdges.push({ id: `auto-e-${Date.now()}-${i}`, from: newNodes[i].id, to: newNodes[i + 1].id });
        }

        return { newNodes, newEdges, description: matched.map(m => m.label).join(" → ") };
    }

    // ── CHAT ──
    const sendChat = async () => {
        if (!chatInput.trim() || isProcessing) return;
        const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", content: chatInput.trim() };
        setChatMessages(prev => [...prev, userMsg]);
        const inputText = chatInput.trim();
        setChatInput("");
        setIsProcessing(true);
        addLog("info", `Sending to AI: "${inputText.slice(0, 50)}"`);

        const systemPrompt = `You are a workflow builder AI. The user wants to automate a task. 
Analyze their request and respond with TWO parts:

PART 1: A JSON array of workflow steps. Each step is an object with:
- "label": short name for the step (2-4 words)
- "type": one of "trigger", "agent", "action", "condition"  
- "tool_id": one of "trigger_cron", "trigger_event", "email_read", "email_send", "task_create", "task_update", "calendar_event", "calendar_check", "web_search", "web_scrape", "file_read", "file_write", "notify", "condition", "delay", "agent_general", "agent_coder", "agent_trader"
- "icon": one of "Clock", "Mail", "FileText", "Calendar", "Globe", "Bell", "Zap", "GitBranch", "Database", "Sparkles"
- "color": one of "amber", "blue", "green", "red", "purple", "yellow", "cyan", "orange", "emerald"

PART 2: A brief explanation of the workflow.

Format your response EXACTLY like:
\`\`\`json
[{"label": "Every Morning", "type": "trigger", "tool_id": "trigger_cron", "icon": "Clock", "color": "amber"}, ...]
\`\`\`
Then your explanation text after the JSON block.`;

        try {
            const res = await fetch("http://localhost:8000/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: `${systemPrompt}\n\nUser request: ${inputText}` }),
                signal: AbortSignal.timeout(30000),
            });

            if (res.ok) {
                const data = await res.json();
                const responseText = data.response || "";

                const jsonMatch = responseText.match(/\[[\s\S]*?\]/);
                let createdNodes = false;

                if (jsonMatch) {
                    try {
                        const steps = JSON.parse(jsonMatch[0]);
                        if (Array.isArray(steps) && steps.length > 0) {
                            const startX = 60, startY = 60, spacingX = 220, spacingY = 100;
                            const cols = Math.min(steps.length, 4);

                            const newNodes: WorkflowNode[] = steps.map((step: any, i: number) => ({
                                id: `ai-${Date.now()}-${i}`,
                                type: step.type || "action",
                                label: step.label || `Step ${i + 1}`,
                                icon: step.icon || "Zap",
                                tool_id: step.tool_id || "agent_general",
                                x: startX + (i % cols) * spacingX,
                                y: startY + Math.floor(i / cols) * spacingY,
                                color: step.color || "slate",
                                status: "idle" as const,
                                config: step.config || {},
                            }));

                            const newEdges: WorkflowEdge[] = [];
                            for (let i = 0; i < newNodes.length - 1; i++) {
                                newEdges.push({ id: `ai-e-${Date.now()}-${i}`, from: newNodes[i].id, to: newNodes[i + 1].id });
                            }

                            setNodes(newNodes);
                            setEdges(newEdges);
                            addLog("success", `AI created ${newNodes.length} workflow nodes`);
                            createdNodes = true;
                        }
                    } catch {
                        addLog("warn", "Could not parse AI workflow JSON, using keyword fallback");
                    }
                }

                if (!createdNodes) {
                    const { newNodes, newEdges, description } = parseWorkflowFromText(inputText);
                    setNodes(newNodes);
                    setEdges(newEdges);
                    addLog("info", `Fallback: ${description}`);
                }

                const explanation = responseText.replace(/```json[\s\S]*?```/g, "").replace(/\[[\s\S]*?\]/g, "").trim();
                setChatMessages(prev => [...prev, {
                    id: `a-${Date.now()}`, role: "agent",
                    content: explanation || `Workflow created! Click nodes to configure them, then click Run to execute.`
                }]);
            } else {
                throw new Error("API error");
            }
        } catch {
            addLog("warn", "AI unavailable, using keyword parser");
            const { newNodes, newEdges, description } = parseWorkflowFromText(inputText);
            setNodes(newNodes);
            setEdges(newEdges);
            setChatMessages(prev => [...prev, {
                id: `a-${Date.now()}`, role: "agent",
                content: `Workflow created with ${newNodes.length} steps: ${description}\n\nClick each node to configure it, then click Run to execute.\n\n(Start the Python backend for AI-powered workflow generation)`
            }]);
        }

        setIsProcessing(false);
    };

    const selectedNodeObj = selectedNode ? nodes.find(n => n.id === selectedNode) : null;

    return (
        <div className="fixed inset-0 z-[100] bg-[#050505] flex flex-col">
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-2.5 border-b border-yellow-500/20 bg-gradient-to-r from-yellow-500/5 to-transparent shrink-0">
                <div className="w-8 h-8 rounded-xl bg-yellow-500/10 border border-yellow-500/30 flex items-center justify-center">
                    <Sparkles size={16} className="text-yellow-400" />
                </div>

                {/* Editable workflow name */}
                <input
                    value={workflowName}
                    onChange={(e) => setWorkflowName(e.target.value)}
                    className="text-sm font-semibold text-yellow-400 tracking-wide bg-transparent border-none outline-none focus:bg-white/5 px-2 py-0.5 rounded"
                    spellCheck={false}
                />

                <div className="flex-1" />

                <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-white/5 border border-white/10 text-[10px] text-slate-500 font-mono">
                    {nodes.length} nodes / {edges.length} edges
                    {workflowId && <span className="ml-1 text-emerald-400">· saved</span>}
                </div>

                {/* Browse saved */}
                <button onClick={() => { setShowSavedPanel(!showSavedPanel); loadSavedWorkflows(); }} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-400 text-xs font-medium hover:bg-white/10 transition-colors">
                    <FolderOpen size={12} /> Browse
                </button>

                {/* Run */}
                <button onClick={runWorkflow} disabled={nodes.length === 0 || isRunning} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 text-xs font-medium hover:bg-emerald-500/30 transition-colors disabled:opacity-30">
                    {isRunning ? <Loader size={12} className="animate-spin" /> : <Play size={12} />}
                    {isRunning ? "Running..." : "Run"}
                </button>

                {/* Save */}
                <button onClick={saveWorkflow} disabled={nodes.length === 0 || isSaving} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500/20 border border-blue-500/30 text-blue-400 text-xs font-medium hover:bg-blue-500/30 transition-colors disabled:opacity-30">
                    {isSaving ? <Loader size={12} className="animate-spin" /> : <Save size={12} />}
                    Save
                </button>

                {/* Schedule */}
                <button onClick={() => setShowScheduleModal(true)} disabled={!workflowId} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/30 text-amber-400 text-xs font-medium hover:bg-amber-500/30 transition-colors disabled:opacity-30" title="Schedule workflow (save first)">
                    <Timer size={12} /> Schedule
                </button>

                {/* Clear */}
                <button onClick={() => { setNodes([]); setEdges([]); setSelectedNode(null); setWorkflowId(null); setWorkflowName("Untitled Workflow"); setShowConfigPanel(false); addLog("warn", "Canvas cleared"); }} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-400 text-xs font-medium hover:bg-white/10 transition-colors">
                    <Trash2 size={12} /> Clear
                </button>

                <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                    <X size={18} className="text-slate-400 hover:text-white" />
                </button>
            </div>

            {/* Canvas + Config Panel */}
            <div ref={canvasContainerRef} className="flex-[55] relative border-b border-white/5 min-h-0 overflow-hidden">
                {/* Saved workflows panel */}
                {showSavedPanel && (
                    <SavedWorkflowsPanel
                        workflows={savedWorkflows}
                        onLoad={loadWorkflow}
                        onDelete={deleteWorkflow}
                        onClose={() => setShowSavedPanel(false)}
                        currentId={workflowId}
                    />
                )}

                <WorkflowCanvas
                    nodes={nodes} edges={edges} selectedNode={selectedNode}
                    onNodeDragStart={handleNodeDragStart}
                    onConnectStart={handleConnectStart}
                    onSelectNode={handleSelectNode}
                    onCanvasClick={() => { setSelectedNode(null); setShowConfigPanel(false); }}
                    onDrop={handleCanvasDrop}
                    connectingFrom={connectingFrom}
                    mousePos={mousePos}
                />

                {/* Node config panel */}
                {showConfigPanel && selectedNodeObj && (
                    <NodeConfigPanel
                        node={selectedNodeObj}
                        onUpdateConfig={handleUpdateNodeConfig}
                        onClose={() => { setShowConfigPanel(false); setSelectedNode(null); }}
                    />
                )}

                {/* Selection hint */}
                {selectedNode && !showConfigPanel && (
                    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-full bg-black/80 border border-white/10 text-[10px] text-slate-400 font-mono">
                        Press <kbd className="px-1 py-0.5 bg-white/10 rounded text-white">Delete</kbd> to remove · Click to configure
                    </div>
                )}
            </div>

            {/* Schedule Modal */}
            {showScheduleModal && (
                <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowScheduleModal(false)}>
                    <div className="bg-[#111] rounded-2xl border border-yellow-500/20 p-6 w-96 shadow-2xl shadow-yellow-500/10" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
                                <Timer size={20} className="text-amber-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-semibold text-amber-400">Schedule Workflow</h3>
                                <p className="text-[10px] text-slate-500">{workflowName}</p>
                            </div>
                        </div>

                        <label className="block text-[10px] text-slate-400 uppercase tracking-wider mb-2 font-medium">Cron Expression</label>
                        <input
                            value={cronInput}
                            onChange={(e) => setCronInput(e.target.value)}
                            className="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 font-mono focus:outline-none focus:border-amber-500/40 mb-3"
                            placeholder="0 9 * * *"
                        />

                        <div className="grid grid-cols-2 gap-2 mb-4">
                            {[
                                { label: "Every 5 min", cron: "*/5 * * * *" },
                                { label: "Hourly", cron: "0 * * * *" },
                                { label: "Daily 9 AM", cron: "0 9 * * *" },
                                { label: "Weekdays 9 AM", cron: "0 9 * * 1-5" },
                                { label: "Weekly Mon", cron: "0 9 * * 1" },
                                { label: "Monthly 1st", cron: "0 9 1 * *" },
                            ].map(preset => (
                                <button
                                    key={preset.cron}
                                    onClick={() => setCronInput(preset.cron)}
                                    className={`px-2 py-1.5 rounded-lg text-[10px] font-medium border transition-colors ${cronInput === preset.cron ? 'bg-amber-500/20 border-amber-500/30 text-amber-400' : 'bg-white/5 border-white/10 text-slate-400 hover:border-amber-500/20'}`}
                                >
                                    {preset.label}
                                </button>
                            ))}
                        </div>

                        <div className="flex gap-2">
                            <button onClick={() => setShowScheduleModal(false)} className="flex-1 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-400 text-xs font-medium hover:bg-white/10 transition-colors">Cancel</button>
                            <button onClick={scheduleWorkflow} className="flex-1 py-2 rounded-lg bg-amber-500/20 border border-amber-500/30 text-amber-400 text-xs font-medium hover:bg-amber-500/30 transition-colors">Set Schedule</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Tool Cards */}
            <div className="border-b border-white/5 bg-white/[0.01] shrink-0">
                <div className="flex items-center gap-1 px-4 pt-2">
                    <button onClick={() => setActiveCategory(null)} className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${!activeCategory ? 'bg-yellow-500/20 text-yellow-400' : 'text-slate-500 hover:text-slate-300'}`}>All</button>
                    {categories.map(cat => (
                        <button key={cat} onClick={() => setActiveCategory(activeCategory === cat ? null : cat)} className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${activeCategory === cat ? 'bg-yellow-500/20 text-yellow-400' : 'text-slate-500 hover:text-slate-300'}`}>
                            {cat}
                        </button>
                    ))}
                </div>
                <div className="flex gap-2 px-4 py-2.5 overflow-x-auto">
                    {filteredTools.map(tool => {
                        const ToolIcon = ICON_MAP[tool.icon] || Zap;
                        return (
                            <div
                                key={tool.id}
                                draggable
                                onDragStart={(e) => {
                                    e.dataTransfer.setData("tool-id", tool.id);
                                    e.dataTransfer.effectAllowed = "copy";
                                }}
                                className="flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5 hover:border-yellow-500/30 hover:bg-white/[0.06] transition-all cursor-grab active:cursor-grabbing group"
                            >
                                <GripVertical size={10} className="text-slate-700 group-hover:text-slate-500" />
                                <ToolIcon size={14} className={`${COLOR_MAP[tool.color]?.text || 'text-slate-400'} opacity-70 group-hover:opacity-100`} />
                                <span className="text-[11px] text-slate-400 group-hover:text-slate-200 whitespace-nowrap">{tool.label}</span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Bottom: Chat + Logs */}
            <div className="flex-[35] flex min-h-0">
                {/* Chat */}
                <div className="flex-1 flex flex-col border-r border-white/5">
                    <div className="px-4 py-2 text-[10px] font-semibold text-yellow-400/60 tracking-wider uppercase border-b border-white/5 shrink-0">
                        Chat with Workflow Agent
                    </div>
                    <div ref={chatRef} className="flex-1 overflow-y-auto p-3 space-y-2">
                        {chatMessages.length === 0 && (
                            <div className="text-xs text-slate-600 italic p-2">
                                Try: "Create a workflow that checks email every morning and creates tasks"
                            </div>
                        )}
                        {chatMessages.map(m => (
                            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs ${m.role === 'user' ? 'bg-yellow-500/10 text-yellow-200 border border-yellow-500/20' : 'bg-white/5 text-slate-300 border border-white/5'}`}>
                                    {m.content}
                                </div>
                            </div>
                        ))}
                        {isProcessing && (
                            <div className="flex gap-1 px-3 py-2">
                                <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                            </div>
                        )}
                    </div>
                    <form onSubmit={e => { e.preventDefault(); sendChat(); }} className="p-3 border-t border-white/5 shrink-0">
                        <div className="flex rounded-lg overflow-hidden border border-yellow-500/20 hover:border-yellow-500/40 transition-colors">
                            <input value={chatInput} onChange={e => setChatInput(e.target.value)} disabled={isProcessing} placeholder="Describe your workflow..." className="flex-1 px-3 py-2 bg-transparent text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none" />
                            <button type="submit" disabled={isProcessing || !chatInput.trim()} className="px-3 bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 transition-colors disabled:opacity-30">
                                <Send size={14} />
                            </button>
                        </div>
                    </form>
                </div>

                {/* Logs */}
                <div className="flex-1 flex flex-col">
                    <div className="px-4 py-2 text-[10px] font-semibold text-slate-500 tracking-wider uppercase border-b border-white/5 flex items-center gap-2 shrink-0">
                        <Activity size={10} /> Execution Logs
                    </div>
                    <div className="flex-1 overflow-y-auto p-3 space-y-1 font-mono text-[11px]">
                        {logs.map((log, i) => (
                            <div key={i} className="flex items-start gap-2">
                                <span className="text-slate-600 shrink-0">{log.timestamp}</span>
                                <span className={log.level === "success" ? "text-emerald-400" : log.level === "error" ? "text-red-400" : log.level === "warn" ? "text-yellow-400" : "text-slate-500"}>
                                    {log.level === "success" ? "[OK]" : log.level === "error" ? "[ERR]" : log.level === "warn" ? "[!]" : "[LOG]"}
                                </span>
                                <span className="text-slate-300">{log.message}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
