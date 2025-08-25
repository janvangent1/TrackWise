#!/usr/bin/env python3
"""
Build script for creating macOS applications and installers of Trackwise
"""

import subprocess
import sys
import os
import shutil
import time
import platform
from pathlib import Path

def check_macos():
    """Check if we're running on macOS"""
    if platform.system() != "Darwin":
        print("❌ This script is designed for macOS only!")
        print(f"   Current platform: {platform.system()}")
        print("   Please run this script on a macOS system")
        return False
    return True

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

def install_dmgbuild():
    """Install dmgbuild for creating DMG files"""
    if platform.system() != "Darwin":
        print("⚠️  dmgbuild is only available on macOS")
        return False
    
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

def create_app_bundle(main_file_path):
    """Create a macOS .app bundle using PyInstaller"""
    print("🍎 Creating macOS .app bundle...")
    
    # PyInstaller command for macOS
    cmd = [
        "pyinstaller",
        "--onedir",  # Use directory mode for better compatibility
        "--windowed",  # No terminal window
        "--name=Trackwise",
        "--distpath=dist",
        "--workpath=build",
        "--specpath=build",
        "--clean",
        "--noconfirm",
        "--debug=all",  # Add debug info for troubleshooting
        main_file_path
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
        if icon_found.endswith('.icns'):
            print(f"🎨  Using macOS native icon: {icon_path}")
        elif icon_found.endswith('Trackwise.ico'):
            print(f"🎨  Using primary Trackwise icon: {icon_path}")
            print("💡 Consider converting to .icns format for better macOS integration")
        else:
            print(f"⚠️  Using fallback icon: {icon_path}")
            print("💡 Consider using Trackwise.ico for better branding")
    else:
        print("ℹ️  No icon file found - app will use default icon")
        print("💡 Add Trackwise.ico to the project directory for custom app icon")
    
    # Add additional PyInstaller options for macOS
    cmd.extend([
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk", 
        "--hidden-import=tkinter.filedialog",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=requests",
        "--hidden-import=gpxpy",
        "--hidden-import=geopy",
        "--hidden-import=geopy.distance",
        "--hidden-import=shapely",
        "--hidden-import=shapely.geometry",
        "--hidden-import=matplotlib",
        "--hidden-import=matplotlib.pyplot",
        "--hidden-import=matplotlib.backends.backend_tkagg",
        "--hidden-import=folium",
        "--hidden-import=folium.plugins",
        "--hidden-import=numpy",
        "--hidden-import=tempfile",
        "--hidden-import=webbrowser",
        "--hidden-import=threading",
        "--hidden-import=csv",
        "--hidden-import=concurrent.futures",
        "--hidden-import=xml.etree.ElementTree",
        "--hidden-import=urllib3",
        "--hidden-import=certifi",
        "--collect-all=matplotlib",
        "--collect-all=folium",
        "--collect-all=geopy",
        "--collect-all=shapely",
        "--collect-all=gpxpy"
    ])
    
    try:
        print("Running PyInstaller...")
        print(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ PyInstaller completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False

def create_dmg_installer():
    """Create a .dmg installer file"""
    print("📦 Creating .dmg installer...")
    
    if not install_dmgbuild():
        print("❌ Cannot create DMG without dmgbuild")
        return False
    
    try:
        import dmgbuild
        
        # DMG settings
        settings = {
            'title': 'Trackwise Installer',
            'format': 'UDBZ',  # Compressed DMG
            'size': None,  # Auto-size
            'files': ['dist/Trackwise.app'],
            'symlinks': {'Applications': '/Applications'},
            'icon_size': 128,
            'background': None,  # Could add custom background image
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
        
        # Create DMG
        dmgbuild.build_dmg('dist/Trackwise.dmg', 'Trackwise', settings)
        print("✓ DMG installer created successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create DMG: {e}")
        return False

def create_pkg_installer():
    """Create a .pkg installer using pkgbuild"""
    print("📦 Creating .pkg installer...")
    
    try:
        # Check if pkgbuild is available (comes with macOS)
        result = subprocess.run(['which', 'pkgbuild'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ pkgbuild not found. This tool comes with macOS Xcode Command Line Tools.")
            print("   Install with: xcode-select --install")
            return False
        
        # Create package
        cmd = [
            'pkgbuild',
            '--component', 'dist/Trackwise.app',
            '--install-location', '/Applications',
            '--identifier', 'com.trackwise.app',
            '--version', '1.0.0',
            '--scripts', 'scripts',  # Optional: custom install scripts
            'dist/Trackwise.pkg'
        ]
        
        # Remove scripts option if scripts directory doesn't exist
        if not os.path.exists('scripts'):
            cmd = [c for c in cmd if c != '--scripts' and c != 'scripts']
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ PKG installer created successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create PKG: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error creating PKG: {e}")
        return False

def sign_app_bundle():
    """Sign the app bundle with developer certificate (optional)"""
    print("🔐 Signing app bundle...")
    
    try:
        # Check if codesign is available
        result = subprocess.run(['which', 'codesign'], capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️  codesign not found. App will not be signed.")
            print("   This is optional but recommended for distribution.")
            return False
        
        # Try to sign with available identity
        cmd = [
            'codesign',
            '--force',
            '--deep',
            '--sign', '-',  # Use ad-hoc signing (no certificate required)
            'dist/Trackwise.app'
        ]
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ App bundle signed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️  App signing failed: {e}")
        print("   App will still work, but may show security warnings")
        return False
    except Exception as e:
        print(f"⚠️  Unexpected error during signing: {e}")
        return False

def create_notarization_script():
    """Create a script for notarizing the app (required for distribution outside App Store)"""
    notarize_script = '''#!/bin/bash
# Notarization script for Trackwise
# This script helps notarize your app for distribution outside the Mac App Store

APP_PATH="dist/Trackwise.app"
BUNDLE_ID="com.trackwise.app"
TEAM_ID="YOUR_TEAM_ID"  # Replace with your Apple Developer Team ID
APPLE_ID="your.email@example.com"  # Replace with your Apple ID

echo "🍎 Notarizing Trackwise app..."

# Create a temporary zip file
ditto -c -k --keepParent "$APP_PATH" "Trackwise.zip"

# Submit for notarization
xcrun altool --notarize-app \
    --primary-bundle-id "$BUNDLE_ID" \
    --username "$APPLE_ID" \
    --password "@env:APPLE_APP_PASSWORD" \
    --file "Trackwise.zip"

echo "✅ Notarization submitted. Check email for status."
echo "💡 After approval, staple the ticket:"
echo "   xcrun stapler staple \"$APP_PATH\""
echo "   xcrun stapler validate \"$APP_PATH\""

# Clean up
rm "Trackwise.zip"
'''
    
    with open('notarize.sh', 'w') as f:
        f.write(notarize_script)
    
    # Make executable
    os.chmod('notarize.sh', 0o755)
    print("✓ Created notarization script: notarize.sh")
    print("   Edit this script with your Apple Developer details")

def main():
    """Main build function"""
    print("🍎 Trackwise macOS Builder")
    print("=" * 40)
    
    if not check_macos():
        return
    
    # Get main file path
    main_file = "main_gui_enhanced.py"
    if not os.path.exists(main_file):
        print(f"❌ Main file not found: {main_file}")
        return
    
    print(f"📁 Building from: {main_file}")
    
    # Clean up
    safe_cleanup_build_dirs()
    
    # Install required tools
    if not install_pyinstaller():
        print("❌ Cannot proceed without PyInstaller")
        return
    
    # Create app bundle
    if not create_app_bundle(main_file):
        print("❌ Failed to create app bundle")
        return
    
    # Sign the app (optional)
    sign_app_bundle()
    
    # Create installers
    print("\n📦 Creating installers...")
    
    # Try DMG first
    if create_dmg_installer():
        print("✅ DMG installer created successfully")
    else:
        print("⚠️  DMG creation failed, trying PKG...")
        if create_pkg_installer():
            print("✅ PKG installer created successfully")
        else:
            print("⚠️  Both DMG and PKG creation failed")
    
    # Create notarization script
    create_notarization_script()
    
    print("\n🎉 Build completed!")
    print("\n📁 Output files:")
    if os.path.exists("dist/Trackwise.app"):
        print("   • dist/Trackwise.app (App bundle)")
    if os.path.exists("dist/Trackwise.dmg"):
        print("   • dist/Trackwise.dmg (DMG installer)")
    if os.path.exists("dist/Trackwise.pkg"):
        print("   • dist/Trackwise.pkg (PKG installer)")
    
    print("\n💡 Next steps:")
    print("   1. Test the .app bundle by double-clicking")
    print("   2. If app crashes, run from Terminal for error details:")
    print("      cd dist && ./Trackwise.app/Contents/MacOS/Trackwise")
    print("   3. Test the installer (.dmg or .pkg)")
    print("   4. Edit notarize.sh with your Apple Developer details")
    print("   5. Notarize the app for distribution outside App Store")
    print("   6. Consider code signing with a Developer ID certificate")
    
    print("\n🔧 Troubleshooting:")
    print("   • App built with --onedir mode for better compatibility")
    print("   • Debug mode enabled for detailed error logging")
    print("   • All dependencies collected with --collect-all flags")
    print("   • If still crashing, try building without --windowed flag")

if __name__ == "__main__":
    main()
