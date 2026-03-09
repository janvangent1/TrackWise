#!/usr/bin/env python3
"""
Cross-platform build script for Trackwise
Automatically detects OS and builds appropriate executable/installer
"""

import subprocess
import sys
import os
import shutil
import time
import platform
from pathlib import Path

def get_platform_info():
    """Get detailed platform information"""
    system = platform.system()
    machine = platform.machine()
    release = platform.release()
    
    print(f"🖥️  Platform: {system}")
    print(f"   Architecture: {machine}")
    print(f"   Version: {release}")
    
    return system, machine, release

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

def install_dmgbuild():
    """Install dmgbuild for macOS DMG creation"""
    try:
        import dmgbuild
        print("✓ dmgbuild is already installed")
        return True
    except ImportError:
        print("Installing dmgbuild...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "dmgbuild"])
            print("✓ dmgbuild installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install dmgbuild")
            return False

def build_windows():
    """Build for Windows"""
    print("\n🪟 Building for Windows...")
    
    # Install cx_Freeze for MSI creation
    if not install_cx_freeze():
        print("❌ Cannot create MSI without cx_Freeze")
        return False
    
    # Run the Windows MSI builder
    try:
        result = subprocess.run([sys.executable, "build_msi_installer.py"], check=True)
        print("✅ Windows MSI installer created successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Windows build failed: {e}")
        return False

def build_macos():
    """Build for macOS"""
    print("\n🍎 Building for macOS...")
    
    # Install required tools
    if not install_pyinstaller():
        print("❌ Cannot proceed without PyInstaller")
        return False
    
    if not install_dmgbuild():
        print("⚠️  DMG creation may fail without dmgbuild")
    
    # Create app bundle
    print("Creating macOS .app bundle...")
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name=Trackwise",
        "--distpath=dist",
        "--workpath=build",
        "--clean",
        "--noconfirm",
        "main_gui_enhanced.py"
    ]
    
    # Add icon if available - prioritize Trackwise.ico
    icon_paths = [
        "Trackwise.icns",  # macOS native format (preferred)
        "Trackwise.ico",   # Primary icon file
        "icon.icns",       # Fallback macOS format
        "icon.ico"         # Fallback icon
    ]
    icon_found = None
    for icon_path in icon_paths:
        if os.path.exists(icon_path):
            icon_found = icon_path
            break
    
    if icon_found:
        cmd.extend(["--icon", icon_path])
        if icon_found.endswith('Trackwise.ico'):
            print(f"🎨  Using primary Trackwise icon: {icon_path}")
        elif icon_found.endswith('.icns'):
            print(f"🎨  Using macOS native icon: {icon_path}")
        else:
            print(f"⚠️  Using fallback icon: {icon_path}")
            print("💡 Consider using Trackwise.ico for better branding")
    else:
        print("ℹ️  No icon file found - app will use default icon")
        print("💡 Add Trackwise.ico to the project directory for custom app icon")
    
    # Add macOS-specific options
    cmd.extend([
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.filedialog",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=requests",
        "--hidden-import=gpxpy",
        "--hidden-import=geopy",
        "--hidden-import=shapely",
        "--hidden-import=matplotlib",
        "--hidden-import=folium",
        "--hidden-import=numpy",
        "--collect-all=matplotlib",
        "--collect-all=folium"
    ])
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ macOS app bundle created successfully")
        
        # Try to create DMG
        if install_dmgbuild():
            try:
                import dmgbuild
                settings = {
                    'title': 'Trackwise Installer',
                    'format': 'UDBZ',
                    'files': ['dist/Trackwise.app'],
                    'symlinks': {'Applications': '/Applications'},
                    'icon_size': 128,
                    'show_icon_size': True,
                    'show_item_info': True,
                    'show_status_bar': True,
                    'show_path_bar': True,
                    'show_toolbar': True,
                    'show_sidebar': True,
                    'sidebar_width': 200,
                    'window_rect': ((100, 100), (800, 600)),
                    'default_view': 'icon-view',
                    'icon_locations': {
                        'Trackwise.app': (200, 200),
                        'Applications': (400, 200)
                    }
                }
                dmgbuild.build_dmg('dist/Trackwise.dmg', 'Trackwise', settings)
                print("✅ macOS DMG installer created successfully")
            except Exception as e:
                print(f"⚠️  DMG creation failed: {e}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ macOS build failed: {e}")
        return False

