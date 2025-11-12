console.log('Testing electron require...');
const electron = require('electron');
console.log('Type of electron:', typeof electron);
console.log('Electron keys:', Object.keys(electron).slice(0, 10));
console.log('Has app?:', 'app' in electron);
console.log('electron.app:', electron.app);
