import React, { useState, useRef, useEffect } from 'react';
import { X, FolderOpen, ChevronRight, ChevronDown, FileText, Folder, Send, Sparkles, Code2, Wand2, Plus, FilePlus, Save, Copy, Scissors, Clipboard, RotateCcw, RotateCw, Eye, EyeOff, Terminal, Settings } from 'lucide-react';
import Editor from '@monaco-editor/react';
import TerminalPanel from './TerminalPanel';
import { DiffPreview } from './DiffPreview';
import { CopilotModeSelector, CopilotMode } from './CopilotModeSelector';
import { registerInlineCompletionProvider } from './InlineCompletionProvider';
import * as monaco from 'monaco-editor';


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

export default function CodeEditorView({ onClose }: CodeEditorViewProps) {
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
    const [activeMenu, setActiveMenu] = useState<string | null>(null);
    const [showSidebar, setShowSidebar] = useState(true);
    const [showAgent, setShowAgent] = useState(true);
    const rootHandleRef = useRef<FileSystemDirectoryHandle | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Copilot State
    const [copilotMode, setCopilotMode] = useState<CopilotMode>('suggest');
    const [diffPreviewOpen, setDiffPreviewOpen] = useState(false);
    const [proposalDiff, setProposalDiff] = useState('');
    const [proposalId, setProposalId] = useState('');
    const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

    // Derived state
    const currentFile = openFiles.find(f => f.path === activeFile);
    const saveFunctionRef = useRef<() => void>(() => { });

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

            setRootPath(folderPath);
            loadProjectHistory(folderPath);

            if (window.electronAPI?.fs) {
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
            }
        } catch (err) {
            console.error('Failed to open folder:', err);
        }
    };

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
                // TODO: Implement save from menu
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
                        user_input: originalMessage
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



    const renderNode = (node: FileNode, depth = 0): React.ReactNode => (
        <div key={node.path}>
            <div
                className={`flex items - center gap - 1.5 px - 2 py - 1 cursor - pointer hover: bg - cyan - 500 / 10 rounded text - sm ${activeFile === node.path ? 'bg-cyan-500/20' : ''} `}
                style={{ paddingLeft: `${depth * 16 + 8} px` }}
                onClick={() => node.type === 'folder' ? toggleFolder(node) : openFile(node)}
            >
                {node.type === 'folder' ? (
                    <>
                        {node.expanded ? <ChevronDown size={14} className="text-cyan-500/60" /> : <ChevronRight size={14} className="text-cyan-500/60" />}
                        <Folder size={14} className="text-cyan-400" />
                    </>
                ) : (
                    <>
                        <span className="w-3.5" />
                        <FileText size={14} className="text-cyan-500/50" />
                    </>
                )}
                <span className="truncate text-white/80">{node.name}</span>
            </div>
            {node.type === 'folder' && node.expanded && node.children?.map(child => renderNode(child, depth + 1))}
        </div>
    );

    return (
        <div className="fixed inset-0 flex flex-col" style={{ zIndex: 99999, background: '#0a0f1a' }} onClick={() => setActiveMenu(null)}>
            {/* Menu Bar */}
            <div className="h-8 bg-[#1e1e1e] flex items-center px-2 text-sm shrink-0 border-b border-[#333]">
                {/* Window Controls */}
                <div className="flex items-center gap-1.5 mr-4">
                    <div className="w-3 h-3 rounded-full bg-red-500 cursor-pointer hover:brightness-110" onClick={onClose} />
                    <div className="w-3 h-3 rounded-full bg-yellow-500 hover:brightness-110" />
                    <div className="w-3 h-3 rounded-full bg-green-500 hover:brightness-110" />
                </div>

                {/* Menu Items */}
                {['File', 'Edit', 'View', 'Run', 'Terminal', 'Help'].map(menu => (
                    <div key={menu} className="relative">
                        <button
                            className={`px-3 py-1 text-white/80 hover:bg-white/10 rounded text-xs ${activeMenu === menu ? 'bg-white/10' : ''}`}
                            onClick={(e) => { e.stopPropagation(); setActiveMenu(activeMenu === menu ? null : menu); }}
                        >
                            {menu}
                        </button>

                        {/* Dropdown Menu */}
                        {activeMenu === menu && (
                            <div className="absolute top-full left-0 mt-1 bg-[#252526] border border-[#454545] rounded shadow-xl min-w-[220px] py-1 z-50" onClick={e => e.stopPropagation()}>
                                {menu === 'File' && (
                                    <>
                                        <button onClick={() => { const name = prompt('File name:'); if (name) { createNewFile(name, '', getLanguage(name)); } setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>New File</span><span className="text-white/40">Ctrl+N</span>
                                        </button>
                                        <button onClick={() => { handleSelectFolder(); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>Open Folder...</span><span className="text-white/40">Ctrl+K Ctrl+O</span>
                                        </button>
                                        <div className="border-t border-[#454545] my-1" />
                                        <button onClick={() => { const f = openFiles.find(f => f.path === activeFile); if (f) saveFileToBackend(f.path, f.content); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs" disabled={!activeFile}>
                                            <span>Save</span><span className="text-white/40">Ctrl+S</span>
                                        </button>
                                        <button className="w-full px-4 py-1.5 text-left text-white/40 cursor-not-allowed flex justify-between text-xs">
                                            <span>Save As...</span><span className="text-white/40">Ctrl+Shift+S</span>
                                        </button>
                                        <button onClick={() => { openFiles.forEach(f => saveFileToBackend(f.path, f.content)); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>Save All</span><span className="text-white/40">Ctrl+K S</span>
                                        </button>
                                        <div className="border-t border-[#454545] my-1" />
                                        <button onClick={() => { if (activeFile) closeFile(activeFile); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>Close Editor</span><span className="text-white/40">Ctrl+W</span>
                                        </button>
                                        <button onClick={() => { setOpenFiles([]); setActiveFile(null); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 text-xs">
                                            Close All Editors
                                        </button>
                                        <div className="border-t border-[#454545] my-1" />
                                        <button onClick={onClose} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>Exit</span><span className="text-white/40">Alt+F4</span>
                                        </button>
                                    </>
                                )}
                                {menu === 'Edit' && (
                                    <>
                                        <button className="w-full px-4 py-1.5 text-left text-white/40 cursor-not-allowed flex justify-between text-xs">
                                            <span>Undo</span><span className="text-white/40">Ctrl+Z</span>
                                        </button>
                                        <button className="w-full px-4 py-1.5 text-left text-white/40 cursor-not-allowed flex justify-between text-xs">
                                            <span>Redo</span><span className="text-white/40">Ctrl+Y</span>
                                        </button>
                                        <div className="border-t border-[#454545] my-1" />
                                        <button className="w-full px-4 py-1.5 text-left text-white/40 cursor-not-allowed flex justify-between text-xs">
                                            <span>Cut</span><span className="text-white/40">Ctrl+X</span>
                                        </button>
                                        <button className="w-full px-4 py-1.5 text-left text-white/40 cursor-not-allowed flex justify-between text-xs">
                                            <span>Copy</span><span className="text-white/40">Ctrl+C</span>
                                        </button>
                                        <button className="w-full px-4 py-1.5 text-left text-white/40 cursor-not-allowed flex justify-between text-xs">
                                            <span>Paste</span><span className="text-white/40">Ctrl+V</span>
                                        </button>
                                        <div className="border-t border-[#454545] my-1" />
                                        <button className="w-full px-4 py-1.5 text-left text-white/40 cursor-not-allowed flex justify-between text-xs">
                                            <span>Find</span><span className="text-white/40">Ctrl+F</span>
                                        </button>
                                        <button className="w-full px-4 py-1.5 text-left text-white/40 cursor-not-allowed flex justify-between text-xs">
                                            <span>Replace</span><span className="text-white/40">Ctrl+H</span>
                                        </button>
                                    </>
                                )}
                                {menu === 'View' && (
                                    <>
                                        <button onClick={() => { setShowSidebar(!showSidebar); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>{showSidebar ? '✓ ' : ''}Explorer</span><span className="text-white/40">Ctrl+B</span>
                                        </button>
                                        <button onClick={() => { setShowAgent(!showAgent); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>{showAgent ? '✓ ' : ''}AI Agent Panel</span>
                                        </button>
                                        <button onClick={() => { setTerminalOpen(!terminalOpen); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>{terminalOpen ? '✓ ' : ''}Terminal</span><span className="text-white/40">Ctrl+`</span>
                                        </button>
                                    </>
                                )}
                                {menu === 'Run' && (
                                    <>
                                        <button onClick={() => { setTerminalOpen(true); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>Run Current File</span><span className="text-white/40">F5</span>
                                        </button>
                                        <button className="w-full px-4 py-1.5 text-left text-white/40 cursor-not-allowed flex justify-between text-xs">
                                            <span>Run Without Debugging</span><span className="text-white/40">Ctrl+F5</span>
                                        </button>
                                    </>
                                )}
                                {menu === 'Terminal' && (
                                    <>
                                        <button onClick={() => { setTerminalOpen(true); setActiveMenu(null); }} className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 flex justify-between text-xs">
                                            <span>New Terminal</span><span className="text-white/40">Ctrl+Shift+`</span>
                                        </button>
                                    </>
                                )}
                                {menu === 'Help' && (
                                    <>
                                        <button className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 text-xs">
                                            Keyboard Shortcuts
                                        </button>
                                        <div className="border-t border-[#454545] my-1" />
                                        <button className="w-full px-4 py-1.5 text-left text-white/80 hover:bg-cyan-500/30 text-xs">
                                            About Neural Code Editor
                                        </button>
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                ))}

                <div className="flex-1" />
                <span className="text-white/40 text-xs">{rootPath || 'Neural Code Editor'}</span>
            </div>


            <div className="flex-1 flex overflow-hidden">
                {/* File Explorer */}
                {showSidebar && (
                    <div className="w-60 bg-[#0c1624] border-r border-cyan-500/10 flex flex-col shrink-0">
                        <div className="px-3 py-2 text-xs text-cyan-500/60 font-medium uppercase tracking-wider border-b border-cyan-500/10 flex items-center justify-between">
                            <span>Explorer</span>
                            <button
                                onClick={handleSelectFolder}
                                className="hover:bg-cyan-500/20 p-1 rounded"
                                title="Open Folder"
                            >
                                <FolderOpen size={14} className="text-cyan-500/60" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto">
                            {rootPath ? (
                                <div>
                                    {/* Folder Name Header */}
                                    <div
                                        className="flex items-center gap-1.5 px-2 py-1.5 cursor-pointer hover:bg-cyan-500/10 text-xs font-semibold text-white/90 border-b border-cyan-500/5"
                                    >
                                        <ChevronDown size={14} className="text-cyan-500/60" />
                                        <Folder size={14} className="text-cyan-400" />
                                        <span className="truncate uppercase tracking-wide">
                                            {rootPath.split('\\').pop() || rootPath.split('/').pop() || 'Folder'}
                                        </span>
                                    </div>
                                    {/* Disconnected Warning */}
                                    {!isFolderConnected() && (
                                        <div className="px-2 py-2 bg-yellow-500/10 border-b border-yellow-500/20">
                                            <p className="text-yellow-400/80 text-xs mb-1">⚠️ Folder disconnected</p>
                                            <button
                                                onClick={handleSelectFolder}
                                                className="text-xs text-cyan-400 hover:underline"
                                            >
                                                Reconnect to save files
                                            </button>
                                        </div>
                                    )}
                                    {/* File Tree */}
                                    <div className="py-1">
                                        {fileTree.map(node => renderNode(node, 1))}
                                    </div>
                                </div>
                            ) : fileTree.length > 0 ? (
                                <div className="py-1">
                                    {fileTree.map(node => renderNode(node))}
                                </div>
                            ) : (
                                <div className="p-4 text-center">
                                    <FolderOpen size={32} className="mx-auto mb-3 text-cyan-500/30" />
                                    <p className="text-cyan-500/40 text-sm">No folder open</p>
                                    <button onClick={handleSelectFolder} className="text-cyan-400 text-sm hover:underline mt-2">Open a folder</button>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Editor + Terminal */}
                <div className="flex-1 flex flex-col min-w-0 bg-[#0d1520]">
                    {/* File Tabs */}
                    <div className="h-9 bg-[#0c1624] border-b border-cyan-500/10 flex items-center overflow-x-auto shrink-0">
                        {openFiles.length === 0 && <div className="px-4 text-cyan-500/40 text-sm">No files open</div>}
                        {openFiles.map(file => (
                            <div key={file.path} className={`flex items-center gap-2 px-3 py-1.5 border-r border-cyan-500/10 cursor-pointer shrink-0 ${activeFile === file.path ? 'bg-[#0d1520] text-white' : 'text-white/50 hover:bg-white/5'}`} onClick={() => setActiveFile(file.path)}>
                                <FileText size={12} className="text-cyan-500/50" />
                                <span className="text-sm whitespace-nowrap">{file.modified && '● '}{file.name}</span>
                                <X size={14} className="text-white/30 hover:text-red-400" onClick={(e) => { e.stopPropagation(); closeFile(file.path); }} />
                            </div>
                        ))}
                    </div>

                    <div className={`flex-1 min-h-0 ${terminalOpen ? 'h-[calc(100%-200px)]' : 'h-full'}`}>
                        {currentFile ? (
                            <Editor
                                height="100%"
                                language={currentFile.language}
                                value={currentFile.content}
                                theme="vs-dark"
                                onMount={handleEditorDidMount}
                                onChange={(v) => updateFileContent(currentFile.path, v || '')}
                                options={{ fontSize: 14, fontFamily: "'JetBrains Mono', Consolas, monospace", minimap: { enabled: true }, scrollBeyondLastLine: false, wordWrap: 'on', padding: { top: 12 } }}
                            />
                        ) : (
                            <div className="h-full flex items-center justify-center text-cyan-500/40">
                                <div className="text-center">
                                    <FileText size={56} className="mx-auto mb-4 opacity-40" />
                                    <p>Select a file to edit</p>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Terminal Panel */}
                    <TerminalPanel
                        isOpen={terminalOpen}
                        onToggle={() => setTerminalOpen(!terminalOpen)}
                        cwd={rootPath || undefined}
                    />
                </div>

                {/* AI Agent */}
                {showAgent && (
                    <div className="w-80 bg-[#0c1624] border-l border-cyan-500/10 flex flex-col shrink-0">
                        <div className="px-3 py-2 border-b border-cyan-500/10 flex items-center gap-2">
                            <Sparkles size={16} className="text-cyan-400" />
                            <span className="text-sm font-medium text-white">Code Agent</span>
                            <Wand2 size={14} className="ml-auto text-cyan-500/50" />
                        </div>
                        <div className="flex-1 overflow-y-auto p-3 space-y-3">
                            {agentMessages.map((msg, i) => (
                                <div key={i} className={`p - 3 rounded - lg text - sm ${msg.role === 'user' ? 'bg-cyan-500/20 ml-6' : 'bg-[#0a0f1a] mr-2'} `}>
                                    <pre className="whitespace-pre-wrap font-sans text-sm text-white/85">{msg.text}</pre>
                                </div>
                            ))}
                            {isLoading && <div className="p-3 rounded-lg bg-[#0a0f1a] flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" /><span className="text-cyan-400 text-sm">Generating...</span></div>}
                            <div ref={messagesEndRef} />
                        </div>
                        <div className="p-3 border-t border-cyan-500/10">
                            <div className="flex gap-2">
                                <input type="text" value={agentInput} onChange={(e) => setAgentInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendToAgent()} placeholder="Ask or generate code..." className="flex-1 bg-[#0a0f1a] border border-cyan-500/30 rounded-lg px-3 py-2 text-sm text-white placeholder-cyan-500/40 focus:outline-none focus:border-cyan-500" />
                                <button onClick={sendToAgent} disabled={isLoading} className="p-2.5 bg-cyan-500 hover:bg-cyan-400 rounded-lg disabled:opacity-40">
                                    <Send size={16} className="text-[#0a0f1a]" />
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div >
    );
}
