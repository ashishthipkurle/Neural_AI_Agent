import { app, shell, BrowserWindow, ipcMain, Menu, dialog } from 'electron'
import { join } from 'path'
// import { electronApp, optimizer, is } from '@electron-toolkit/utils'

import { PtyManager } from './pty/ptyManager'
import { registerPtyHandlers, cleanupAllSessions } from './pty/ptyServer'
import { TerminalWebSocketServer } from './terminal/terminalServer'
import { registerTerminalHandlers } from './ipc/terminal.ipc'
import { registerFileSystemHandlers } from './ipc/filesystem.ipc'
import { registerAgentHandlers } from './ipc/agent.ipc'
import { registerSystemHandlers } from './ipc/system.ipc'

console.log('DEBUG: Main process starting...')

// Prevent webview ERR_ABORTED from crashing the entire app
process.on('unhandledRejection', (reason: any) => {
    // ERR_ABORTED (-3) happens when webview pages redirect or block embedding - not fatal
    if (reason?.message?.includes('ERR_ABORTED') || reason?.message?.includes('GUEST_VIEW_MANAGER_CALL')) {
        console.warn('Webview load error (non-fatal):', reason?.message?.substring(0, 100));
        return;
    }
    console.error('Unhandled rejection:', reason);
});

process.on('uncaughtException', (error: Error) => {
    if (error.message?.includes('ERR_ABORTED') || error.message?.includes('GUEST_VIEW_MANAGER_CALL')) {
        console.warn('Webview exception (non-fatal):', error.message.substring(0, 100));
        return;
    }
    console.error('Uncaught exception:', error);
});


let mainWindow: BrowserWindow | null = null
const ptyManager = new PtyManager()
const terminalServer = new TerminalWebSocketServer(8765)

function createWindow(): void {
    // Create the browser window.
    mainWindow = new BrowserWindow({
        width: 1600,
        height: 1000,
        minWidth: 1200,
        minHeight: 800,
        show: false,
        backgroundColor: '#0a0a0f',
        autoHideMenuBar: false,
        webPreferences: {
            preload: join(__dirname, '../preload/index.js'),
            sandbox: false,
            contextIsolation: true,
            nodeIntegration: false,
            webviewTag: true // Added to allow embedding external trading sites
        }
    })

    mainWindow.on('ready-to-show', () => {
        mainWindow?.show()
    })

    mainWindow.webContents.setWindowOpenHandler((details) => {
        shell.openExternal(details.url)
        return { action: 'deny' }
    })

    // Basic env check for dev
    if (process.env['ELECTRON_RENDERER_URL']) {
        mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
        mainWindow.webContents.openDevTools()
    } else {
        mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
    }
    // Handle webview errors gracefully
    mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
        console.warn(`Main window load error: ${errorCode} ${errorDescription} ${validatedURL}`);
    });

    // Handle errors from embedded webviews (guest webContents)
    app.on('web-contents-created', (_event, contents) => {
        if (contents.getType() === 'webview') {
            contents.on('did-fail-load', (_evt, errorCode, errorDescription, validatedURL) => {
                console.warn(`Webview load error (${errorCode}): ${errorDescription} - ${validatedURL}`);
            });
            contents.on('crashed', () => {
                console.warn('Webview process crashed, but app continues.');
            });
        }
    });
}

function createMenuTemplate(): Electron.MenuItemConstructorOptions[] {
    return [
        {
            label: 'File',
            submenu: [
                { label: 'New File', accelerator: 'CmdOrCtrl+N', click: () => mainWindow?.webContents.send('menu:newFile') },
                {
                    label: 'Open Folder...', accelerator: 'CmdOrCtrl+O', click: async () => {
                        console.log('DEBUG: Menu > Open Folder clicked');
                        const win = BrowserWindow.getFocusedWindow() || mainWindow;
                        if (!win) {
                            console.error('ERROR: No window found for Open Folder dialog');
                            return;
                        }

                        try {
                            const result = await dialog.showOpenDialog(win, { properties: ['openDirectory'] });
                            if (!result.canceled && result.filePaths.length > 0) {
                                console.log('DEBUG: Sending menu:openFolder', result.filePaths[0]);
                                win.webContents.send('menu:openFolder', result.filePaths[0]);
                            }
                        } catch (err) {
                            console.error('ERROR in Open Folder:', err);
                        }
                    }
                },
                { type: 'separator' },
                { label: 'Save', accelerator: 'CmdOrCtrl+S', click: () => mainWindow?.webContents.send('menu:save') },
                { type: 'separator' },
                { label: 'Exit', accelerator: 'Alt+F4', click: () => app.quit() }
            ]
        },
        {
            label: 'View',
            submenu: [
                { label: 'Toggle Code Editor', accelerator: 'CmdOrCtrl+Shift+E', click: () => mainWindow?.webContents.send('menu:toggleCodeEditor') },
                { label: 'Toggle Terminal', accelerator: 'CmdOrCtrl+`', click: () => mainWindow?.webContents.send('menu:toggleTerminal') },
                { label: 'Reload', accelerator: 'CmdOrCtrl+R', role: 'reload' },
                { label: 'DevTools', accelerator: 'F12', role: 'toggleDevTools' }
            ]
        }
    ]
}

let isInitialized = false

app.whenReady().then(() => {
    if (isInitialized) return
    isInitialized = true

    // electronApp.setAppUserModelId('com.neural-ai-agent') // removed

    app.on('browser-window-created', (_, window) => {
        // optimizer.watchWindowShortcuts(window) // removed
    })

    const menu = Menu.buildFromTemplate(createMenuTemplate())
    Menu.setApplicationMenu(menu)

    // Start WebSocket terminal server
    terminalServer.start()

    createWindow()

    // NEW: Python Sync WebSocket Bridge
    function connectToPythonSync() {
        const WebSocket = require('ws');
        // Force 127.0.0.1 to avoid IPv6 localhost issues (::1)
        const ws = new WebSocket('ws://127.0.0.1:8000/api/ws');

        ws.on('open', () => {
            console.log('✅ Connected to Python Sync WebSocket');
        });

        ws.on('message', (data: Buffer) => {
            try {
                const event = JSON.parse(data.toString());
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('agent:sync', event);
                }
            } catch (e) {
                console.error('Failed to parse sync event:', e);
            }
        });

        ws.on('close', () => {
            console.log('❌ Python Sync WebSocket closed. Retrying in 5s...');
            setTimeout(connectToPythonSync, 5000);
        });

        ws.on('error', (err: Error) => {
            console.error('Python Sync WebSocket error:', err.message);
        });
    }

    // Attempt connection
    connectToPythonSync();

    // Register PTY handlers for VS Code-style terminal
    if (mainWindow) {
        registerPtyHandlers(mainWindow)
    }

    registerTerminalHandlers(ipcMain, ptyManager, mainWindow)
    registerFileSystemHandlers(ipcMain)
    registerAgentHandlers(ipcMain, mainWindow)
    registerSystemHandlers(ipcMain, mainWindow)

    app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })

    app.on('before-quit', () => {
        ptyManager.disposeAll()
        terminalServer.stop()
        cleanupAllSessions()
    })
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit()
    }
})
