import * as pty from 'node-pty'
import os from 'os'
import { randomUUID } from 'crypto'

interface TerminalSession {
    id: string
    pty: pty.IPty
    shell: 'powershell' | 'cmd'
}

export class PtyManager {
    private sessions: Map<string, TerminalSession> = new Map()
    private dataListeners: Map<string, (data: string) => void> = new Map()
    private exitListeners: Map<string, (code: number) => void> = new Map()

    create(shell: 'powershell' | 'cmd', id?: string, cwd?: string): string {
        const sessionId = id || randomUUID()
        const workingDir = cwd || os.homedir()
        const shellPath = shell === 'powershell' ? 'powershell.exe' : 'cmd.exe'
        // Use -NoExit to keep shell alive after commands complete
        // Use -ExecutionPolicy Bypass to allow script execution
        const shellArgs = shell === 'powershell'
            ? ['-NoLogo', '-NoExit', '-ExecutionPolicy', 'Bypass']
            : ['/K']  // /K keeps cmd.exe running after command execution

        const ptyProcess = pty.spawn(shellPath, shellArgs, {
            name: 'xterm-256color',
            cols: 80,
            rows: 24,
            cwd: workingDir,
            env: {
                ...process.env,
                TERM: 'xterm-256color',
                // Force Python to not buffer stdout/stderr
                PYTHONUNBUFFERED: '1',
                PYTHONIOENCODING: 'utf-8',
                // Enable colors for frameworks that support it
                FORCE_COLOR: '1',
                // Prevent Flask from spawning reloader subprocess
                WERKZEUG_RUN_MAIN: 'true'
            },
            // Use legacy mode for better Flask/Werkzeug compatibility
            useConpty: false
        })

        this.sessions.set(sessionId, { id: sessionId, pty: ptyProcess, shell })

        ptyProcess.onData((data) => {
            const listener = this.dataListeners.get(sessionId)
            if (listener) listener(data)
        })

        ptyProcess.onExit(({ exitCode }) => {
            const listener = this.exitListeners.get(sessionId)
            if (listener) listener(exitCode)
            this.sessions.delete(sessionId)
        })

        return sessionId
    }

    write(id: string, data: string): void {
        this.sessions.get(id)?.pty.write(data)
    }

    resize(id: string, cols: number, rows: number): void {
        this.sessions.get(id)?.pty.resize(cols, rows)
    }

    dispose(id: string): void {
        const session = this.sessions.get(id)
        if (session) {
            try {
                session.pty.kill()
            } catch (e) {
                console.error('Error killing PTY:', e)
            }
            this.sessions.delete(id)
            this.dataListeners.delete(id)
            this.exitListeners.delete(id)
        }
    }

    disposeAll(): void {
        for (const [id] of this.sessions) {
            this.dispose(id)
        }
    }

    onData(id: string, callback: (data: string) => void): void {
        this.dataListeners.set(id, callback)
    }

    onExit(id: string, callback: (code: number) => void): void {
        this.exitListeners.set(id, callback)
    }
}
