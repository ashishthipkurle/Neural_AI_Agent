import { IpcMain, dialog, BrowserWindow } from 'electron'
import { readdir, readFile, writeFile, mkdir, access } from 'fs/promises'
import { join, isAbsolute, normalize, dirname } from 'path'

interface FileEntry {
    name: string
    path: string
    type: 'file' | 'directory'
}

function validatePath(filePath: string): boolean {
    const normalized = normalize(filePath)
    return isAbsolute(normalized) && !normalized.includes('..')
}

export function registerFileSystemHandlers(ipcMain: IpcMain): void {
    console.log('DEBUG: Registering FileSystem Handlers');
    // Remove existing handlers first
    ipcMain.removeHandler('fs:openFolder');
    ipcMain.removeHandler('fs:listDir');
    ipcMain.removeHandler('fs:readFile');
    ipcMain.removeHandler('fs:writeFile');
    ipcMain.removeHandler('fs:exists');

    try {
        ipcMain.handle('fs:openFolder', async (event) => {
            const window = BrowserWindow.fromWebContents(event.sender)
            if (!window) return null
            const result = await dialog.showOpenDialog(window, { properties: ['openDirectory'] })
            return result.canceled ? null : result.filePaths[0]
        })

        ipcMain.handle('fs:listDir', async (_, dirPath: string): Promise<FileEntry[]> => {
            if (!validatePath(dirPath)) throw new Error('Invalid path')
            const entries = await readdir(dirPath, { withFileTypes: true })
            const result: FileEntry[] = []

            for (const entry of entries) {
                if (entry.name.startsWith('.')) continue
                result.push({
                    name: entry.name,
                    path: join(dirPath, entry.name),
                    type: entry.isDirectory() ? 'directory' : 'file'
                })
            }

            result.sort((a, b) => {
                if (a.type !== b.type) return a.type === 'directory' ? -1 : 1
                return a.name.localeCompare(b.name)
            })

            return result
        })

        ipcMain.handle('fs:readFile', async (_, filePath: string): Promise<string> => {
            if (!validatePath(filePath)) throw new Error('Invalid path')
            return readFile(filePath, 'utf-8')
        })

        ipcMain.handle('fs:writeFile', async (_, filePath: string, content: string): Promise<void> => {
            if (!validatePath(filePath)) throw new Error('Invalid path')
            await mkdir(dirname(filePath), { recursive: true })
            await writeFile(filePath, content, 'utf-8')
        })

        ipcMain.handle('fs:exists', async (_, filePath: string): Promise<boolean> => {
            if (!validatePath(filePath)) return false
            try {
                await access(filePath)
                return true
            } catch {
                return false
            }
        })
    } catch (error) {
        console.error('ERROR: Failed to register FileSystem handlers:', error);
    }
}
