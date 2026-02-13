import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, Clock, Play, Pause, XCircle, AlertCircle, Plus, Terminal } from 'lucide-react';

interface Task {
    id: string;
    description: string;
    status: string;
    progress: number;
    result?: string;
    error?: string;
    created_at: string;
}

export default function TaskView() {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);

    // New Task Form State
    const [description, setDescription] = useState("");
    const [skillName, setSkillName] = useState("research"); // Default

    const fetchTasks = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/tasks');
            const data = await res.json();
            setTasks(data);
        } catch (e) {
            console.error("Failed to fetch tasks", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTasks();
        const interval = setInterval(fetchTasks, 2000);
        return () => {
            clearInterval(interval);
        };
    }, []);

    const handleCreateTask = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await fetch('http://localhost:8000/api/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    description,
                    skill_name: skillName,
                    priority: 5
                })
            });
            setDescription("");
            setShowCreate(false);
            fetchTasks();
        } catch (err) {
            console.error("Failed to create task", err);
        }
    };

    const handleCancelTask = async (taskId: string) => {
        try {
            await fetch(`http://localhost:8000/api/tasks/${taskId}/stop`, { method: 'POST' });
            fetchTasks(); // Refresh immediately
        } catch (err) {
            console.error("Failed to cancel task", err);
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header / Toolbar */}
            <div className="flex justify-between items-center mb-4 px-1">
                <h2 className="text-cyan-400 font-mono text-sm tracking-wider">ACTIVE PROCESSES</h2>
                <button
                    onClick={() => setShowCreate(!showCreate)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${showCreate ? 'bg-red-500/20 text-red-300' : 'bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30'
                        }`}
                >
                    {showCreate ? <XCircle size={14} /> : <Plus size={14} />}
                    {showCreate ? "Cancel" : "New Task"}
                </button>
            </div>

            {/* Create Task Form */}
            <AnimatePresence>
                {showCreate && (
                    <motion.form
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        onSubmit={handleCreateTask}
                        className="bg-slate-800/50 p-4 rounded-xl border border-cyan-500/30 mb-4 overflow-hidden"
                    >
                        <div className="space-y-3">
                            <div>
                                <label className="block text-xs text-cyan-500/60 mb-1">Task Description</label>
                                <input
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    placeholder="e.g. Research latest AI agent frameworks"
                                    className="w-full bg-black/30 border border-cyan-900/50 rounded-lg p-2 text-sm text-white focus:border-cyan-500/50 outline-none"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-cyan-500/60 mb-1">Target Skill</label>
                                <select
                                    value={skillName}
                                    onChange={(e) => setSkillName(e.target.value)}
                                    className="w-full bg-black/30 border border-cyan-900/50 rounded-lg p-2 text-sm text-cyan-100 outline-none"
                                >
                                    <option value="research">Deep Research</option>
                                    <option value="coding">Coding / Development</option>
                                    <option value="telegram">Telegram / Communication</option>
                                </select>
                            </div>
                            <button type="submit" className="w-full py-2 bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 rounded-lg text-sm font-medium transition-colors border border-cyan-500/30">
                                Launch Process
                            </button>
                        </div>
                    </motion.form>
                )}
            </AnimatePresence>

            {/* Task List */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-2 custom-scrollbar">
                {tasks.length === 0 ? (
                    <div className="text-center py-10 text-cyan-500/30 text-sm italic">
                        No active background tasks.
                    </div>
                ) : (
                    <AnimatePresence mode='popLayout'>
                        {tasks.map((task) => (
                            <TaskItem key={task.id} task={task} onCancel={handleCancelTask} />
                        ))}
                    </AnimatePresence>
                )}
            </div>
        </div>
    );
}

function TaskItem({ task, onCancel }: { task: Task, onCancel: (id: string) => void }) {
    const isRunning = task.status === 'running';
    const isCompleted = task.status === 'completed';
    const isFailed = task.status === 'failed';

    return (
        <motion.div
            layout
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className={`p-3 rounded-xl border ${isRunning ? 'bg-cyan-900/20 border-cyan-500/40' :
                isCompleted ? 'bg-emerald-900/10 border-emerald-500/30' :
                    isFailed ? 'bg-red-900/10 border-red-500/30' : 'bg-slate-800/30 border-slate-700/50'
                }`}
        >
            <div className="flex justify-between items-start mb-2">
                <div className="flex items-center gap-2">
                    <StatusIcon status={task.status} />
                    <span className="text-xs font-mono opacity-70 uppercase tracking-wide">{task.status}</span>
                </div>
                {isRunning && (
                    <button onClick={() => onCancel(task.id)} className="text-red-400 hover:text-red-300 transition-colors">
                        <XCircle size={14} />
                    </button>
                )}
            </div>

            <div className="text-sm text-white font-medium mb-1 line-clamp-2">{task.description}</div>

            {/* Progress Bar (if running) */}
            {isRunning && (
                <div className="mt-2 h-1.5 bg-black/40 rounded-full overflow-hidden">
                    <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${task.progress}%` }}
                        className="h-full bg-cyan-400 rounded-full"
                    />
                </div>
            )}

            {/* Result Preview */}
            {task.result && (
                <div className="mt-2 p-2 bg-black/20 rounded border border-white/5 text-xs text-cyan-200/70 font-mono line-clamp-3 break-all">
                    {'>'} {task.result}
                </div>
            )}
            {task.error && (
                <div className="mt-2 p-2 bg-red-900/20 rounded border border-red-500/20 text-xs text-red-300 font-mono">
                    ERROR: {task.error}
                </div>
            )}

            <div className="mt-2 text-[10px] text-white/30 flex justify-between">
                <span>ID: {task.id.slice(0, 8)}</span>
                <span>{new Date(task.created_at).toLocaleTimeString()}</span>
            </div>
        </motion.div>
    );
}

function StatusIcon({ status }: { status: string }) {
    switch (status) {
        case 'running': return <div className="animate-spin"><Clock size={14} className="text-cyan-400" /></div>;
        case 'completed': return <CheckCircle size={14} className="text-emerald-400" />;
        case 'failed': return <AlertCircle size={14} className="text-red-400" />;
        case 'pending': return <Clock size={14} className="text-slate-400" />;
        default: return <div className="w-3 h-3 rounded-full bg-slate-500" />;
    }
}
