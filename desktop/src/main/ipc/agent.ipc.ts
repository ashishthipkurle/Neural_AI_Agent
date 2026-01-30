import { IpcMain, BrowserWindow } from 'electron'
import { request } from 'http'

let isGenerating = false

export function registerAgentHandlers(ipcMain: IpcMain, mainWindow: BrowserWindow | null): void {
    ipcMain.handle('agent:command', async (_, text: string) => {
        if (!text || typeof text !== 'string') throw new Error('Invalid command')

        const postData = JSON.stringify({
            message: text
        })

        const options = {
            hostname: '127.0.0.1',
            port: 8000,
            path: '/api/chat',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            }
        }

        const req = request(options, (res) => {
            let buffer = '';
            res.on('data', (chunk) => { buffer += chunk; });
            res.on('end', () => {
                try {
                    const data = JSON.parse(buffer);
                    console.log('Agent API Response:', data.status);
                    // Actual chat updates come via WebSocket sync
                } catch (e) {
                    console.error('Failed to parse API response');
                }
            });
        })

        req.on('error', (error: Error) => {
            console.error('Agent API error:', error)
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('agent:sync', {
                    type: 'error',
                    role: 'system',
                    text: `Error: ${error.message}. Is the Python backend running?`
                });
            }
        })

        req.write(postData)
        req.end()
    })

    ipcMain.on('agent:cancel', () => { /* Handled on backend if needed */ })
}
