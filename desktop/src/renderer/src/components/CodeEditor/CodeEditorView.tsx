import React, { useState, useRef, useEffect } from 'react';
import { X, FolderOpen, ChevronRight, ChevronDown, FileText, Folder, Send, Sparkles, Code2, Wand2, Plus, FilePlus, Save, Copy, Scissors, Clipboard, RotateCcw, RotateCw, Eye, EyeOff, Terminal, Settings } from 'lucide-react';
import Editor from '@monaco-editor/react';
import TerminalPanel from './TerminalPanel';
import { DiffPreview } from './DiffPreview';
import { CopilotModeSelector, CopilotMode } from './CopilotModeSelector';
import { registerInlineCompletionProvider } from './InlineCompletionProvider';
import * as monaco from 'monaco-editor';

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

    // Copilot State
    const [copilotMode, setCopilotMode] = useState<CopilotMode>('suggest');
    const [diffPreviewOpen, setDiffPreviewOpen] = useState(false);
    const [proposalDiff, setProposalDiff] = useState('');
    const [proposalId, setProposalId] = useState('');
    const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

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

    // Effect to register inline provider
    useEffect(() => {
        if (editorRef.current) {
            const disposable = registerInlineCompletionProvider(editorRef.current);
            return () => disposable.dispose();
        }
    }, [editorRef.current]);

    // Auto-Save Effect (Debounced)
    useEffect(() => {
        if (currentFile?.modified) {
            const timer = setTimeout(() => {
                console.log('🔄 Auto-saving:', currentFile.name);
                saveFunctionRef.current();
            }, 2000); // 2 seconds debounce
            return () => clearTimeout(timer);
        }
    }, [currentFile, openFiles]);

    const handleEditorDidMount = (editor: monaco.editor.IStandaloneCodeEditor) => {
        editorRef.current = editor;
        registerInlineCompletionProvider(editor);

        // Register Ctrl+S / Cmd+S
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
            console.log('💾 Ctrl+S triggered');
            saveFunctionRef.current();
        });
    };


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
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [agentMessages]);

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

    const createNewFile = async (name: string, content: string, lang: string) => {
        // Check if we have a selected folder with full path
        if (!rootPath) {
            // No folder selected - just add to editor
            setOpenFiles(prev => [...prev, {
                path: `unsaved/${name}`,
                name,
                content,
                language: lang,
                modified: true
            }]);
            setActiveFile(`unsaved/${name}`);

            setAgentMessages(prev => [...prev, {
                role: 'agent',
                text: `⚠️ **No folder selected!** File "${name}" is in editor only.\n\n👉 Click the folder icon in Explorer to select your project folder first.`
            }]);
            return;
        }

        // Build full file path
        const filePath = `${rootPath}\\${name.replace(/\//g, '\\')}`;

        // Add to editor tabs
        setOpenFiles(prev => [...prev, { path: filePath, name, content, language: lang, modified: false }]);
        setActiveFile(filePath);

        console.log('📁 createNewFile called:', { name, filePath, hasElectronAPI: !!window.electronAPI });

        // Use Electron API if available
        if (window.electronAPI?.fs) {
            try {
                await window.electronAPI.fs.writeFile(filePath, content);
                console.log(`✅ File saved via Electron: ${filePath}`);

                // Refresh file tree
                await refreshFileTree();

                setAgentMessages(prev => [...prev, {
                    role: 'agent',
                    text: `📁 File saved: ${name}`
                }]);
            } catch (err) {
                console.error('Failed to save file:', err);
                setAgentMessages(prev => [...prev, {
                    role: 'agent',
                    text: `❌ Failed to save: ${err}. File is in editor but not on disk.`
                }]);
            }
        } else {
            // No Electron API - try backend
            try {
                const response = await fetch('http://localhost:8000/api/save-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: filePath, content, directory: rootPath })
                });
                if (response.ok) {
                    setAgentMessages(prev => [...prev, { role: 'agent', text: `📁 File saved: ${name}` }]);
                    await refreshFileTree();
                }
            } catch (err) {
                console.error('Backend save failed:', err);
                setAgentMessages(prev => [...prev, {
                    role: 'agent',
                    text: `⚠️ File in editor only. Backend unavailable.`
                }]);
            }
        }
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

        // Copilot Mode Logic
        if (copilotMode === 'refactor') {
            // Call Refactor Endpoint
            try {
                const currentFile = openFiles.find(f => f.path === activeFile);
                if (!currentFile) {
                    setAgentMessages(prev => [...prev, { role: 'agent', text: "Please open a file to refactor." }]);
                    setIsLoading(false);
                    return;
                }

                // Get selection if any
                const selection = editorRef.current?.getModel()?.getValueInRange(editorRef.current.getSelection()!);

                const response = await fetch('http://localhost:8000/api/copilot/refactor', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_content: currentFile.content,
                        cursor_line: editorRef.current?.getPosition()?.lineNumber || 1,
                        cursor_column: editorRef.current?.getPosition()?.column || 1,
                        language: currentFile.language,
                        file_path: currentFile.path,
                        selection: selection || '',
                        user_input: originalMessage,
                        ...(selectedLlmModel !== 'auto' ? { model_name: selectedLlmModel } : {})
                    })
                });

                const data = await response.json();
                if (data.proposal_id && data.diff) {
                    setProposalId(data.proposal_id);
                    setProposalDiff(data.diff);
                    setDiffPreviewOpen(true);
                    setAgentMessages(prev => [...prev, { role: 'agent', text: "I've proposed a refactor. Please review the diff." }]);
                } else {
                    setAgentMessages(prev => [...prev, { role: 'agent', text: "Could not generate a refactor proposal." }]);
                }
            } catch (e: any) {
                setAgentMessages(prev => [...prev, { role: 'agent', text: `Error: ${e.message}` }]);
            }
            setIsLoading(false);
            return; // Stop here, don't cascade to old logic
        }

        if (copilotMode === 'explain') {
            // Call Explain Endpoint
            // ... similar logic ...
            setAgentMessages(prev => [...prev, { role: 'agent', text: "Explanation: (Mock) This code does X..." }]);
            setIsLoading(false);
            return;
        }

        // Default / Suggest Mode -> Fallback to Chat or existing logic but STRICTLY NO AUTO-SAVE
        // Note: Inline suggestions happen automatically via Monaco provider.
        // If user chats in "Suggest" mode, we treat it as Q&A or generate code to clipboard/buffer.
        // All code generation now goes through the LLM for proper context understanding.

        // For other requests, use the LLM
        try {
            const currentFile = openFiles.find(f => f.path === activeFile);
            const context = currentFile ? `\nOPEN FILE: ${currentFile.name}\n\`\`\`${currentFile.language}\n${currentFile.content.slice(0, 1500)}\n\`\`\`` : '';

            // Serialize file tree for context
            const serializeFileTree = (nodes: FileNode[], depth = 0): string => {
                return nodes.map(n => {
                    const indent = '  '.repeat(depth);
                    if (n.type === 'folder') {
                        const children = n.children && n.expanded ? serializeFileTree(n.children, depth + 1) : '';
                        return `${indent}📁 ${n.name}/${children ? '\n' + children : ''}`;
                    }
                    return `${indent}📄 ${n.name}`;
                }).join('\n');
            };
            const fileTreeContext = fileTree.length > 0 ? serializeFileTree(fileTree) : '(No files loaded)';

            // Use coding model endpoint with context-aware prompt
            const response = await fetch('http://localhost:8000/api/code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: `You are an expert AI coding assistant embedded in an IDE.

PROJECT FILES:
${fileTreeContext}
${context}

USER REQUEST: ${originalMessage}

INSTRUCTIONS:
- If the user asks to "scan", "list", "show", "describe", or "tell me about" the project, summarize the file tree above. Do NOT generate code.
- If the user asks to "explain" code, explain it clearly without generating new code.
- If the user asks to "generate", "create", "write", or "build" something, provide complete, runnable code in a code block.
- Be concise and helpful. Match your response to the user's intent.`
                    ,
                    ...(selectedLlmModel !== 'auto' ? { model_name: selectedLlmModel } : {})
                })
            });

            console.log('Response status:', response.status);
            const data = await response.json();
            console.log('Response data:', data);

            if (data.status === 'error') {
                setAgentMessages(prev => [...prev, { role: 'agent', text: data.response }]);
                setIsLoading(false);
                return;
            }

            const text = data.response || 'No response received';
            setAgentMessages(prev => [...prev, { role: 'agent', text }]);

            // Extract ALL code blocks from response (supports multiple files)
            const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
            const matches = [...text.matchAll(codeBlockRegex)];

            if (matches.length > 0) {
                const extMap: Record<string, string> = {
                    javascript: 'js', typescript: 'ts', python: 'py',
                    html: 'html', css: 'css', json: 'json', jsx: 'jsx', tsx: 'tsx'
                };

                // Better detection for modification requests
                // Detects: "add X", "update", "modify", "change", "fix", "improve", "in this", "to this file", etc.
                const modificationKeywords = [
                    'modify', 'refine', 'update', 'change', 'fix', 'improve',
                    'add ', 'add a ', 'add the ', 'add to', 'insert',
                    'in this', 'to this', 'this file', 'this code',
                    'edit', 'replace', 'remove', 'delete from'
                ];

                const isModificationRequest = modificationKeywords.some(keyword =>
                    userMessage.includes(keyword)
                );

                const currentFileInfo = openFiles.find(f => f.path === activeFile);

                // If there's an active file and user is asking to modify it
                if (currentFileInfo && matches.length === 1 && isModificationRequest) {
                    // Single code block + modification request = update existing file
                    const code = matches[0][2].trim();
                    updateFileContent(currentFileInfo.path, code);
                    updateFileContent(currentFileInfo.path, code);
                    // AUTO-SAVE REMOVED: saveFileToBackend(currentFileInfo.path, code);
                    setAgentMessages(prev => [...prev, { role: 'agent', text: `✅ Updated ${currentFileInfo.name} in buffer (unsaved).` }]);
                    setAgentMessages(prev => [...prev, { role: 'agent', text: `✅ Updated ${currentFileInfo.name}!` }]);
                } else if (currentFileInfo && matches.length === 1) {
                    // Even without explicit modification keywords, if there's an active file
                    // and a single code block of the same language, assume update
                    const lang = matches[0][1] || 'text';
                    const currentLang = currentFileInfo.language;
                    const code = matches[0][2].trim();

                    // Check if languages match (jsx matches javascript, etc.)
                    const langMatches = lang === currentLang ||
                        (lang === 'javascript' && (currentLang === 'javascript' || currentLang === 'jsx')) ||
                        (lang === 'jsx' && currentLang === 'javascript') ||
                        (lang === 'typescript' && (currentLang === 'typescript' || currentLang === 'tsx'));

                    if (langMatches) {
                        updateFileContent(currentFileInfo.path, code);
                        updateFileContent(currentFileInfo.path, code);
                        // AUTO-SAVE REMOVED: saveFileToBackend(currentFileInfo.path, code);
                        setAgentMessages(prev => [...prev, { role: 'agent', text: `✅ Updated ${currentFileInfo.name} in buffer (unsaved).` }]);
                        setAgentMessages(prev => [...prev, { role: 'agent', text: `✅ Updated ${currentFileInfo.name}!` }]);
                    } else {
                        // Different language - create new file
                        const ext = extMap[lang] || lang;
                        createNewFile(`generated.${ext}`, code, lang);
                    }
                } else {
                    // Create new file(s) for each code block
                    let fileCount = 0;
                    matches.forEach((match, index) => {
                        const lang = match[1] || 'text';
                        const code = match[2].trim();
                        const ext = extMap[lang] || lang;

                        // Generate unique filename based on language
                        let filename = 'generated';
                        if (lang === 'html') filename = 'index';
                        else if (lang === 'css') filename = 'styles';
                        else if (lang === 'python') filename = 'app';
                        else if (lang === 'javascript' || lang === 'js' || lang === 'jsx') filename = 'script';

                        // Add index if multiple files of same type
                        if (matches.filter(m => (m[1] || 'text') === lang).length > 1) {
                            filename += `_${index + 1}`;
                        }

                        createNewFile(`${filename}.${ext}`, code, lang);
                        fileCount++;
                    });

                    if (fileCount > 1) {
                        setAgentMessages(prev => [...prev, { role: 'agent', text: `✅ Created ${fileCount} files!` }]);
                    } else if (fileCount === 1) {
                        setAgentMessages(prev => [...prev, { role: 'agent', text: `✅ Created new file!` }]);
                    }
                }
            }
        } catch (err: any) {
            console.error('Code generation error:', err);
            setAgentMessages(prev => [...prev, { role: 'agent', text: `Connection error: ${err.message || 'Unknown error'}. Is the server running?` }]);
        } finally {
            setIsLoading(false);
        }
    };

        const handleAgentSubmit = () => {
            if (isLoading) return;
            void sendToAgent();
        };



    const renderTree = (nodes: FileNode[], level = 0) => {
        return nodes.map((node) => (
            <div key={node.path} className="flex flex-col">
                <div
                    className={`flex items-center py-1.5 px-4 cursor-pointer transition-all duration-200 border-l-2 ${
                        activeFile === node.path 
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
                    
                    <span className="text-[13px] tracking-tight">{node.name}</span>
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
                {showSidebar && (
                    <div className="flex flex-col glass shrink-0 relative" style={{ width: sidebarWidth }}>
                        <div className="h-9 flex items-center justify-between px-4 pt-1 mb-2">
                            <span className="text-[10px] font-medium tracking-[0.1em] text-gray-500 uppercase">Explorer</span>
                            <span className="material-symbols-outlined text-[16px] text-gray-600 cursor-pointer hover:text-white transition-colors">more_horiz</span>
                        </div>
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
                                <span className={`text-[12px] mr-2 font-mono flex items-center ${activeFile === file.path ? 'text-gray-200' : 'text-gray-400'}`}>
                                    <span className={`material-symbols-outlined text-[14px] mr-2 ${getFileIconColor(file.name)}`}>{getFileIcon(file.name)}</span>
                                    {file.name}
                                </span>
                                <span onClick={(e) => { e.stopPropagation(); closeFile(file.path); }} className="material-symbols-outlined text-[14px] text-gray-500 hover:text-white opacity-0 group-hover:opacity-100 transition-all rounded p-0.5 hover:bg-white/10">close</span>
                            </div>
                        )) : (
                            <div className="flex items-center px-4 pr-2 bg-transparent min-w-fit cursor-pointer group opacity-50 border-r border-gray-800/50">
                                <span className="text-[12px] text-gray-400 mr-2 font-mono flex items-center">No Active Editor</span>
                            </div>
                        )}
                    </div>
                    <div className="flex-1 flex flex-col items-center justify-center relative bg-[#050505] min-h-0 overflow-hidden">
                         {activeFile ? (
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
                                        <p class="mb-2">I'm ready to help with your code.</p>
                                        <ul class="list-none space-y-1.5 text-gray-500">
                                        <li class="flex items-center gap-2"><span class="w-1 h-1 bg-gray-600 rounded-full"></span> Generate components</li>
                                        <li class="flex items-center gap-2"><span class="w-1 h-1 bg-gray-600 rounded-full"></span> Refactor logic</li>
                                        <li class="flex items-center gap-2"><span class="w-1 h-1 bg-gray-600 rounded-full"></span> Debug issues</li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            
                            {agentMessages.slice(1).map((msg, i) => (
                                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border ${msg.role === 'agent' ? 'bg-primary/10 border-primary/20' : 'bg-gray-700/50 border-gray-600'}`}>
                                        <span className="material-symbols-outlined text-primary text-[14px]">{msg.role === 'agent' ? 'smart_toy' : 'person'}</span>
                                    </div>
                                    <div className="space-y-1 w-full max-w-[85%]">
                                        <div className={`text-[10px] font-medium uppercase tracking-wider mb-1 ${msg.role === 'user' ? 'text-right' : ''} text-gray-500`}>{msg.role === 'agent' ? 'Assistant' : 'You'}</div>
                                        <div className={`text-[12px] text-gray-300 leading-relaxed p-3 rounded-lg border shadow-sm ${msg.role === 'agent' ? 'bg-[#121215] border-gray-800/80' : 'bg-[#1e1e24] border-gray-700'}`}>
                                            <p className="whitespace-pre-wrap">{msg.text}</p>
                                        </div>
                                    </div>
                                </div>
                            ))}
                            
                            {isLoading && (
                                <div className="flex gap-3">
                                    <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20">
                                        <span className="material-symbols-outlined text-primary text-[14px] animate-spin">sync</span>
                                    </div>
                                </div>
                            )}

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
                            </div>
                            <div className="flex justify-between items-center mt-2 px-1 opacity-50">
                                <span className="text-[9px] text-gray-500">Enter to send • Shift+Enter for newline</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
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
