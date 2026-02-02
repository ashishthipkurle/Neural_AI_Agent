import { IpcMain, dialog, shell, BrowserWindow } from 'electron'
import { exec } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)

const BLOCKED_PATTERNS = [
    /rm\s+-rf\s+[\/\\]/i,
    /del\s+\/f\s+\/s\s+\/q/i,
    /format\s+[a-z]:/i
]

function isBlocked(command: string): boolean {
    return BLOCKED_PATTERNS.some(pattern => pattern.test(command))
}

export function registerSystemHandlers(ipcMain: IpcMain, mainWindow: BrowserWindow | null): void {
    ipcMain.removeHandler('system:runCommand')
    ipcMain.handle('system:runCommand', async (_, command: string) => {
        if (!command || typeof command !== 'string') {
            return { approved: false, error: 'Invalid command' }
        }

        if (isBlocked(command)) {
            return { approved: false, error: 'Command blocked for safety' }
        }

        if (!mainWindow) return { approved: false, error: 'No window' }

        const result = await dialog.showMessageBox(mainWindow, {
            type: 'warning',
            title: 'Permission Required',
            message: 'AI Agent wants to run a command',
            detail: `Command: ${command}\n\nAllow this action?`,
            buttons: ['Deny', 'Allow'],
            defaultId: 0,
            cancelId: 0
        })

        if (result.response !== 1) return { approved: false }

        try {
            const { stdout, stderr } = await execAsync(command, { timeout: 30000 })
            return { approved: true, output: stdout, error: stderr || undefined }
        } catch (error: unknown) {
            const err = error as { message?: string }
            return { approved: true, error: err.message || 'Command failed' }
        }
    })

    ipcMain.removeHandler('system:openApp')
    ipcMain.handle('system:openApp', async (_, appName: string) => {
        if (!appName || typeof appName !== 'string') return { approved: false }
        if (!mainWindow) return { approved: false }

        const result = await dialog.showMessageBox(mainWindow, {
            type: 'question',
            title: 'Permission Required',
            message: 'AI Agent wants to open an application',
            detail: `Application: ${appName}\n\nAllow?`,
            buttons: ['Deny', 'Allow'],
            defaultId: 0
        })

        if (result.response !== 1) return { approved: false }

        try {
            await execAsync(`start "" "${appName}"`)
            return { approved: true }
        } catch {
            return { approved: false }
        }
    })

    ipcMain.removeHandler('system:openUrl')
    ipcMain.handle('system:openUrl', async (_, url: string) => {
        if (url && typeof url === 'string' && (url.startsWith('http://') || url.startsWith('https://'))) {
            await shell.openExternal(url)
        }
    })
}
