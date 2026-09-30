from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH).parent
datas, binaries, hiddenimports = [], [], []
for package in ("pdf2zh", "babeldoc", "onnxruntime", "tiktoken_ext"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
datas += copy_metadata("pdf2zh", recursive=True)
a = Analysis([str(root / "engine" / "bridge.py")], pathex=[str(root)],
             datas=datas, binaries=binaries, hiddenimports=hiddenimports,
             excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "tkinter", "pytest"])
pyz = PYZ(a.pure)
# Keep pipes available. QProcess uses CREATE_NO_WINDOW for the child.
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="pdfmathtranslate-engine",
          console=True, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="pdfmathtranslate-engine", strip=False, upx=False)
