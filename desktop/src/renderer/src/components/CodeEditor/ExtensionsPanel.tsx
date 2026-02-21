import React, { useState, useEffect } from 'react';

interface Extension {
    id: string;
    name: string;
    publisher: string;
    description: string;
    icon: string;          // material-symbols-outlined icon name
    installed: boolean;
    enabled: boolean;
    category: string;
    version: string;
}

const BUILT_IN_EXTENSIONS: Extension[] = [
    {
        id: 'prettier',
        name: 'Prettier',
        publisher: 'Prettier',
        description: 'Code formatter using Prettier',
        icon: 'format_align_left',
        installed: true,
        enabled: true,
        category: 'Formatters',
        version: '11.0.0',
    },
    {
        id: 'eslint',
        name: 'ESLint',
        publisher: 'Microsoft',
        description: 'Integrates ESLint JavaScript linting',
        icon: 'rule',
        installed: true,
        enabled: true,
        category: 'Linters',
        version: '3.0.10',
    },
    {
        id: 'copilot-ai',
        name: 'AI Copilot',
        publisher: 'Obsidian Pro',
        description: 'AI-powered code suggestions, refactoring, and explanations',
        icon: 'auto_awesome',
        installed: true,
        enabled: true,
        category: 'AI',
        version: '2.1.0',
    },
    {
        id: 'git-lens',
        name: 'GitLens',
        publisher: 'GitKraken',
        description: 'Git supercharged — blame, history, and more',
        icon: 'commit',
        installed: false,
        enabled: false,
        category: 'Source Control',
        version: '15.6.0',
    },
    {
        id: 'python',
        name: 'Python',
        publisher: 'Microsoft',
        description: 'Python language support with IntelliSense and debugging',
        icon: 'code',
        installed: true,
        enabled: true,
        category: 'Languages',
        version: '2024.22.0',
    },
    {
        id: 'tailwind-intellisense',
        name: 'Tailwind CSS IntelliSense',
        publisher: 'Tailwind Labs',
        description: 'Intelligent Tailwind CSS tooling',
        icon: 'style',
        installed: true,
        enabled: true,
        category: 'CSS',
        version: '0.14.0',
    },
    {
        id: 'thunder-client',
        name: 'Thunder Client',
        publisher: 'Thunder Client',
        description: 'Lightweight REST API client',
        icon: 'api',
        installed: false,
        enabled: false,
        category: 'API Testing',
        version: '2.30.1',
    },
    {
        id: 'docker',
        name: 'Docker',
        publisher: 'Microsoft',
        description: 'Build, manage, and deploy containerized apps',
        icon: 'deployed_code',
        installed: false,
        enabled: false,
        category: 'DevOps',
        version: '1.29.3',
    },
    {
        id: 'markdown-preview',
        name: 'Markdown Preview',
        publisher: 'Obsidian Pro',
        description: 'Enhanced markdown preview with mermaid support',
        icon: 'article',
        installed: true,
        enabled: true,
        category: 'Formatters',
        version: '3.0.1',
    },
    {
        id: 'auto-rename-tag',
        name: 'Auto Rename Tag',
        publisher: 'Jun Han',
        description: 'Automatically rename paired HTML/XML tag',
        icon: 'label',
        installed: false,
        enabled: false,
        category: 'HTML',
        version: '0.1.10',
    },
    {
        id: 'bracket-colorizer',
        name: 'Bracket Pair Colorizer',
        publisher: 'CoenraadS',
        description: 'Colorize matching brackets in code',
        icon: 'data_array',
        installed: true,
        enabled: true,
        category: 'Editor',
        version: '2.0.2',
    },
    {
        id: 'live-server',
        name: 'Live Server',
        publisher: 'Ritwick Dey',
        description: 'Launch local dev server with live reload',
        icon: 'dns',
        installed: false,
        enabled: false,
        category: 'Web',
        version: '5.7.9',
    },
];

interface ExtensionsPanelProps {
    rootPath: string | null;
}

