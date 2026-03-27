import React, { useState, useRef, useEffect } from 'react';
import { X, FolderOpen, ChevronRight, ChevronDown, FileText, Folder, Send, Sparkles, Code2, Wand2, Plus, FilePlus, Save, Copy, Scissors, Clipboard, RotateCcw, RotateCw, Eye, EyeOff, Terminal, Settings } from 'lucide-react';
import Editor from '@monaco-editor/react';
import TerminalPanel from './TerminalPanel';
import { DiffPreview } from './DiffPreview';
import { registerInlineCompletionProvider } from './InlineCompletionProvider';
import * as monaco from 'monaco-editor';

import { PlanPanel, PlanReadyButton } from './PlanPanel';
import { ExtensionsPanel } from './ExtensionsPanel';
import { EditorStateManager } from './editor-core/editorStateManager';
import type { EditorStage, ImplementationPlan, PatchEntry } from './editor-core/types';
import { applyUnifiedDiff, extractChangedLineNumbers, UnifiedDiffApplyError } from './editor-core/unifiedDiff';

import './obsidian-pro.css';


interface FileNode {
    name: string;
    path: string;
    type: 'file' | 'folder';
    children?: FileNode[];
    expanded?: boolean;
    handle?: FileSystemHandle;
}

interface OpenFile {
    path: string;
    name: string;
    content: string;
    language: string;
    modified: boolean;
}

interface CodeEditorViewProps {
    onClose: () => void;
    initialProjectPath?: string | null;
}

interface MenuItem {
    label: string;
    shortcut?: string;
    action?: () => void;
    divider?: boolean;
    disabled?: boolean;
}

const getLanguage = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    const langMap: Record<string, string> = {
        'js': 'javascript', 'jsx': 'javascript', 'ts': 'typescript', 'tsx': 'typescript',
        'py': 'python', 'css': 'css', 'html': 'html', 'json': 'json', 'md': 'markdown',
        'yaml': 'yaml', 'yml': 'yaml', 'sql': 'sql', 'sh': 'shell', 'bash': 'shell',
    };
    return langMap[ext] || 'plaintext';
};

