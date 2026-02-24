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

    ipcMain.removeHandler('system:captureWebview')
    ipcMain.handle('system:captureWebview', async (event) => {
        // Get the webContents of the window that sent the IPC message
        const senderWebContents = event.sender

        // The webview is hosted within this window. We can iterate over all webContents
        // and find the one that corresponds to the webview (guest).
        const { webContents } = require('electron')
        const allWebContents = webContents.getAllWebContents()

        // Find a webContents that is a guest (webview) and belongs to our mainWindow
        // In this app architecture there is only one webview.
        const guestContents = allWebContents.find((wc: Electron.WebContents) => wc.getType() === 'webview')

        console.log('System IPC: Handling system:captureWebview request...');
        if (!guestContents) {
            console.error('System IPC: No webview guest found to capture.');
            return null;
        }

        try {
            console.log(`System IPC: Capturing guest webContents ID: ${guestContents.id}`);

            // Wrap in a Promise.race to prevent indefinite hangs
            const capturePromise = guestContents.capturePage()
            const timeoutPromise = new Promise<null>((resolve) => {
                setTimeout(() => {
                    console.error('System IPC: capturePage timed out after 10 seconds');
                    resolve(null);
                }, 10000);
            });

            const nativeImage = await Promise.race([capturePromise, timeoutPromise]);

            if (!nativeImage) {
                return null; // Timed out or failed
            }

            console.log('System IPC: Capture successful. Converting to Data URL...');
            const dataUrl = nativeImage.toDataURL();
            // Truncate for logging
            console.log(`System IPC: Data URL generated. Length: ${dataUrl.length}`);
            return dataUrl;
        } catch (err) {
            console.error('System IPC: Failed to capture webview:', err)
            return null
        }
    })
}
