#!/usr/bin/env python3
"""
Build script for creating a standalone executable of Trackwise
"""

import subprocess
import sys
import os
import shutil
import time
from pathlib import Path

def safe_cleanup_build_dirs():
    """Safely clean up build directories, handling permission errors"""
    print("🧹 Cleaning up previous build directories...")
    
    dirs_to_clean = ["build", "dist", "__pycache__"]
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                # Try to remove the directory
                shutil.rmtree(dir_name)
                print(f"✓ Cleaned up {dir_name}/")
            except PermissionError as e:
                print(f"⚠️  Permission error cleaning {dir_name}/: {e}")
                print("   This is common on Windows. Trying alternative cleanup...")
                
                # Try to remove individual files first
                try:
                    for root, dirs, files in os.walk(dir_name, topdown=False):
                        # Remove files first
                        for file in files:
                            try:
                                file_path = os.path.join(root, file)
                                os.chmod(file_path, 0o777)  # Give full permissions
                                os.remove(file_path)
                            except Exception as fe:
                                print(f"   ⚠️  Could not remove file {file}: {fe}")
                        
                        # Then remove directories
                        for dir in dirs:
                            try:
                                dir_path = os.path.join(root, dir)
                                os.chmod(dir_path, 0o777)  # Give full permissions
                                os.rmdir(dir_path)
                            except Exception as de:
                                print(f"   ⚠️  Could not remove directory {dir}: {de}")
                    
                    # Try to remove the main directory again
                    try:
                        os.chmod(dir_name, 0o777)
                        os.rmdir(dir_name)
                        print(f"✓ Successfully cleaned up {dir_name}/ after permission fix")
                    except Exception as e2:
                        print(f"   ⚠️  Still cannot remove {dir_name}/: {e2}")
                        print(f"   💡 You may need to manually delete the {dir_name}/ folder")
                        print(f"   💡 Or restart your terminal/IDE and try again")
                        
                except Exception as cleanup_error:
                    print(f"   ❌ Alternative cleanup failed: {cleanup_error}")
                    print(f"   💡 Please manually delete the {dir_name}/ folder and try again")
                    
            except Exception as e:
                print(f"❌ Unexpected error cleaning {dir_name}/: {e}")
    
    # Also clean up any .spec files that might cause conflicts
    spec_files = [f for f in os.listdir(".") if f.endswith(".spec") and f != "Trackwise.spec"]
    for spec_file in spec_files:
        try:
            os.remove(spec_file)
            print(f"✓ Removed old spec file: {spec_file}")
        except Exception as e:
            print(f"⚠️  Could not remove {spec_file}: {e}")
    
    # Provide additional solutions for persistent permission issues
    print("\n💡 If you continue to have permission issues:")
    print("   1. Close any applications that might be using the build files")
    print("   2. Restart your terminal/IDE")
    print("   3. Try running as Administrator")
    print("   4. Move the project to a different location (not OneDrive)")
    print("   5. Use the manual cleanup option (option 7) before building")

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    try:
        import PyInstaller
        print("✓ PyInstaller is already installed")
        return True
    except ImportError:
        print("Installing PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✓ PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install PyInstaller")
            return False

