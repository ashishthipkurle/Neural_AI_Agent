import React, { useState, useRef, useEffect } from 'react';
import { X, FolderOpen, ChevronRight, ChevronDown, FileText, Folder, Send, Sparkles, Code2, Wand2, Plus, FilePlus, Save, Copy, Scissors, Clipboard, RotateCcw, RotateCw, Eye, EyeOff, Terminal, Settings } from 'lucide-react';
import Editor from '@monaco-editor/react';
import TerminalPanel from './TerminalPanel';

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


    // Load session from localStorage on mount
    useEffect(() => {
        let sessionLoaded = false;
        try {
            const savedSession = localStorage.getItem('codeEditorSession');
            if (savedSession) {
                const session = JSON.parse(savedSession);
                if (session.openFiles) setOpenFiles(session.openFiles);
                if (session.activeFile) setActiveFile(session.activeFile);
                if (session.rootPath) setRootPath(session.rootPath);
                if (session.fileTree && session.fileTree.length > 0) {
                    setFileTree(session.fileTree);
                    sessionLoaded = true;
                }
                if (session.agentMessages) setAgentMessages(session.agentMessages);
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
            fileTree,
            agentMessages: agentMessages.slice(-20) // Keep last 20 messages
        };
        localStorage.setItem('codeEditorSession', JSON.stringify(session));
    }, [openFiles, activeFile, rootPath, fileTree, agentMessages]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [agentMessages]);

    // Handle folder selection - simple top-level only
    const handleSelectFolder = async () => {
        try {
            // @ts-ignore
            const dirHandle: FileSystemDirectoryHandle = await window.showDirectoryPicker();
            rootHandleRef.current = dirHandle;
            setRootPath(dirHandle.name);

            const items: FileNode[] = [];
            // @ts-ignore - entries() is experimental
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
            console.log('Loaded', items.length, 'items from', dirHandle.name);
        } catch (err) {
            console.error('Folder selection error:', err);
        }
    };

    // Load children when folder is expanded
    const loadChildren = async (node: FileNode): Promise<FileNode[]> => {
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

            if (node.handle) {
                // Use FileSystem API for user-selected folders
                const fileHandle = node.handle as FileSystemFileHandle;
                const file = await fileHandle.getFile();
                content = await file.text();
            } else {
                // Use backend API for files without handles (default generated folder)
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

    const createNewFile = (name: string, content: string, lang: string) => {
        // Use selected folder if available, otherwise use generated/
        const basePath = rootPath || 'generated';
        const path = `${basePath}/${name}`;
        setOpenFiles(prev => [...prev, { path, name, content, language: lang, modified: true }]);
        setActiveFile(path);
        // Auto-save generated files to disk
        saveFileToBackend(path, content, name);
    };

    const saveFileToBackend = async (path: string, content: string, filename?: string) => {
        try {
            // Determine save location - use rootPath if selected, else default
            const saveDir = rootPath || 'D:\\All Projects\\My AI Agent\\generated';
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
        if (!rootHandleRef.current) return;
        try {
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
        } catch (err) {
            console.error('Failed to refresh file tree:', err);
        }
    };

    const saveCurrentFile = () => {
        if (currentFile) {
            saveFileToBackend(currentFile.path, currentFile.content);
        }
    };

    const sendToAgent = async () => {
        if (!agentInput.trim()) return;
        const originalMessage = agentInput;  // Save before clearing
        const userMessage = agentInput.toLowerCase();
        setAgentMessages(prev => [...prev, { role: 'user', text: originalMessage }]);
        setAgentInput('');
        setIsLoading(true);

        // Check for calculator request - use built-in template
        if (userMessage.includes('calculator')) {
            const calculatorCode = `<!DOCTYPE html>
<html>
<head>
    <title>Calculator</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            font-family: 'Segoe UI', sans-serif;
        }
        .calculator {
            background: linear-gradient(145deg, #2d2d44, #1a1a2e);
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5), inset 0 1px 1px rgba(255,255,255,0.1);
        }
        .display {
            background: #0a0a15;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            text-align: right;
            border: 1px solid rgba(0,200,220,0.2);
        }
        .display .previous { color: rgba(0,200,220,0.5); font-size: 14px; min-height: 20px; }
        .display .current { color: #00c8d4; font-size: 36px; font-weight: 300; word-break: break-all; }
        .buttons { display: grid; grid-template-columns: repeat(4, 70px); gap: 12px; }
        button {
            height: 70px;
            border: none;
            border-radius: 12px;
            font-size: 24px;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        button:hover { transform: translateY(-2px); }
        button:active { transform: translateY(0); }
        .number {
            background: linear-gradient(145deg, #3d3d5c, #2a2a40);
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
        .number:hover { background: linear-gradient(145deg, #4a4a6a, #3a3a50); }
        .operator {
            background: linear-gradient(145deg, #00c8d4, #00a0b0);
            color: #1a1a2e;
            font-weight: bold;
            box-shadow: 0 4px 15px rgba(0,200,220,0.3);
        }
        .operator:hover { background: linear-gradient(145deg, #00e0f0, #00b8c8); }
        .clear {
            background: linear-gradient(145deg, #ff6b6b, #ee5a5a);
            color: white;
            box-shadow: 0 4px 15px rgba(255,100,100,0.3);
        }
        .equals { grid-column: span 2; }
    </style>
</head>
<body>
    <div class="calculator">
        <div class="display">
            <div class="previous" id="previous"></div>
            <div class="current" id="current">0</div>
        </div>
        <div class="buttons">
            <button class="clear" onclick="clearAll()">C</button>
            <button class="operator" onclick="appendOperator('/')">/</button>
            <button class="operator" onclick="appendOperator('*')">×</button>
            <button class="operator" onclick="backspace()">⌫</button>
            <button class="number" onclick="appendNumber('7')">7</button>
            <button class="number" onclick="appendNumber('8')">8</button>
            <button class="number" onclick="appendNumber('9')">9</button>
            <button class="operator" onclick="appendOperator('-')">−</button>
            <button class="number" onclick="appendNumber('4')">4</button>
            <button class="number" onclick="appendNumber('5')">5</button>
            <button class="number" onclick="appendNumber('6')">6</button>
            <button class="operator" onclick="appendOperator('+')">+</button>
            <button class="number" onclick="appendNumber('1')">1</button>
            <button class="number" onclick="appendNumber('2')">2</button>
            <button class="number" onclick="appendNumber('3')">3</button>
            <button class="number" onclick="appendNumber('.')">.</button>
            <button class="number" onclick="appendNumber('0')">0</button>
            <button class="operator equals" onclick="calculate()">=</button>
        </div>
    </div>
    <script>
        let current = '0';
        let previous = '';
        let operator = null;

        function updateDisplay() {
            document.getElementById('current').textContent = current;
            document.getElementById('previous').textContent = previous;
        }

        function appendNumber(num) {
            if (current === '0' && num !== '.') current = num;
            else if (num === '.' && current.includes('.')) return;
            else current += num;
            updateDisplay();
        }

        function appendOperator(op) {
            if (operator) calculate();
            previous = current + ' ' + op;
            operator = op;
            current = '0';
            updateDisplay();
        }

        function calculate() {
            if (!operator) return;
            const prev = parseFloat(previous);
            const curr = parseFloat(current);
            let result;
            switch(operator) {
                case '+': result = prev + curr; break;
                case '-': result = prev - curr; break;
                case '*': result = prev * curr; break;
                case '/': result = prev / curr; break;
            }
            current = result.toString();
            previous = '';
            operator = null;
            updateDisplay();
        }

        function clearAll() {
            current = '0';
            previous = '';
            operator = null;
            updateDisplay();
        }

        function backspace() {
            current = current.length > 1 ? current.slice(0, -1) : '0';
            updateDisplay();
        }
    </script>
</body>
</html>`;

            setAgentMessages(prev => [...prev, {
                role: 'agent',
                text: '✨ Created a beautiful calculator! I\'ve opened it in a new tab. It has:\n• Number buttons (0-9)\n• Operators (+, −, ×, /)\n• Display with history\n• Clear & Backspace\n• Modern dark theme\n\nSave the file and open in browser to use!'
            }]);
            createNewFile('calculator.html', calculatorCode, 'html');
            setIsLoading(false);
            return;
        }

        // For other requests, use the LLM
        try {
            const currentFile = openFiles.find(f => f.path === activeFile);
            const context = currentFile ? `\nFile: ${currentFile.name}\n\`\`\`${currentFile.language}\n${currentFile.content.slice(0, 1500)}\n\`\`\`` : '';
            // Use coding model endpoint for code generation
            const response = await fetch('http://localhost:8000/api/code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: `You are an expert software engineer. Generate clean, working, well-documented code.

User request: ${originalMessage}${context}

Requirements:
- Write complete, runnable code
- Include comments explaining the logic
- Use modern best practices
- Format code properly in a code block`
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
                    html: 'html', css: 'css', json: 'json'
                };

                // Check if this is a modification request
                const isModificationRequest = userMessage.includes('modify') || userMessage.includes('refine') ||
                    userMessage.includes('update') || userMessage.includes('change') || userMessage.includes('fix') ||
                    userMessage.includes('improve') || userMessage.includes('add ');

                const currentFileInfo = openFiles.find(f => f.path === activeFile);

                if (isModificationRequest && currentFileInfo && matches.length === 1) {
                    // Single code block + modification request = update existing file
                    const code = matches[0][2].trim();
                    updateFileContent(currentFileInfo.path, code);
                    saveFileToBackend(currentFileInfo.path, code);
                    setAgentMessages(prev => [...prev, { role: 'agent', text: '✅ Updated the current file!' }]);
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
                        else if (lang === 'javascript' || lang === 'js') filename = 'script';

                        // Add index if multiple files of same type
                        if (matches.filter(m => (m[1] || 'text') === lang).length > 1) {
                            filename += `_${index + 1}`;
                        }

                        createNewFile(`${filename}.${ext}`, code, lang);
                        fileCount++;
                    });

                    if (fileCount > 1) {
                        setAgentMessages(prev => [...prev, { role: 'agent', text: `✅ Created ${fileCount} files!` }]);
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

    const currentFile = openFiles.find(f => f.path === activeFile);

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
                        <div className="px-3 py-2 text-xs text-cyan-500/60 font-medium uppercase tracking-wider border-b border-cyan-500/10">Explorer</div>
                        <div className="flex-1 overflow-y-auto py-1">
                            {fileTree.length > 0 ? fileTree.map(node => renderNode(node)) : (
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

                    {/* Editor Area */}
                    <div className={`flex-1 min-h-0 ${terminalOpen ? 'h-[calc(100%-200px)]' : 'h-full'}`}>
                        {currentFile ? (
                            <Editor height="100%" language={currentFile.language} value={currentFile.content} theme="vs-dark" onChange={(v) => updateFileContent(currentFile.path, v || '')} options={{ fontSize: 14, fontFamily: "'JetBrains Mono', Consolas, monospace", minimap: { enabled: true }, scrollBeyondLastLine: false, wordWrap: 'on', padding: { top: 12 } }} />
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
                        currentFile={currentFile?.path}
                        workingDirectory={rootPath || 'D:\\All Projects\\My AI Agent\\generated'}
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
        </div>
    );
}
