import { IpcMain, BrowserWindow } from 'electron'

interface PtyManager {
    create: (shell: 'powershell' | 'cmd', id?: string, cwd?: string) => string
    write: (id: string, data: string) => void
    resize: (id: string, cols: number, rows: number) => void
    dispose: (id: string) => void
    onData: (id: string, callback: (data: string) => void) => void
    onExit: (id: string, callback: (code: number) => void) => void
}

export function registerTerminalHandlers(
    ipcMain: IpcMain,
    ptyManager: PtyManager,
    mainWindow: BrowserWindow | null
): void {
    ipcMain.removeHandler('terminal:create')
    ipcMain.removeHandler('terminal:create')
    ipcMain.handle('terminal:create', async (_, options: { id: string; shell: 'powershell' | 'cmd'; cwd?: string } | string) => {
        // Handle both object (new frontend) and string (legacy/test)
        let shell: 'powershell' | 'cmd' = 'powershell'
        let id: string | undefined
        let cwd: string | undefined

        if (typeof options === 'string') {
            shell = options as 'powershell' | 'cmd'
        } else {
            shell = options.shell
            id = options.id
            cwd = options.cwd
        }

        if (shell !== 'powershell' && shell !== 'cmd') {
            throw new Error('Invalid shell type')
        }

        // Pass ID to manager so it matches frontend
        const sessionId = ptyManager.create(shell, id, cwd)

        ptyManager.onData(sessionId, (data: string) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('terminal:data', sessionId, data)
            }
        })

        ptyManager.onExit(sessionId, (code: number) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('terminal:exit', sessionId, code)
            }
        })

        return sessionId
    })

    // Add support for terminal:input (matching frontend)
    ipcMain.removeAllListeners('terminal:input')
    ipcMain.on('terminal:input', (_, data: { id: string; data: string } | string, legacyData?: string) => {
        // Handle object style (invoke) or legacy (id, data) args
        let id: string
        let inputData: string

        if (typeof data === 'string' && typeof legacyData === 'string') {
            id = data
            inputData = legacyData
        } else if (typeof data === 'object') {
            id = data.id
            inputData = data.data
        } else {
            return
        }

        ptyManager.write(id, inputData)
    })

    ipcMain.removeAllListeners('terminal:write')
    ipcMain.on('terminal:write', (_, id: string, data: string) => {
        if (typeof id === 'string' && typeof data === 'string') {
            ptyManager.write(id, data)
        }
    })

    ipcMain.removeAllListeners('terminal:resize')
    ipcMain.on('terminal:resize', (_, id: string, cols: number, rows: number) => {
        if (typeof id === 'string' && cols > 0 && rows > 0) {
            ptyManager.resize(id, cols, rows)
        }
    })

    ipcMain.removeAllListeners('terminal:dispose')
    ipcMain.on('terminal:dispose', (_, id: string) => {
        if (typeof id === 'string') {
            ptyManager.dispose(id)
        }
    })
}
