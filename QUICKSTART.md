# Quick Start Guide - Trackwise

Get Trackwise up and running in minutes! 🚀

## ⚡ Super Quick Start

1. **Download & Extract**: Get the latest release and extract to a folder
2. **Run**: Double-click `main_gui_enhanced.py` (if Python is installed)
3. **Or Build**: Use the build scripts to create a standalone executable

## 🐍 Python Users

### Prerequisites
- Python 3.7+ installed
- pip package manager

### Installation instructions
```bash
# Clone or download the repository
cd trackwise

# Install dependencies
pip install -r requirements.txt

# Run the application
python main_gui_enhanced.py
```

## 🖥️ Windows Users (No Python Required)

### Option 1: MSI Installer (Recommended)
1. Download the `.msi` file from releases
2. Double-click to install
3. Use Start Menu or Desktop shortcut

### Option 2: Standalone Executable
1. Download the `Trackwise` folder from releases
2. Extract to any location
3. Run `Trackwise.exe` inside the folder

## 🔨 Build Your Own Executable

### Quick Build (PyInstaller)
```bash
python build_executable.py
# Choose option 1 (recommended)
```

### Professional Build (MSI Installer)
```bash
python build_msi_installer.py
# Choose option 1 (recommended)
```

## 📱 First Run

1. **Load GPX**: Click "Browse" and select your route file
2. **Set Distances**: Configure search distances for each place type
3. **Select Types**: Check the place types you want to find
4. **Search**: Click "Search Selected Places"
5. **Review**: Check found places in the list
6. **Generate**: Create GPX with "Create GPX" button
7. **Maps**: View results on built-in map or open in browser

## 🎯 Example Workflow

### Motorcycle Trip Planning
1. Load your planned route GPX
2. Set petrol distance to 5.0 km
3. Set cafe distance to 0.1 km
4. Search for places
5. Review fuel gaps (warnings shown for >150km)
6. Generate enhanced GPX with waypoints
7. Load into your GPS device

### Cycling Route
1. Load cycling route GPX
2. Set supermarket distance to 0.1 km
3. Set cafe distance to 0.1 km
4. Search for refreshment stops
5. Generate waypoints-only GPX
6. Use on cycling computer

## 🚨 Common Issues & Solutions

### "Python not found"
- **Solution**: Download the pre-built executable instead
- **Alternative**: Install Python from python.org

### "Missing modules"
- **Solution**: Run `pip install -r requirements.txt`
- **Alternative**: Use the build scripts to create standalone exe

### "Permission denied"
- **Solution**: Run as Administrator
- **Alternative**: Use cleanup option in build script

### "Antivirus warning"
- **Solution**: Use MSI installer (much lower false positive rate)
- **Alternative**: Add folder to antivirus exclusions

## 📞 Need Help?

- **Issues**: Check GitHub Issues page
- **Documentation**: Read the full README.md
- **Build Problems**: Try different build options
- **Usage Questions**: Check the examples folder

## 🎉 You're Ready!

Trackwise is now ready to help you plan amazing routes with all the essential stops along the way!

---

**Pro Tip**: Start with small GPX files to test the application before using it with long routes.

