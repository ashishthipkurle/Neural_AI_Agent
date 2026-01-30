/**
 * PTY Server - Production-grade terminal backend
 * Handles multiple terminal sessions with node-pty
 */
import * as pty from 'node-pty'
import { BrowserWindow, ipcMain } from 'electron'
import os from 'os'

type TerminalSession = {
    id: string
    pty: pty.IPty
    shell: 'powershell' | 'cmd'
}

const sessions = new Map<string, TerminalSession>()

export function registerPtyHandlers(win: BrowserWindow) {
    // Create a new terminal session
    ipcMain.handle('terminal:create', (_, { id, cwd, shell }) => {
        const shellPath = shell === 'cmd' ? 'cmd.exe' : 'powershell.exe'
        const shellArgs = shell === 'cmd' ? ['/K'] : ['-NoLogo', '-NoExit']

        const ptyProcess = pty.spawn(shellPath, shellArgs, {
            cwd: cwd || os.homedir(),
            env: {
                ...process.env,
                TERM: 'xterm-256color',
                PYTHONUNBUFFERED: '1',
                PYTHONIOENCODING: 'utf-8',
                FORCE_COLOR: '1'
            },
            cols: 120,
            rows: 30,
            name: 'xterm-256color',
            useConpty: true
        })

        // Send PTY output to renderer
        ptyProcess.onData((data) => {
            if (win && !win.isDestroyed()) {
                win.webContents.send(`terminal:data:${id}`, data)
            }
        })

        // Handle PTY exit
        ptyProcess.onExit(({ exitCode }) => {
            if (win && !win.isDestroyed()) {
                win.webContents.send(`terminal:exit:${id}`, exitCode)
            }
            sessions.delete(id)
        })

        sessions.set(id, { id, pty: ptyProcess, shell })
        console.log(`Terminal created: ${id} (${shell})`)

        return { success: true, id }
    })

    // Write input to terminal
    ipcMain.handle('terminal:input', (_, { id, data }) => {
        const session = sessions.get(id)
        if (session) {
            session.pty.write(data)
            return { success: true }
        }
        return { success: false, error: 'Session not found' }
    })

    // Resize terminal
    ipcMain.handle('terminal:resize', (_, { id, cols, rows }) => {
        const session = sessions.get(id)
        if (session) {
            session.pty.resize(cols, rows)
            return { success: true }
        }
        return { success: false }
    })

    // Kill terminal session
    ipcMain.handle('terminal:kill', (_, id) => {
        const session = sessions.get(id)
        if (session) {
            session.pty.kill()
            sessions.delete(id)
            console.log(`Terminal killed: ${id}`)
            return { success: true }
        }
        return { success: false }
    })

    // List active sessions
    ipcMain.handle('terminal:list', () => {
        return Array.from(sessions.keys())
    })
}

// Cleanup all sessions on app quit
export function cleanupAllSessions() {
    for (const [id, session] of sessions) {
        try {
            session.pty.kill()
        } catch (e) {
            console.error(`Failed to kill session ${id}:`, e)
        }
    }
    sessions.clear()
}