export function ExtensionsPanel({ rootPath }: ExtensionsPanelProps) {
    const [extensions, setExtensions] = useState<Extension[]>(BUILT_IN_EXTENSIONS);
    const [searchQuery, setSearchQuery] = useState('');
    const [filter, setFilter] = useState<'all' | 'installed' | 'available'>('all');

    // Load persisted extension state
    useEffect(() => {
        try {
            const saved = localStorage.getItem('obsidian_extensions_state');
            if (saved) {
                const savedState: Record<string, { installed: boolean; enabled: boolean }> = JSON.parse(saved);
                setExtensions(prev => prev.map(ext => {
                    const s = savedState[ext.id];
                    return s ? { ...ext, installed: s.installed, enabled: s.enabled } : ext;
                }));
            }
        } catch { /* ignore */ }
    }, []);

    // Persist extension state
    const persistState = (exts: Extension[]) => {
        const state: Record<string, { installed: boolean; enabled: boolean }> = {};
        exts.forEach(e => { state[e.id] = { installed: e.installed, enabled: e.enabled }; });
        localStorage.setItem('obsidian_extensions_state', JSON.stringify(state));
    };

    const toggleInstall = (id: string) => {
        setExtensions(prev => {
            const next = prev.map(ext =>
                ext.id === id
                    ? { ...ext, installed: !ext.installed, enabled: !ext.installed ? true : false }
                    : ext
            );
            persistState(next);
            return next;
        });
    };

    const toggleEnable = (id: string) => {
        setExtensions(prev => {
            const next = prev.map(ext =>
                ext.id === id && ext.installed
                    ? { ...ext, enabled: !ext.enabled }
                    : ext
            );
            persistState(next);
            return next;
        });
    };

    const filtered = extensions.filter(ext => {
        const matchesSearch = !searchQuery ||
            ext.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            ext.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
            ext.category.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesFilter = filter === 'all' ||
            (filter === 'installed' && ext.installed) ||
            (filter === 'available' && !ext.installed);

        return matchesSearch && matchesFilter;
    });

    const installedCount = extensions.filter(e => e.installed).length;

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            {/* Search */}
            <div className="px-3 py-2">
                <div className="relative">
                    <span className="material-symbols-outlined text-[14px] text-gray-500 absolute left-2.5 top-1/2 -translate-y-1/2">search</span>
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search extensions..."
                        className="w-full bg-[#121215] text-gray-200 text-[11px] pl-8 pr-3 py-1.5 rounded border border-gray-800/80 focus:border-primary/50 focus:outline-none placeholder-gray-600 transition-colors"
                    />
                </div>
            </div>

            {/* Filter tabs */}
            <div className="flex px-3 gap-1 mb-2">
                {(['all', 'installed', 'available'] as const).map(f => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={`px-2 py-1 text-[10px] rounded transition-colors uppercase tracking-wider font-medium ${
                            filter === f
                                ? 'bg-primary/20 text-primary border border-primary/30'
                                : 'text-gray-500 hover:text-gray-300 border border-transparent'
                        }`}
                    >
                        {f}{f === 'installed' ? ` (${installedCount})` : ''}
                    </button>
                ))}
            </div>

            {/* Extension list */}
            <div className="flex-1 overflow-y-auto px-2 space-y-1">
                {filtered.map(ext => (
                    <div
                        key={ext.id}
                        className="group flex items-start gap-2.5 p-2.5 rounded-lg hover:bg-white/5 transition-colors cursor-default"
                    >
                        {/* Icon */}
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                            ext.installed && ext.enabled
                                ? 'bg-primary/15 border border-primary/30'
                                : 'bg-gray-800/50 border border-gray-700/50'
                        }`}>
                            <span className={`material-symbols-outlined text-[18px] ${
                                ext.installed && ext.enabled ? 'text-primary' : 'text-gray-500'
                            }`}>{ext.icon}</span>
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5">
                                <span className="text-[12px] font-medium text-gray-200 truncate">{ext.name}</span>
                                <span className="text-[9px] text-gray-600 font-mono">v{ext.version}</span>
                            </div>
                            <div className="text-[10px] text-gray-500 truncate">{ext.publisher}</div>
                            <div className="text-[10px] text-gray-600 mt-0.5 leading-tight line-clamp-2">{ext.description}</div>

                            {/* Controls */}
                            <div className="flex items-center gap-1.5 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                {ext.installed ? (
                                    <>
                                        <button
                                            onClick={() => toggleEnable(ext.id)}
                                            className={`px-2 py-0.5 text-[9px] rounded border transition-colors font-medium ${
                                                ext.enabled
                                                    ? 'border-yellow-600/40 text-yellow-500 hover:bg-yellow-500/10'
                                                    : 'border-green-600/40 text-green-500 hover:bg-green-500/10'
                                            }`}
                                        >
                                            {ext.enabled ? 'Disable' : 'Enable'}
                                        </button>
                                        <button
                                            onClick={() => toggleInstall(ext.id)}
                                            className="px-2 py-0.5 text-[9px] rounded border border-red-600/40 text-red-500 hover:bg-red-500/10 transition-colors font-medium"
                                        >
                                            Uninstall
                                        </button>
                                    </>
                                ) : (
                                    <button
                                        onClick={() => toggleInstall(ext.id)}
                                        className="px-2.5 py-0.5 text-[9px] rounded bg-primary/20 border border-primary/40 text-primary hover:bg-primary/30 transition-colors font-medium"
                                    >
                                        Install
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* Status indicator */}
                        <div className="shrink-0 mt-1">
                            {ext.installed && ext.enabled && (
                                <span className="w-2 h-2 rounded-full bg-green-500 block" title="Active" />
                            )}
                            {ext.installed && !ext.enabled && (
                                <span className="w-2 h-2 rounded-full bg-yellow-500 block" title="Disabled" />
                            )}
                        </div>
                    </div>
                ))}

                {filtered.length === 0 && (
                    <div className="text-center py-8 text-gray-600 text-[11px]">
                        No extensions found
                    </div>
                )}
            </div>
        </div>
    );
}