def rebuild_bootloader():
    """Rebuild PyInstaller bootloader from source to reduce false positives"""
    print("🔧 Rebuilding PyInstaller bootloader from source...")
    print("⚠️  This may take several minutes and requires a C++ compiler")
    
    response = input("Do you want to rebuild the bootloader? (y/N): ").lower().strip()
    if response != 'y':
        print("Skipping bootloader rebuild")
        return True
    
    try:
        # Uninstall existing PyInstaller
        print("Uninstalling existing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "pyinstaller", "-y"])
        
        # Install from source (no binary)
        print("Installing PyInstaller from source...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-binary", "pyinstaller", "pyinstaller"])
        
        print("✓ PyInstaller bootloader rebuilt successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to rebuild bootloader: {e}")
        print("Installing regular PyInstaller as fallback...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            return True
        except:
            return False

def create_nuitka_build_script():
    """Create an alternative build script using Nuitka"""
    nuitka_script = """#!/usr/bin/env python3
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
    
    main_file = "main_gui_enhanced.py"
    if not os.path.exists(main_file):
        print(f"Error: {main_file} not found")
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
    
    print("✓ Created alternative build script: build_with_nuitka.py")
    print("  Run this if PyInstaller continues to trigger false positives")

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

def fix_ctypes_issue(exe_dir):
    """Manually copy _ctypes.pyd if it's missing"""
    try:
        import _ctypes
        ctypes_location = _ctypes.__file__
        print(f"✓ Found _ctypes at: {ctypes_location}")
        
        # Copy _ctypes.pyd to the executable directory
        import shutil
        dest_path = exe_dir / "_ctypes.pyd"
        if not dest_path.exists():
            shutil.copy2(ctypes_location, dest_path)
            print(f"✓ Copied _ctypes.pyd to: {dest_path}")
        
        # Also check for _ctypes_test.pyd
        try:
            import _ctypes_test
            ctypes_test_location = _ctypes_test.__file__
            dest_test_path = exe_dir / "_ctypes_test.pyd"
            if not dest_test_path.exists():
                shutil.copy2(ctypes_test_location, dest_test_path)
                print(f"✓ Copied _ctypes_test.pyd to: {dest_test_path}")
        except ImportError:
            pass  # _ctypes_test is optional
            
    except Exception as e:
        print(f"⚠️  Could not manually fix _ctypes: {e}")
        return False
    return True

def build_executable(console_mode=False, onefile_mode=False):
    """Build the standalone executable"""
    
    # Clean up any existing build directories first
    safe_cleanup_build_dirs()
    
    # Find main file in current directory or subdirectories
    main_file = find_main_file()
    if not main_file:
        print(f"❌ Error: main_gui_enhanced.py not found in current directory or subdirectories")
        print("💡 Make sure the file exists and you're running the build script from the correct location")
        return False
    
    if onefile_mode:
        print("🔨 Building standalone executable (single file)...")
        print("⚠️  Single file mode may have higher antivirus false positive rates")
        if console_mode:
            print("🖥️  Console mode enabled for debugging")
    elif console_mode:
        print("🔨 Building standalone executable (console mode)...")
        print("🖥️  Console mode may help with _ctypes issues")
    else:
        print("🔨 Building standalone executable...")
        print("🛡️  Using --onedir mode to reduce antivirus false positives")
    
    # Get the directory containing the main file
    main_dir = os.path.dirname(main_file) if os.path.dirname(main_file) else "."
    
    # PyInstaller command - choose between onefile and onedir
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile" if onefile_mode else "--onedir",  # Single file or directory mode
        "--name", "Trackwise",          # Name of the executable
        "--distpath", "dist",           # Explicitly set distribution path
        "--workpath", "build",          # Explicitly set work path
    ]
    
    # Add windowed flag only if not in console mode
    if not console_mode:
        cmd.append("--windowed")  # No console window (GUI only)
    
    # Add all the hidden imports
    hidden_imports = [
        "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox",
        "requests", "gpxpy", "geopy", "geopy.distance", 
        "shapely", "shapely.geometry", 
        "matplotlib", "matplotlib.pyplot", "matplotlib.backends.backend_tkagg", "matplotlib.figure",
        "folium", "folium.plugins", "numpy", "tempfile", "webbrowser", 
        "threading", "csv", "os", "time", 
        "ctypes", "_ctypes", "ctypes.wintypes", "ctypes.util",
        "concurrent.futures", "xml.etree.ElementTree", "urllib3", "certifi"
    ]
    
    # Add hidden imports to command
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])
    
    # Add collect-all and other options
    cmd.extend([
        "--collect-all", "matplotlib",
        "--collect-all", "shapely", 
        "--collect-all", "geopy",
        "--collect-all", "ctypes",
        "--paths", sys.prefix,
        "--clean",
        "--noconfirm",
        main_file
    ])
    
    # Only add copy-metadata for Python versions that support it properly
    if sys.version_info < (3, 13):
        cmd.insert(-1, "--copy-metadata")
        cmd.insert(-1, "matplotlib")
        cmd.insert(-1, "--copy-metadata")
        cmd.insert(-1, "numpy")
    else:
        print("⚠️  Python 3.13 detected - skipping copy-metadata (may cause issues)")
        print("💡 Consider using Python 3.11 or 3.12 for better PyInstaller compatibility")
    
    # Look for icon file - prioritize Trackwise.ico
    icon_paths = [
        "Trackwise.ico",  # Primary icon file
        os.path.join(main_dir, "Trackwise.ico"),  # In main directory
        "icon.ico",  # Fallback icon
        os.path.join(main_dir, "icon.ico")  # Fallback in main directory
    ]
    icon_found = None
    for icon_path in icon_paths:
        if os.path.exists(icon_path):
            icon_found = icon_path
            break
    
    if icon_found:
        cmd.insert(-1, "--icon")
        cmd.insert(-1, icon_found)
        print(f"✓ Using icon: {icon_found}")
        if icon_found.endswith("Trackwise.ico"):
            print("🎨  Using primary Trackwise icon for executable")
        else:
            print("⚠️  Using fallback icon - consider using Trackwise.ico for better branding")
    else:
        print("ℹ️  No icon file found, building without custom icon")
        print("💡 Add Trackwise.ico to the project directory for custom executable icon")
    
    # Add Python files from the main directory
    if main_dir != ".":
        py_files_pattern = os.path.join(main_dir, "*.py")
        cmd.insert(-1, "--add-data")
        cmd.insert(-1, f"{py_files_pattern};.")
        print(f"✓ Including Python files from: {main_dir}")
    
    try:
        # Run PyInstaller with retry logic for permission issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🔨 Build attempt {attempt + 1}/{max_retries}...")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    break  # Success, exit retry loop
                else:
                    # Check if it's a permission error
                    if "PermissionError" in result.stderr or "Access is denied" in result.stderr:
                        if attempt < max_retries - 1:
                            print(f"⚠️  Permission error on attempt {attempt + 1}, retrying...")
                            print("   This is common on Windows. Waiting before retry...")
                            time.sleep(2)  # Wait before retry
                            # Try to clean up again
                            safe_cleanup_build_dirs()
                            continue
                        else:
                            print("❌ Permission errors persisted after all retries")
                    else:
                        # Non-permission error, don't retry
                        break
                        
            except Exception as run_error:
                if attempt < max_retries - 1:
                    print(f"⚠️  Build error on attempt {attempt + 1}: {run_error}")
                    print("   Retrying...")
                    time.sleep(2)
                    continue
                else:
                    raise run_error
        
        if result.returncode == 0:
            print("✓ Executable built successfully!")
            
            if onefile_mode:
                # Check for single file executable
                exe_path = Path("dist") / "Trackwise.exe"
                
                if exe_path.exists():
                    exe_size = exe_path.stat().st_size / (1024 * 1024)  # Size in MB
                    print(f"✓ Single file executable created: {exe_path}")
                    print(f"📦 File size: {exe_size:.1f} MB")
                    print(f"📁 Location: {exe_path.absolute()}")
                    
                    # Provide instructions for single file
                    print("\n🎉 Single file build completed successfully!")
                    print("📋 Instructions:")
                    print(f"   • Your executable is: {exe_path.absolute()}")
                    print("   • This is a single file - easy to distribute")
                    print("   • No Python installation required on target machines")
                    print("   • Internet connection required for API calls")
                    print("\n⚠️  Antivirus Warning:")
                    print("   • Single file mode has higher false positive rates")
                    print("   • If flagged by antivirus, try --onedir mode instead")
                    
                    return True
                else:
                    print("❌ Single file executable not found after build")
                    return False
            else:
                # Check for directory-based executable
                exe_dir = Path("dist") / "Trackwise"
                exe_path = exe_dir / "Trackwise.exe"
                
                if exe_path.exists():
                    exe_size = exe_path.stat().st_size / (1024 * 1024)  # Size in MB
                    print(f"✓ Executable created: {exe_path}")
                    print(f"📦 File size: {exe_size:.1f} MB")
                    print(f"📁 Location: {exe_path.absolute()}")
                    
                    # Try to fix _ctypes issue by manually copying the module
                    print("\n🔧 Checking for _ctypes issue...")
                    fix_ctypes_issue(exe_dir)
                    
                    # Calculate total directory size
                    total_size = sum(f.stat().st_size for f in exe_dir.rglob('*') if f.is_file()) / (1024 * 1024)
                    print(f"📦 Total directory size: {total_size:.1f} MB")
                    
                    # Provide instructions
                    print("\n🎉 Build completed successfully!")
                    print("📋 Instructions:")
                    print(f"   • Your executable directory is located at: {exe_dir.absolute()}")
                    print(f"   • The main executable is: {exe_path.name}")
                    print("   • Copy the entire 'Trackwise' folder to distribute the application")
                    print("   • No Python installation required on target machines")
                    print("   • Internet connection required for API calls")
                    print("\n🛡️  Antivirus Information:")
                    print("   • Using --onedir mode significantly reduces false positive detections")
                    print("   • If still flagged, see the troubleshooting section below")
                    print("\n🔧 _ctypes Issue:")
                    print("   • The build script has attempted to fix common _ctypes issues")
                    print("   • If you still get _ctypes errors, try the console build option below")
                    
                    return True
                else:
                    print("❌ Executable file not found after build")
                    return False
        else:
            print("❌ Build failed!")
            print("Error output:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error during build: {e}")
        return False

