# Trackwise Build Guide

This guide explains how to build Trackwise for different platforms, creating standalone executables and installers.

## 🚀 Quick Start

For the easiest experience, use the cross-platform builder:

```bash
python build_cross_platform.py
```

This script automatically detects your OS and builds the appropriate package.

## 🪟 Windows

### Prerequisites
- Python 3.7+
- Windows 10/11

### Build Options

#### Option 1: MSI Installer (Recommended)
```bash
python build_msi_installer.py
```
Creates a professional MSI installer with:
- Automatic installation to Program Files
- Start menu shortcuts
- Desktop shortcut
- Uninstall support

#### Option 2: Standalone Executable
```bash
python build_executable.py
```
Creates a single `.exe` file that can run anywhere.

### Output Files
- `dist/Trackwise.msi` - MSI installer
- `dist/Trackwise.exe` - Standalone executable

## 🍎 macOS

### Prerequisites
- Python 3.7+
- macOS 10.14+ (Mojave or later)
- Xcode Command Line Tools: `xcode-select --install`

### Build Options

#### Option 1: Full Build (Recommended)
```bash
python build_macos.py
```
Creates both an `.app` bundle and a `.dmg` installer.

#### Option 2: Cross-platform Builder
```bash
python build_cross_platform.py
```

### Output Files
- `dist/Trackwise.app` - macOS application bundle
- `dist/Trackwise.dmg` - DMG installer
- `dist/Trackwise.pkg` - PKG installer (if DMG fails)

### Additional Features
- **Code Signing**: Automatically signs the app bundle
- **Notarization Script**: Creates `notarize.sh` for App Store distribution
- **Icon Support**: Uses `.icns` files for best macOS integration

## 🐧 Linux

### Prerequisites
- Python 3.7+
- Linux distribution (Ubuntu, Fedora, etc.)

### Build Options

#### Option 1: Cross-platform Builder
```bash
python build_cross_platform.py
```

#### Option 2: Linux-specific Build
```bash
python build_linux.py
```

### Output Files
- `dist/Trackwise` - Linux executable
- `dist/Trackwise-x86_64.AppImage` - AppImage (if appimagetool available)

### AppImage Creation
To create AppImages, install the AppImage tools:
```bash
# Ubuntu/Debian
sudo apt install appimagetool

# Fedora
sudo dnf install appimagetool

# Or download from: https://github.com/AppImage/AppImageKit/releases
```

## 🔧 Manual Build Commands

### PyInstaller (All Platforms)
```bash
# Install PyInstaller
pip install pyinstaller

# Basic build
pyinstaller --onefile --windowed main_gui_enhanced.py

# With icon
pyinstaller --onefile --windowed --icon=Trackwise.ico main_gui_enhanced.py

# With additional options
pyinstaller --onefile --windowed --name=Trackwise --distpath=dist --workpath=build --clean main_gui_enhanced.py
```

### cx_Freeze (Windows MSI)
```bash
# Install cx_Freeze
pip install cx_Freeze

# Build MSI
python setup.py bdist_msi
```

## 📦 Package Types Explained

### Windows
- **MSI (.msi)**: Professional installer with Windows integration
- **EXE (.exe)**: Standalone executable, portable

### macOS
- **APP (.app)**: Native macOS application bundle
- **DMG (.dmg)**: Disk image installer (most common)
- **PKG (.pkg)**: Package installer (alternative to DMG)

### Linux
- **Binary**: Standalone executable
- **AppImage**: Portable application package
- **DEB/RPM**: Distribution-specific packages (manual creation)

## 🎨 Icon Requirements

### Windows
- **ICO (.ico)**: Multi-size icon file
- **Recommended sizes**: 16x16, 32x32, 48x48, 256x256

### macOS
- **ICNS (.icns)**: Native macOS icon format
- **Recommended sizes**: 16x16, 32x32, 128x128, 256x256, 512x512
- **Conversion**: Use `iconutil` or online converters

### Linux
- **PNG (.png)**: Standard image format
- **Recommended size**: 256x256 or 512x512

## 🔐 Code Signing & Security

### Windows
- **Code Signing**: Recommended for distribution
- **Certificates**: Purchase from trusted CAs
- **Timestamping**: Ensures long-term validity

### macOS
- **Code Signing**: Required for distribution
- **Developer ID**: Apple Developer Program ($99/year)
- **Notarization**: Required for Gatekeeper approval
- **Ad-hoc Signing**: Free but shows warnings

### Linux
- **GPG Signing**: Optional but recommended
- **Package Signing**: For distribution packages

## 🚨 Troubleshooting

### Common Issues

#### PyInstaller Fails
```bash
# Clean build directories
rm -rf build dist __pycache__

# Reinstall PyInstaller
pip uninstall pyinstaller
pip install pyinstaller

# Check Python version compatibility
python --version
```

#### Missing Dependencies
```bash
# Install all requirements
pip install -r requirements.txt

# Install build tools
pip install pyinstaller cx_Freeze dmgbuild
```

#### Permission Errors (Windows)
- Run as Administrator
- Close any applications using build files
- Move project outside OneDrive
- Restart terminal/IDE

#### macOS Gatekeeper Issues
```bash
# Allow unsigned apps
sudo spctl --master-disable

# Or sign the app properly
codesign --force --deep --sign - dist/Trackwise.app
```

### Platform-Specific Issues

#### Windows
- **Antivirus False Positives**: Common with PyInstaller
- **Missing DLLs**: Use `--collect-all` flags
- **UAC Issues**: Run as Administrator

#### macOS
- **Python Version**: Use Python 3.7-3.11 (3.12+ may have issues)
- **Xcode Tools**: Ensure Command Line Tools are installed
- **Rosetta**: For Intel/Apple Silicon compatibility

#### Linux
- **Library Dependencies**: Install system packages
- **GLIBC Version**: Check compatibility with target systems
- **Desktop Integration**: Ensure desktop files are created

## 📋 Build Checklist

### Before Building
- [ ] Python 3.7+ installed
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Main script (`main_gui_enhanced.py`) exists
- [ ] Icon files available (optional but recommended)
- [ ] Build directories cleaned

### After Building
- [ ] Test executable/installer on target system
- [ ] Check file sizes (should be reasonable)
- [ ] Verify all functionality works
- [ ] Test on clean system (no Python installed)
- [ ] Check for antivirus false positives

### Distribution
- [ ] Code sign the application
- [ ] Test installer on target platform
- [ ] Create release notes
- [ ] Upload to distribution platform
- [ ] Test download and installation

## 🌐 Cross-Platform Development

### Building for Multiple Platforms
1. **Windows**: Build on Windows or use WSL
2. **macOS**: Build on macOS (required for .app bundles)
3. **Linux**: Build on Linux or use Docker

### Docker Build Environment
```dockerfile
FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "build_cross_platform.py"]
```

## 📚 Additional Resources

- [PyInstaller Documentation](https://pyinstaller.readthedocs.io/)
- [cx_Freeze Documentation](https://cx-freeze.readthedocs.io/)
- [macOS Code Signing Guide](https://developer.apple.com/support/code-signing/)
- [Linux AppImage Guide](https://docs.appimage.org/)
- [Windows MSI Creation](https://docs.microsoft.com/en-us/windows/msi/)

## 🤝 Contributing

When adding new build features:
1. Test on all target platforms
2. Update this documentation
3. Add error handling for edge cases
4. Consider cross-platform compatibility
5. Update requirements.txt if needed

---

**Note**: This build system is designed to work across different platforms, but some features (like code signing) may require platform-specific tools and certificates.
