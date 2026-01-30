console.log('--- DIAGNOSTIC START ---');
console.log('Node version:', process.version);
console.log('Electron version:', process.versions.electron);
console.log('Chrome version:', process.versions.chrome);
console.log('Exec path:', process.execPath);
try {
    const electron = require('electron');
    console.log('Electron module type:', typeof electron);
    if (typeof electron === 'object') {
        console.log('Electron keys:', Object.keys(electron));
    } else {
        console.log('Electron value:', electron);
    }
} catch (e) {
    console.log('Error requiring electron:', e.message);
}
console.log('--- DIAGNOSTIC END ---');
process.exit(0);
