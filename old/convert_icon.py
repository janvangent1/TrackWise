#!/usr/bin/env python3
"""
Icon conversion utility for Trackwise
Converts Trackwise.ico to .icns format for better macOS integration
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_requirements():
    """Check if required tools are available"""
    print("🔍 Checking requirements for icon conversion...")
    
    # Check if we're on macOS
    if sys.platform != "darwin":
        print("⚠️  This script is designed for macOS")
        print("   On Windows/Linux, the .ico file will work fine")
        print("   For macOS, you can manually convert using:")
        print("   • Icon Composer (part of Xcode)")
        print("   • Online converters like convertio.co")
        return False
    
    # Check if sips is available (comes with macOS)
    try:
        subprocess.run(["sips", "--help"], capture_output=True, check=True)
        print("✓ sips tool available (macOS built-in)")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ sips tool not found")
        print("   This tool comes with macOS by default")
        return False

def convert_ico_to_icns():
    """Convert Trackwise.ico to Trackwise.icns using macOS tools"""
    print("🔄 Converting Trackwise.ico to Trackwise.icns...")
    
    if not os.path.exists("Trackwise.ico"):
        print("❌ Trackwise.ico not found in current directory")
        print("💡 Make sure Trackwise.ico is in the same folder as this script")
        return False
    
    try:
        # Create a temporary directory for the conversion
        temp_dir = "temp_icon_conversion"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Extract different sizes from the ICO file
        sizes = [16, 32, 48, 128, 256, 512]
        
        print("📏 Extracting icon sizes...")
        for size in sizes:
            output_file = os.path.join(temp_dir, f"icon_{size}x{size}.png")
            cmd = ["sips", "-s", "format", "png", "--resampleHeightWidth", str(size), str(size), 
                   "Trackwise.ico", "--out", output_file]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"✓ Created {size}x{size} PNG")
            except subprocess.CalledProcessError:
                print(f"⚠️  Could not create {size}x{size} PNG (size may not exist in ICO)")
        
        # Create the ICNS file using iconutil (macOS built-in)
        print("🎨 Creating ICNS file...")
        
        # Create iconset directory
        iconset_dir = "Trackwise.iconset"
        os.makedirs(iconset_dir, exist_ok=True)
        
        # Move PNG files to iconset with proper naming
        for size in sizes:
            png_file = os.path.join(temp_dir, f"icon_{size}x{size}.png")
            if os.path.exists(png_file):
                if size <= 16:
                    # For small icons, also create @2x versions
                    dest_file = os.path.join(iconset_dir, f"icon_{size}x{size}.png")
                    os.rename(png_file, dest_file)
                    
                    # Create @2x version for retina displays
                    dest_file_2x = os.path.join(iconset_dir, f"icon_{size}x{size}@2x.png")
                    os.rename(png_file, dest_file_2x)
                else:
                    dest_file = os.path.join(iconset_dir, f"icon_{size}x{size}.png")
                    os.rename(png_file, dest_file)
                    
                    # Create @2x version for retina displays
                    dest_file_2x = os.path.join(iconset_dir, f"icon_{size}x{size}@2x.png")
                    os.rename(png_file, dest_file_2x)
        
        # Use iconutil to create the ICNS file
        cmd = ["iconutil", "-c", "icns", iconset_dir, "-o", "Trackwise.icns"]
        subprocess.run(cmd, check=True)
        
        print("✅ Successfully created Trackwise.icns!")
        print("🎯 The ICNS file is now ready for macOS builds")
        
        # Clean up
        shutil.rmtree(temp_dir)
        shutil.rmtree(iconset_dir)
        
        return True
        
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return False

def main():
    """Main conversion process"""
    print("🎨 Trackwise Icon Converter")
    print("=" * 40)
    
    if not check_requirements():
        return
    
    print("\n💡 This will convert Trackwise.ico to Trackwise.icns")
    print("   The ICNS format provides better macOS integration")
    print("   and will be used automatically by the build scripts")
    
    response = input("\nContinue with conversion? (y/n): ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ Conversion cancelled")
        return
    
    if convert_ico_to_icns():
        print("\n🎉 Icon conversion completed successfully!")
        print("📱 Your macOS builds will now use the native ICNS format")
        print("🖥️  Windows/Linux builds will continue to use the ICO format")
    else:
        print("\n💥 Icon conversion failed")
        print("💡 You can still build with the ICO file - it will work fine")

if __name__ == "__main__":
    main()
