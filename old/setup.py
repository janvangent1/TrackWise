#!/usr/bin/env python3
"""
Setup script for cx_Freeze to create MSI installer
"""

import sys
from cx_Freeze import setup, Executable

# Dependencies that cx_Freeze might miss
build_exe_options = {
    "packages": [
        "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox",
        "requests", "gpxpy", "geopy", "geopy.distance", 
        "shapely", "shapely.geometry", 
        "matplotlib", "matplotlib.pyplot", "matplotlib.backends.backend_tkagg", "matplotlib.figure",
        "folium", "folium.plugins", "numpy", "tempfile", "webbrowser", 
        "threading", "csv", "os", "time", 
        "ctypes", "_ctypes", "ctypes.wintypes", "ctypes.util",
        "concurrent.futures", "xml.etree.ElementTree", "urllib3", "certifi"
    ],
    "excludes": ["test", "distutils"],
    "include_files": [],
    "optimize": 2
}

# Base for Windows systems
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # No console window

# Main executable - ALWAYS create shortcuts
executables = [
    Executable(
        "main_gui_enhanced.py",
        base=base,
        target_name="Trackwise.exe",
        icon="Trackwise.ico",
        copyright="Trackwise GPX Waypoint Finder",
        shortcut_name="Trackwise",
        shortcut_dir="DesktopFolder"
    )
]

# Setup configuration
setup(
    name="Trackwise",
    version="1.0.0",
    description="GPX Waypoint Finder - Find petrol stations, supermarkets, and more along your route",
    author="Trackwise Developer",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": {
        "add_to_path": False,
        "initial_target_dir": r"[ProgramFilesFolder]\\Trackwise",
        "target_name": "Trackwise",
        "upgrade_code": "{12345678-1234-1234-1234-123456789012}"
    }
    },
    executables=executables
)