def build_linux():
    """Build for Linux"""
    print("\n🐧 Building for Linux...")
    
    # Install PyInstaller
    if not install_pyinstaller():
        print("❌ Cannot proceed without PyInstaller")
        return False
    
    # Create Linux executable
    print("Creating Linux executable...")
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name=Trackwise",
        "--distpath=dist",
        "--workpath=build",
        "--clean",
        "--noconfirm",
        "main_gui_enhanced.py"
    ]
    
    # Add icon if available - prioritize Trackwise.ico
    icon_paths = [
        "Trackwise.ico",   # Primary icon file
        "Trackwise.png",   # Linux PNG format
        "icon.ico",        # Fallback icon
        "icon.png"         # Fallback PNG
    ]
    icon_found = None
    for icon_path in icon_paths:
        if os.path.exists(icon_path):
            icon_found = icon_path
            break
    
    if icon_found:
        if icon_found.endswith('Trackwise.ico'):
            print(f"🎨  Using primary Trackwise icon: {icon_path}")
        elif icon_found.endswith('Trackwise.png'):
            print(f"🎨  Using Linux PNG icon: {icon_path}")
        else:
            print(f"⚠️  Using fallback icon: {icon_path}")
            print("💡 Consider using Trackwise.ico for better branding")
    else:
        print("ℹ️  No icon file found - executable will use default icon")
        print("💡 Add Trackwise.ico to the project directory for custom executable icon")
    
    if icon_found:
        cmd.extend(["--icon", icon_path])
    
    # Add Linux-specific options
    cmd.extend([
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.filedialog",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=requests",
        "--hidden-import=gpxpy",
        "--hidden-import=geopy",
        "--hidden-import=shapely",
        "--hidden-import=matplotlib",
        "--hidden-import=folium",
        "--hidden-import=numpy",
        "--collect-all=matplotlib",
        "--collect-all=folium"
    ])
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Linux executable created successfully")
        
        # Create AppImage if appimagetool is available
        try:
            result = subprocess.run(['which', 'appimagetool'], capture_output=True, text=True)
            if result.returncode == 0:
                print("Creating AppImage...")
                # Create AppDir structure
                appdir = "Trackwise.AppDir"
                if os.path.exists(appdir):
                    shutil.rmtree(appdir)
                
                os.makedirs(f"{appdir}/usr/bin", exist_ok=True)
                os.makedirs(f"{appdir}/usr/share/applications", exist_ok=True)
                os.makedirs(f"{appdir}/usr/share/icons/hicolor/256x256/apps", exist_ok=True)
                
                # Copy executable
                shutil.copy("dist/Trackwise", f"{appdir}/usr/bin/")
                os.chmod(f"{appdir}/usr/bin/Trackwise", 0o755)
                
                # Create desktop file
                desktop_content = """[Desktop Entry]
Name=Trackwise
Comment=GPX Waypoint Finder
Exec=Trackwise
Icon=Trackwise
Terminal=false
Type=Application
Categories=Utility;Geography;
"""
                with open(f"{appdir}/usr/share/applications/Trackwise.desktop", 'w') as f:
                    f.write(desktop_content)
                
                # Copy icon if available
                if icon_found:
                    shutil.copy(icon_found, f"{appdir}/usr/share/icons/hicolor/256x256/apps/Trackwise.png")
                
                # Create AppImage
                subprocess.run(['appimagetool', appdir, 'dist/Trackwise-x86_64.AppImage'], check=True)
                print("✅ Linux AppImage created successfully")
                
                # Clean up AppDir
                shutil.rmtree(appdir)
            else:
                print("⚠️  appimagetool not found. Install it to create AppImages.")
        except Exception as e:
            print(f"⚠️  AppImage creation failed: {e}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Linux build failed: {e}")
        return False

def create_package_scripts():
    """Create platform-specific packaging scripts"""
    print("\n📝 Creating platform-specific scripts...")
    
    # Windows batch file
    windows_bat = '''@echo off
echo Building Trackwise for Windows...
python build_msi_installer.py
pause
'''
    with open('build_windows.bat', 'w') as f:
        f.write(windows_bat)
    
    # macOS shell script
    macos_sh = '''#!/bin/bash
echo "Building Trackwise for macOS..."
python3 build_macos.py
'''
    with open('build_macos.sh', 'w') as f:
        f.write(macos_sh)
    
    # Linux shell script
    linux_sh = '''#!/bin/bash
echo "Building Trackwise for Linux..."
python3 build_linux.py
'''
    with open('build_linux.sh', 'w') as f:
        f.write(linux_sh)
    
    # Make shell scripts executable
    if platform.system() != "Windows":
        os.chmod('build_macos.sh', 0o755)
        os.chmod('build_linux.sh', 0o755)
    
    print("✅ Created platform-specific build scripts:")
    print("   • build_windows.bat")
    print("   • build_macos.sh")
    print("   • build_linux.sh")

def main():
    """Main cross-platform build function"""
    print("🌍 Trackwise Cross-Platform Builder")
    print("=" * 50)
    
    # Get platform info
    system, machine, release = get_platform_info()
    
    # Check if main file exists
    main_file = "main_gui_enhanced.py"
    if not os.path.exists(main_file):
        print(f"❌ Main file not found: {main_file}")
        return
    
    print(f"📁 Building from: {main_file}")
    
    # Clean up
    safe_cleanup_build_dirs()
    
    # Build for current platform
    success = False
    if system == "Windows":
        success = build_windows()
    elif system == "Darwin":  # macOS
        success = build_macos()
    elif system == "Linux":
        success = build_linux()
    else:
        print(f"❌ Unsupported platform: {system}")
        return
    
    if success:
        print(f"\n🎉 {system} build completed successfully!")
        
        # Show output files
        print("\n📁 Output files:")
        if os.path.exists("dist"):
            for file in os.listdir("dist"):
                file_path = os.path.join("dist", file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                    print(f"   • {file} ({size:.1f} MB)")
                elif os.path.isdir(file_path):
                    print(f"   • {file}/ (directory)")
        
        # Create platform-specific scripts
        create_package_scripts()
        
        print(f"\n💡 Next steps for {system}:")
        if system == "Windows":
            print("   1. Test the MSI installer")
            print("   2. Check for antivirus false positives")
            print("   3. Consider code signing for distribution")
        elif system == "Darwin":
            print("   1. Test the .app bundle")
            print("   2. Test the .dmg installer")
            print("   3. Consider notarization for distribution")
        elif system == "Linux":
            print("   1. Test the executable")
            print("   2. Test the AppImage (if created)")
            print("   3. Consider creating distribution packages")
    else:
        print(f"\n❌ {system} build failed!")
        print("   Check the error messages above for details")

if __name__ == "__main__":
    main()
