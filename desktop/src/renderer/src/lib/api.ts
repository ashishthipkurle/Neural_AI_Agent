import { ElectronAPI } from '../types/electron'

// Detect if we are running in Electron
const isElectron = typeof window !== 'undefined' && (window as any).electronAPI !== undefined

// Mock API for Web (to be implemented fully later or effectively no-op for now)
const webAPI: Partial<ElectronAPI> = {
    terminal: {
        create: async () => { console.warn('Terminal not supported on web yet'); return '' },
        input: async () => { console.log('Terminal input not supported') },
        resize: async () => { },
        kill: async () => { },
        list: async () => [],
        onData: () => () => { },
        onExit: () => () => { }
    },
    fs: {
        openFolder: async () => null,
        listDir: async () => [],
        readFile: async () => '',
        writeFile: async () => { },
        exists: async () => false
    },
    agent: {
        sendCommand: async () => { },
        onResponse: () => { },
        onSync: () => () => { },
        cancel: () => { }
    },
    system: {
        runCommand: async () => ({ approved: false, error: 'Not supported' }),
        openApp: async () => ({ approved: false }),
        openUrl: async (url) => { window.open(url, '_blank') }
    },
    menu: {
        onNewFile: () => { },
        onOpenFolder: () => { },
        onSave: () => { },
        onToggleCodeEditor: () => { },
        onToggleTerminal: () => { },
        onNewTerminal: () => { }
    }
}

// Export the API
export const api = isElectron ? (window as any).electronAPI as ElectronAPI : webAPI as ElectronAPI