export default function CodeEditorView({ onClose, initialProjectPath = null }: CodeEditorViewProps) {
    const [rootPath, setRootPath] = useState<string | null>(null);
    const [fileTree, setFileTree] = useState<FileNode[]>([]);
    const [openFiles, setOpenFiles] = useState<OpenFile[]>([]);
    const [activeFile, setActiveFile] = useState<string | null>(null);
    const [agentMessages, setAgentMessages] = useState<{ role: 'user' | 'agent'; text: string }[]>([
        { role: 'agent', text: 'Hello! I can:\n• Generate new code\n• Explain code\n• Debug & refactor\n\nTry: "create a calculator"' }
    ]);
    const [agentInput, setAgentInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [terminalOpen, setTerminalOpen] = useState(false);
    const [terminalHeight, setTerminalHeight] = useState<number>(() => {
        const saved = localStorage.getItem('obsidian_terminal_height');
        const parsed = saved ? Number(saved) : NaN;
        return Number.isFinite(parsed) ? parsed : 320;
    });
    const [activeMenu, setActiveMenu] = useState<string | null>(null);
    const [showSidebar, setShowSidebar] = useState(true);
    const [showAgent, setShowAgent] = useState(true);

    const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
        const saved = localStorage.getItem('obsidian_sidebar_width');
        const parsed = saved ? Number(saved) : NaN;
        return Number.isFinite(parsed) ? parsed : 260;
    });

    const [agentWidth, setAgentWidth] = useState<number>(() => {
        const saved = localStorage.getItem('obsidian_agent_width');
        const parsed = saved ? Number(saved) : NaN;
        return Number.isFinite(parsed) ? parsed : 300;
    });
    const rootHandleRef = useRef<FileSystemDirectoryHandle | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const messagesScrollRef = useRef<HTMLDivElement>(null);

    const [diffPreviewOpen, setDiffPreviewOpen] = useState(false);
    const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

    // Editor-local deterministic state (no silent disk mutation)
    const editorStateRef = useRef<EditorStateManager>(new EditorStateManager());
    const [editorStage, setEditorStage] = useState<EditorStage>('idle');
    const [stageMessage, setStageMessage] = useState<string>('');
    const [pendingPlan, setPendingPlan] = useState<ImplementationPlan | null>(null);
    const [showPlanModal, setShowPlanModal] = useState(false);
    const [pendingPatches, setPendingPatches] = useState<PatchEntry[]>([]);
    const [lastRefactorRequest, setLastRefactorRequest] = useState<string>('');
    const [changedFiles, setChangedFiles] = useState<Set<string>>(new Set());
    const [aiChangedLinesByFile, setAiChangedLinesByFile] = useState<Record<string, number[]>>({});
    const decorationsRef = useRef<string[]>([]);
    const inlineProviderDisposableRef = useRef<monaco.IDisposable | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);

    const [activeSidebarTab, setActiveSidebarTab] = useState<'explorer' | 'extensions'>('explorer');

    const [selectedLlmModel, setSelectedLlmModel] = useState<string>(() => {
        const saved = localStorage.getItem('codeAgent_llm_model');
        return saved && saved.trim() ? saved : 'auto';
    });

    const terminalResizeRef = useRef<{ dragging: boolean; startY: number; startHeight: number } | null>(null);

    const sidebarResizeRef = useRef<{ dragging: boolean; startX: number; startWidth: number } | null>(null);
    const agentResizeRef = useRef<{ dragging: boolean; startX: number; startWidth: number } | null>(null);

    useEffect(() => {
        localStorage.setItem('obsidian_terminal_height', String(terminalHeight));
    }, [terminalHeight]);

    useEffect(() => {
        localStorage.setItem('codeAgent_llm_model', selectedLlmModel);
    }, [selectedLlmModel]);

    useEffect(() => {
        localStorage.setItem('obsidian_sidebar_width', String(sidebarWidth));
    }, [sidebarWidth]);

    useEffect(() => {
        localStorage.setItem('obsidian_agent_width', String(agentWidth));
    }, [agentWidth]);

    // Derived state
    const currentFile = openFiles.find(f => f.path === activeFile);
    const saveFunctionRef = useRef<() => void>(() => { });
    const hasUserMessages = agentMessages.some(m => m.role === 'user');

    // IMPORTANT: No auto-save-to-disk in this editor subsystem.
    // Buffer changes remain in Monaco until user explicitly saves/applies.

    const handleEditorDidMount = (editor: monaco.editor.IStandaloneCodeEditor) => {
        editorRef.current = editor;
        inlineProviderDisposableRef.current?.dispose();
        inlineProviderDisposableRef.current = registerInlineCompletionProvider(editor);

        // Register Ctrl+S / Cmd+S
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
            console.log('💾 Ctrl+S triggered');
            saveFunctionRef.current();
        });
    };

    useEffect(() => {
        return () => {
            inlineProviderDisposableRef.current?.dispose();
            inlineProviderDisposableRef.current = null;
        };
    }, []);


    // Helper to get project-specific storage key
    const getProjectHistoryKey = (path: string) => {
        // Create a safe key from the path
        const safePath = path.replace(/[\\/:]/g, '_').toLowerCase();
        return `agent_history_${safePath}`;
    };

    // Load project-specific agent history
    const loadProjectHistory = (projectPath: string) => {
        try {
            const historyKey = getProjectHistoryKey(projectPath);
            const saved = localStorage.getItem(historyKey);
            if (saved) {
                const history = JSON.parse(saved);
                setAgentMessages(history);
                console.log(`Loaded ${history.length} messages for project: ${projectPath}`);
            } else {
                // New project - show welcome message
                setAgentMessages([
                    { role: 'agent', text: `Hello! I can:\n• Generate new code\n• Explain code\n• Debug & refactor\n\nProject: ${projectPath.split('\\\\').pop() || projectPath}\n\nTry: "create a calculator"` }
                ]);
            }
        } catch (e) {
            console.error('Failed to load project history:', e);
        }
    };

    // Save project-specific agent history
    const saveProjectHistory = (projectPath: string, messages: { role: 'user' | 'agent'; text: string }[]) => {
        try {
            const historyKey = getProjectHistoryKey(projectPath);
            // Keep last 50 messages per project
            localStorage.setItem(historyKey, JSON.stringify(messages.slice(-50)));
        } catch (e) {
            console.error('Failed to save project history:', e);
        }
    };

    // Load session from localStorage on mount
    useEffect(() => {
        let sessionLoaded = false;
        try {
            const savedSession = localStorage.getItem('codeEditorSession');
            if (savedSession) {
                const session = JSON.parse(savedSession);
                if (session.openFiles) setOpenFiles(session.openFiles);
                if (session.activeFile) setActiveFile(session.activeFile);
                if (session.rootPath) {
                    setRootPath(session.rootPath);
                    // Load project-specific agent history
                    loadProjectHistory(session.rootPath);
                    // Note: rootHandleRef is NOT restored - user needs to reconnect
                    console.log('⚠️ Session restored but folder handle lost. User needs to re-select folder for file operations.');
                }
                if (session.fileTree && session.fileTree.length > 0) {
                    setFileTree(session.fileTree);
                    sessionLoaded = true;
                }
                console.log('Session restored from localStorage');
            }
        } catch (e) {
            console.error('Failed to restore session:', e);
        }

        // Prefer explicit project path from parent for newly generated projects
        if (initialProjectPath && !sessionLoaded) {
            openProjectFolder(initialProjectPath);
            return;
        }

        // Load default generated folder contents if no session file tree
        if (!sessionLoaded) {
            loadDefaultFolder();
        }
    }, []);

    // Check if folder is connected (has live handle)
    // Check if folder is connected (has live handle or using Electron API)
    const isFolderConnected = (): boolean => {
        if (window.electronAPI?.fs) return true;
        return !!rootHandleRef.current;
    };

    // Load files from default generated folder
    const loadDefaultFolder = async () => {
        const defaultPath = 'D:\\All Projects\\My AI Agent\\generated';
        console.log('Loading default folder:', defaultPath);

        try {
            // Add timeout to prevent hanging
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);

            const response = await fetch(
                `http://localhost:8000/api/list-files?directory=${encodeURIComponent(defaultPath)}`,
                { signal: controller.signal }
            );
            clearTimeout(timeoutId);

            if (response.ok) {
                const data = await response.json();
                console.log('API response:', data);

                if (data.files && data.files.length > 0) {
                    const nodes: FileNode[] = data.files.map((f: any) => ({
                        name: f.name,
                        path: `${defaultPath}\\${f.name}`,
                        type: f.isDirectory ? 'folder' : 'file'
                    }));
                    setFileTree(nodes);
                    setRootPath(defaultPath);
                    console.log('Loaded default folder:', nodes.length, 'files');
                } else {
                    console.log('No files in generated folder');
                    setRootPath(defaultPath);
                }
            } else {
                console.log('API error:', response.status);
            }
        } catch (err: any) {
            if (err.name === 'AbortError') {
                console.log('API request timed out');
            } else {
                console.log('Default folder not available:', err.message);
            }
        }
    };

    // Save session to localStorage when state changes
    useEffect(() => {
        const session = {
            openFiles,
            activeFile,
            rootPath,
            fileTree
            // Note: agentMessages now saved per-project separately
        };
        localStorage.setItem('codeEditorSession', JSON.stringify(session));

        // Save agent history for current project
        if (rootPath) {
            saveProjectHistory(rootPath, agentMessages);
        }
    }, [openFiles, activeFile, rootPath, fileTree, agentMessages]);

    useEffect(() => {
        messagesScrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [agentMessages, isLoading]);

    // Helper to open a project folder given a path
    const openProjectFolder = async (folderPath: string) => {
        try {
            // Save current project history before switching
            if (rootPath) {
                saveProjectHistory(rootPath, agentMessages);
            }

            // Clear stale tree immediately while new folder is loading
            setFileTree([]);
            setRootPath(folderPath);
            loadProjectHistory(folderPath);

            if (window.electronAPI?.fs) {
                let lastError: any = null;

                for (let attempt = 0; attempt < 5; attempt++) {
                    try {
                        const entries = await window.electronAPI.fs.listDir(folderPath);
                        const items: FileNode[] = entries.map(entry => ({
                            name: entry.name,
                            path: entry.path,
                            type: entry.type === 'directory' ? 'folder' : 'file',
                            children: entry.type === 'directory' ? [] : undefined,
                            expanded: false,
                        }));

                        items.sort((a, b) => {
                            if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
                            return a.name.localeCompare(b.name);
                        });

                        setFileTree(items);
                        console.log('✅ Loaded', items.length, 'items from', folderPath);
                        return;
                    } catch (error) {
                        lastError = error;
                        await new Promise(resolve => setTimeout(resolve, 300));
                    }
                }

                console.warn('Electron listDir failed after retries, trying backend fallback:', lastError);
            }

            const response = await fetch(`http://localhost:8000/api/list-files?directory=${encodeURIComponent(folderPath)}`);
            if (response.ok) {
                const data = await response.json();
                const nodes: FileNode[] = (data.files || []).map((f: any) => ({
                    name: f.name,
                    path: `${folderPath}\\${f.name}`,
                    type: f.isDirectory ? 'folder' : 'file',
                    children: f.isDirectory ? [] : undefined,
                    expanded: false,
                }));

                nodes.sort((a, b) => {
                    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
                    return a.name.localeCompare(b.name);
                });

                setFileTree(nodes);
                console.log('✅ Loaded', nodes.length, 'items from backend fallback for', folderPath);
            }
        } catch (err) {
            console.error('Failed to open folder:', err);
            setFileTree([]);
        }
    };

    useEffect(() => {
        if (!initialProjectPath) return;
        if (initialProjectPath === rootPath) return;
        openProjectFolder(initialProjectPath);
    }, [initialProjectPath]);

    // Handle folder selection - uses Electron IPC for proper file system access
    const handleSelectFolder = async () => {
        try {
            // Use Electron API if available, fall back to browser API
            if (window.electronAPI?.fs) {
                const folderPath = await window.electronAPI.fs.openFolder();
                if (folderPath) {
                    await openProjectFolder(folderPath);
                }
            } else {
                // Fallback to browser File System Access API (won't work well in Electron)
                // @ts-ignore
                const dirHandle: FileSystemDirectoryHandle = await window.showDirectoryPicker();
                rootHandleRef.current = dirHandle;

                if (rootPath) {
                    saveProjectHistory(rootPath, agentMessages);
                }

                setRootPath(dirHandle.name);
                loadProjectHistory(dirHandle.name);

                const items: FileNode[] = [];
                // @ts-ignore
                for await (const [name, handle] of dirHandle.entries()) {
                    items.push({
                        name,
                        path: name,
                        type: handle.kind === 'directory' ? 'folder' : 'file',
                        children: handle.kind === 'directory' ? [] : undefined,
                        expanded: false,
                        handle,
                    });
                }

                items.sort((a, b) => {
                    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
                    return a.name.localeCompare(b.name);
                });

                setFileTree(items);
            }
        } catch (err) {
            console.error('Folder selection error:', err);
        }
    };

    // Listen for Menu Events
    useEffect(() => {
        if (window.electronAPI?.menu) {
            window.electronAPI.menu.onOpenFolder((path) => {
                openProjectFolder(path);
            });

            window.electronAPI.menu.onNewFile(() => {
                setOpenFiles(prev => [...prev, {
                    path: `untitled-${Date.now()}`,
                    name: 'Untitled',
                    content: '',
                    language: 'plaintext',
                    modified: true
                }]);
            });

            window.electronAPI.menu.onSave(() => {
                console.log('Save triggered from menu');
                saveFunctionRef.current();
            });

            window.electronAPI.menu.onToggleTerminal(() => {
                setTerminalOpen(prev => !prev);
            });
        }
    }, [rootPath]);

    // Load children when folder is expanded
    const loadChildren = async (node: FileNode): Promise<FileNode[]> => {
        // Use Electron API if available
        if (window.electronAPI?.fs) {
            if (node.type !== 'folder') return [];
            try {
                const entries = await window.electronAPI.fs.listDir(node.path);
                const items: FileNode[] = entries.map(entry => ({
                    name: entry.name,
                    path: entry.path,
                    type: entry.type === 'directory' ? 'folder' : 'file',
                    children: entry.type === 'directory' ? [] : undefined,
                    expanded: false,
                }));
                items.sort((a, b) => {
                    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
                    return a.name.localeCompare(b.name);
                });
                return items;
            } catch (err) {
                console.error('Error loading children via Electron:', err);
                return [];
            }
        }

        // Fallback to browser (check handle)
        if (!node.handle || node.type !== 'folder') return [];
        const dirHandle = node.handle as FileSystemDirectoryHandle;
        const items: FileNode[] = [];

        try {
            // @ts-ignore
            for await (const [name, handle] of dirHandle.entries()) {
                items.push({
                    name,
                    path: `${node.path}/${name}`,
                    type: handle.kind === 'directory' ? 'folder' : 'file',
                    children: handle.kind === 'directory' ? [] : undefined,
                    expanded: false,
                    handle,
                });
            }
            items.sort((a, b) => {
                if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
                return a.name.localeCompare(b.name);
            });
        } catch (err) {
            console.error('Error loading children:', err);
        }
        return items;
    };

    // Toggle folder expansion
    const toggleFolder = async (node: FileNode) => {
        if (!node.expanded && node.children?.length === 0) {
            const children = await loadChildren(node);
            setFileTree(prev => {
                const update = (nodes: FileNode[]): FileNode[] => nodes.map(n => {
                    if (n.path === node.path) return { ...n, expanded: true, children };
                    if (n.children) return { ...n, children: update(n.children) };
                    return n;
                });
                return update(prev);
            });
        } else {
            setFileTree(prev => {
                const toggle = (nodes: FileNode[]): FileNode[] => nodes.map(n => {
                    if (n.path === node.path) return { ...n, expanded: !n.expanded };
                    if (n.children) return { ...n, children: toggle(n.children) };
                    return n;
                });
                return toggle(prev);
            });
        }
    };

    /** Insert a new (unsaved) file into the file tree so it's visible in the explorer. */
    const insertFileIntoTree = (filePath: string) => {
        if (!rootPath) return;

        // Compute the path relative to rootPath
        const normalizedRoot = rootPath.replace(/[\\/]+$/, '');
        const normalizedFile = filePath.replace(/\//g, '\\');
        if (!normalizedFile.toLowerCase().startsWith(normalizedRoot.toLowerCase())) return;

        const relative = normalizedFile.slice(normalizedRoot.length + 1); // e.g. "src\\theme\\colors.ts"
        const segments = relative.split('\\');

        setFileTree(prev => {
            const insertAt = (nodes: FileNode[], segs: string[], parentPath: string): FileNode[] => {
                if (segs.length === 0) return nodes;

                const [current, ...rest] = segs;
                const currentPath = parentPath ? `${parentPath}\\${current}` : `${normalizedRoot}\\${current}`;

                // Last segment → it's the file
                if (rest.length === 0) {
                    if (nodes.some(n => n.path.toLowerCase() === currentPath.toLowerCase())) return nodes;
                    const fileNode: FileNode = { name: current, path: currentPath, type: 'file' };
                    const updated = [...nodes, fileNode];
                    updated.sort((a, b) => {
                        if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
                        return a.name.localeCompare(b.name);
                    });
                    return updated;
                }

                // Intermediate segment → it's a folder
                const existing = nodes.find(n => n.name.toLowerCase() === current.toLowerCase() && n.type === 'folder');
                if (existing) {
                    return nodes.map(n =>
                        n === existing
                            ? { ...n, children: insertAt(n.children || [], rest, currentPath), expanded: true }
                            : n
                    );
                } else {
                    // Create the folder node and recurse
                    const folderNode: FileNode = {
                        name: current,
                        path: currentPath,
                        type: 'folder',
                        expanded: true,
                        children: insertAt([], rest, currentPath),
                    };
                    const updated = [...nodes, folderNode];
                    updated.sort((a, b) => {
                        if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
                        return a.name.localeCompare(b.name);
                    });
                    return updated;
                }
            };

            return insertAt(prev, segments, normalizedRoot);
        });
    };

    // Open a file
    const openFile = async (node: FileNode) => {
        if (node.type !== 'file') return;

        // If already open, just switch to it
        if (openFiles.some(f => f.path === node.path)) {
            setActiveFile(node.path);
            return;
        }

        try {
            let content = '';

            if (window.electronAPI?.fs) {
                // Use Electron API
                content = await window.electronAPI.fs.readFile(node.path);
            } else if (node.handle) {
                // Use FileSystem API for user-selected folders (browser)
                const fileHandle = node.handle as FileSystemFileHandle;
                const file = await fileHandle.getFile();
                content = await file.text();
            } else {
                // Use backend API for files without handles (fallback)
                const response = await fetch(`http://localhost:8000/api/read-file?path=${encodeURIComponent(node.path)}`);
                if (response.ok) {
                    const data = await response.json();
                    content = data.content || '';
                }
            }

            setOpenFiles(prev => [...prev, {
                path: node.path,
                name: node.name,
                content,
                language: getLanguage(node.name),
                modified: false,
            }]);
            setActiveFile(node.path);
        } catch (err) {
            console.error('Failed to read file:', err);
        }
    };

    const closeFile = (path: string) => {
        setOpenFiles(prev => {
            const remaining = prev.filter(f => f.path !== path);
            if (activeFile === path && remaining.length > 0) {
                setActiveFile(remaining[remaining.length - 1].path);
            } else if (remaining.length === 0) {
                setActiveFile(null);
            }
            return remaining;
        });
    };

    const updateFileContent = (path: string, content: string) => {
        setOpenFiles(prev => prev.map(f => f.path === path ? { ...f, content, modified: true } : f));
    };

    const handleEditorChange = (value: string) => {
        if (!activeFile) return;
        updateFileContent(activeFile, value);
    };

    const clearAIDecorations = () => {
        try {
            const editor = editorRef.current;
            const model = editor?.getModel();
            if (!editor || !model) return;
            decorationsRef.current = editor.deltaDecorations(decorationsRef.current, []);
        } catch (e) {
            console.warn('Failed to clear AI decorations', e);
        }
    };

    const applyAIDecorations = (changedLineNumbers: number[]) => {
        const editor = editorRef.current;
        const model = editor?.getModel();
        if (!editor || !model) return;

        const decorations: monaco.editor.IModelDeltaDecoration[] = changedLineNumbers.map((line) => ({
            range: new monaco.Range(line, 1, line, 1),
            options: {
                isWholeLine: true,
                className: 'ai-line-modified',
            },
        }));

        decorationsRef.current = editor.deltaDecorations(decorationsRef.current, decorations);
    };

    useEffect(() => {
        // Re-apply decorations when switching files (only the active Monaco model can be decorated)
        if (!activeFile) return;
        const lines = aiChangedLinesByFile[activeFile] || [];
        clearAIDecorations();
        if (lines.length > 0) applyAIDecorations(lines);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeFile]);

    const fileExistsOnDisk = async (filePath: string): Promise<boolean> => {
        // If it's already open in the editor, it "exists"
        if (openFiles.some(f => f.path === filePath)) return true;
        try {
            if (window.electronAPI?.fs) {
                await window.electronAPI.fs.readFile(filePath);
                return true;
            }
            const response = await fetch(`http://localhost:8000/api/read-file?path=${encodeURIComponent(filePath)}`);
            return response.ok;
        } catch {
            return false;
        }
    };

    const readFileContent = async (filePath: string): Promise<string> => {
        const open = openFiles.find(f => f.path === filePath);
        if (open) return open.content;

        if (window.electronAPI?.fs) {
            return await window.electronAPI.fs.readFile(filePath);
        }

        const response = await fetch(`http://localhost:8000/api/read-file?path=${encodeURIComponent(filePath)}`);
        if (!response.ok) {
            throw new Error(`Failed to read file: ${filePath}`);
        }
        const data = await response.json();
        return data.content || '';
    };

    const ensureOpenFile = async (filePath: string): Promise<void> => {
        if (openFiles.some(f => f.path === filePath)) return;
        const name = filePath.split(/[\\/]/).pop() || filePath;
        const content = await readFileContent(filePath);
        setOpenFiles(prev => {
            if (prev.some(f => f.path === filePath)) return prev;
            return [...prev, { path: filePath, name, content, language: getLanguage(name), modified: false }];
        });
    };

    const resolvePlanPath = (planPath: string): string => {
        const raw = (planPath || '').trim();
        if (!raw) return raw;
        const normalized = raw.replace(/\//g, '\\');
        const isAbsWin = /^[a-zA-Z]:\\/.test(normalized);
        if (isAbsWin) return normalized;
        if (rootPath) return `${rootPath}\\${normalized}`;
        return normalized;
    };

    const extractFirstCodeBlock = (text: string): string | null => {
        const m = /```(?:\w+)?\n([\s\S]*?)```/m.exec(text || '');
        if (!m) return null;
        return (m[1] || '').trim();
    };

    const createUnifiedDiffForNewFile = (filePath: string, content: string): string => {
        const lines = (content ?? '').replace(/\r\n/g, '\n').split('\n');
        const newCount = content.length === 0 ? 0 : lines.length;
        const header = [
            `--- ${filePath}`,
            `+++ ${filePath}`,
            `@@ -0,0 +1,${newCount} @@`,
        ];
        const body = lines.map(l => `+${l}`);
        return [...header, ...body].join('\n');
    };

    const generateNewFileContent = async (plan: ImplementationPlan, filePath: string, requestText: string): Promise<string> => {
        setEditorStage('generating_patch');
        setStageMessage(`Generating new file: ${filePath.split(/[\\/]/).pop() || filePath}...`);

        const response = await fetch('http://localhost:8000/api/code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: `You are an AI coding agent inside an IDE.

Generate ONLY the complete contents for this NEW file.

File path: ${filePath}
Language hint: ${getLanguage(filePath)}

Plan objective: ${plan.objective}
User request: ${requestText}

Rules:
- Output ONLY the file contents.
- No markdown.
- No explanations.
`,
                ...(selectedLlmModel !== 'auto' ? { model_name: selectedLlmModel } : {})
            })
        });

        const data = await response.json();
        const raw = String(data?.response ?? '').trim();
        const codeBlock = extractFirstCodeBlock(raw);
        const content = (codeBlock ?? raw).replace(/\r\n/g, '\n');
        if (!content.trim()) throw new Error(`Generated new file is empty: ${filePath}`);
        return content.endsWith('\n') ? content : content + '\n';
    };

    const safeJsonParse = <T,>(text: string): T | null => {
        try {
            return JSON.parse(text) as T;
        } catch {
            return null;
        }
    };

    const generateImplementationPlan = async (requestText: string, filePath: string, fileContent: string, signal?: AbortSignal) => {
        setEditorStage('planning');
        setStageMessage('Generating implementation plan...');

        const response = await fetch('http://localhost:8000/api/code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            ...(signal ? { signal } : {}),
            body: JSON.stringify({
                message: `You are an AI coding agent inside an IDE. Produce a structured implementation plan as STRICT JSON (no markdown, no commentary).

Return exactly this shape:
{
  "objective": string,
  "files_to_modify": string[],
  "new_files": string[],
  "dependencies_affected": string[],
  "risk_level": "low"|"medium"|"high",
  "test_plan": string,
  "rollback_strategy": string
}

Workspace context:
- Active file: ${filePath}
- Active file content (truncated):\n${fileContent.slice(0, 4000)}

User request: ${requestText}
`,
                ...(selectedLlmModel !== 'auto' ? { model_name: selectedLlmModel } : {})
            })
        });

        const data = await response.json();
        const raw = (data?.response ?? '').trim();
        const plan = safeJsonParse<ImplementationPlan>(raw);
        if (!plan || !plan.objective) {
            throw new Error('Plan generation failed: model did not return valid JSON');
        }
        return plan;
    };

    const generatePatchForFile = async (plan: ImplementationPlan, filePath: string, fileContent: string, originalMessage: string) => {
        const language = getLanguage(filePath);
        const name = filePath.split(/[\\/]/).pop() || filePath;

        setEditorStage('generating_patch');
        setStageMessage(`Generating deterministic patch for ${name}...`);

        const response = await fetch('http://localhost:8000/api/copilot/refactor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_content: fileContent,
                cursor_line: editorRef.current?.getPosition()?.lineNumber || 1,
                cursor_column: editorRef.current?.getPosition()?.column || 1,
                language,
                file_path: filePath,
                // Force full-file replace in backend (deterministic string replace)
                selection: fileContent,
                user_input: `${plan.objective}\n\nUser request: ${originalMessage}`,
                ...(selectedLlmModel !== 'auto' ? { model_name: selectedLlmModel } : {}),
            })
        });

        const data = await response.json();
        if (!data?.diff) throw new Error('No diff returned');

        setEditorStage('validating');
        setStageMessage('Validating patch applies cleanly...');

        let patchedContent: string;
        try {
            patchedContent = applyUnifiedDiff(fileContent, data.diff);
        } catch (e: any) {
            const msg = e instanceof UnifiedDiffApplyError ? e.message : String(e?.message ?? e);
            throw new Error(`Diff validation failed: ${msg}`);
        }

        const changedLineNumbers = extractChangedLineNumbers(data.diff);

        return {
            filePath,
            originalContent: fileContent,
            patchedContent,
            unifiedDiff: data.diff,
            proposalId: data.proposal_id,
            changedLineNumbers,
        } satisfies PatchEntry;
    };

    const createNewFile = async (name: string, content: string, lang: string) => {
        // Copilot-class rule: AI never writes to disk silently.
        // New files are created in the editor buffer and must be explicitly saved by the user.

        const filePath = rootPath
            ? `${rootPath}\\${name.replace(/\//g, '\\')}`
            : `unsaved/${name}`;

        setOpenFiles(prev => {
            // avoid duplicate tabs
            if (prev.some(f => f.path === filePath)) return prev;
            return [...prev, { path: filePath, name, content, language: lang, modified: true }];
        });
        setActiveFile(filePath);

        // Show in explorer sidebar
        insertFileIntoTree(filePath);

        setAgentMessages(prev => [...prev, {
            role: 'agent',
            text: rootPath
                ? `📄 Created ${name} in editor (pending save). Use Ctrl+S to write to disk.`
                : `⚠️ No folder selected. Created ${name} in editor only (pending save).`
        }]);
    };

    const saveFileToBackend = async (path: string, content: string, filename?: string) => {
        try {
            const saveDir = rootPath || 'D:\\All Projects\\My AI Agent\\generated';

            // Use Electron API if available
            if (window.electronAPI?.fs) {
                const targetPath = filename ? `${saveDir}\\${filename}` : path;
                await window.electronAPI.fs.writeFile(targetPath, content);

                setOpenFiles(prev => prev.map(f => f.path === path ? { ...f, modified: false } : f));
                console.log('✅ File saved via Electron:', targetPath);

                // Refresh file tree if needed
                if (rootPath) refreshFileTree();
                return;
            }

            // Fallback to backend API
            const response = await fetch('http://localhost:8000/api/save-file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    path: rootPath ? path : `generated/${filename || path.split('/').pop()}`,
                    content,
                    directory: saveDir
                })
            });
            if (response.ok) {
                setOpenFiles(prev => prev.map(f => f.path === path ? { ...f, modified: false } : f));
                console.log('File saved to:', saveDir);
                // Refresh file tree if we have a selected folder
                if (rootHandleRef.current) {
                    refreshFileTree();
                }
            }
        } catch (err) {
            console.error('Failed to save file:', err);
        }
    };

    const refreshFileTree = async () => {
        if (!rootPath) return;

        try {
            // Use Electron API if available
            if (window.electronAPI?.fs) {
                const entries = await window.electronAPI.fs.listDir(rootPath);
                const children: FileNode[] = entries.map(entry => ({
                    name: entry.name,
                    path: entry.path,
                    type: entry.type === 'directory' ? 'folder' : 'file',
                    children: entry.type === 'directory' ? [] : undefined,
                    expanded: false,
                }));

                children.sort((a, b) => {
                    if (a.type === 'folder' && b.type !== 'folder') return -1;
                    if (a.type !== 'folder' && b.type === 'folder') return 1;
                    return a.name.localeCompare(b.name);
                });

                setFileTree(children);
                console.log('📁 File tree refreshed:', children.length, 'items');
            } else if (rootHandleRef.current) {
                // Fallback to browser File System Access API
                const children: FileNode[] = [];
                // @ts-ignore
                for await (const entry of rootHandleRef.current.values()) {
                    children.push({
                        name: entry.name,
                        path: entry.name,
                        type: entry.kind === 'directory' ? 'folder' : 'file',
                        handle: entry
                    });
                }
                children.sort((a, b) => {
                    if (a.type === 'folder' && b.type !== 'folder') return -1;
                    if (a.type !== 'folder' && b.type === 'folder') return 1;
                    return a.name.localeCompare(b.name);
                });
                setFileTree(children);
            }
        } catch (err) {
            console.error('Failed to refresh file tree:', err);
        }
    };

    const saveCurrentFile = () => {
        if (currentFile) {
            console.log('💾 Manual Save Triggered via Ctrl+S');
            saveFileToBackend(currentFile.path, currentFile.content);
        } else {
            console.log('⚠️ No active file to save');
        }
    };

    // Update ref for keyboard shortcuts
    useEffect(() => {
        saveFunctionRef.current = saveCurrentFile;
    }, [saveCurrentFile]);

    const sendToAgent = async () => {
        if (!agentInput.trim()) return;
        const originalMessage = agentInput;  // Save before clearing
        const userMessage = agentInput.toLowerCase();
        setAgentMessages(prev => [...prev, { role: 'user', text: originalMessage }]);
        setAgentInput('');
        setIsLoading(true);

        // Check for calculator request - use built-in template (Legacy)
        if (userMessage.includes('calculator')) {
            // ... existing calculator logic ...
            // (Keeping it but removing auto-save if inside createNewFile)
        }

        // Intelligent Intent Classification & Routing
        try {
            const current = openFiles.find(f => f.path === activeFile);

            // 1. Ask the LLM to classify the intent
            const controller = new AbortController();
            abortControllerRef.current = controller;

            const intentResponse = await fetch('http://localhost:8000/api/code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                signal: controller.signal,
                body: JSON.stringify({
                    message: `Analyze this user request: "${originalMessage}"
                    
Reply with exactly ONE word from this list:
- "MODIFY" (if they are asking to change, refactor, rewrite, add to, or delete from existing code/files)
- "CREATE" (if they are asking to build, generate, or write a NEW file or project from scratch)
- "EXPLAIN" (if they are asking how something works, or to explain code)
- "CHAT" (if they are just saying hi, asking a general question, or anything else)`,
                    ...(selectedLlmModel !== 'auto' ? { model_name: selectedLlmModel } : {})
                })
            });

            if (!intentResponse.ok) throw new Error('Failed to classify intent');

            const intentData = await intentResponse.json();
            const intentText = (intentData?.response || '').trim().toUpperCase();

            const intent = intentText.includes('MODIFY') ? 'MODIFY' :
                intentText.includes('CREATE') ? 'CREATE' :
                    intentText.includes('EXPLAIN') ? 'EXPLAIN' : 'CHAT';

            console.log(`🧠 Intent detected: ${intent}`);

            // 2. Route based on intent
            if (intent === 'MODIFY' || intent === 'CREATE') {
                setAgentMessages(prev => [...prev, { role: 'agent', text: '🔍 Scanning project and creating implementation plan...' }]);

                const planController = new AbortController();
                abortControllerRef.current = planController;

                const proposeResponse = await fetch('http://localhost:8000/api/agent/propose_edit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    signal: planController.signal,
                    body: JSON.stringify({
                        instruction: originalMessage,
                        active_file: current?.path
                    })
                });

                if (!proposeResponse.ok) {
                    throw new Error(await proposeResponse.text() || 'Failed to generate patch');
                }

                const proposeData = await proposeResponse.json();

                // ── Plan Approval Flow ──
                if (proposeData.intent === 'plan_awaiting_approval') {
                    const planText = proposeData.explanation || 'No plan details available.';
                    const threadId = proposeData.proposal_id || '';

                    setAgentMessages(prev => [...prev, {
                        role: 'agent',
                        text: `📋 **Implementation Plan**\n\n${planText}\n\n---\n*Click **Approve** to execute this plan, or **Reject** to cancel.*`
                    }]);

                    // Show approve/reject buttons by setting a pending plan state
                    setIsLoading(false);

                    // Create approval handler that will be called when user clicks approve
                    const handleApproval = async (approved: boolean) => {
                        setIsLoading(true);
                        setAgentMessages(prev => {
                            const updatedMessages = [...prev];
                            // Find the latest plan message and remove the action prompt
                            for (let i = updatedMessages.length - 1; i >= 0; i--) {
                                if (updatedMessages[i].role === 'agent' && updatedMessages[i].text.includes('Implementation Plan')) {
                                    updatedMessages[i] = { 
                                        ...updatedMessages[i], 
                                        text: updatedMessages[i].text.replace('*Click **Approve** to execute this plan, or **Reject** to cancel.*', `*Plan ${approved ? 'Accepted' : 'Declined'}*`)
                                    };
                                    break;
                                }
                            }
                            updatedMessages.push({
                                role: 'agent',
                                text: approved ? '✅ Plan approved! Implementing changes...' : '❌ Plan rejected.'
                            });
                            return updatedMessages;
                        });

                        if (!approved) {
                            setIsLoading(false);
                            return;
                        }

                        try {
                            const execController = new AbortController();
                            abortControllerRef.current = execController;

                            const execResponse = await fetch('http://localhost:8000/api/agent/approve_plan', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                signal: execController.signal,
                                body: JSON.stringify({
                                    thread_id: threadId,
                                    approved: true,
                                    active_file: current?.path
                                })
                            });

                            if (!execResponse.ok) {
                                throw new Error(await execResponse.text() || 'Execution failed');
                            }

                            const execData = await execResponse.json();

                            if (execData.patches && execData.patches.length > 0) {
                                // Apply patches same as before
                                const mappedPatches: PatchEntry[] = [];
                                const changedLinesMap: Record<string, number[]> = {};
                                const changed = new Set<string>();

                                for (const p of execData.patches) {
                                    const filePath = p.file_path;
                                    let originalContent = '';
                                    const f = openFiles.find(xf => xf.path === filePath);
                                    if (f) originalContent = f.content;
                                    else if (!p.is_new) {
                                        try {
                                            originalContent = await readFileContent(filePath);
                                        } catch (e) { }
                                    }

                                    const patchedContent = p.new_content || '';
                                    const lineNums = Array.from({ length: patchedContent.split('\n').length }, (_, i) => i + 1);

                                    mappedPatches.push({
                                        filePath,
                                        originalContent,
                                        patchedContent,
                                        unifiedDiff: p.diff,
                                        proposalId: execData.proposal_id || undefined,
                                        changedLineNumbers: p.is_new ? lineNums : [],
                                        isNewFile: p.is_new,
                                    } as PatchEntry);

                                    changedLinesMap[filePath] = lineNums;
                                    changed.add(filePath);

                                    const name = filePath.split(/[\\/]/).pop() || filePath;
                                    setOpenFiles(prev => {
                                        if (prev.some(xf => xf.path === filePath)) {
                                            return prev.map(xf => xf.path === filePath ? { ...xf, content: patchedContent, modified: true } : xf);
                                        }
                                        return [...prev, { path: filePath, name, content: patchedContent, language: getLanguage(name), modified: true }];
                                    });

                                    insertFileIntoTree(filePath);
                                }

                                setPendingPatches(mappedPatches);
                                setChangedFiles(changed);
                                setAiChangedLinesByFile(changedLinesMap);

                                setAgentMessages(prev => [...prev, {
                                    role: 'agent',
                                    text: `✅ Implementation complete! Modified ${execData.patches.length} file(s).\n\n${execData.explanation || ''}`
                                }]);
                            } else {
                                setAgentMessages(prev => [...prev, {
                                    role: 'agent',
                                    text: execData.explanation || 'Plan executed but no file changes were made.'
                                }]);
                            }
                        } catch (execErr: any) {
                            setAgentMessages(prev => [...prev, {
                                role: 'agent',
                                text: `❌ Execution failed: ${execErr.message}`
                            }]);
                        } finally {
                            setIsLoading(false);
                        }
                    };

                    // Store the handler for the UI buttons
                    (window as any).__pendingPlanApproval = handleApproval;
                    return;
                }

                if (!proposeData.patches || proposeData.patches.length === 0) {
                    setAgentMessages(prev => [...prev, { role: 'agent', text: proposeData.explanation || 'Done, but no file changes were made.' }]);
                    setIsLoading(false);
                    return;
                }

                const mappedPatches: PatchEntry[] = [];
                const changedLinesMap: Record<string, number[]> = {};
                const changed = new Set<string>();

                for (const p of proposeData.patches) {
                    const filePath = p.file_path;
                    let originalContent = '';
                    const f = openFiles.find(xf => xf.path === filePath);
                    if (f) originalContent = f.content;
                    else if (!p.is_new) {
                        try {
                            originalContent = await readFileContent(filePath);
                        } catch (e) { }
                    }

                    const patchedContent = p.new_content || '';
                    const lineNums = Array.from({ length: patchedContent.split('\n').length }, (_, i) => i + 1);

                    mappedPatches.push({
                        filePath,
                        originalContent,
                        patchedContent,
                        unifiedDiff: p.diff,
                        proposalId: proposeData.proposal_id || undefined,
                        changedLineNumbers: p.is_new ? lineNums : [],
                        isNewFile: p.is_new,
                    } as PatchEntry);

                    changedLinesMap[filePath] = lineNums;
                    changed.add(filePath);

                    const name = filePath.split(/[\\/]/).pop() || filePath;
                    setOpenFiles(prev => {
                        if (prev.some(xf => xf.path === filePath)) {
                            return prev.map(xf => xf.path === filePath ? { ...xf, content: patchedContent, modified: true } : xf);
                        }
                        return [...prev, { path: filePath, name, content: patchedContent, language: getLanguage(name), modified: true }];
                    });

                    insertFileIntoTree(filePath);
                }

                setPendingPatches(mappedPatches);
                setAiChangedLinesByFile(changedLinesMap);
                setChangedFiles(changed);
                setLastRefactorRequest(originalMessage);

                if (mappedPatches.length > 0) {
                    setActiveFile(mappedPatches[0].filePath);
                }

                setEditorStage('waiting_for_patch_approval');
                setStageMessage('Review the changes generated by the agent.');
                setAgentMessages(prev => [...prev, { role: 'agent', text: `✅ I've made changes to ${mappedPatches.length} file(s). Please review and accept/reject them in the editor.` }]);

            } else if (intent === 'EXPLAIN') {
                // Route to Explain workflow
                if (!current) {
                    setAgentMessages(prev => [...prev, { role: 'agent', text: 'Please open a file to explain.' }]);
                    setIsLoading(false);
                    return;
                }

                const editorInstance = editorRef.current;
                const sel = editorInstance?.getSelection();
                const editorModel = editorInstance?.getModel();
                let selectedText = '';
                if (sel && editorModel && !sel.isEmpty()) {
                    selectedText = editorModel.getValueInRange(sel);
                }

                const codeToExplain = selectedText || current.content.slice(0, 6000);

                let explanation = '';
                try {
                    const response = await fetch('http://localhost:8000/api/copilot/explain', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            file_content: current.content,
                            cursor_line: editorInstance?.getPosition()?.lineNumber || 1,
                            cursor_column: editorInstance?.getPosition()?.column || 1,
                            selection: selectedText || undefined,
                            language: current.language,
                            file_path: current.path,
                            user_input: originalMessage,
                            ...(selectedLlmModel !== 'auto' ? { model_name: selectedLlmModel } : {})
                        }),
                        signal: controller.signal,
                    });

                    if (response.ok) {
                        const data = await response.json();
                        explanation = data?.explanation || data?.response || '';
                    }
                } catch (e) {
                    // Fallback handled below
                }

                if (!explanation) {
                    const fallbackResponse = await fetch('http://localhost:8000/api/code', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        signal: controller.signal,
                        body: JSON.stringify({
                            message: `Explain the following code clearly and concisely. Describe what it does, key components, and any notable patterns or issues.\n\nFile: ${current.name}\n\`\`\`${current.language}\n${codeToExplain}\n\`\`\`\n\nUser question: ${originalMessage}`,
                            ...(selectedLlmModel !== 'auto' ? { model_name: selectedLlmModel } : {})
                        })
                    });
                    const fallbackData = await fallbackResponse.json();
                    explanation = fallbackData?.response || 'Could not generate explanation.';
                }

                setAgentMessages(prev => [...prev, { role: 'agent', text: `📖 **Explanation:**\n\n${explanation}` }]);

            } else {
                // Route to Chat workflow
                const context = current ? `\nOPEN FILE: ${current.name}\n\`\`\`${current.language}\n${current.content.slice(0, 1500)}\n\`\`\`` : '';

                const chatResponse = await fetch('http://localhost:8000/api/code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    signal: controller.signal,
                    body: JSON.stringify({
                        message: `You are an expert AI coding assistant embedded in an IDE. Answer the user's question clearly and concisely. 
                        
${context}

USER REQUEST: ${originalMessage}`,
                        ...(selectedLlmModel !== 'auto' ? { model_name: selectedLlmModel } : {})
                    })
                });

                const data = await chatResponse.json();
                const text = data.response || 'No response received';
                setAgentMessages(prev => [...prev, { role: 'agent', text }]);
            }

        } catch (err: any) {
            if (err.name === 'AbortError') {
                setAgentMessages(prev => [...prev, { role: 'agent', text: '⏹ Request stopped.' }]);
                setEditorStage('idle');
            } else {
                console.error('Agent error:', err);
                setAgentMessages(prev => [...prev, { role: 'agent', text: `Error: ${err.message || 'Unknown error'}. Is the server running?` }]);
            }
        } finally {
            abortControllerRef.current = null;
            setIsLoading(false);
        }
    };

    const handleApprovePlan = async () => {
        if (!pendingPlan) return;

        // Capture plan before closing the modal so the async work uses a stable reference
        const approvedPlan = pendingPlan;

        // Close the plan panel IMMEDIATELY so the editor is visible during generation
        setShowPlanModal(false);

        try {
            setPendingPatches([]);
            setAiChangedLinesByFile({});
            clearAIDecorations();

            // Determine which files to patch (modify) and which to create (new)
            const allModify = Array.from(new Set((approvedPlan.files_to_modify || []).map(resolvePlanPath).filter(Boolean)));
            const allNew = Array.from(new Set((approvedPlan.new_files || []).map(resolvePlanPath).filter(Boolean)));

            // Check which "modify" targets actually exist; move missing ones to the new-file list
            const existingTargets: string[] = [];
            const newFileTargets: string[] = [...allNew];
            for (const fp of allModify) {
                if (await fileExistsOnDisk(fp)) {
                    existingTargets.push(fp);
                } else if (!newFileTargets.includes(fp)) {
                    newFileTargets.push(fp);
                }
            }

            const totalTargets = existingTargets.length + newFileTargets.length;
            if (totalTargets === 0) {
                setAgentMessages(prev => [...prev, { role: 'agent', text: 'Plan contains no files to modify or create.' }]);
                return;
            }

            setAgentMessages(prev => [...prev, {
                role: 'agent',
                text: `🔄 Plan approved. Generating patches for ${existingTargets.length} existing file${existingTargets.length !== 1 ? 's' : ''}${newFileTargets.length > 0 ? ` and ${newFileTargets.length} new file${newFileTargets.length !== 1 ? 's' : ''}` : ''}...`
            }]);

            const patches: PatchEntry[] = [];
            const changedLinesMap: Record<string, number[]> = {};
            const changed = new Set<string>();

            // --- Process existing files (generate diff patches) ---
            for (const filePath of existingTargets) {
                await ensureOpenFile(filePath);
                const content = await readFileContent(filePath);

                // Snapshot for revert
                editorStateRef.current.addSnapshot(filePath, content);

                const patch = await generatePatchForFile(approvedPlan, filePath, content, lastRefactorRequest);
                patches.push(patch);
                changedLinesMap[filePath] = patch.changedLineNumbers;
                changed.add(filePath);

                // Apply to buffer (still not disk)
                setOpenFiles(prev => prev.map(f => f.path === filePath ? { ...f, content: patch.patchedContent, modified: true } : f));
            }

            // --- Process new files (generate from scratch) ---
            for (const filePath of newFileTargets) {
                const newContent = await generateNewFileContent(approvedPlan, filePath, lastRefactorRequest);
                const name = filePath.split(/[\\/]/).pop() || filePath;
                const diff = createUnifiedDiffForNewFile(filePath, newContent);
                const lineNums = Array.from({ length: newContent.split('\n').length }, (_, i) => i + 1);

                patches.push({
                    filePath,
                    originalContent: '',
                    patchedContent: newContent,
                    unifiedDiff: diff,
                    proposalId: undefined,
                    changedLineNumbers: lineNums,
                    isNewFile: true,
                } as PatchEntry);
                changedLinesMap[filePath] = lineNums;
                changed.add(filePath);

                // Open the new file in a tab
                setOpenFiles(prev => {
                    if (prev.some(f => f.path === filePath)) return prev;
                    return [...prev, { path: filePath, name, content: newContent, language: getLanguage(name), modified: true }];
                });

                // Add to the explorer file tree so it's visible in the sidebar
                insertFileIntoTree(filePath);
            }

            setPendingPatches(patches);
            setAiChangedLinesByFile(changedLinesMap);
            setChangedFiles(changed);

            // Navigate to the first modified file so the user sees inline changes
            const firstTarget = existingTargets[0] || newFileTargets[0];
            if (firstTarget) {
                setActiveFile(firstTarget);
            }

            // Apply decorations on the active file
            const fileToDecorate = firstTarget || activeFile;
            if (fileToDecorate && changedLinesMap[fileToDecorate]) {
                // Small delay to let the editor mount the new file content
                setTimeout(() => {
                    applyAIDecorations(changedLinesMap[fileToDecorate]);
                }, 100);
            }

            setEditorStage('waiting_for_patch_approval');
            setStageMessage('Review changes in the editor. Accept or reject from the toolbar above.');
            setAgentMessages(prev => [...prev, {
                role: 'agent',
                text: `✅ Patches generated for ${patches.length} file${patches.length > 1 ? 's' : ''}. Review the highlighted changes in the editor and use the toolbar to Accept or Reject.`
            }]);
        } catch (e: any) {
            setEditorStage('error');
            setStageMessage('');
            setAgentMessages(prev => [...prev, { role: 'agent', text: `Patch error: ${e.message || e}` }]);
        }
    };

    const handleRejectPlan = () => {
        setPendingPlan(null);
        setShowPlanModal(false);
        setEditorStage('idle');
        setStageMessage('');
    };

    const handleRejectPatch = () => {
        if (pendingPatches.length === 0) {
            setDiffPreviewOpen(false);
            return;
        }
        clearAIDecorations();
        setOpenFiles(prev => prev.map(f => {
            const p = pendingPatches.find(pp => pp.filePath === f.path);
            if (!p) return f;
            return { ...f, content: p.originalContent, modified: false };
        }));
        setPendingPatches([]);
        setPendingPlan(null);
        setShowPlanModal(false);
        setChangedFiles(new Set());
        setAiChangedLinesByFile({});
        setDiffPreviewOpen(false);
        setEditorStage('idle');
        setStageMessage('');
    };

    const handleApplyPatchSet = async (proposalIdsToApply: string[]) => {
        const ids = (proposalIdsToApply || []).filter(Boolean);
        try {
            setEditorStage('applying');
            setStageMessage('Applying patch to disk (approved)...');
            for (const proposalId of ids) {
                const response = await fetch('http://localhost:8000/api/copilot/apply-diff', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ proposal_id: proposalId, user_approved: true })
                });
                if (!response.ok) {
                    const text = await response.text();
                    throw new Error(text || `HTTP ${response.status}`);
                }
            }

            // Save new files and manual edits (no proposal_id) explicitly on Apply
            const manualSaveFiles = pendingPatches.filter(p => !p.proposalId);
            for (const nf of manualSaveFiles) {
                if (!rootPath) {
                    setAgentMessages(prev => [...prev, { role: 'agent', text: `⚠️ Cannot save ${nf.filePath} to disk: no folder selected.` }]);
                    continue;
                }
                await saveFileToBackend(nf.filePath, nf.patchedContent);
            }

            // Mark patched files with proposals as clean
            const patchedByProposal = new Set(pendingPatches.filter(p => p.proposalId && ids.includes(p.proposalId)).map(p => p.filePath));
            const manualSavePaths = new Set(manualSaveFiles.map(n => n.filePath));
            setOpenFiles(prev => prev.map(f => (patchedByProposal.has(f.path) || manualSavePaths.has(f.path)) ? { ...f, modified: false } : f));
            pendingPatches.forEach(p => {
                if (p.proposalId && ids.includes(p.proposalId)) editorStateRef.current.recordAppliedPatch(p);
            });

            clearAIDecorations();
            setChangedFiles(new Set());
            setAiChangedLinesByFile({});
            setPendingPatches([]);
            setPendingPlan(null);
            setShowPlanModal(false);
            setDiffPreviewOpen(false);
            setEditorStage('completed');
            setStageMessage('Patch applied.');
        } catch (e: any) {
            setEditorStage('error');
            setStageMessage('');
            setAgentMessages(prev => [...prev, { role: 'agent', text: `Apply error: ${e.message || e}` }]);
        }
    };

    const handleApplySinglePatch = async (filePath: string) => {
        const patch = pendingPatches.find(p => p.filePath === filePath);
        if (!patch) return;

        try {
            setEditorStage('applying');
            setStageMessage(`Applying ${filePath.split(/[\\/]/).pop() || filePath} to disk (approved)...`);

            if (patch.proposalId) {
                const response = await fetch('http://localhost:8000/api/copilot/apply-diff', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ proposal_id: patch.proposalId, user_approved: true })
                });
                if (!response.ok) {
                    const text = await response.text();
                    throw new Error(text || `HTTP ${response.status}`);
                }
                editorStateRef.current.recordAppliedPatch(patch);
            } else if (patch.isNewFile) {
                if (!rootPath) {
                    throw new Error('Cannot save new file to disk: no folder selected');
                }
                await saveFileToBackend(patch.filePath, patch.patchedContent);
            } else {
                if (!rootPath) {
                    throw new Error('Cannot save manually edited file to disk: no folder selected');
                }
                await saveFileToBackend(patch.filePath, patch.patchedContent);
            }

            // Mark file clean and remove from pending list
            setOpenFiles(prev => prev.map(f => f.path === filePath ? { ...f, modified: false } : f));
            setPendingPatches(prev => prev.filter(p => p.filePath !== filePath));
            setChangedFiles(prev => {
                const next = new Set(prev);
                next.delete(filePath);
                return next;
            });
            setAiChangedLinesByFile(prev => {
                const next = { ...prev };
                delete next[filePath];
                return next;
            });
            if (activeFile === filePath) {
                clearAIDecorations();
            }

            // Close modal if nothing pending
            const remaining = pendingPatches.filter(p => p.filePath !== filePath);
            if (remaining.length === 0) {
                setPendingPlan(null);
                setShowPlanModal(false);
                setDiffPreviewOpen(false);
                setEditorStage('completed');
                setStageMessage('All patches applied.');
            } else {
                setEditorStage('waiting_for_patch_approval');
                setStageMessage('Remaining patches pending approval...');
            }
        } catch (e: any) {
            setEditorStage('error');
            setStageMessage('');
            setAgentMessages(prev => [...prev, { role: 'agent', text: `Apply error: ${e.message || e}` }]);
        }
    };

    const handleAgentSubmit = () => {
        if (isLoading) return;
        void sendToAgent();
    };

    const handleStop = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        setIsLoading(false);
        setEditorStage('idle');
        setStageMessage('');
    };



    const renderTree = (nodes: FileNode[], level = 0) => {
        return nodes.map((node) => (
            <div key={node.path} className="flex flex-col">
                <div
                    className={`flex items-center py-1.5 px-4 cursor-pointer transition-all duration-200 border-l-2 ${activeFile === node.path
                        ? 'text-gray-200 bg-blue-500/10 border-blue-500'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border-transparent'
                        }`}
                    style={{ paddingLeft: `${Math.max(1, level + 1) * 12}px` }}
                    onClick={(e) => {
                        e.stopPropagation();
                        if (node.type === 'folder') toggleFolder(node);
                        else openFile(node);
                    }}
                >
                    {node.type === 'folder' && (
                        <span className={`material-symbols-outlined text-[16px] mr-1.5 text-gray-500 transform transition-transform duration-200 ${node.expanded ? 'rotate-90' : ''}`}>chevron_right</span>
                    )}
                    {!node.type || node.type === 'file' ? (
                        <span className={`material-symbols-outlined text-[16px] mr-2 ${getFileIconColor(node.name)}`}>{getFileIcon(node.name)}</span>
                    ) : node.type === 'folder' ? (
                        <span className={`material-symbols-outlined text-[16px] mr-2 ${node.expanded ? 'text-blue-400' : 'text-blue-400/80'}`}>{node.expanded ? 'folder_open' : 'folder'}</span>
                    ) : null}

                    <span className="text-[13px] tracking-tight flex items-center gap-2 flex-1 min-w-0">
                        <span className="truncate">{node.name}</span>
                    </span>
                    {node.type === 'file' && changedFiles.has(node.path) && (
                        <span className="ml-auto shrink-0 w-4 h-4 rounded flex items-center justify-center text-[10px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/25" title="AI changes pending">
                            M
                        </span>
                    )}
                </div>
                {node.type === 'folder' && node.expanded && node.children && (
                    <div className="flex flex-col">
                        {renderTree(node.children, level + 1)}
                    </div>
                )}
            </div>
        ));
    };

    const getFileIcon = (filename: string) => {
        const ext = filename.split('.').pop()?.toLowerCase();
        if (ext === 'js') return 'javascript';
        if (ext === 'css') return 'css';
        if (ext === 'html') return 'html';
        return 'description';
    };

    const getFileIconColor = (filename: string) => {
        const ext = filename.split('.').pop()?.toLowerCase();
        if (ext === 'js') return 'text-yellow-500/80';
        if (ext === 'css') return 'text-blue-400/80';
        if (ext === 'html') return 'text-orange-500/90';
        return 'text-gray-600';
    };

    return (
        <div className="obsidian-pro fixed inset-0 z-[99999] bg-[#050505] text-gray-400 overflow-hidden flex flex-col antialiased selection:bg-primary/30 selection:text-white dark">
            <div className="h-9 flex items-center justify-between px-3 glass-header z-50 shrink-0 select-none">
                <div className="flex items-center shrink-0">
                    <div className="flex items-center space-x-2 mr-6 opacity-60 hover:opacity-100 transition-opacity">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f56] cursor-pointer" onClick={onClose}></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-[#ffbd2e]"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-[#27c93f]"></div>
                    </div>
                    <div className="hidden md:flex items-center space-x-5 text-[11px] tracking-wide font-light text-gray-500">
                        <span
                            className="hover:text-gray-200 cursor-pointer transition-colors duration-200"
                            onClick={() => handleSelectFolder()}
                            title="Open Folder"
                        >
                            File
                        </span>
                        <span
                            className="hover:text-gray-200 cursor-pointer transition-colors duration-200"
                            onClick={() => saveFunctionRef.current()}
                            title="Save"
                        >
                            Edit
                        </span>
                        <span
                            className="hover:text-gray-200 cursor-pointer transition-colors duration-200"
                            onClick={() => setTerminalOpen(prev => !prev)}
                            title="Toggle Terminal"
                        >
                            View
                        </span>
                        <span className="hover:text-gray-200 cursor-pointer transition-colors duration-200" title="(Not wired)">
                            Go
                        </span>
                        <span
                            className="hover:text-gray-200 cursor-pointer transition-colors duration-200"
                            onClick={() => setTerminalOpen(true)}
                            title="Open Terminal"
                        >
                            Run
                        </span>
                    </div>
                </div>
                <div className="flex-1 flex items-center justify-center pointer-events-none">
                    <div className="flex items-center space-x-2 text-[10px] font-mono tracking-wider opacity-100">
                        <span className="material-symbols-outlined text-[14px] text-gray-500">deployed_code</span>
                        <span className="text-gray-400">obsidian_pro</span>
                        <span className="text-gray-700">/</span>
                        <span className="text-gray-500">src</span>
                        <span className="text-gray-700">/</span>
                        <span className="text-gray-200">{activeFile ? activeFile.split(/[\\/]/).pop() : 'main.rs'}</span>
                    </div>
                </div>
                <div className="flex items-center space-x-4 text-gray-600 shrink-0">
                    <span className="material-symbols-outlined text-[16px] cursor-pointer hover:text-gray-300 transition-colors" onClick={() => setShowSidebar(!showSidebar)}>tune</span>
                    <div className="w-px h-3 bg-gray-800"></div>
                    <span className="material-symbols-outlined text-[16px] cursor-pointer hover:text-gray-300 transition-colors" onClick={() => setShowAgent(!showAgent)}>notifications</span>
                    <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-gray-700 to-gray-800 border border-gray-700 flex items-center justify-center">
                        <span className="text-[9px] text-white font-medium">OP</span>
                    </div>
                </div>
            </div>
            <div className="flex flex-1 overflow-hidden relative">
                {/* Activity Bar (VS Code-style left edge icons) */}
                <div className="w-12 bg-[#0a0a0c] border-r border-gray-800/50 flex flex-col items-center py-2 gap-1 shrink-0">
                    <button
                        onClick={() => { setShowSidebar(true); setActiveSidebarTab('explorer'); }}
                        className={`w-10 h-10 flex items-center justify-center rounded-lg transition-all ${showSidebar && activeSidebarTab === 'explorer'
                            ? 'text-white border-l-2 border-primary bg-white/5'
                            : 'text-gray-500 hover:text-gray-300 border-l-2 border-transparent'
                            }`}
                        title="Explorer"
                    >
                        <span className="material-symbols-outlined text-[20px]">folder_open</span>
                    </button>
                    <button
                        onClick={() => { setShowSidebar(true); setActiveSidebarTab('extensions'); }}
                        className={`w-10 h-10 flex items-center justify-center rounded-lg transition-all ${showSidebar && activeSidebarTab === 'extensions'
                            ? 'text-white border-l-2 border-primary bg-white/5'
                            : 'text-gray-500 hover:text-gray-300 border-l-2 border-transparent'
                            }`}
                        title="Extensions"
                    >
                        <span className="material-symbols-outlined text-[20px]">extension</span>
                    </button>
                    <button
                        onClick={() => { /* search - future */ }}
                        className="w-10 h-10 flex items-center justify-center rounded-lg text-gray-500 hover:text-gray-300 border-l-2 border-transparent transition-all"
                        title="Search"
                    >
                        <span className="material-symbols-outlined text-[20px]">search</span>
                    </button>
                    <button
                        onClick={() => { /* git - future */ }}
                        className="w-10 h-10 flex items-center justify-center rounded-lg text-gray-500 hover:text-gray-300 border-l-2 border-transparent transition-all"
                        title="Source Control"
                    >
                        <span className="material-symbols-outlined text-[20px]">commit</span>
                    </button>
                    <div className="flex-1" />
                    <button
                        onClick={() => setShowAgent(!showAgent)}
                        className={`w-10 h-10 flex items-center justify-center rounded-lg transition-all ${showAgent ? 'text-white bg-white/5' : 'text-gray-500 hover:text-gray-300'
                            }`}
                        title="Code Agent"
                    >
                        <span className="material-symbols-outlined text-[20px]">smart_toy</span>
                    </button>
                    <button
                        onClick={() => { }}
                        className="w-10 h-10 flex items-center justify-center rounded-lg text-gray-500 hover:text-gray-300 transition-all"
                        title="Settings"
                    >
                        <span className="material-symbols-outlined text-[20px]">settings</span>
                    </button>
                </div>

                {showSidebar && (
                    <div className="flex flex-col glass shrink-0 relative" style={{ width: sidebarWidth }}>
                        <div className="h-9 flex items-center justify-between px-4 pt-1 mb-2">
                            <span className="text-[10px] font-medium tracking-[0.1em] text-gray-500 uppercase">
                                {activeSidebarTab === 'explorer' ? 'Explorer' : 'Extensions'}
                            </span>
                            <span className="material-symbols-outlined text-[16px] text-gray-600 cursor-pointer hover:text-white transition-colors">more_horiz</span>
                        </div>

                        {activeSidebarTab === 'explorer' && (
                            <>
                                <div className="flex-1 overflow-y-auto px-0 text-[13px] font-light select-none">
                                    <div className="px-4 py-1.5 flex items-center text-gray-300 group cursor-pointer hover:text-white transition-colors mb-1">
                                        <span className="material-symbols-outlined text-[16px] mr-1.5 transform group-hover:rotate-90 transition-transform text-gray-500">chevron_right</span>
                                        <span className="tracking-tight font-medium uppercase">{rootPath ? rootPath.split(/[\\/]/).pop() : 'PROJECT'}</span>
                                    </div>
                                    <div className="flex flex-col">
                                        {fileTree.length > 0 ? (
                                            <div className="flex flex-col ml-4 border-l border-gray-800/50 my-1">
                                                {renderTree(fileTree)}
                                            </div>
                                        ) : (
                                            <div className="pl-4 py-1.5 flex items-center text-gray-500 hover:text-gray-300 cursor-pointer antigravity-hover border-l-2 border-transparent">
                                                <span className="opacity-80">Loading...</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <div className="h-10 border-t border-gray-800/50 flex items-center px-4 justify-between bg-black/20">
                                    <div className="flex items-center space-x-3 text-[10px] text-gray-500 font-mono">
                                        <span className="flex items-center hover:text-gray-300 cursor-pointer"><span className="material-symbols-outlined text-[12px] mr-1">code</span> master*</span>
                                        <span className="flex items-center hover:text-gray-300 cursor-pointer"><span className="material-symbols-outlined text-[12px] mr-1">sync</span> 0↓ 1↑</span>
                                    </div>
                                </div>
                            </>
                        )}

                        {activeSidebarTab === 'extensions' && (
                            <ExtensionsPanel rootPath={rootPath} />
                        )}

                        {/* Sidebar resize handle */}
                        <div
                            className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-transparent hover:bg-cyan-500/10 transition-colors select-none"
                            onMouseDown={(e) => {
                                e.preventDefault();
                                sidebarResizeRef.current = { dragging: true, startX: e.clientX, startWidth: sidebarWidth };

                                const onMove = (ev: MouseEvent) => {
                                    const ref = sidebarResizeRef.current;
                                    if (!ref?.dragging) return;
                                    const delta = ev.clientX - ref.startX;
                                    const next = ref.startWidth + delta;
                                    const min = 180;
                                    const max = Math.min(600, Math.floor(window.innerWidth * 0.6));
                                    setSidebarWidth(Math.max(min, Math.min(max, next)));
                                };

                                const onUp = () => {
                                    sidebarResizeRef.current = null;
                                    window.removeEventListener('mousemove', onMove);
                                    window.removeEventListener('mouseup', onUp);
                                };

                                window.addEventListener('mousemove', onMove);
                                window.addEventListener('mouseup', onUp);
                            }}
                            title="Drag to resize Explorer"
                        />
                    </div>
                )}
                <div className="flex-1 flex flex-col min-w-0 bg-[#050505] relative">
                    <div className="flex h-9 bg-[#050505] border-b border-gray-800/50 overflow-x-auto shrink-0">
                        {openFiles.length > 0 ? openFiles.map(file => (
                            <div key={file.path} onClick={() => setActiveFile(file.path)} className={`flex items-center px-4 pr-2 min-w-fit cursor-pointer group relative ${activeFile === file.path ? 'bg-[#0a0a0c] border-t-2 border-t-primary' : 'bg-transparent opacity-50 hover:opacity-100 border-r border-gray-800/50'}`}>
                                {activeFile === file.path && <div className="absolute inset-x-0 top-0 h-full bg-gradient-to-b from-white/5 to-transparent pointer-events-none"></div>}
                                <span className={`text-[12px] mr-2 font-mono flex items-center gap-1.5 ${activeFile === file.path ? 'text-gray-200' : 'text-gray-400'}`}>
                                    <span className={`material-symbols-outlined text-[14px] ${getFileIconColor(file.name)}`}>{getFileIcon(file.name)}</span>
                                    {file.name}
                                    {changedFiles.has(file.path) && (
                                        <span className="w-3.5 h-3.5 rounded flex items-center justify-center text-[9px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/25">M</span>
                                    )}
                                </span>
                                <span onClick={(e) => { e.stopPropagation(); closeFile(file.path); }} className="material-symbols-outlined text-[14px] text-gray-500 hover:text-white opacity-0 group-hover:opacity-100 transition-all rounded p-0.5 hover:bg-white/10 ml-1">close</span>
                            </div>
                        )) : (
                            <div className="flex items-center px-4 pr-2 bg-transparent min-w-fit cursor-pointer group opacity-50 border-r border-gray-800/50">
                                <span className="text-[12px] text-gray-400 mr-2 font-mono flex items-center">No Active Editor</span>
                            </div>
                        )}
                    </div>
                    <div className="flex-1 flex flex-col items-stretch relative bg-[#050505] min-h-0 overflow-hidden">
                        {showPlanModal && pendingPlan ? (
                            <PlanPanel
                                plan={pendingPlan}
                                onApprove={handleApprovePlan}
                                onReject={handleRejectPlan}
                                onClose={() => setShowPlanModal(false)}
                                stageLabel={editorStage !== 'idle' ? `${editorStage}${stageMessage ? ` • ${stageMessage}` : ''}` : undefined}
                                isGenerating={editorStage === 'generating_patch' || editorStage === 'validating'}
                            />
                        ) : activeFile ? (
                            <>
                                {/* Generation-in-progress banner (visible while patches are being generated) */}
                                {(editorStage === 'generating_patch' || editorStage === 'validating') && (
                                    <div className="w-full flex items-center gap-3 px-4 py-2.5 bg-gradient-to-r from-violet-900/20 via-[#0c0c10] to-violet-900/20 border-b border-violet-500/25 shrink-0 z-10 animate-pulse">
                                        <span className="material-symbols-outlined text-violet-400 text-[16px] animate-spin">sync</span>
                                        <span className="text-[11px] text-gray-300 font-medium">
                                            {stageMessage || 'Generating patches...'}
                                        </span>
                                    </div>
                                )}
                                {/* Inline Accept/Reject toolbar when patches are pending */}
                                {pendingPatches.length > 0 && changedFiles.has(activeFile) && (
                                    <div className="w-full flex items-center justify-between px-4 py-2 bg-gradient-to-r from-indigo-900/20 via-[#0c0c10] to-indigo-900/20 border-b border-indigo-500/20 shrink-0 z-10">
                                        <div className="flex items-center gap-2">
                                            <span className="material-symbols-outlined text-indigo-400 text-[16px]">auto_fix_high</span>
                                            <span className="text-[11px] text-gray-300 font-medium">
                                                AI changes pending — {pendingPatches.length} file{pendingPatches.length > 1 ? 's' : ''} modified
                                            </span>
                                            {pendingPatches.length > 1 && (
                                                <div className="flex items-center gap-1 ml-2">
                                                    {pendingPatches.map(p => (
                                                        <button
                                                            key={p.filePath}
                                                            onClick={() => setActiveFile(p.filePath)}
                                                            className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${p.filePath === activeFile
                                                                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                                                                : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
                                                                }`}
                                                        >
                                                            {p.filePath.split(/[\\/]/).pop()}
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={() => setDiffPreviewOpen(true)}
                                                className="px-3 py-1.5 rounded-lg text-[11px] font-medium text-gray-400 hover:text-white
                                                       bg-gray-800/50 hover:bg-gray-700/50 border border-gray-700/50
                                                       transition-all flex items-center gap-1.5"
                                                title="View full diff"
                                            >
                                                <span className="material-symbols-outlined text-[14px]">difference</span>
                                                View Diff
                                            </button>
                                            <button
                                                onClick={handleRejectPatch}
                                                className="px-3 py-1.5 rounded-lg text-[11px] font-medium text-red-400 hover:text-red-300
                                                       bg-red-500/5 hover:bg-red-500/15 border border-red-500/20 hover:border-red-500/30
                                                       transition-all flex items-center gap-1.5"
                                            >
                                                <span className="material-symbols-outlined text-[14px]">close</span>
                                                Reject
                                            </button>
                                            <button
                                                onClick={() => handleApplyPatchSet(pendingPatches.map(p => p.proposalId).filter(Boolean) as string[])}
                                                className="px-3 py-1.5 rounded-lg text-[11px] font-semibold text-white
                                                       bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500
                                                       shadow-md shadow-green-500/10
                                                       transition-all flex items-center gap-1.5"
                                            >
                                                <span className="material-symbols-outlined text-[14px]">check</span>
                                                Accept All
                                            </button>
                                        </div>
                                    </div>
                                )}
                                <Editor
                                    height="100%"
                                    path={activeFile}
                                    defaultLanguage={getLanguage(activeFile)}
                                    defaultValue={openFiles.find(f => f.path === activeFile)?.content || ''}
                                    value={openFiles.find(f => f.path === activeFile)?.content || ''}
                                    theme="vs-dark"
                                    onMount={handleEditorDidMount}
                                    onChange={(value) => {
                                        if (value !== undefined) handleEditorChange(value);
                                    }}
                                    options={{
                                        minimap: { enabled: false },
                                        fontSize: 14,
                                        fontFamily: "'JetBrains Mono', monospace",
                                        lineHeight: 24,
                                        padding: { top: 16 },
                                        scrollBeyondLastLine: false,
                                        smoothScrolling: true,
                                        cursorBlinking: "smooth",
                                        cursorSmoothCaretAnimation: "on",
                                        renderLineHighlight: "all",
                                        bracketPairColorization: { enabled: true },
                                        guides: {
                                            indentation: true,
                                            bracketPairs: true
                                        }
                                    }}
                                    className="obsidian-pro-editor"
                                />
                            </>
                        ) : (
                            <div className="flex-1 flex flex-col items-center justify-center bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9InJnYmEoMjU1LDI13LhADtNNGYrWCYdaGcRiGWmwjXACLGuiX=')] bg-cover bg-center relative w-full h-full">
                                <div className="absolute inset-0 bg-background-dark/95 backdrop-blur-[2px]"></div>
                                <div className="relative z-10 text-center animate-[fadeIn_0.8s_ease-out_forwards]">
                                    <div className="w-20 h-20 mx-auto mb-8 rounded-full bg-gradient-to-b from-gray-800 to-black shadow-[0_0_40px_-10px_rgba(0,0,0,0.8)] flex items-center justify-center border border-white/5 ring-1 ring-white/5">
                                        <span className="material-symbols-outlined text-[40px] text-gray-600">code_off</span>
                                    </div>
                                    <h2 className="text-lg font-light tracking-wide text-gray-300 mb-3">No Active Editor</h2>
                                    <div className="inline-flex items-center px-3 py-1 rounded-full border border-gray-800 bg-gray-900/50 text-xs text-gray-500 font-mono mb-10">
                                        <span className="mr-2">⌘ P</span> to search files
                                    </div>
                                    <div className="flex gap-6 justify-center">
                                        <div className="flex flex-col items-center group cursor-pointer" onClick={() => createNewFile('untitled', '', 'plaintext')}>
                                            <div className="w-10 h-10 rounded-full bg-gray-900 border border-gray-800 flex items-center justify-center group-hover:border-primary/50 group-hover:text-primary transition-all duration-300 mb-3 shadow-lg">
                                                <span className="material-symbols-outlined text-[18px] text-gray-500 group-hover:text-primary transition-colors">add</span>
                                            </div>
                                            <span className="text-[10px] uppercase tracking-widest text-gray-600 group-hover:text-gray-400 transition-colors">New</span>
                                        </div>
                                        <div className="flex flex-col items-center group cursor-pointer" onClick={() => handleSelectFolder()}>
                                            <div className="w-10 h-10 rounded-full bg-gray-900 border border-gray-800 flex items-center justify-center group-hover:border-primary/50 group-hover:text-primary transition-all duration-300 mb-3 shadow-lg">
                                                <span className="material-symbols-outlined text-[18px] text-gray-500 group-hover:text-primary transition-colors">folder_open</span>
                                            </div>
                                            <span className="text-[10px] uppercase tracking-widest text-gray-600 group-hover:text-gray-400 transition-colors">Open</span>
                                        </div>
                                        <div className="flex flex-col items-center group cursor-pointer" onClick={() => setTerminalOpen(true)}>
                                            <div className="w-10 h-10 rounded-full bg-gray-900 border border-gray-800 flex items-center justify-center group-hover:border-primary/50 group-hover:text-primary transition-all duration-300 mb-3 shadow-lg">
                                                <span className="material-symbols-outlined text-[18px] text-gray-500 group-hover:text-primary transition-colors">terminal</span>
                                            </div>
                                            <span className="text-[10px] uppercase tracking-widest text-gray-600 group-hover:text-gray-400 transition-colors">Run</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                    {/* Terminal: always render a collapsed bar so users can re-open with an UP button */}
                    {terminalOpen ? (
                        <div
                            className="border-t border-gray-800 bg-[#08080a] flex flex-col shrink-0"
                            style={{ height: terminalHeight }}
                        >
                            {/* Resize handle */}
                            <div
                                className="h-2.5 cursor-row-resize bg-transparent hover:bg-cyan-500/20 active:bg-cyan-500/30 transition-colors select-none flex items-center justify-center group"
                                onMouseDown={(e) => {
                                    e.preventDefault();
                                    terminalResizeRef.current = { dragging: true, startY: e.clientY, startHeight: terminalHeight };
                                    const onMove = (ev: MouseEvent) => {
                                        const ref = terminalResizeRef.current;
                                        if (!ref?.dragging) return;
                                        const delta = ref.startY - ev.clientY; // dragging up increases height
                                        const next = ref.startHeight + delta;
                                        const min = 180;
                                        const max = Math.floor(window.innerHeight * 0.7);
                                        setTerminalHeight(Math.max(min, Math.min(max, next)));
                                    };
                                    const onUp = () => {
                                        terminalResizeRef.current = null;
                                        window.removeEventListener('mousemove', onMove);
                                        window.removeEventListener('mouseup', onUp);
                                    };
                                    window.addEventListener('mousemove', onMove);
                                    window.addEventListener('mouseup', onUp);
                                }}
                                title="Drag to resize terminal"
                            >
                                <div className="w-10 h-1 rounded-full bg-gray-600/40 group-hover:bg-cyan-500/50 transition-colors" />
                            </div>
                            <div className="flex-1 min-h-0 overflow-hidden">
                                <TerminalPanel
                                    isOpen={true}
                                    onToggle={() => setTerminalOpen(false)}
                                    cwd={rootPath || undefined}
                                    hideHeader={false}
                                />
                            </div>
                        </div>
                    ) : (
                        <div className="h-8 border-t border-gray-800 bg-[#08080a] flex items-center justify-between px-4 shrink-0">
                            <div className="flex items-center gap-2 text-[11px] text-gray-500 select-none">
                                <span className="material-symbols-outlined text-[14px] text-gray-600">terminal</span>
                                <span>Terminal</span>
                            </div>
                            <button
                                className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-white transition-colors"
                                onClick={() => setTerminalOpen(true)}
                                title="Expand Terminal"
                            >
                                <span className="material-symbols-outlined text-[16px]">keyboard_arrow_up</span>
                            </button>
                        </div>
                    )}
                </div>
                {showAgent && (
                    <div className="border-l border-gray-800/50 glass-lighter bg-[#070709] flex flex-col shrink-0 z-10 relative" style={{ width: agentWidth }}>
                        {/* Agent resize handle */}
                        <div
                            className="absolute top-0 left-0 h-full w-2 cursor-col-resize bg-transparent hover:bg-cyan-500/10 transition-colors select-none"
                            onMouseDown={(e) => {
                                e.preventDefault();
                                agentResizeRef.current = { dragging: true, startX: e.clientX, startWidth: agentWidth };

                                const onMove = (ev: MouseEvent) => {
                                    const ref = agentResizeRef.current;
                                    if (!ref?.dragging) return;
                                    const delta = ref.startX - ev.clientX; // drag left increases width
                                    const next = ref.startWidth + delta;
                                    const min = 260;
                                    const max = Math.min(700, Math.floor(window.innerWidth * 0.65));
                                    setAgentWidth(Math.max(min, Math.min(max, next)));
                                };

                                const onUp = () => {
                                    agentResizeRef.current = null;
                                    window.removeEventListener('mousemove', onMove);
                                    window.removeEventListener('mouseup', onUp);
                                };

                                window.addEventListener('mousemove', onMove);
                                window.addEventListener('mouseup', onUp);
                            }}
                            title="Drag to resize Code Agent"
                        />
                        <div className="h-10 flex items-center justify-between px-4 border-b border-gray-800/50 bg-[#0a0a0c]/50">
                            <div className="flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary text-[16px] animate-pulse">auto_awesome</span>
                                <span className="font-medium text-[12px] text-gray-300">Code Agent</span>
                            </div>
                            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20">
                                <span className="w-1 h-1 rounded-full bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.8)]"></span>
                                <span className="text-[9px] uppercase text-green-400 tracking-wider font-medium">Ready</span>
                            </div>
                        </div>

                        {/* LLM selector */}
                        <div className="px-4 py-2 border-b border-gray-800/40 bg-black/10">
                            <div className="flex items-center justify-between gap-3">
                                <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">LLM</span>
                                <select
                                    value={selectedLlmModel}
                                    onChange={(e) => setSelectedLlmModel(e.target.value)}
                                    className="text-[11px] bg-[#121215] text-gray-200 border border-gray-800/80 rounded px-2 py-1 outline-none focus:border-white/20"
                                    title="Select which model to use for Code Agent replies. Auto chooses based on task complexity."
                                >
                                    <option value="auto">Auto (smart)</option>
                                    <option value="qwen3-coder:480b-cloud">Qwen3-Coder 480B (cloud)</option>
                                    <option value="gpt-oss:120b-cloud">GPT-OSS 120B (cloud)</option>
                                    <option value="kimi-k2.5:cloud">Kimi K2.5 (cloud)</option>
                                </select>
                            </div>
                        </div>

                        <div className="flex-1 p-4 overflow-y-auto space-y-6" ref={messagesEndRef}>
                            <div className="flex gap-3">
                                <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20">
                                    <span className="material-symbols-outlined text-primary text-[14px]">smart_toy</span>
                                </div>
                                <div className="space-y-1 w-full">
                                    <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wider mb-1">Assistant</div>
                                    <div className="text-[12px] text-gray-300 leading-relaxed bg-[#121215] p-3 rounded-lg border border-gray-800/80 shadow-sm">
                                        <p className="mb-2">I'm ready to help with your code.</p>
                                        <ul className="list-none space-y-1.5 text-gray-500">
                                            <li className="flex items-center gap-2"><span className="w-1 h-1 bg-gray-600 rounded-full"></span> Generate components</li>
                                            <li className="flex items-center gap-2"><span className="w-1 h-1 bg-gray-600 rounded-full"></span> Refactor logic</li>
                                            <li className="flex items-center gap-2"><span className="w-1 h-1 bg-gray-600 rounded-full"></span> Debug issues</li>
                                        </ul>
                                    </div>
                                </div>
                            </div>

                            {agentMessages.slice(1).map((msg, i) => {
                                /* Special: plan-ready button */
                                if (msg.role === 'agent' && msg.text === '::plan_ready::') {
                                    return (
                                        <div key={i} className="px-1">
                                            <PlanReadyButton onClick={() => setShowPlanModal(true)} />
                                        </div>
                                    );
                                }
                                const isPlanMessage = msg.role === 'agent' && msg.text.includes('Implementation Plan') && msg.text.includes('Approve');
                                return (
                                    <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border ${msg.role === 'agent' ? 'bg-primary/10 border-primary/20' : 'bg-gray-700/50 border-gray-600'}`}>
                                            <span className="material-symbols-outlined text-primary text-[14px]">{msg.role === 'agent' ? 'smart_toy' : 'person'}</span>
                                        </div>
                                        <div className="space-y-1 w-full max-w-[85%]">
                                            <div className={`text-[10px] font-medium uppercase tracking-wider mb-1 ${msg.role === 'user' ? 'text-right' : ''} text-gray-500`}>{msg.role === 'agent' ? 'Assistant' : 'You'}</div>
                                            <div className={`text-[12px] text-gray-300 leading-relaxed p-3 rounded-lg border shadow-sm ${msg.role === 'agent' ? 'bg-[#121215] border-gray-800/80' : 'bg-[#1e1e24] border-gray-700'}`}>
                                                <p className="whitespace-pre-wrap">{msg.text}</p>
                                            </div>
                                            {isPlanMessage && (
                                                <div className="flex gap-2 mt-2">
                                                    <button
                                                        className="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-white text-[11px] font-medium rounded-md transition-all duration-200 flex items-center gap-1.5 shadow-lg shadow-green-500/20"
                                                        onClick={() => {
                                                            const handler = (window as any).__pendingPlanApproval;
                                                            if (handler) handler(true);
                                                        }}
                                                    >
                                                        <span className="material-symbols-outlined text-[14px]">check_circle</span>
                                                        Approve & Execute
                                                    </button>
                                                    <button
                                                        className="px-4 py-1.5 bg-red-600/20 hover:bg-red-600/40 text-red-400 text-[11px] font-medium rounded-md border border-red-600/30 transition-all duration-200 flex items-center gap-1.5"
                                                        onClick={() => {
                                                            const handler = (window as any).__pendingPlanApproval;
                                                            if (handler) handler(false);
                                                        }}
                                                    >
                                                        <span className="material-symbols-outlined text-[14px]">cancel</span>
                                                        Reject
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}

                            {isLoading && (
                                <div className="flex gap-3 items-center">
                                    <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20">
                                        <span className="material-symbols-outlined text-primary text-[14px] animate-spin">sync</span>
                                    </div>
                                    <span className="text-[11px] text-gray-500">Processing...</span>
                                </div>
                            )}
                            <div ref={messagesScrollRef} />

                            {/* Active Context removed per user request */}
                            {!hasUserMessages && (
                                <div className="space-y-2">
                                    <div className="text-[10px] uppercase text-gray-600 tracking-wider font-medium ml-1">Suggestions</div>
                                    <button className="w-full text-left px-3 py-2.5 rounded bg-[#121215] hover:bg-[#18181b] border border-gray-800 hover:border-gray-700 text-[11px] text-gray-400 transition-all flex items-center gap-2 group">
                                        <span className="material-symbols-outlined text-[14px] text-gray-600 group-hover:text-primary transition-colors">play_arrow</span>
                                        Create calculator component
                                    </button>
                                    <button className="w-full text-left px-3 py-2.5 rounded bg-[#121215] hover:bg-[#18181b] border border-gray-800 hover:border-gray-700 text-[11px] text-gray-400 transition-all flex items-center gap-2 group">
                                        <span className="material-symbols-outlined text-[14px] text-gray-600 group-hover:text-primary transition-colors">bug_report</span>
                                        Scan for vulnerabilities
                                    </button>
                                </div>
                            )}
                        </div>
                        <div className="p-3 bg-[#070709] border-t border-gray-800/50">
                            <div className="relative group">
                                <textarea className="w-full bg-[#121215] text-gray-200 text-[12px] p-3 pr-10 rounded-lg border border-gray-800/80 focus:border-primary/50 focus:ring-1 focus:ring-primary/20 focus:outline-none resize-none placeholder-gray-600 transition-all shadow-inner" placeholder="Describe what you want to build..." rows={2} value={agentInput} onChange={(e) => setAgentInput(e.target.value)} onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleAgentSubmit();
                                    }
                                }}></textarea>
                                <button className="absolute bottom-2.5 right-2.5 p-1 text-gray-500 hover:text-white transition-colors" onClick={handleAgentSubmit}>
                                    <span className="material-symbols-outlined text-[16px] transform -rotate-45 translate-x-0.5 -translate-y-0.5">send</span>
                                </button>
                                {(isLoading || editorStage === 'generating_patch' || editorStage === 'validating' || editorStage === 'planning' || editorStage === 'applying') && (
                                    <button
                                        className="absolute bottom-2.5 right-10 p-1 text-red-400 hover:text-red-300 transition-colors"
                                        onClick={handleStop}
                                        title="Stop current operation"
                                    >
                                        <span className="material-symbols-outlined text-[16px]">stop_circle</span>
                                    </button>
                                )}
                            </div>
                            <div className="flex justify-between items-center mt-2 px-1 opacity-50">
                                <span className="text-[9px] text-gray-500">Enter to send • Shift+Enter for newline</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
            <DiffPreview
                open={diffPreviewOpen}
                patches={pendingPatches.map(p => ({ filePath: p.filePath, diff: p.unifiedDiff, proposalId: p.proposalId, isNewFile: p.isNewFile }))}
                onClose={() => setDiffPreviewOpen(false)}
                onReject={handleRejectPatch}
                onApply={handleApplyPatchSet}
                onApplyOne={handleApplySinglePatch}
            />
            <div className="h-6 bg-[#050505] border-t border-white/5 text-slate-200 text-[10px] flex items-center justify-between px-3 select-none z-50">
                <div className="flex items-center space-x-3">
                    <span className="font-bold flex items-center gap-1.5 hover:bg-white/10 px-1.5 py-0.5 rounded cursor-pointer transition-colors"><span className="material-symbols-outlined text-[12px]">cloud_done</span> REMOTE</span>
                    <span className="opacity-80 hover:opacity-100 cursor-pointer hover:bg-white/10 px-1.5 py-0.5 rounded transition-colors">Live Share</span>
                </div>
                <div className="flex items-center space-x-2 opacity-90">
                    <span className="hover:bg-white/10 px-1.5 py-0.5 rounded cursor-pointer transition-colors">Ln 12, Col 45</span>
                    <span className="hover:bg-white/10 px-1.5 py-0.5 rounded cursor-pointer transition-colors">UTF-8</span>
                    <span className="hover:bg-white/10 px-1.5 py-0.5 rounded cursor-pointer transition-colors">JavaScript</span>
                    <span className="hover:bg-white/10 px-1.5 py-0.5 rounded cursor-pointer transition-colors flex items-center gap-1"><span className="material-symbols-outlined text-[12px]">notifications_none</span></span>
                </div>
            </div>
        </div>
    );
}
