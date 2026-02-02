import { IpcMain, BrowserWindow } from 'electron'

interface PtyManager {
    create: (shell: 'powershell' | 'cmd', cwd?: string) => string
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
    ipcMain.handle('terminal:create', async (_, shell: 'powershell' | 'cmd') => {
        if (shell !== 'powershell' && shell !== 'cmd') {
            throw new Error('Invalid shell type')
        }
        const id = ptyManager.create(shell)

        ptyManager.onData(id, (data: string) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('terminal:data', id, data)
            }
        })

        ptyManager.onExit(id, (code: number) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('terminal:exit', id, code)
            }
        })

        return id
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
