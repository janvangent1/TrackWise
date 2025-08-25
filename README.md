# Trackwise - GPX Waypoint Finder

A powerful Python application for finding petrol stations, supermarkets, bakeries, cafes, repair shops, accommodation, and speed cameras along GPX routes. Perfect for motorcyclists, cyclists, and travelers planning their journeys.

## 🚀 Features

- **Multi-Place Search**: Find petrol stations, supermarkets, bakeries, cafes, repair shops, hotels, and speed cameras
- **Smart Distance Calculation**: Configurable search distances for each place type
- **Interactive Maps**: Built-in matplotlib preview and browser-based folium maps
- **GPX Generation**: Create enhanced GPX files with waypoints and route deviations
- **Road Routing**: Uses OSRM for accurate road-following routes to places
- **User-Friendly GUI**: Intuitive tkinter interface with progress tracking
- **Antivirus-Friendly**: Multiple build options to reduce false positive detections

## 📋 Requirements

- Python 3.7 or higher
- Windows 10/11 (primary target)
- Internet connection for API calls

## 🛠️ Installation

### Option 1: Run from Source (Recommended for Development)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/trackwise.git
cd trackwise
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main_gui_enhanced.py
```

### Option 2: Build Executable

Use the included build scripts to create standalone executables:

```bash
# Build with PyInstaller (recommended for antivirus)
python build_executable.py

# Build MSI installer with cx_Freeze (best for distribution)
python build_msi_installer.py
```

## 🔧 Build Options

### PyInstaller Build (`build_executable.py`)
- **Directory Mode** (Recommended): Creates a folder with all dependencies
- **Single File Mode**: Creates one .exe file (higher antivirus risk)
- **Console Mode**: Includes console window for debugging
- **Bootloader Rebuild**: Compile from source to reduce false positives

### MSI Installer Build (`build_msi_installer.py`)
- **Professional Installation**: Creates Windows MSI installer
- **Lower False Positives**: MSI format reduces antivirus detections
- **Auto Shortcuts**: Desktop and Start Menu shortcuts
- **Easy Uninstall**: Standard Windows uninstallation

## 📦 Dependencies

Core dependencies (automatically installed):
- `tkinter` - GUI framework
- `requests` - HTTP requests for APIs
- `gpxpy` - GPX file parsing
- `geopy` - Geographic calculations
- `shapely` - Geometric operations
- `matplotlib` - Map visualization
- `folium` - Interactive web maps
- `numpy` - Numerical operations

## 🗺️ Usage

1. **Load GPX File**: Select your route file (.gpx format)
2. **Configure Search**: Choose place types and search distances
3. **Start Search**: Click "Search Selected Places" to begin
4. **Review Results**: Check found places in the interactive list
5. **Generate GPX**: Create enhanced GPX with selected waypoints
6. **View Maps**: Use built-in preview or open in browser

## 🎯 Place Types

| Type | Default Distance | Description |
|------|------------------|-------------|
| ⛽ Petrol Stations | 5.0 km | Fuel stops along route |
| 🛒 Supermarkets | 0.1 km | Shopping opportunities |
| 🥖 Bakeries | 0.1 km | Fresh bread and pastries |
| ☕ Cafés/Restaurants | 0.1 km | Food and refreshments |
| 🔧 Repair Shops | 0.1 km | Vehicle maintenance |
| 🏨 Accommodation | 0.1 km | Hotels, camping, B&Bs |
| 📷 Speed Cameras | 0.05 km | Traffic enforcement (on-route only) |

## 🗺️ Map Features

- **Route Display**: Shows your GPX track in blue
- **Place Markers**: Color-coded by type with numbered labels
- **Road Routes**: Actual road paths to places (when available)
- **Interactive Selection**: Click places to highlight on map
- **Browser Maps**: Full-featured folium maps with clustering

## 📁 File Structure

```
trackwise/
├── main_gui_enhanced.py      # Main application
├── build_executable.py       # PyInstaller build script
├── build_msi_installer.py    # cx_Freeze MSI builder
├── requirements.txt          # Python dependencies
├── README.md                # This file
├── LICENSE                  # License information
└── examples/                # Sample GPX files
```

## 🛡️ Antivirus False Positive Solutions

If your executable is flagged as suspicious:

1. **Use MSI Installers**: Much lower false positive rates
2. **Directory Mode**: Use `--onedir` instead of `--onefile`
3. **Code Signing**: Professional certificates eliminate most issues
4. **Report False Positives**: Submit to Microsoft Defender
5. **Alternative Builders**: Try Nuitka or cx_Freeze

## 🔍 API Services

- **Overpass API**: OpenStreetMap data for place locations
- **OSRM**: Road routing and navigation
- **Rate Limiting**: Built-in retry logic and delays

## 🚨 Troubleshooting

### Common Issues

1. **Permission Errors**: Run as Administrator or use cleanup option
2. **Missing Dependencies**: Install with `pip install -r requirements.txt`
3. **API Failures**: Check internet connection and try again later
4. **Large GPX Files**: Reduce search distances for better performance

### Build Issues

1. **PyInstaller Failures**: Try MSI installer option
2. **Antivirus Blocking**: Use MSI format or directory mode
3. **Missing Modules**: Check hidden imports in build scripts

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Use GitHub Discussions for questions
- **Wiki**: Check the repository wiki for detailed guides

## 🙏 Acknowledgments

- **OpenStreetMap** contributors for map data
- **Overpass API** for place search services
- **OSRM** for road routing
- **Python community** for excellent libraries

## 📊 Performance Tips

- **Search Distances**: Smaller distances = faster processing
- **Route Length**: Very long routes may take several minutes
- **Internet Speed**: Faster connections improve API response times
- **Memory Usage**: Large datasets may require more RAM

## 🔄 Version History

- **v1.0.0**: Initial release with core functionality
- **v1.1.0**: Added MSI installer support
- **v1.2.0**: Enhanced map visualization and place selection
- **v1.3.0**: Improved antivirus compatibility and build options

---

**Happy Route Planning! 🗺️✨**

