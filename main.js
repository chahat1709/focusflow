const { app, BrowserWindow, ipcMain, Tray, Menu } = require('electron');
const { autoUpdater } = require('electron-updater');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let tray;
let backendProcess;

// Disable hardware acceleration for better compatibility
app.disableHardwareAcceleration();

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1200,
        minHeight: 800,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true
        },
        icon: path.join(__dirname, 'icon.ico'),
        title: 'Omni-Monitor - Muse 2 Dashboard',
        backgroundColor: '#0f172a'
    });

    // Load the dashboard
    mainWindow.loadFile('dashboard.html');

    // System tray
    createTray();

    // Handle window close
    mainWindow.on('close', (event) => {
        if (!app.isQuitting) {
            event.preventDefault();
            mainWindow.hide();
        }
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function createTray() {
    tray = new Tray(path.join(__dirname, 'icon.ico'));

    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Show Omni-Monitor',
            click: () => {
                mainWindow.show();
            }
        },
        {
            label: 'Check for Updates',
            click: () => {
                autoUpdater.checkForUpdates();
            }
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => {
                app.isQuitting = true;
                app.quit();
            }
        }
    ]);

    tray.setToolTip('Omni-Monitor');
    tray.setContextMenu(contextMenu);

    tray.on('double-click', () => {
        mainWindow.show();
    });
}

// --- SERVER MANAGEMENT ---

function killExistingServer() {
    return new Promise((resolve) => {
        const cmd = process.platform === 'win32'
            ? 'taskkill /F /IM muse_eeg_server.exe /T'
            : 'pkill -f muse_eeg_server';

        require('child_process').exec(cmd, (err) => {
            // Ignore errors (process might not exist)
            resolve();
        });
    });
}

async function startBackend() {
    // 1. Kill zombies first
    await killExistingServer();

    const isDev = !app.isPackaged;
    const backendPath = isDev
        ? path.join(__dirname, 'muse_eeg_server.py')
        : path.join(process.resourcesPath, 'build', 'muse_eeg_server.exe');

    console.log('🚀 Starting Neural Core:', backendPath);

    const spawnOptions = {
        stdio: 'pipe',
        windowsHide: true  // Hide console window on Windows
    };

    if (isDev) {
        // Dev: Python
        backendProcess = spawn('python', [backendPath], spawnOptions);
    } else {
        // Prod: EXE
        backendProcess = spawn(backendPath, [], spawnOptions);
    }

    backendProcess.stdout.on('data', (data) => {
        console.log(`[Core]: ${data}`);
    });

    backendProcess.stderr.on('data', (data) => {
        console.error(`[Core Error]: ${data}`);
    });

    backendProcess.on('close', (code) => {
        console.log(`[Core] Process exited with code ${code}`);
        // Optional: Auto-restart if crashed unexpectedly
        // if (code !== 0 && !app.isQuitting) setTimeout(startBackend, 1000);
    });
}

function setupAutoUpdater() {
    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = true;

    autoUpdater.on('update-available', (info) => {
        mainWindow.webContents.send('update-available', info);
    });

    autoUpdater.on('update-downloaded', (info) => {
        mainWindow.webContents.send('update-downloaded', info);
    });

    // Check for updates every hour
    setInterval(() => {
        autoUpdater.checkForUpdates();
    }, 3600000);

    // Initial check after 30 seconds
    setTimeout(() => {
        autoUpdater.checkForUpdates();
    }, 30000);
}

app.whenReady().then(async () => {
    createWindow();
    await startBackend(); // Wait for cleanup
    setupAutoUpdater();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    if (backendProcess) {
        backendProcess.kill();
    }
});

// IPC handlers
ipcMain.on('install-update', () => {
    autoUpdater.quitAndInstall();
});
