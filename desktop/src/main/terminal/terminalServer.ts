/**
 * WebSocket Terminal Server - Persistent Windows Terminal
 * This runs inside the Electron main process
 */
import { WebSocketServer, WebSocket } from 'ws'
import * as pty from 'node-pty'
import os from 'os'

const DEFAULT_CWD = 'D:\\All Projects\\My AI Agent\\generated'

interface TerminalSession {
    ws: WebSocket
    pty: pty.IPty
}

export class TerminalWebSocketServer {
    private wss: WebSocketServer | null = null
    private sessions: Map<WebSocket, TerminalSession> = new Map()
    private port: number

    constructor(port: number = 8765) {
        this.port = port
    }

    start(): void {
        if (this.wss) return

        this.wss = new WebSocketServer({ port: this.port })

        this.wss.on('connection', (ws: WebSocket) => {
            console.log('Terminal WebSocket connected')

            const shell = os.platform() === 'win32'
                ? 'powershell.exe'
                : process.env.SHELL || 'bash'

            const ptyProcess = pty.spawn(shell, ['-NoLogo', '-NoExit'], {
                name: 'xterm-256color',
                cwd: DEFAULT_CWD,
                env: {
                    ...process.env,
                    TERM: 'xterm-256color',
                    PYTHONUNBUFFERED: '1',
                    PYTHONIOENCODING: 'utf-8',
                    FORCE_COLOR: '1'
                },
                cols: 120,
                rows: 30,
                useConpty: true
            })

            this.sessions.set(ws, { ws, pty: ptyProcess })

            // Send PTY output → WebSocket → Frontend
            ptyProcess.onData((data: string) => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(data)
                }
            })

            // Handle PTY exit
            ptyProcess.onExit(({ exitCode }) => {
                console.log(`Terminal exited with code ${exitCode}`)
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send('\r\n\x1b[31m[Terminal session ended]\x1b[0m\r\n')
                }
            })

            // Frontend keystrokes → PTY
            ws.on('message', (msg: Buffer) => {
                const data = msg.toString()

                // Handle resize command
                if (data.startsWith('RESIZE:')) {
                    const [, cols, rows] = data.split(':')
                    ptyProcess.resize(parseInt(cols), parseInt(rows))
                    return
                }

                ptyProcess.write(data)
            })

            // Cleanup on disconnect
            ws.on('close', () => {
                console.log('Terminal WebSocket disconnected')
                const session = this.sessions.get(ws)
                if (session) {
                    session.pty.kill()
                    this.sessions.delete(ws)
                }
            })

            ws.on('error', (err) => {
                console.error('Terminal WebSocket error:', err)
            })
        })

        console.log(`✅ Terminal WebSocket server running on ws://localhost:${this.port}`)
    }

    stop(): void {
        // Kill all PTY sessions
        for (const [ws, session] of this.sessions) {
            session.pty.kill()
            ws.close()
        }
        this.sessions.clear()

        if (this.wss) {
            this.wss.close()
            this.wss = null
        }
        console.log('Terminal WebSocket server stopped')
    }

    getPort(): number {
        return this.port
    }
}
