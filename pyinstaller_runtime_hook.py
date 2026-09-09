import os
import sys


if getattr(sys, "frozen", False):
    extraction_root = getattr(sys, "_MEIPASS", "")
    candidates = (
        os.path.join(extraction_root, "PySide6"),
        os.path.join(extraction_root, "_internal", "PySide6"),
    )
    for bundled_pyside in candidates:
        if os.path.isdir(bundled_pyside):
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(bundled_pyside)
            os.environ["PATH"] = bundled_pyside + os.pathsep + os.environ.get("PATH", "")
            os.environ.setdefault("QT_PLUGIN_PATH", os.path.join(bundled_pyside, "plugins"))
            break
