import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, List, MessageCircle, X } from 'lucide-react';
import LearningView from './LearningView';
import TaskView from './TaskView';
import TelegramView from './TelegramView';

interface DashboardProps {
    isOpen: boolean;
    onClose: () => void;
}

export default function Dashboard({ isOpen, onClose }: DashboardProps) {
    const [activeTab, setActiveTab] = useState<'learning' | 'tasks' | 'telegram'>('tasks');

    const tabs = [
        { id: 'tasks', label: 'Tasks', icon: List },
        { id: 'learning', label: 'Learning', icon: Brain },
        { id: 'telegram', label: 'Telegram', icon: MessageCircle },
    ];

    if (!isOpen) return null;

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="absolute top-20 left-1/2 -translate-x-1/2 w-[700px] h-[600px] bg-[#020a12]/90 backdrop-blur-xl border border-cyan-500/30 rounded-2xl shadow-2xl z-40 flex flex-col overflow-hidden"
        >
            {/* Header */}
            <div className="px-5 py-4 border-b border-cyan-500/20 flex justify-between items-center bg-cyan-900/10">
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-cyan-400 rounded-full animate-pulse" />
                    <span className="text-lg font-medium text-white tracking-wider">SYSTEM DASHBOARD</span>
                </div>
                <button onClick={onClose} className="text-cyan-500/60 hover:text-white transition-colors">
                    <X size={20} />
                </button>
            </div>

            {/* Navigation Tabs */}
            <div className="flex border-b border-cyan-500/20 px-2 pt-2">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id as any)}
                        className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-all relative ${activeTab === tab.id
                            ? 'text-cyan-300'
                            : 'text-cyan-500/50 hover:text-cyan-400 hover:bg-cyan-500/5'
                            }`}
                    >
                        <tab.icon size={16} />
                        {tab.label}
                        {activeTab === tab.id && (
                            <motion.div
                                layoutId="activeTab"
                                className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-400 shadow-[0_0_10px_rgba(0,255,255,0.5)]"
                            />
                        )}
                    </button>
                ))}
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative p-1 bg-gradient-to-b from-transparent to-cyan-900/5">
                <AnimatePresence mode="wait">
                    {activeTab === 'learning' && (
                        <motion.div
                            key="learning"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="h-full overflow-y-auto custom-scrollbar"
                        >
                            <LearningView />
                        </motion.div>
                    )}
                    {activeTab === 'tasks' && (
                        <motion.div
                            key="tasks"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="h-full overflow-y-auto custom-scrollbar p-4"
                        >
                            <TaskView />
                        </motion.div>
                    )}
                    {activeTab === 'telegram' && (
                        <motion.div
                            key="telegram"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="h-full overflow-y-auto custom-scrollbar"
                        >
                            <TelegramView />
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    );
}
