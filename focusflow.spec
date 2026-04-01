# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for FocusFlow — single-file native EXE
"""
import os

# ── Collect pylsl native DLLs ──
pylsl_binaries = []
try:
    import pylsl
    pylsl_dir = os.path.dirname(pylsl.__file__)
    for root, dirs, files in os.walk(pylsl_dir):
        for f in files:
            if f.endswith(('.dll', '.so', '.dylib')):
                rel = os.path.relpath(root, os.path.dirname(pylsl_dir))
                pylsl_binaries.append((os.path.join(root, f), rel))
except ImportError:
    pass

# ── Collect bleak backends ──
bleak_binaries = []
try:
    import bleak
    bleak_dir = os.path.dirname(bleak.__file__)
    for root, dirs, files in os.walk(bleak_dir):
        for f in files:
            if f.endswith(('.dll', '.so', '.dylib')):
                rel = os.path.relpath(root, os.path.dirname(bleak_dir))
                bleak_binaries.append((os.path.join(root, f), rel))
except ImportError:
    pass

a = Analysis(
    ['production_server.py'],
    pathex=[],
    binaries=pylsl_binaries + bleak_binaries,
    datas=[
        ('dashboard.html', '.'),
        ('dashboard_therapeutic.js', '.'),
        ('config.py', '.'),
        ('.env', '.'),
        ('database.py', '.'),
        ('reporting.py', '.'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'pylsl',
        'aiohttp', 'aiohttp.web',
        'numpy',
        'bleak', 'bleak.backends', 'bleak.backends.winrt',
        'muse_ble',
        'supabase',
        'fpdf',
        'postgrest', # sometimes needed as hidden dep for supabase
        'gotrue',
        'storage3',
        'realtime',
        'scipy', 'scipy.signal',
        'numba', 'llvmlite',
        'database', 'reporting'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FocusFlow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
