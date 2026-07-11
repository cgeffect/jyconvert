# PyInstaller spec：打包为 Electron 内嵌二进制
# 构建: cd python && pyinstaller jyconvert.spec

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

datas = [
    (str(root / "templates"), "templates"),
]

hiddenimports = [
    "app_root",
    "capcut",
    "capcut.lib",
    "jianying",
    "jianying.convert_lib",
    "jianying.import_draft",
    "jianying.lib",
    "protocol",
    "protocol.converter",
    "protocol.path_resolver",
]

a = Analysis(
    ["cli.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="jyconvert-py",
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
