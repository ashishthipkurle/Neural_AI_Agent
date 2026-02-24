export interface ElectronAPI {
    terminal: {
        create: (data: { id: string; cwd: string; shell: 'powershell' | 'cmd' }) => Promise<any>
        input: (data: { id: string; data: string }) => Promise<any>
        resize: (data: { id: string; cols: number; rows: number }) => Promise<any>
        kill: (id: string) => Promise<any>
        list: () => Promise<string[]>
        onData: (id: string, callback: (data: string) => void) => () => void
        onExit: (id: string, callback: (code: number) => void) => () => void
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
        onSync: (callback: (data: any) => void) => (() => void)
        cancel: () => void
    }
    system: {
        runCommand: (cmd: string) => Promise<{ approved: boolean, output?: string, error?: string }>
        openApp: (appName: string) => Promise<{ approved: boolean }>
        openUrl: (url: string) => Promise<void>
        captureWebview: () => Promise<string | null>
    }
    menu: {
        onNewFile: (cb: () => void) => void
        onOpenFolder: (cb: (path: string) => void) => void
        onSave: (cb: () => void) => void
        onToggleCodeEditor: (cb: () => void) => void
        onToggleTerminal: (cb: () => void) => void
        onNewTerminal: (cb: (shell?: string) => void) => void
    }
}

declare global {
    interface Window {
        electronAPI: ElectronAPI
    }
}
