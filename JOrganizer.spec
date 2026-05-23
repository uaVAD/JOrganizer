# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo,
    StringTable, StringStruct, VarFileInfo, VarStruct,
)

hiddenimports = ['api', 'config', 'core', 'database', 'monitoring', 'ui']
hiddenimports += collect_submodules('aiohttp')

version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(0, 3, 4, 0),
        prodvers=(0, 3, 4, 0),
        mask=0x3f,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable('040904B0', [
                StringStruct('FileDescription',
                    'JOrganizer - AI Media Organizer & Auto Renamer (Jellyfin Compatible)'),
                StringStruct('ProductName', 'JOrganizer'),
                StringStruct('FileVersion', '0.3.4'),
                StringStruct('ProductVersion', '0.3.4'),
                StringStruct('LegalCopyright', '\u00a9 2026 Vadym Krypko'),
                StringStruct('OriginalFilename', 'JOrganizer.exe'),
                StringStruct('InternalName', 'JOrganizer'),
            ]),
        ]),
        VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
    ],
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/JO.ico', 'assets'), ('config/init.json', 'config'), ('languages', 'languages'), ('assets/preview.svg', 'assets'), ('assets/rename.svg', 'assets'), ('assets/undo.svg', 'assets'), ('assets/refresh.svg', 'assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'setuptools', 'wheel'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='JOrganizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/JO.ico'],
    version=version_info,
)
