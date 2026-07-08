# PyInstaller spec：yt-dlp 独立二进制 → jyconvert/bin/yt-dlp

block_cipher = None

hiddenimports = [
    "yt_dlp",
    "yt_dlp.compat",
    "yt_dlp.compat.compat_utils",
    "yt_dlp.extractor",
    "yt_dlp.postprocessor",
    "yt_dlp.downloader",
]

a = Analysis(
    ["ytdlp_entry.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="yt-dlp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="yt-dlp",
)
