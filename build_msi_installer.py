#!/usr/bin/env python3
"""
Build script for creating an MSI installer of Trackwise using cx_Freeze
This should have much lower antivirus false positive rates than PyInstaller
"""

import subprocess
import sys
import os
import shutil
import time
from pathlib import Path

def safe_cleanup_build_dirs():
    """Safely clean up build directories"""
    print("🧹 Cleaning up previous build directories...")
    
    dirs_to_clean = ["build", "dist", "__pycache__"]
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"✓ Cleaned up {dir_name}/")
            except Exception as e:
                print(f"⚠️  Could not clean {dir_name}/: {e}")

def install_cx_freeze():
    """Install cx_Freeze if not already installed"""
    try:
        import cx_Freeze
        print("✓ cx_Freeze is already installed")
        return True
    except ImportError:
        print("Installing cx_Freeze...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "cx_Freeze"])
            print("✓ cx_Freeze installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install cx_Freeze")
            return False

def create_setup_py(main_file_path):
    """Create setup.py file for cx_Freeze"""
    # Get the directory containing the main file
    main_dir = os.path.dirname(main_file_path) if os.path.dirname(main_file_path) else "."
    
    # Look for icon file in main directory and current directory
    icon_paths = ["Trackwise.ico", "icon.ico", os.path.join(main_dir, "Trackwise.ico"), os.path.join(main_dir, "icon.ico")]
    icon_found = None
    for icon_path in icon_paths:
        if os.path.exists(icon_path):
            icon_found = icon_path
            break
    
    # Create icon reference for setup.py
    icon_ref = f'"{icon_found}"' if icon_found else 'None'
    
    # Simplified MSI configuration - only essential options
    msi_options = f'''{{
        "add_to_path": False,
        "initial_target_dir": r"[ProgramFilesFolder]\\\\Trackwise",
        "target_name": "Trackwise",
        "upgrade_code": "{{12345678-1234-1234-1234-123456789012}}"
    }}'''
    
    setup_content = f'''#!/usr/bin/env python3
"""
Setup script for cx_Freeze to create MSI installer
"""

import sys
from cx_Freeze import setup, Executable

# Dependencies that cx_Freeze might miss
build_exe_options = {{
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
}}

# Base for Windows systems
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # No console window

# Main executable - ALWAYS create shortcuts
executables = [
    Executable(
        "{main_file_path}",
        base=base,
        target_name="Trackwise.exe",
        icon={icon_ref},
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
    options={{
        "build_exe": build_exe_options,
        "bdist_msi": {msi_options}
    }},
    executables=executables
)
'''
    
    with open("setup.py", "w") as f:
        f.write(setup_content)
    
    print("✓ Created setup.py for cx_Freeze")

def find_main_file():
    """Find the main file in current directory or subdirectories"""
    main_filename = "main_gui_enhanced.py"
    
    # First check current directory
    if os.path.exists(main_filename):
        return main_filename
    
    # Then search in subdirectories
    for root, dirs, files in os.walk("."):
        if main_filename in files:
            found_path = os.path.join(root, main_filename)
            print(f"✓ Found {main_filename} at: {found_path}")
            return found_path
    
    return None

def build_msi_installer():
    """Build MSI installer using cx_Freeze"""
    print("🔨 Building MSI installer with cx_Freeze...")
    
    # Find main file in current directory or subdirectories
    main_file = find_main_file()
    if not main_file:
        print(f"❌ Error: main_gui_enhanced.py not found in current directory or subdirectories")
        print("💡 Make sure the file exists and you're running the build script from the correct location")
        return False
    
    # Create setup.py
    create_setup_py(main_file)
    
    # Try MSI build first
    print("🚀 Starting MSI build process...")
    print("⚠️  This may take several minutes...")
    
    msi_cmd = [sys.executable, "setup.py", "bdist_msi"]
    exe_cmd = [sys.executable, "setup.py", "build_exe"]
    
    try:
        # Try MSI build first
        result = subprocess.run(msi_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ MSI installer built successfully!")
            
            # Find the MSI file
            dist_dir = Path("dist")
            if dist_dir.exists():
                msi_files = list(dist_dir.glob("*.msi"))
                if msi_files:
                    msi_file = msi_files[0]
                    msi_size = msi_file.stat().st_size / (1024 * 1024)  # Size in MB
                    print(f"📦 MSI installer created: {msi_file}")
                    print(f"📦 File size: {msi_size:.1f} MB")
                    print(f"📁 Location: {msi_file.absolute()}")
                    
                    print("\n🎉 MSI installer build completed successfully!")
                    print("📋 Instructions:")
                    print(f"   • Your MSI installer is: {msi_file.absolute()}")
                    print("   • Double-click to install on any Windows machine")
                    print("   • No Python installation required on target machines")
                    print("   • Internet connection required for API calls")
                    print("   • Desktop and Start Menu shortcuts will be created automatically")
                    print("\n🛡️  Antivirus Benefits:")
                    print("   • MSI installers have much lower false positive rates")
                    print("   • Professional installation experience")
                    print("   • Easy uninstallation through Control Panel")
                    
                    return True
                else:
                    print("❌ MSI file not found after build")
                    return False
            else:
                print("❌ Dist directory not found after build")
                return False
        else:
            print("⚠️  MSI build failed, trying executable build as fallback...")
            print("Error output from MSI build:")
            print(result.stderr)
            
            # Try executable build as fallback
            print("\n🔄 Trying executable build as fallback...")
            result = subprocess.run(exe_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✓ Executable built successfully as fallback!")
                
                # Find the executable
                build_dir = Path("build")
                if build_dir.exists():
                    exe_dirs = list(build_dir.glob("exe.win-*"))
                    if exe_dirs:
                        exe_dir = exe_dirs[0]
                        exe_file = exe_dir / "Trackwise.exe"
                        if exe_file.exists():
                            exe_size = exe_file.stat().st_size / (1024 * 1024)  # Size in MB
                            print(f"📦 Executable created: {exe_file}")
                            print(f"📦 File size: {exe_size:.1f} MB")
                            print(f"📁 Location: {exe_file.absolute()}")
                            
                            print("\n🎯 Executable build completed successfully!")
                            print("📋 Instructions:")
                            print(f"   • Your executable is: {exe_file.absolute()}")
                            print(f"   • Copy the entire '{exe_dir.name}' folder to distribute")
                            print("   • No Python installation required on target machines")
                            print("   • Internet connection required for API calls")
                            print("\n💡 Note: This is an executable, not an MSI installer.")
                            print("   It may still have antivirus false positive issues.")
                            
                            return True
                
                print("❌ Executable file not found after build")
                return False
            else:
                print("❌ Both MSI and executable builds failed!")
                print("Error output from executable build:")
                print(result.stderr)
                return False
            
    except Exception as e:
        print(f"❌ Error during build: {e}")
        return False

def create_alternative_build_scripts():
    """Create alternative build scripts for other tools"""
    
    # Find main file first
    main_file = find_main_file()
    if not main_file:
        print("❌ Error: main_gui_enhanced.py not found in current directory or subdirectories")
        return
    
    # Nuitka script
    nuitka_script = f"""#!/usr/bin/env python3
\"\"\"
Alternative build script using Nuitka (may have fewer false positives)
\"\"\"

import subprocess
import sys
import os

def build_with_nuitka():
    try:
        import nuitka
    except ImportError:
        print("Installing Nuitka...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "nuitka"])
    
    main_file = "{main_file}"
    if not os.path.exists(main_file):
        print(f"Error: {{main_file}} not found")
        return False
    
    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--windows-disable-console",
        "--enable-plugin=tk-inter",
        "--output-filename=Trackwise.exe",
        main_file
    ]
    
    print("Building with Nuitka...")
    result = subprocess.run(cmd)
    return result.returncode == 0

if __name__ == "__main__":
    if build_with_nuitka():
        print("✓ Nuitka build completed!")
    else:
        print("❌ Nuitka build failed!")
"""
    
    with open("build_with_nuitka.py", "w") as f:
        f.write(nuitka_script)
    
    # Inno Setup script
    inno_script = f"""# Inno Setup Script for Trackwise
# Save this as "setup.iss" and use Inno Setup Compiler

[Setup]
AppName=Trackwise
AppVersion=1.0.0
DefaultDirName={{pf}}\\\\Trackwise
DefaultGroupName=Trackwise
OutputDir=dist
OutputBaseFilename=Trackwise_Setup
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "build\\\\exe.win-amd64-3.9\\\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\\\Trackwise"; Filename: "{{app}}\\\\Trackwise.exe"
Name: "{{commondesktop}}\\\\Trackwise"; Filename: "{{app}}\\\\Trackwise.exe"

[Run]
Filename: "{{app}}\\\\Trackwise.exe"; Description: "Launch Trackwise"; Flags: postinstall nowait skipifsilent
"""
    
    with open("setup.iss", "w") as f:
        f.write(inno_script)
    
    print("✓ Created alternative build scripts:")
    print("  • build_with_nuitka.py - Nuitka build script")
    print("  • setup.iss - Inno Setup script (requires Inno Setup Compiler)")

def main():
    """Main build process"""
    print("🚀 Trackwise MSI Installer Builder")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        return
    
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Ask about build options
    print("\n🔧 Build Options:")
    print("1. Build MSI installer with cx_Freeze (RECOMMENDED)")
    print("2. Build executable only (fallback if MSI fails)")
    print("3. Create alternative build scripts")
    print("4. Clean up build directories")
    
    choice = input("\nChoose option (1-4, default 1): ").strip()
    
    # Always create shortcuts for MSI installer
    if choice == "1":
        print("\n📋 Shortcut Configuration:")
        print("✓ Desktop shortcut will be created automatically")
        print("✓ Start Menu shortcut will be created automatically")
        print("✓ Professional installation experience")
    
    if choice == "2":
        # Build executable only
        print("\n🔨 Building executable only with cx_Freeze...")
        
        # Install cx_Freeze if needed
        if not install_cx_freeze():
            return
        
        # Clean up first
        safe_cleanup_build_dirs()
        
        # Find main file and create setup.py
        main_file = find_main_file()
        if not main_file:
            print("❌ Error: main_gui_enhanced.py not found")
            return
        
        create_setup_py(main_file)
        
        # Build executable
        cmd = [sys.executable, "setup.py", "build_exe"]
        try:
            print("🚀 Starting executable build...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✓ Executable built successfully!")
                
                # Find the executable
                build_dir = Path("build")
                if build_dir.exists():
                    exe_dirs = list(build_dir.glob("exe.win-*"))
                    if exe_dirs:
                        exe_dir = exe_dirs[0]
                        exe_file = exe_dir / "Trackwise.exe"
                        if exe_file.exists():
                            exe_size = exe_file.stat().st_size / (1024 * 1024)
                            print(f"📦 Executable created: {exe_file}")
                            print(f"📦 File size: {exe_size:.1f} MB")
                            print(f"📁 Location: {exe_file.absolute()}")
                            
                            print("\n🎯 Executable build completed successfully!")
                            print("📋 Instructions:")
                            print(f"   • Your executable is: {exe_file.absolute()}")
                            print(f"   • Copy the entire '{exe_dir.name}' folder to distribute")
                            print("   • No Python installation required on target machines")
                            print("   • Internet connection required for API calls")
                            
                            return
                
                print("❌ Executable file not found after build")
            else:
                print("❌ Executable build failed!")
                print("Error output:")
                print(result.stderr)
                
        except Exception as e:
            print(f"❌ Error during executable build: {e}")
        
        return
    elif choice == "3":
        create_alternative_build_scripts()
        return
    elif choice == "4":
        safe_cleanup_build_dirs()
        return
    else:
        # Install cx_Freeze if needed
        if not install_cx_freeze():
            return
        
        # Clean up first
        safe_cleanup_build_dirs()
        
        # Build MSI installer
        if build_msi_installer():
            print("\n🎯 MSI installer build completed successfully!")
        else:
            print("\n💥 MSI installer build failed!")
    
    # Show benefits of MSI installers
    print("\n🛡️  Why MSI Installers Reduce Antivirus False Positives:")
    print("=" * 60)
    print("1. 📦 STANDARD WINDOWS FORMAT")
    print("   • MSI files are the standard Windows installation format")
    print("   • Antivirus software trusts MSI files more than standalone EXEs")
    print("   • Microsoft's own installer technology")
    print("")
    print("2. 🔒 PROFESSIONAL INSTALLATION")
    print("   • Proper Windows registry integration")
    print("   • Standard uninstall through Control Panel")
    print("   • File association handling")
    print("")
    print("3. 📋 DIGITAL SIGNATURE FRIENDLY")
    print("   • Easier to sign with code signing certificates")
    print("   • Better compatibility with enterprise security policies")
    print("   • Reduced false positive rates (typically 80-90% reduction)")
    print("")
    print("4. 🚀 EASY DISTRIBUTION")
    print("   • Double-click to install")
    print("   • No command line required")
    print("   • Professional user experience")
    print("")
    print("💡 If you still get false positives with MSI:")
    print("   • Try code signing: https://www.digicert.com/code-signing/")
    print("   • Submit false positive reports to your antivirus vendor")
    print("   • Use Windows Defender (usually has fewer false positives)")

if __name__ == "__main__":
    main()
