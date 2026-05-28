import React, { useState } from 'react';
import { 
    Crosshair, MousePointer2, Eraser, 
    TrendingUp, Minus, ArrowRight,
    AlignEndHorizontal, Layers,
    PenTool, Highlighter, Square, Circle, Triangle,
    Type, 
    Activity, GitMerge,
    BarChart2, Ruler,
    ZoomIn, Magnet, Lock, EyeOff, Trash2, ChevronRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface DrawingToolbarProps {
    activeTool: string | null;
    setActiveTool: (tool: string | null) => void;
}

export default function DrawingToolbar({ activeTool, setActiveTool }: DrawingToolbarProps) {
    const [hoveredMenu, setHoveredMenu] = useState<string | null>(null);

    const menuData = [
        {
            id: 'cursors',
            icon: <Crosshair size={18} strokeWidth={1.5} />,
            items: [
                { id: 'cross', label: 'Cross', icon: <Crosshair size={14} /> },
                { id: 'dot', label: 'Dot', icon: <Circle size={14} fill="currentColor" /> },
                { id: 'arrow', label: 'Arrow', icon: <MousePointer2 size={14} /> },
                { id: 'eraser', label: 'Eraser', icon: <Eraser size={14} /> },
            ]
        },
        {
            id: 'lines',
            icon: <TrendingUp size={18} strokeWidth={1.5} />,
            items: [
                { id: 'trendline', label: 'Trend Line', icon: <TrendingUp size={14} />, shortcut: 'Alt + T' },
                { id: 'ray', label: 'Ray', icon: <ArrowRight size={14} /> },
                { id: 'hline', label: 'Horizontal Line', icon: <Minus size={14} />, shortcut: 'Alt + H' },
                { id: 'vline', label: 'Vertical Line', icon: <Minus size={14} className="rotate-90" />, shortcut: 'Alt + V' },
            ]
        },
        {
            id: 'fibonacci',
            icon: <AlignEndHorizontal size={18} strokeWidth={1.5} />,
            items: [
                { id: 'fib_retracement', label: 'Fib Retracement', icon: <AlignEndHorizontal size={14} />, shortcut: 'Alt + F' },
                { id: 'pitchfork', label: 'Pitchfork', icon: <Layers size={14} /> },
            ]
        },
        {
            id: 'shapes',
            icon: <PenTool size={18} strokeWidth={1.5} />,
            items: [
                { id: 'brush', label: 'Brush', icon: <PenTool size={14} /> },
                { id: 'highlighter', label: 'Highlighter', icon: <Highlighter size={14} /> },
                { id: 'rectangle', label: 'Rectangle', icon: <Square size={14} /> },
                { id: 'ellipse', label: 'Ellipse', icon: <Circle size={14} /> },
                { id: 'triangle', label: 'Triangle', icon: <Triangle size={14} /> },
            ]
        },
        {
            id: 'text',
            icon: <Type size={18} strokeWidth={1.5} />,
            items: [
                { id: 'text', label: 'Text', icon: <Type size={14} /> }
            ]
        },
        {
            id: 'patterns',
            icon: <Activity size={18} strokeWidth={1.5} />,
            items: [
                { id: 'xabcd', label: 'XABCD Pattern', icon: <Activity size={14} /> },
                { id: 'elliott', label: 'Elliott Wave', icon: <GitMerge size={14} /> },
            ]
        },
        {
            id: 'positions',
            icon: <BarChart2 size={18} strokeWidth={1.5} />,
            items: [
                { id: 'long_position', label: 'Long Position', icon: <BarChart2 size={14} className="rotate-180" /> },
                { id: 'short_position', label: 'Short Position', icon: <BarChart2 size={14} /> },
                { id: 'measure', label: 'Price Range', icon: <Ruler size={14} /> },
            ]
        }
    ];

    const bottomTools = [
        { id: 'measure_tool', icon: <Ruler size={18} strokeWidth={1.5} />, label: 'Measure' },
        { id: 'zoom', icon: <ZoomIn size={18} strokeWidth={1.5} />, label: 'Zoom In' },
        { id: 'magnet', icon: <Magnet size={18} strokeWidth={1.5} />, label: 'Magnet Mode' },
        { id: 'lock', icon: <Lock size={18} strokeWidth={1.5} />, label: 'Lock All Drawings' },
        { id: 'hide', icon: <EyeOff size={18} strokeWidth={1.5} />, label: 'Hide All Drawings' },
        { id: 'trash', icon: <Trash2 size={18} strokeWidth={1.5} />, label: 'Remove Drawings' },
    ];

    return (
        <div className="w-[48px] border-r border-[#222] bg-[#000] flex flex-col h-full overflow-y-auto overflow-x-visible pb-2 select-none" style={{ scrollbarWidth: 'none' }}>
            <div className="flex-1 flex flex-col items-center py-2 gap-1 relative">
                {menuData.map((menu) => (
                    <div 
                        key={menu.id} 
                        className="relative group w-full flex justify-center"
                        onMouseEnter={() => setHoveredMenu(menu.id)}
                        onMouseLeave={() => setHoveredMenu(null)}
                    >
                        {/* MAIN ICON BUTTON */}
                        <button
                            onClick={() => setActiveTool(menu.items[0].id)}
                            className={`p-2 rounded transition-colors relative z-20 ${
                                menu.items.some(i => i.id === activeTool)
                                    ? 'text-[#00e676]'
                                    : 'text-gray-400 hover:bg-[#222] hover:text-white'
                            }`}
                        >
                            {menu.icon}
                            {/* Tiny expand arrow on the right side of the button */}
                            <ChevronRight size={10} className="absolute right-0 top-1/2 -translate-y-1/2 text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </button>

                        {/* HOVER DROPDOWN MENU */}
                        <AnimatePresence>
                            {hoveredMenu === menu.id && (
                                <motion.div
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -10 }}
                                    transition={{ duration: 0.15 }}
                                    className="absolute left-[48px] top-0 bg-[#1e1e1e] border border-[#333] rounded shadow-xl py-1 w-48 z-50 overflow-hidden"
                                >
                                    {menu.items.map((item) => (
                                        <button
                                            key={item.id}
                                            onClick={() => setActiveTool(item.id)}
                                            className={`w-full text-left px-3 py-1.5 text-xs flex items-center justify-between transition-colors ${
                                                activeTool === item.id 
                                                    ? 'bg-[#00e676]/10 text-[#00e676]' 
                                                    : 'text-gray-300 hover:bg-[#2a2a2a] hover:text-white'
                                            }`}
                                        >
                                            <div className="flex items-center gap-2">
                                                <span className="opacity-70">{item.icon}</span>
                                                <span>{item.label}</span>
                                            </div>
                                            {item.shortcut && (
                                                <span className="text-[10px] text-gray-500 font-mono">{item.shortcut}</span>
                                            )}
                                        </button>
                                    ))}
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                ))}

                <div className="w-6 h-[1px] bg-[#222] my-2" />

                {/* BOTTOM TOOLS */}
                {bottomTools.map((tool) => (
                    <button
                        key={tool.id}
                        onClick={() => {
                            if (tool.id === 'trash') {
                                setActiveTool('clear_drawings');
                                setTimeout(() => setActiveTool(null), 100);
                            } else {
                                setActiveTool(activeTool === tool.id ? null : tool.id);
                            }
                        }}
                        className={`p-2 rounded transition-colors w-full flex justify-center ${
                            activeTool === tool.id || (tool.id === 'trash' && activeTool === 'clear_drawings')
                                ? 'text-[#00e676]'
                                : 'text-gray-400 hover:bg-[#222] hover:text-white'
                        }`}
                        title={tool.label}
                    >
                        {tool.icon}
                    </button>
                ))}
            </div>
        </div>
    );
}