def main():
    """Main build process"""
    print("🚀 Trackwise Executable Builder")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        return
    
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Python 3.13 compatibility warning
    if sys.version_info >= (3, 13):
        print("⚠️  Python 3.13 detected - some PyInstaller features may not work properly")
        print("💡 The --copy-metadata flag has been disabled for compatibility")
        print("💡 Consider using Python 3.11 or 3.12 for best PyInstaller compatibility")
        print("🔄 Build will continue with reduced metadata handling")
    
    # Ask about build options
    print("\n🔧 Build Options:")
    print("1. Standard build - Directory mode (recommended for antivirus)")
    print("2. Single file build - One .exe file (higher antivirus risk)")
    print("3. Console mode build (for _ctypes debugging)")
    print("4. Single file + console mode (debugging single file issues)")
    print("5. Rebuild bootloader from source (reduces false positives)")
    print("6. Create Nuitka alternative build script")
    print("7. Clean up build directories (fix permission issues)")
    print("8. Build MSI installer with cx_Freeze (BEST for antivirus)")
    
    choice = input("\nChoose option (1-8, default 1): ").strip()
    
    if choice == "2":
        # Install PyInstaller if needed
        if not install_pyinstaller():
            return
        # Build single file
        if build_executable(onefile_mode=True):
            print("\n🎯 Single file build completed successfully!")
            print("💡 Single .exe file created - easy to distribute")
        else:
            print("\n💥 Single file build failed!")
    elif choice == "3":
        # Install PyInstaller if needed
        if not install_pyinstaller():
            return
        # Build with console mode
        if build_executable(console_mode=True):
            print("\n🎯 Console mode build completed successfully!")
            print("💡 The executable will show a console window for debugging")
        else:
            print("\n💥 Console mode build failed!")
    elif choice == "4":
        # Install PyInstaller if needed
        if not install_pyinstaller():
            return
        # Build single file with console mode
        if build_executable(console_mode=True, onefile_mode=True):
            print("\n🎯 Single file + console mode build completed successfully!")
            print("💡 Single .exe with console window for debugging")
        else:
            print("\n💥 Single file + console mode build failed!")
    elif choice == "5":
        if not rebuild_bootloader():
            return
        # Build executable after bootloader rebuild
        if build_executable():
            print("\n🎯 Build with custom bootloader completed successfully!")
        else:
            print("\n💥 Build with custom bootloader failed!")
    elif choice == "6":
        create_nuitka_build_script()
        return
    elif choice == "7":
        print("\n🧹 Manual cleanup of build directories...")
        safe_cleanup_build_dirs()
        print("\n✅ Cleanup completed!")
        print("💡 You can now try building again")
        return
    elif choice == "8":
        # Build MSI installer with cx_Freeze
        print("\n🔨 Building MSI installer with cx_Freeze...")
        print("💡 This should have much lower antivirus false positive rates!")
        
        # Check if cx_Freeze is available
        try:
            import cx_Freeze
            print("✓ cx_Freeze is available")
        except ImportError:
            print("Installing cx_Freeze...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "cx_Freeze"])
                print("✓ cx_Freeze installed successfully")
            except subprocess.CalledProcessError:
                print("❌ Failed to install cx_Freeze")
                return
        
        # Create setup.py for cx_Freeze
        setup_content = '''#!/usr/bin/env python3
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
    "optimize": 2,
}

# Base for Windows systems
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # No console window

# Main executable
executables = [
    Executable(
        "main_gui_enhanced.py",
        base=base,
        target_name="Trackwise.exe",
        icon="Trackwise.ico" if os.path.exists("Trackwise.ico") else ("icon.ico" if os.path.exists("icon.ico") else None),
        shortcut_name="Trackwise",
        shortcut_dir="DesktopFolder",
        copyright="Trackwise GPX Waypoint Finder"
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
        }
    },
    executables=executables
 )
'''
        
        with open("setup.py", "w") as f:
            f.write(setup_content)
        
        print("✓ Created setup.py for cx_Freeze")
        
        # Build MSI installer
        cmd = [sys.executable, "setup.py", "bdist_msi"]
        
        try:
            print("🚀 Starting MSI build process...")
            print("⚠️  This may take several minutes...")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
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
                        print("\n🛡️  Antivirus Benefits:")
                        print("   • MSI installers have much lower false positive rates")
                        print("   • Professional installation experience")
                        print("   • Easy uninstallation through Control Panel")
                        
                        return
                    else:
                        print("❌ MSI file not found after build")
                        return
                else:
                    print("❌ Dist directory not found after build")
                    return
            else:
                print("❌ MSI build failed!")
                print("Error output:")
                print(result.stderr)
                return
                
        except Exception as e:
            print(f"❌ Error during MSI build: {e}")
            return
    else:
        # Install PyInstaller if needed
        if not install_pyinstaller():
            return
        # Standard build
        if build_executable():
            print("\n🎯 Build process completed successfully!")
        else:
            print("\n💥 Build process failed!")
        print("\nTroubleshooting tips:")
        print("• Make sure all required packages are installed:")
        print("  pip install tkinter requests gpxpy geopy shapely matplotlib folium numpy")
        print("• Check that main_gui_enhanced.py runs without errors")
        print("• Try running the build command manually if needed")
    
    # Always show antivirus troubleshooting info
    print("\n🛡️  Antivirus False Positive Solutions:")
    print("=" * 50)
    print("If your executable is still flagged as a trojan:")
    print("")
    print("1. 📁 USE --onedir MODE (RECOMMENDED - already implemented)")
    print("   • Creates a directory instead of single file")
    print("   • Significantly reduces false positive rates")
    print("   • Distribute the entire 'Trackwise' folder")
    print("")
    print("2. 🔒 CODE SIGNING (Most Effective)")
    print("   • Get a code signing certificate from a trusted CA")
    print("   • Sign the executable with signtool.exe")
    print("   • Cost: ~$100-400/year but eliminates most false positives")
    print("")
    print("3. 🔧 REBUILD BOOTLOADER (Advanced)")
    print("   • Compile PyInstaller bootloader from source")
    print("   • Creates unique binary signature")
    print("   • Run: pip uninstall pyinstaller")
    print("   • Then: pip install --no-binary pyinstaller pyinstaller")
    print("")
    print("4. 📢 REPORT FALSE POSITIVE")
    print("   • Submit to Microsoft Defender:")
    print("     https://www.microsoft.com/en-us/wdsi/filesubmission")
    print("   • Include your contact info and explanation")
    print("   • May take 1-7 days for resolution")
    print("")
    print("5. 🔄 ALTERNATIVE TOOLS")
    print("   • Try Nuitka: pip install nuitka")
    print("   • Try cx_Freeze: pip install cx_Freeze")
    print("   • These may have lower false positive rates")
    print("")
    print("6. ⚠️  TEMPORARY WORKAROUNDS")
    print("   • Add executable folder to Windows Defender exclusions")
    print("   • Disable real-time protection temporarily during build")
    print("   • Note: These are for development only!")

if __name__ == "__main__":
    main()

