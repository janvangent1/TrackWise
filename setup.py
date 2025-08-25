#!/usr/bin/env python3
"""
Setup script for Trackwise GPX Waypoint Finder
"""

from setuptools import setup, find_packages
import os

# Read the README file for long description
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements from requirements.txt
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        requirements = []
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                requirements.append(line)
        return requirements

setup(
    name="trackwise",
    version="1.0.0",
    author="Trackwise Developer",
    author_email="developer@trackwise.com",
    description="GPX Waypoint Finder - Find petrol stations, supermarkets, and more along your route",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/trackwise",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/trackwise/issues",
        "Source": "https://github.com/yourusername/trackwise",
        "Documentation": "https://github.com/yourusername/trackwise/wiki",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Scientific/Engineering :: GIS",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Environment :: X11 Applications :: GTK",
        "Environment :: Win32 (MS Windows)",
    ],
    python_requires=">=3.7",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
        "build": [
            "pyinstaller>=4.0",
            "cx_Freeze>=6.0",
            "nuitka>=1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "trackwise=main_gui_enhanced:main",
        ],
        "gui_scripts": [
            "trackwise-gui=main_gui_enhanced:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.txt", "*.md", "*.ico", "*.png"],
    },
    keywords="gpx, waypoint, petrol, station, route, planning, gis, mapping",
    platforms=["Windows", "Linux", "macOS"],
    license="MIT",
    zip_safe=False,
)

