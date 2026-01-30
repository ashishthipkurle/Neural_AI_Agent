export interface ElectronAPI {
    terminal: {
        create: (shell: 'powershell' | 'cmd', cwd?: string) => Promise<string>
        write: (id: string, data: string) => void
        resize: (id: string, cols: number, rows: number) => void
        dispose: (id: string) => void
        onData: (callback: (id: string, data: string) => void) => void
        onExit: (callback: (id: string, code: number) => void) => void
    }
    fs: {
        openFolder: () => Promise<string | null>
        listDir: (dirPath: string) => Promise<Array<{ name: string, path: string, type: 'file' | 'directory' }>>
        readFile: (filePath: string) => Promise<string>
        writeFile: (filePath: string, content: string) => Promise<void>
        exists: (filePath: string) => Promise<boolean>
    }
    agent: {
        sendCommand: (text: string, context?: string) => Promise<void>
        onResponse: (callback: (chunk: string, done: boolean) => void) => void
        cancel: () => void
    }
    system: {
        runCommand: (cmd: string) => Promise<{ approved: boolean, output?: string, error?: string }>
        openApp: (appName: string) => Promise<{ approved: boolean }>
        openUrl: (url: string) => Promise<void>
    }
    menu: {
        onNewFile: (cb: () => void) => void
        onOpenFolder: (cb: (path: string) => void) => void
        onSave: (cb: () => void) => void
        onToggleTerminal: (cb: () => void) => void
        onNewTerminal: (cb: (shell?: string) => void) => void
    }
}

declare global {
    interface Window {
        electronAPI: ElectronAPI
    }
}
