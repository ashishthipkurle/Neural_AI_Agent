import { contextBridge, ipcRenderer } from 'electron'

// Terminal API - VS Code-grade terminal with tabs
const terminalAPI = {
    create: (data: { id: string; cwd: string; shell: 'powershell' | 'cmd' }) =>
        ipcRenderer.invoke('terminal:create', data),
    input: (data: { id: string; data: string }) => {
        ipcRenderer.send('terminal:input', data)
        return Promise.resolve()
    },
    resize: (data: { id: string; cols: number; rows: number }) => {
        ipcRenderer.send('terminal:resize', data.id, data.cols, data.rows)
        return Promise.resolve()
    },
    kill: (id: string) =>
        ipcRenderer.invoke('terminal:kill', id),
    list: () =>
        ipcRenderer.invoke('terminal:list'),
    onData: (id: string, callback: (data: string) => void) => {
        const handler = (_: any, incomingId: string, data: string) => {
            if (incomingId === id) callback(data)
        }
        ipcRenderer.on('terminal:data', handler)
        return () => ipcRenderer.removeListener('terminal:data', handler)
    },
    onExit: (id: string, callback: (code: number) => void) => {
        const handler = (_: any, incomingId: string, code: number) => {
            if (incomingId === id) callback(code)
        }
        ipcRenderer.on('terminal:exit', handler)
        return () => ipcRenderer.removeListener('terminal:exit', handler)
    }
}

// File System API
const fsAPI = {
    openFolder: (): Promise<string | null> =>
        ipcRenderer.invoke('fs:openFolder'),
    listDir: (dirPath: string): Promise<Array<{ name: string; path: string; type: 'file' | 'directory' }>> =>
        ipcRenderer.invoke('fs:listDir', dirPath),
    readFile: (filePath: string): Promise<string> =>
        ipcRenderer.invoke('fs:readFile', filePath),
    writeFile: (filePath: string, content: string): Promise<void> =>
        ipcRenderer.invoke('fs:writeFile', filePath, content),
    exists: (filePath: string): Promise<boolean> =>
        ipcRenderer.invoke('fs:exists', filePath)
}

// Agent API
const agentAPI = {
    sendCommand: (text: string, context?: string): Promise<void> =>
        ipcRenderer.invoke('agent:command', text, context),
    onResponse: (callback: (chunk: string, done: boolean) => void): void => {
        ipcRenderer.on('agent:response', (_, chunk: string, done: boolean) => callback(chunk, done))
    },
    onSync: (callback: (data: any) => void): (() => void) => {
        const handler = (_: any, data: any) => callback(data)
        ipcRenderer.on('agent:sync', handler)
        return () => ipcRenderer.removeListener('agent:sync', handler)
    },
    cancel: (): void => ipcRenderer.send('agent:cancel')
}

// System API
const systemAPI = {
    runCommand: (cmd: string): Promise<{ approved: boolean; output?: string; error?: string }> =>
        ipcRenderer.invoke('system:runCommand', cmd),
    openApp: (appName: string): Promise<{ approved: boolean }> =>
        ipcRenderer.invoke('system:openApp', appName),
    openUrl: (url: string): Promise<void> =>
        ipcRenderer.invoke('system:openUrl', url),
    captureWebview: (): Promise<string | null> =>
        ipcRenderer.invoke('system:captureWebview')
}

// Menu API
const menuAPI = {
    onNewFile: (cb: () => void): void => { ipcRenderer.on('menu:newFile', () => cb()) },
    onOpenFolder: (cb: (path: string) => void): void => { ipcRenderer.on('menu:openFolder', (_, p: string) => cb(p)) },
    onSave: (cb: () => void): void => { ipcRenderer.on('menu:save', () => cb()) },
    onToggleCodeEditor: (cb: () => void): void => { ipcRenderer.on('menu:toggleCodeEditor', () => cb()) },
    onToggleTerminal: (cb: () => void): void => { ipcRenderer.on('menu:toggleTerminal', () => cb()) },
    onNewTerminal: (cb: (shell?: string) => void): void => { ipcRenderer.on('menu:newTerminal', (_, s?: string) => cb(s)) }
}

// Expose APIs to renderer
if (process.contextIsolated) {
    try {
        contextBridge.exposeInMainWorld('terminalAPI', terminalAPI)
        contextBridge.exposeInMainWorld('electronAPI', {
            terminal: terminalAPI,
            fs: fsAPI,
            agent: agentAPI,
            system: systemAPI,
            menu: menuAPI
        })
    } catch (error) {
        console.error(error)
    }
} else {
    // @ts-ignore
    window.terminalAPI = terminalAPI
    // @ts-ignore
    window.electronAPI = { terminal: terminalAPI, fs: fsAPI, agent: agentAPI, system: systemAPI, menu: menuAPI }
}
