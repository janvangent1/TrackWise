import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import gpxpy
import requests
import csv
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from geopy.distance import geodesic
from shapely.geometry import Point, LineString
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import folium
from folium import plugins
import webbrowser
import tempfile

class CustomNavigationToolbar:
    """Custom navigation toolbar that works with grid layout"""
    def __init__(self, canvas, parent):
        self.canvas = canvas
        self.parent = parent
        
        # Create toolbar frame
        self.toolbar_frame = ttk.Frame(parent)
        
        # Create buttons
        self.home_btn = ttk.Button(self.toolbar_frame, text="🏠", width=3, 
                                  command=self.home)
        self.home_btn.pack(side=tk.LEFT, padx=2)
        
        self.back_btn = ttk.Button(self.toolbar_frame, text="◀", width=3,
                                   command=self.back)
        self.back_btn.pack(side=tk.LEFT, padx=2)
        
        self.forward_btn = ttk.Button(self.toolbar_frame, text="▶", width=3,
                                     command=self.forward)
        self.forward_btn.pack(side=tk.LEFT, padx=2)
        
        # Add separator
        ttk.Separator(self.toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        
        # Add zoom info
        self.zoom_label = ttk.Label(self.toolbar_frame, text="Zoom: 100%")
        self.zoom_label.pack(side=tk.LEFT, padx=5)
        
        # Add separator
        ttk.Separator(self.toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        
        # Add save button
        self.save_btn = ttk.Button(self.toolbar_frame, text="Save", 
                                  command=self.save_figure)
        self.save_btn.pack(side=tk.LEFT, padx=2)
        
        # Bind mouse events for zoom and pan
        self.canvas.get_tk_widget().bind("<ButtonPress-1>", self.on_press)
        self.canvas.get_tk_widget().bind("<B1-Motion>", self.on_drag)
        self.canvas.get_tk_widget().bind("<MouseWheel>", self.on_scroll)
        
        self._xdata = None
        self._ydata = None
        
    def home(self):
        """Reset to home view"""
        self.canvas.figure.gca().autoscale()
        self.canvas.draw()
        self.update_zoom_label()
    
    def back(self):
        """Go back to previous view"""
        # This would require storing view history
        pass
    
    def forward(self):
        """Go forward to next view"""
        # This would require storing view history
        pass
    
    def save_figure(self):
        """Save the current figure"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
        )
        if filename:
            self.canvas.figure.savefig(filename, dpi=150, bbox_inches='tight')
            messagebox.showinfo("Success", f"Figure saved as {filename}")
    
    def on_press(self, event):
        """Handle mouse button press for panning"""
        self._xdata = event.x
        self._ydata = event.y
    
    def on_drag(self, event):
        """Handle mouse drag for panning"""
        if self._xdata is None:
            return
        
        dx = event.x - self._xdata
        dy = event.y - self._ydata
        
        ax = self.canvas.figure.gca()
        
        # Get current limits
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        
        # Calculate pan amount (convert pixels to data coordinates)
        x_range = x_max - x_min
        y_range = y_max - y_min
        
        # Pan factor (adjust this for sensitivity)
        pan_factor = 0.001
        
        # Update limits
        new_x_min = x_min - dx * x_range * pan_factor
        new_x_max = x_max - dx * x_range * pan_factor
        new_y_min = y_min + dy * y_range * pan_factor
        new_y_max = y_max + dy * y_range * pan_factor
        
        ax.set_xlim(new_x_min, new_x_max)
        ax.set_ylim(new_y_min, new_y_max)
        
        self._xdata = event.x
        self._ydata = event.y
        
        self.canvas.draw()
        self.update_zoom_label()
    
    def on_scroll(self, event):
        """Handle mouse scroll for zooming"""
        ax = self.canvas.figure.gca()
        
        # Get current limits
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        
        # Calculate zoom factor
        if event.delta > 0:
            factor = 0.9  # Zoom in
        else:
            factor = 1.1  # Zoom out
        
        # Calculate new limits
        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2
        x_range = (x_max - x_min) * factor
        y_range = (y_max - y_min) * factor
        
        ax.set_xlim(x_center - x_range/2, x_center + x_range/2)
        ax.set_ylim(y_center - y_range/2, y_center + y_range/2)
        
        self.canvas.draw()
        self.update_zoom_label()
    
    def update_zoom_label(self):
        """Update the zoom percentage label"""
        ax = self.canvas.figure.gca()
        x_range = ax.get_xlim()[1] - ax.get_xlim()[0]
        # Calculate approximate zoom level (this is a rough estimate)
        zoom_percent = int(100 / (x_range * 10))  # Rough calculation
        self.zoom_label.config(text=f"Zoom: {max(1, zoom_percent)}%")
    
    def grid(self, **kwargs):
        """Grid the toolbar frame"""
        self.toolbar_frame.grid(**kwargs)

class GPXPetrolFinderEnhancedGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Trackwise - a gpx waypoint finder")
        self.root.geometry("1200x950")
        self.root.resizable(True, True)
        
        # Variables
        self.gpx_file_path = tk.StringVar()
        self.distance_km = tk.StringVar(value="0.1")
        self.output_dir = tk.StringVar()
        
        # New variables for different place types
        self.petrol_distance = tk.StringVar(value="5")
        self.supermarket_distance = tk.StringVar(value="0.1")
        self.bakery_distance = tk.StringVar(value="0.1")
        self.cafe_distance = tk.StringVar(value="0.1")
        self.repair_distance = tk.StringVar(value="0.1")
        self.accommodation_distance = tk.StringVar(value="0.1")
        self.speed_camera_distance = tk.StringVar(value="0.1")
        
        # Initialize data structures
        self.stations_data = []
        self.supermarkets_data = []
        self.bakeries_data = []
        self.cafes_data = []
        self.repair_data = []
        self.accommodation_data = []
        self.speed_cameras_data = []
        self.road_routes = {}
        self.route_points = []
        self.map_html_path = None
        
        # Track API failures and retries
        self.api_failures = {'overpass': 0, 'osrm': 0, 'total_attempts': 0}
        self.api_retries = {'overpass_resolved': 0, 'osrm_resolved': 0}
        self.logged_errors = set()  # Track which errors have been logged to avoid duplicates
        
        # Track what was last searched
        self.last_search_types = []
        
        # Processing control
        self.processing_cancelled = False
        
        # Create GUI
        self.create_widgets()
        
    def create_widgets(self):
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(3, weight=1)
        
        # Left panel - Controls
        left_panel = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        left_panel.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(left_panel, text="Trackwise - a gpx waypoint finder", 
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 15))
        
        # GPX File Selection
        ttk.Label(left_panel, text="GPX File:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(left_panel, textvariable=self.gpx_file_path, width=35).grid(
            row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        ttk.Button(left_panel, text="Browse", command=self.browse_gpx_file).grid(
            row=1, column=2, pady=5)
        
        # Output Directory
        ttk.Label(left_panel, text="Output Directory:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(left_panel, textvariable=self.output_dir, width=35).grid(
            row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        ttk.Button(left_panel, text="Browse", command=self.browse_output_dir).grid(
            row=2, column=2, pady=5)
        
        # Search Controls Frame
        search_frame = ttk.LabelFrame(left_panel, text="Search Controls", padding="10")
        search_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        search_frame.columnconfigure(1, weight=1)
        
        # Create checkbox variables
        self.petrol_enabled = tk.BooleanVar(value=True)  # Default checked
        self.supermarket_enabled = tk.BooleanVar(value=False)
        self.bakery_enabled = tk.BooleanVar(value=False)
        self.cafe_enabled = tk.BooleanVar(value=False)
        self.repair_enabled = tk.BooleanVar(value=False)
        self.accommodation_enabled = tk.BooleanVar(value=False)
        self.speed_camera_enabled = tk.BooleanVar(value=False)
        
        # Petrol Stations
        petrol_check = ttk.Checkbutton(search_frame, text="Petrol Stations", variable=self.petrol_enabled)
        petrol_check.grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(search_frame, textvariable=self.petrol_distance, width=8).grid(
            row=0, column=1, sticky=tk.W, padx=(5, 5), pady=2)
        ttk.Label(search_frame, text="km").grid(row=0, column=2, sticky=tk.W, pady=2)
        
        # Supermarkets
        supermarket_check = ttk.Checkbutton(search_frame, text="Supermarkets", variable=self.supermarket_enabled)
        supermarket_check.grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(search_frame, textvariable=self.supermarket_distance, width=8).grid(
            row=1, column=1, sticky=tk.W, padx=(5, 5), pady=2)
        ttk.Label(search_frame, text="km").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        # Bakeries
        bakery_check = ttk.Checkbutton(search_frame, text="Bakeries", variable=self.bakery_enabled)
        bakery_check.grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(search_frame, textvariable=self.bakery_distance, width=8).grid(
            row=2, column=1, sticky=tk.W, padx=(5, 5), pady=2)
        ttk.Label(search_frame, text="km").grid(row=2, column=2, sticky=tk.W, pady=2)
        
        # Cafés/Restaurants
        cafe_check = ttk.Checkbutton(search_frame, text="Cafes/Restaurants", variable=self.cafe_enabled)
        cafe_check.grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(search_frame, textvariable=self.cafe_distance, width=8).grid(
            row=3, column=1, sticky=tk.W, padx=(5, 5), pady=2)
        ttk.Label(search_frame, text="km").grid(row=3, column=2, sticky=tk.W, pady=2)
        
        # Repair Shops
        repair_check = ttk.Checkbutton(search_frame, text="Repair Shops", variable=self.repair_enabled)
        repair_check.grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(search_frame, textvariable=self.repair_distance, width=8).grid(
            row=4, column=1, sticky=tk.W, padx=(5, 5), pady=2)
        ttk.Label(search_frame, text="km").grid(row=4, column=2, sticky=tk.W, pady=2)
        
        # Accommodation (Hotels/Camping/B&B)
        accommodation_check = ttk.Checkbutton(search_frame, text="Hotels/Camping/B&B", variable=self.accommodation_enabled)
        accommodation_check.grid(row=5, column=0, sticky=tk.W, pady=2)
        ttk.Entry(search_frame, textvariable=self.accommodation_distance, width=8).grid(
            row=5, column=1, sticky=tk.W, padx=(5, 5), pady=2)
        ttk.Label(search_frame, text="km").grid(row=5, column=2, sticky=tk.W, pady=2)
        
        # Speed Cameras (no distance input - only on track)
        speed_camera_check = ttk.Checkbutton(search_frame, text="Speed Cameras (on track only)", variable=self.speed_camera_enabled)
        speed_camera_check.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=2)
        
        # Search and Stop Buttons Frame
        buttons_frame = ttk.Frame(search_frame)
        buttons_frame.grid(row=7, column=0, columnspan=3, pady=(10, 5), sticky=(tk.W, tk.E))
        buttons_frame.columnconfigure(0, weight=1)
        
        # Search Button
        self.search_button = ttk.Button(buttons_frame, text="Search Selected Places", 
                                      command=self.start_checkbox_processing,
                                      style="Accent.TButton")
        self.search_button.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # Stop Button
        self.stop_button = ttk.Button(buttons_frame, text="Stop", 
                                    command=self.stop_processing,
                                    state='disabled')
        self.stop_button.grid(row=0, column=1, sticky=tk.E, padx=(0, 5))
        
        # Create GPX Button
        self.create_gpx_button = ttk.Button(buttons_frame, text="Create GPX", 
                                           command=self.create_gpx_file,
                                           state='disabled')
        self.create_gpx_button.grid(row=0, column=2, sticky=tk.E)
        
        # GPX Generation Options (moved here from below)
        gpx_options_frame = ttk.LabelFrame(left_panel, text="GPX Generation Options", padding="10")
        gpx_options_frame.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        self.gpx_generation_mode = tk.StringVar(value="waypoints_only")
        
        ttk.Radiobutton(gpx_options_frame, text="Waypoints only", 
                       variable=self.gpx_generation_mode, value="waypoints_only").grid(
                       row=0, column=0, sticky=tk.W, pady=2)
        
        ttk.Radiobutton(gpx_options_frame, text="Enhanced track with route deviations to waypoints", 
                       variable=self.gpx_generation_mode, value="enhanced_track").grid(
                       row=1, column=0, sticky=tk.W, pady=2)
        
        # Progress Bar
        self.progress = ttk.Progressbar(left_panel, mode='indeterminate')
        self.progress.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Status Label
        self.status_label = ttk.Label(left_panel, text="Ready to process GPX file")
        self.status_label.grid(row=10, column=0, columnspan=3, pady=5)
        
        # Places List
        places_frame = ttk.LabelFrame(left_panel, text="Places Found", padding="10")
        places_frame.grid(row=11, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        places_frame.columnconfigure(0, weight=1)
        places_frame.rowconfigure(0, weight=1)
        
        # Create Treeview for places list
        columns = ('Include', 'Type', 'Name', 'Distance')
        self.places_tree = ttk.Treeview(places_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        self.places_tree.heading('Include', text='Include')
        self.places_tree.heading('Type', text='Type')
        self.places_tree.heading('Name', text='Place Name')
        self.places_tree.heading('Distance', text='Distance (km)')
        
        # Set column widths
        self.places_tree.column('Include', width=60)
        self.places_tree.column('Type', width=80)
        self.places_tree.column('Name', width=150)
        self.places_tree.column('Distance', width=80)
        
        # Store place selection state and data
        self.place_selections = {}  # Will store {item_id: True/False}
        self.place_data = {}  # Will store {item_id: place_dict}
        self.highlighted_place = None  # Will store currently highlighted place data
        
        # Bind double-click to toggle checkbox and single-click to highlight on map
        self.places_tree.bind('<Double-1>', self.toggle_place_selection)
        self.places_tree.bind('<<TreeviewSelect>>', self.highlight_selected_place)
        
        # Add scrollbar for places list
        places_scrollbar = ttk.Scrollbar(places_frame, orient=tk.VERTICAL, command=self.places_tree.yview)
        self.places_tree.configure(yscrollcommand=places_scrollbar.set)
        
        # Grid the treeview and scrollbar
        self.places_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        places_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Right panel - Map and Output
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        
        # Map Frame
        map_frame = ttk.LabelFrame(right_panel, text="Route Map", padding="10")
        map_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        
        # Create matplotlib figure for the map preview
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, map_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add custom navigation toolbar
        self.toolbar = CustomNavigationToolbar(self.canvas, map_frame)
        self.toolbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Add map controls frame below toolbar
        map_controls_frame = ttk.Frame(map_frame)
        map_controls_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Add open in browser button
        self.open_map_btn = ttk.Button(map_controls_frame, text="Open Full Map in Browser", 
                                      command=self.open_map_in_browser, state='disabled')
        self.open_map_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Add refresh map button
        self.refresh_map_btn = ttk.Button(map_controls_frame, text="Refresh Map", 
                                        command=self.refresh_map, state='normal')
        self.refresh_map_btn.pack(side=tk.LEFT)
        
        # Text Output Area
        output_frame = ttk.LabelFrame(right_panel, text="Processing Output", padding="10")
        output_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        # Scrollbar for text area
        scrollbar = ttk.Scrollbar(output_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Text widget for output
        self.output_text = tk.Text(output_frame, height=11, width=80, yscrollcommand=scrollbar.set)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.output_text.yview)
        
        # Configure weights
        main_frame.rowconfigure(0, weight=1)
        left_panel.rowconfigure(7, weight=1)
        right_panel.rowconfigure(1, weight=1)
    
    def browse_gpx_file(self):
        filename = filedialog.askopenfilename(
            title="Select GPX File",
            filetypes=[("GPX files", "*.gpx"), ("All files", "*.*")]
        )
        if filename:
            self.gpx_file_path.set(filename)
            # Auto-set output directory to same location as GPX file
            output_dir = os.path.dirname(filename)
            self.output_dir.set(output_dir)
    
    def browse_output_dir(self):
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir.set(directory)
    
    def log_message(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def check_internet_connection(self):
        """Check if internet connection is available"""
        try:
            # Try to connect to a reliable service
            response = requests.get("https://www.google.com", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def check_api_failures(self):
        """Check if there were significant API failures and show warning"""
        total_failures = self.api_failures['overpass'] + self.api_failures['osrm']
        total_resolved = self.api_retries['overpass_resolved'] + self.api_retries['osrm_resolved']
        
        if total_failures > 0 or total_resolved > 0:
            self.log_message(f"\nAPI Status Summary:")
            self.log_message(f"  Overpass API failures: {self.api_failures['overpass']}")
            self.log_message(f"  OSRM API failures: {self.api_failures['osrm']}")
            self.log_message(f"  Total failures: {total_failures}")
            
            if total_resolved > 0:
                self.log_message(f"  Successful retries after failures: {total_resolved}")
                self.log_message(f"  -> {self.api_retries['overpass_resolved']} Overpass API retries succeeded")
                self.log_message(f"  -> {self.api_retries['osrm_resolved']} OSRM API retries succeeded")
            
            # Calculate net failures (failures that weren't resolved by retries)
            net_failures = total_failures - total_resolved
            if net_failures > 0:
                self.log_message(f"  Net unresolved failures: {net_failures}")
            elif total_resolved > 0:
                self.log_message(f"  All API failures were successfully resolved by retries!")
            
            # Show warning only for unresolved failures
            if net_failures >= 5 or self.api_failures['overpass'] - self.api_retries['overpass_resolved'] >= 3:
                warning_msg = f"Warning: {net_failures} unresolved API failures occurred during processing.\n\n"
                
                unresolved_overpass = self.api_failures['overpass'] - self.api_retries['overpass_resolved']
                unresolved_osrm = self.api_failures['osrm'] - self.api_retries['osrm_resolved']
                
                if unresolved_overpass > 0:
                    warning_msg += f"• {unresolved_overpass} unresolved Overpass API failures (place search)\n"
                if unresolved_osrm > 0:
                    warning_msg += f"• {unresolved_osrm} unresolved OSRM API failures (road routing)\n"
                
                warning_msg += ("\nThis may result in:\n"
                              "• Missing places in your results\n"
                              "• Missing road routes on the map\n\n"
                              "Consider:\n"
                              "• Checking your internet connection\n"
                              "• Trying again later if servers are overloaded\n"
                              "• Reducing search distances for large areas")
                
                self.root.after(0, lambda: messagebox.showwarning("API Failures Detected", warning_msg))
    
    def toggle_place_selection(self, event):
        """Toggle the checkbox state when double-clicking on a place in the list"""
        # Get the selected item
        selection = self.places_tree.selection()
        if not selection:
            return
            
        item_id = selection[0]
        
        # Toggle the selection state
        current_state = self.place_selections.get(item_id, True)
        new_state = not current_state
        self.place_selections[item_id] = new_state
        
        # Update the visual checkbox
        checkbox_symbol = "☑" if new_state else "☐"
        current_values = list(self.places_tree.item(item_id, 'values'))
        current_values[0] = checkbox_symbol
        self.places_tree.item(item_id, values=current_values)
        
        # Refresh the map to update colors
        self.update_matplotlib_map()
    
    def highlight_selected_place(self, event):
        """Highlight the selected place on the map"""
        # Get the selected item
        selection = self.places_tree.selection()
        if not selection:
            self.highlighted_place = None
            self.update_matplotlib_map()
            return
            
        item_id = selection[0]
        
        # Get the place data
        place_data = self.place_data.get(item_id)
        if place_data:
            self.highlighted_place = place_data
            self.update_matplotlib_map()  # Refresh map with highlighting
    
    def get_selected_places(self):
        """Get all places that are currently selected (checked) in the list"""
        selected_places = []
        for item_id in self.places_tree.get_children():
            if self.place_selections.get(item_id, True):  # Default to True if not found
                place_data = self.place_data.get(item_id)
                if place_data:  # Make sure we have place data
                    selected_places.append(place_data)
        return selected_places
    
    def get_garmin_symbol(self, place_type):
        """Get the appropriate Garmin symbol for a place type"""
        # Garmin symbol mapping for BaseCamp and GPS devices
        symbol_map = {
            'petrol': 'Gas Station',
            'supermarket': 'Shopping Center', 
            'bakery': 'Restaurant',
            'cafe': 'Restaurant',
            'repair': 'Car Repair',
            'accommodation': 'Lodging',
            'speed_camera': 'Danger'
        }
        return symbol_map.get(place_type, 'Flag, Blue')
    
    def create_waypoint_name(self, place, place_type, place_number):
        """Create a GPX-compatible waypoint name with place info"""
        # Get base name and clean it
        place_name = place.get('base_name', 'Unknown')
        distance = place['distance_km']
        
        # Create base label
        if place_type == 'petrol':
            prefix = f"Fuel {place_number}"
        elif place_type == 'supermarket':
            prefix = f"Market {place_number}"
        elif place_type == 'bakery':
            prefix = f"Bakery {place_number}"
        elif place_type == 'cafe':
            prefix = f"Cafe {place_number}"
        elif place_type == 'repair':
            prefix = f"Repair {place_number}"
        elif place_type == 'accommodation':
            prefix = f"Hotel {place_number}"
        elif place_type == 'speed_camera':
            prefix = f"SpeedCam {place_number}"
        else:
            prefix = f"Place {place_number}"
        
        # Create full name with distance and place name
        full_name = f"{prefix} ({distance:.1f}km) {place_name}"
        
        # Limit to 50 characters to ensure GPX compatibility
        if len(full_name) > 50:
            # Calculate available space for place name
            base_part = f"{prefix} ({distance:.1f}km) "
            available_space = 50 - len(base_part)
            
            if available_space > 0:
                # Truncate place name to fit
                truncated_name = place_name[:available_space-3] + "..."
                full_name = f"{prefix} ({distance:.1f}km) {truncated_name}"
            else:
                # Just use the prefix and distance if no space
                full_name = f"{prefix} ({distance:.1f}km)"
        
        return full_name
    
    def is_place_included(self, place):
        """Check if a place is currently included (checked) in the places list"""
        # Find the place in the tree by matching coordinates
        for item_id in self.places_tree.get_children():
            place_data = self.place_data.get(item_id)
            if (place_data and 
                place_data['lat'] == place['lat'] and 
                place_data['lon'] == place['lon']):
                return self.place_selections.get(item_id, True)
        return True  # Default to included if not found in tree
    
    def add_place_labels(self, places, place_type, color):
        """Add numbered labels to places on the map"""
        # Get all places of this type to maintain consistent numbering
        all_places_of_type = []
        all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.accommodation_data + self.speed_cameras_data
        
        for place in all_places:
            if place.get('place_type') == place_type:
                all_places_of_type.append(place)
        
        # Sort by route position to maintain consistent ordering (order of occurrence along route)
        all_places_of_type.sort(key=lambda x: x['route_position'])
        
        for place in places:
            lon, lat = place['lon'], place['lat']
            
            # Find the index of this place in the sorted list to get consistent numbering
            place_number = 1
            for i, p in enumerate(all_places_of_type):
                if p['lat'] == place['lat'] and p['lon'] == place['lon']:
                    place_number = i + 1
                    break
            
            # Create simple numbered label based on place type
            if place_type == 'petrol':
                label = f"Fuel {place_number} ({place['distance_km']:.1f}km)"
            elif place_type == 'supermarket':
                label = f"Market {place_number} ({place['distance_km']:.1f}km)"
            elif place_type == 'bakery':
                label = f"Bakery {place_number} ({place['distance_km']:.1f}km)"
            elif place_type == 'cafe':
                label = f"Cafe {place_number} ({place['distance_km']:.1f}km)"
            elif place_type == 'repair':
                label = f"Repair {place_number} ({place['distance_km']:.1f}km)"
            elif place_type == 'accommodation':
                label = f"Hotel {place_number} ({place['distance_km']:.1f}km)"
            elif place_type == 'speed_camera':
                label = f"SpeedCam {place_number} ({place['distance_km']:.1f}km)"
            else:
                label = f"Place {place_number} ({place['distance_km']:.1f}km)"
            
            # Set alpha based on whether it's grey (excluded) or not
            alpha = 0.2 if color == 'grey' else 0.3
            
            self.ax.annotate(label, (lon, lat), xytext=(5, 5), textcoords='offset points', 
                           fontsize=8, bbox=dict(boxstyle='round,pad=0.3', facecolor=color, alpha=alpha))
    
    def show_results_popup(self, total_places, total_distance, station_distances=None):
        """Show search results in a popup dialog"""
        result_msg = f"Search completed successfully!\n\n"
        result_msg += f"Places found: {total_places}\n"
        result_msg += f"Total route: {total_distance:.1f} km\n"
        
        if station_distances:
            max_distance = max(station_distances, key=lambda x: x['distance_km'])
            result_msg += f"Longest gap between petrol stations: {max_distance['distance_km']:.1f} km\n"
            result_msg += f"  From: {max_distance['from_station']}\n"
            result_msg += f"  To: {max_distance['to_station']}"
        
        messagebox.showinfo("Search Results", result_msg)
    
    def create_gpx_file(self):
        """Create GPX file with selected places based on chosen generation mode"""
        try:
            # Check if we have processed data
            if not hasattr(self, 'original_gpx') or not hasattr(self, 'current_output_path'):
                messagebox.showerror("Error", "Please search for places first before creating GPX file.")
                return
            
            # Get selected places
            selected_places = self.get_selected_places()
            
            if not selected_places:
                messagebox.showwarning("No Places Selected", 
                                     "No places are selected for GPX generation.\n\n"
                                     "Please double-click on places in the list to select them (☑).")
                return
            
            self.log_message(f"Creating GPX file with {len(selected_places)} selected places...")
            
            # Generate GPX based on selected mode
            generation_mode = self.gpx_generation_mode.get()
            if generation_mode == "waypoints_only":
                self.save_waypoints_only_gpx(selected_places, self.current_output_path)
                self.log_message("Created waypoints-only GPX file.")
            else:  # enhanced_track
                self.save_enhanced_track_gpx(self.original_gpx, selected_places, self.current_output_path)
                self.log_message("Created enhanced track GPX file with route deviations.")
            
            self.log_message(f"GPX file saved to: {self.current_output_path}")
            
            # Show success message
            messagebox.showinfo("GPX Created", 
                              f"GPX file created successfully!\n\n"
                              f"File: {self.current_output_path}\n"
                              f"Mode: {generation_mode.replace('_', ' ').title()}\n"
                              f"Places included: {len(selected_places)}")
            
        except Exception as e:
            error_msg = f"Error creating GPX file: {str(e)}"
            self.log_message(f"Error: {error_msg}")
            messagebox.showerror("GPX Creation Error", error_msg)

    def remove_duplicate_places(self, places_list):
        """Remove duplicate places based on name similarity and location proximity"""
        if not places_list:
            return places_list
        
        deduplicated = []
        
        for place in places_list:
            is_duplicate = False
            
            for existing_place in deduplicated:
                # Check if places are too similar (same type, similar name, close location)
                if (place['place_type'] == existing_place['place_type'] and
                    self.are_places_similar(place, existing_place)):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(place)
        
        return deduplicated
    
    def are_places_similar(self, place1, place2):
        """Check if two places are similar enough to be considered duplicates"""
        from geopy.distance import geodesic
        
        # Calculate distance between places
        distance_km = geodesic(
            (place1['lat'], place1['lon']),
            (place2['lat'], place2['lon'])
        ).km
        
        # If places are very close (within 50 meters), check name similarity
        if distance_km <= 0.05:  # 50 meters
            return self.are_names_similar(place1['base_name'], place2['base_name'])
        
        # If places are close (within 200 meters) and have very similar names
        if distance_km <= 0.2:  # 200 meters
            return self.are_names_very_similar(place1['base_name'], place2['base_name'])
        
        return False
    
    def are_names_similar(self, name1, name2):
        """Check if two place names are similar (for close locations)"""
        if not name1 or not name2:
            return False
        
        # Normalize names (lowercase, remove common words)
        def normalize_name(name):
            name = name.lower().strip()
            # Remove common words that don't help identify uniqueness
            common_words = ['the', 'de', 'la', 'le', 'du', 'des', 'station', 'service', 'gas', 'petrol']
            words = name.split()
            filtered_words = [w for w in words if w not in common_words]
            return ' '.join(filtered_words) if filtered_words else name
        
        norm1 = normalize_name(name1)
        norm2 = normalize_name(name2)
        
        # Exact match after normalization
        if norm1 == norm2:
            return True
        
        # Check if one name is contained in the other (for cases like "Shell" vs "Shell Station")
        if (norm1 in norm2 or norm2 in norm1) and min(len(norm1), len(norm2)) >= 4:
            return True
        
        return False
    
    def are_names_very_similar(self, name1, name2):
        """Check if two place names are very similar (for moderately close locations)"""
        if not name1 or not name2:
            return False
        
        # For moderately close places, require stricter name matching
        norm1 = name1.lower().strip()
        norm2 = name2.lower().strip()
        
        # Must be exact match or very close match
        if norm1 == norm2:
            return True
        
        # Check for exact brand match (like "Shell" == "Shell")
        if len(norm1) >= 4 and len(norm2) >= 4:
            return norm1 in norm2 or norm2 in norm1
        
        return False
    
    def get_road_route(self, start_lat, start_lon, end_lat, end_lon):
        """Get road-following route between two points using OSRM"""
        try:
            # OSRM API endpoint with full geometry
            url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
            self.log_message(f"Requesting road route from ({start_lat:.4f}, {start_lon:.4f}) to ({end_lat:.4f}, {end_lon:.4f})")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("routes") and len(data["routes"]) > 0:
                # Extract route coordinates from GeoJSON geometry
                route = data["routes"][0]
                if "geometry" in route and "coordinates" in route["geometry"]:
                    coordinates = route["geometry"]["coordinates"]
                    # Convert from GeoJSON [lon, lat] to [lon, lat] format for plotting
                    route_points = [(coord[0], coord[1]) for coord in coordinates]
                    return route_points
                else:
                    self.log_message(f"Warning: No geometry data in OSRM response")
                    return None
            else:
                self.log_message(f"Warning: No routes found in OSRM response")
                return None
        except requests.exceptions.ConnectionError:
            self.api_failures['osrm'] += 1
            self.log_message(f"Warning: Could not connect to OSRM routing service - check internet connection")
            return None
        except requests.exceptions.Timeout:
            self.api_failures['osrm'] += 1
            self.log_message(f"Warning: OSRM routing service timeout - server may be busy")
            return None
        except requests.exceptions.HTTPError as e:
            self.api_failures['osrm'] += 1
            self.log_message(f"Warning: OSRM routing service error (HTTP {e.response.status_code})")
            return None
        except Exception as e:
            self.api_failures['osrm'] += 1
            self.log_message(f"Warning: Could not get road route: {e}")
            return None
    
    def open_map_in_browser(self):
        """Open the generated map in the default web browser"""
        try:
            self.log_message("User requested browser map - creating folium map now...")
            
            # Create the folium map with current data
            self.create_folium_map_for_browser()
            
            # Now open the map in browser
            if self.map_html_path and os.path.exists(self.map_html_path):
                self.log_message(f"Opening map in browser: {self.map_html_path}")
                webbrowser.open(f'file://{self.map_html_path}')
            else:
                messagebox.showwarning("Warning", "Map file not found. Please process a GPX file first.")
                
        except Exception as e:
            self.log_message(f"Error creating/opening browser map: {str(e)}")
            messagebox.showerror("Error", f"Could not create browser map: {str(e)}")
    
    def refresh_map(self):
        """Refresh the map display"""
        if self.route_points:
            self.update_map()
    
    def create_folium_map(self):
        """Create a folium map with the route and stations"""
        if not self.route_points:
            return None
        
        # Only log essential info
        all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.accommodation_data + self.speed_cameras_data
        if all_places:
            self.log_message(f"Creating map with {len(all_places)} places ({len(self.stations_data)} fuel, {len(self.supermarkets_data)} markets, {len(self.bakeries_data)} bakeries, {len(self.cafes_data)} cafes, {len(self.repair_data)} repair, {len(self.accommodation_data)} hotels, {len(self.speed_cameras_data)} cameras)")
        
        # Calculate center and bounds
        lats = [point[1] for point in self.route_points]
        lons = [point[0] for point in self.route_points]
        
        # Add all place coordinates if available
        all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.accommodation_data + self.speed_cameras_data
        if all_places:
            lats.extend([place['lat'] for place in all_places])
            lons.extend([place['lon'] for place in all_places])
        
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        
        # Create the map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=10,
            tiles='OpenStreetMap'
        )
        
        # Add route line
        route_coords = [[point[1], point[0]] for point in self.route_points]  # folium expects [lat, lon]
        folium.PolyLine(
            route_coords,
            color='blue',
            weight=3,
            opacity=0.8,
            popup='Main Route'
        ).add_to(m)
        
        # Add all places and road routes
        all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.accommodation_data + self.speed_cameras_data
        if all_places:
            added_markers = 0
            
            # Group places by type for numbering
            place_counts = {'petrol': 0, 'supermarket': 0, 'bakery': 0, 'cafe': 0, 'repair': 0, 'accommodation': 0, 'speed_camera': 0}
            
            for i, place in enumerate(all_places):
                # Verify coordinate data
                if not isinstance(place['lat'], (int, float)) or not isinstance(place['lon'], (int, float)):
                    self.log_message(f"WARNING: Invalid coordinates for {place['name']}")
                    continue
                
                # Get place type configuration
                config = place.get('config', {})
                color = config.get('color', 'gray')
                place_type = place.get('place_type', 'unknown')
                
                # Increment counter for this place type
                place_counts[place_type] = place_counts.get(place_type, 0) + 1
                
                # Create numbered label
                if place_type == 'petrol':
                    display_label = f"Fuel {place_counts[place_type]}"
                elif place_type == 'supermarket':
                    display_label = f"Market {place_counts[place_type]}"
                elif place_type == 'bakery':
                    display_label = f"Bakery {place_counts[place_type]}"
                elif place_type == 'cafe':
                    display_label = f"Cafe {place_counts[place_type]}"
                elif place_type == 'repair':
                    display_label = f"Repair {place_counts[place_type]}"
                elif place_type == 'accommodation':
                    display_label = f"Hotel {place_counts[place_type]}"
                elif place_type == 'speed_camera':
                    display_label = f"SpeedCam {place_counts[place_type]}"
                else:
                    display_label = f"Place {place_counts.get(place_type, i+1)}"
                
                # Add place marker
                try:
                    lat, lon = float(place['lat']), float(place['lon'])
                    
                    # Add marker and circle with type-specific colors
                    folium.Marker(
                        location=[lat, lon],
                        popup=f"<b>{display_label}</b><br>{place['base_name']}<br>Distance: {place['distance_km']} km",
                        tooltip=place['base_name'],  # Show actual place name on hover
                        icon=folium.Icon(color='white', icon_color=color, icon='info-sign')
                    ).add_to(m)
                    
                    folium.Circle(
                        location=[lat, lon],
                        radius=150,
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.3,
                        weight=2
                    ).add_to(m)
                    
                    added_markers += 1
                    
                except Exception as e:
                    self.log_message(f"ERROR adding marker for {display_label}: {e}")
                
                # Add road route to place if available
                place_key = (place['lat'], place['lon'])
                if place_key in self.road_routes:
                    road_route = self.road_routes[place_key]
                    if road_route and len(road_route) > 1:
                        # Convert coordinates to folium format [lat, lon]
                        road_coords = [[point[1], point[0]] for point in road_route]
                        
                        # Add road route line
                        folium.PolyLine(
                            road_coords,
                            color=color,
                            weight=2,
                            opacity=0.7,
                            popup=f'Road to {place["base_name"]}'
                        ).add_to(m)
                        
                        # Add arrow direction
                        if len(road_coords) >= 2:
                            folium.plugins.PolyLineTextPath(
                                polyline=folium.PolyLine(road_coords, color=color, weight=2),
                                text='→',
                                repeat=False,
                                offset=8
                            ).add_to(m)
        
        # Fit map to show all data with padding
        lat_padding = (max(lats) - min(lats)) * 0.1
        lon_padding = (max(lons) - min(lons)) * 0.1
        
        expanded_bounds = [
            [min(lats) - lat_padding, min(lons) - lon_padding],
            [max(lats) + lat_padding, max(lons) + lon_padding]
        ]
        
        m.fit_bounds(expanded_bounds)
        return m
    
    def update_map(self):
        """Update the map display with current data"""
        if not self.route_points:
            return
        
        try:
            # Update matplotlib map in GUI only
            self.update_matplotlib_map()
            
            # Don't create folium map here - wait for user to request it
            # This ensures we have complete data when the browser map is created
            
        except Exception as e:
            self.log_message(f"Error updating map: {str(e)}")
    
    def update_matplotlib_map(self):
        """Update the matplotlib map in the GUI"""
        if not hasattr(self, 'ax') or not self.route_points:
            return
        
        # Clear the current plot
        self.ax.clear()
        
        if self.route_points:
            # Plot route
            lons, lats = zip(*self.route_points)
            self.ax.plot(lons, lats, 'b-', linewidth=2, label='Route', alpha=0.7)
            
            # Plot all place types with different colors
            all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.accommodation_data + self.speed_cameras_data
            
            if all_places:
                # Group places by type and selection status for plotting
                place_types_included = {}
                place_types_excluded = {}
                
                for place in all_places:
                    place_type = place.get('place_type', 'unknown')
                    
                    # Check if this place is selected (included)
                    place_is_included = self.is_place_included(place)
                    
                    if place_is_included:
                        if place_type not in place_types_included:
                            place_types_included[place_type] = []
                        place_types_included[place_type].append(place)
                    else:
                        if place_type not in place_types_excluded:
                            place_types_excluded[place_type] = []
                        place_types_excluded[place_type].append(place)
                
                # Plot included places with their original colors
                for place_type, places in place_types_included.items():
                    config = self.get_place_type_config(place_type)
                    color = config['color']
                    name = config['name']
                    
                    place_lons = [place['lon'] for place in places]
                    place_lats = [place['lat'] for place in places]
                    
                    # Plot places with type-specific color
                    self.ax.scatter(place_lons, place_lats, c=color, s=50, alpha=0.8, label=f'{name}s ({len(places)})')
                    
                    # Add numbered labels with distance
                    self.add_place_labels(places, place_type, color)
                
                # Plot excluded places in grey
                for place_type, places in place_types_excluded.items():
                    name = self.get_place_type_config(place_type)['name']
                    
                    place_lons = [place['lon'] for place in places]
                    place_lats = [place['lat'] for place in places]
                    
                    # Plot excluded places in grey
                    self.ax.scatter(place_lons, place_lats, c='grey', s=50, alpha=0.5, label=f'{name}s - Excluded ({len(places)})')
                    
                    # Add numbered labels with grey background
                    self.add_place_labels(places, place_type, 'grey')
                
                # Draw road-following paths from route to all places
                route_line = LineString(self.route_points)
                road_routes_drawn = False
                
                for place in all_places:
                    # Check if we already have a road route for this place
                    place_key = (place['lat'], place['lon'])
                    if place_key in self.road_routes:
                        road_route = self.road_routes[place_key]
                        if road_route and len(road_route) > 1:
                            # Plot the actual road route
                            road_lons, road_lats = zip(*road_route)
                            label = 'Road Routes' if not road_routes_drawn else ""
                            self.ax.plot(road_lons, road_lats, 'gray', alpha=0.4, linewidth=1, label=label)
                            road_routes_drawn = True
                            
                            # Add a small arrow at the end to show direction
                            if len(road_route) >= 2:
                                end_lon, end_lat = road_route[-1]
                                prev_lon, prev_lat = road_route[-2]
                                # Calculate arrow direction
                                dx = end_lon - prev_lon
                                dy = end_lat - prev_lat
                                # Normalize and scale
                                length = (dx**2 + dy**2)**0.5
                                if length > 0:
                                    dx = dx / length * 0.001
                                    dy = dy / length * 0.001
                                    self.ax.arrow(end_lon - dx, end_lat - dy, dx, dy, 
                                                head_width=0.0005, head_length=0.001, 
                                                fc='gray', ec='gray', alpha=0.6)
                    else:
                        # Only show fallback line if place is far enough from track
                        if place['distance_km'] >= 0.2:
                            # Fallback to straight line if no road route available
                            place_point = Point(place['lon'], place['lat'])
                            nearest_point = route_line.interpolate(route_line.project(place_point))
                            self.ax.plot([place['lon'], nearest_point.x], [place['lat'], nearest_point.y], 
                                       'gray', alpha=0.3, linewidth=1, linestyle='--')
        
        # Set equal aspect ratio to prevent stretching
        self.ax.set_aspect('equal', adjustable='box')
        
        # Improved zooming to show all places with equal scaling
        all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.accommodation_data + self.speed_cameras_data
        
        if self.route_points or all_places:
            all_lons = []
            all_lats = []
            
            # Add route points
            if self.route_points:
                route_lons, route_lats = zip(*self.route_points)
                all_lons.extend(route_lons)
                all_lats.extend(route_lats)
            
            # Add all place points
            if all_places:
                place_lons = [place['lon'] for place in all_places]
                place_lats = [place['lat'] for place in all_places]
                all_lons.extend(place_lons)
                all_lats.extend(place_lats)
            
            if all_lons and all_lats:
                # Calculate bounds with extra padding
                min_lon, max_lon = min(all_lons), max(all_lons)
                min_lat, max_lat = min(all_lats), max(all_lats)
                
                # Calculate the range for each axis
                lon_range = max_lon - min_lon
                lat_range = max_lat - min_lat
                
                # Use the larger range to ensure both axes have the same scale
                max_range = max(lon_range, lat_range)
                
                # Add padding (15% of the range, minimum 0.02 degrees)
                padding = max(max_range * 0.15, 0.02)
                
                # Set bounds ensuring equal scaling
                self.ax.set_xlim(min_lon - padding, min_lon + max_range + padding)
                self.ax.set_ylim(min_lat - padding, min_lat + max_range + padding)
        
        self.ax.set_xlabel('Longitude')
        self.ax.set_ylabel('Latitude')
        self.ax.set_title('Route with Places (Preview)')
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        # Highlight selected place if any
        if self.highlighted_place:
            place = self.highlighted_place
            # Add a bright highlight circle around the selected place
            self.ax.scatter([place['lon']], [place['lat']], c='yellow', s=200, alpha=0.7, 
                          edgecolor='red', linewidth=3, marker='o', label='Selected Place')
            
            # Add a bright text label
            self.ax.annotate(f"SELECTED: {place['base_name']}", 
                           (place['lon'], place['lat']), 
                           xytext=(10, 10), textcoords='offset points', 
                           fontsize=10, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8, edgecolor='red'),
                           arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        # Refresh the canvas
        self.canvas.draw()
    
    def create_folium_map_for_browser(self):
        """Create a folium map for browser viewing"""
        if not self.route_points:
            return
        
        try:
            self.log_message("Creating browser map...")
            
            # Create the folium map
            m = self.create_folium_map()
            if m is None:
                self.log_message("Failed to create map")
                return
            
            # Save map to temporary HTML file
            if hasattr(self, 'map_html_path') and self.map_html_path and os.path.exists(self.map_html_path):
                os.remove(self.map_html_path)
            
            # Create temporary file
            temp_dir = tempfile.gettempdir()
            self.map_html_path = os.path.join(temp_dir, f"gpx_petrol_map_{int(time.time())}.html")
            
            # Save the map
            m.save(self.map_html_path)
            self.log_message(f"Folium map saved to: {self.map_html_path}")
            
            # Create backup and test maps (silent)
            try:
                backup_map_path = os.path.join(tempfile.gettempdir(), f"backup_map_{int(time.time())}.html")
                center_lat = sum([p[1] for p in self.route_points]) / len(self.route_points)
                center_lon = sum([p[0] for p in self.route_points]) / len(self.route_points)
                bounds = [[min([p[1] for p in self.route_points]), min([p[0] for p in self.route_points])],
                         [max([p[1] for p in self.route_points]), max([p[0] for p in self.route_points])]]
                
                backup_m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
                route_coords = [[point[1], point[0]] for point in self.route_points]
                folium.PolyLine(route_coords, color='blue', weight=3, opacity=0.8).add_to(backup_m)
                
                backup_all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.speed_cameras_data
                
                # Limit backup map for performance
                if len(backup_all_places) > 30:
                    backup_all_places = sorted(backup_all_places, key=lambda x: x['distance_km'])[:30]
                
                for place in backup_all_places:
                    place_lat = float(place['lat'])
                    place_lon = float(place['lon'])
                    config = place.get('config', {})
                    color = config.get('color', 'red')
                    folium.Marker(
                        location=[place_lat, place_lon],
                        popup=f"{place['name']}<br>Distance: {place['distance_km']} km",
                        tooltip=place['base_name']  # Show actual place name on hover
                    ).add_to(backup_m)
                    folium.Circle(
                        location=[place_lat, place_lon],
                        radius=200,
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.4
                    ).add_to(backup_m)
                
                backup_m.fit_bounds(bounds)
                backup_m.save(backup_map_path)
                
            except Exception as e:
                pass  # Silent backup creation
            
            # Create a SIMPLE HTML map that will definitely work
            manual_map_path = os.path.join(tempfile.gettempdir(), f"simple_map_{int(time.time())}.html")
            try:
                # Calculate center and bounds
                all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.accommodation_data + self.speed_cameras_data
                
                if not self.route_points and not all_places:
                    self.log_message("No route or places to display")
                    return
                
                # For large datasets, optimize by limiting road routes and using clustering
                total_places = len(all_places)
                use_clustering = total_places > 20
                max_road_routes = min(15, total_places)  # Limit road routes for performance
                
                if use_clustering:
                    self.log_message(f"Large dataset ({total_places} places) - enabling optimizations...")
                
                # Get center point
                if self.route_points:
                    center_lat = sum([p[1] for p in self.route_points]) / len(self.route_points)
                    center_lon = sum([p[0] for p in self.route_points]) / len(self.route_points)
                elif all_places:
                    center_lat = sum([p['lat'] for p in all_places]) / len(all_places)
                    center_lon = sum([p['lon'] for p in all_places]) / len(all_places)
                else:
                    center_lat, center_lon = 51.5, 4.0  # Default center
                
                # Create a very simple HTML file
                html_lines = [
                    '<!DOCTYPE html>',
                    '<html>',
                    '<head>',
                    '    <title>GPX Places Map</title>',
                    '    <meta charset="utf-8" />',
                    '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
                    '    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />',
                    '    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>',
                    '    <style>',
                    '        #map { height: 100vh; width: 100%; }',
                    '        body { margin: 0; padding: 0; }',
                    '    </style>',
                    '</head>',
                    '<body>',
                    '    <div id="map"></div>',
                    '    <script>',
                    f'        var map = L.map("map").setView([{center_lat}, {center_lon}], 10);',
                    '',
                    '        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {',
                    '            attribution: "© OpenStreetMap contributors"',
                    '        }).addTo(map);',
                    ''
                ]
                
                # Add route if available
                if self.route_points:
                    html_lines.append('        var routeCoords = [')
                    for point in self.route_points:
                        html_lines.append(f'            [{point[1]}, {point[0]}],')
                    html_lines.append('        ];')
                    html_lines.append('        L.polyline(routeCoords, {color: "blue", weight: 3, opacity: 0.8}).addTo(map);')
                    html_lines.append('')
                
                # Add places with performance optimizations for large datasets
                if all_places:
                    place_counts = {'petrol': 0, 'supermarket': 0, 'bakery': 0, 'cafe': 0, 'repair': 0, 'accommodation': 0, 'speed_camera': 0}
                    
                    # Performance optimization: limit places for very large datasets
                    places_to_show = all_places
                    if len(all_places) > 50:
                        self.log_message(f"Large dataset ({len(all_places)} places) - limiting to 50 closest places to track for map performance")
                        places_to_show = sorted(all_places, key=lambda x: x['distance_km'])[:50]
                    
                    # Add progress indicator for large datasets
                    if len(places_to_show) > 30:
                        html_lines.append('        // Add progress indicator')
                        html_lines.append('        var progressDiv = L.DomUtil.create("div", "progress-indicator");')
                        html_lines.append('        progressDiv.innerHTML = "Loading places...";')
                        html_lines.append('        progressDiv.style.cssText = "position: fixed; top: 10px; right: 10px; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.3); z-index: 1000;";')
                        html_lines.append('        document.body.appendChild(progressDiv);')
                        html_lines.append('')
                    
                    # Add places in batches to avoid browser timeout
                    batch_size = min(8, max(3, len(places_to_show) // 10))  # Adaptive batch size
                    total_batches = (len(places_to_show) + batch_size - 1) // batch_size
                    
                    for batch_idx, batch_start in enumerate(range(0, len(places_to_show), batch_size)):
                        batch = places_to_show[batch_start:batch_start + batch_size]
                        delay = batch_idx * 200 if len(places_to_show) > 30 else batch_idx * 100  # Longer delays for large datasets
                        
                        if batch_idx > 0:
                            html_lines.append(f'        // Batch {batch_idx + 1}/{total_batches}')
                            html_lines.append('        setTimeout(function() {')
                        
                        # Update progress for large datasets
                        if len(places_to_show) > 30:
                            progress_percent = int((batch_idx + 1) * 100 / total_batches)
                            html_lines.append(f'            if (document.querySelector(".progress-indicator")) {{')
                            html_lines.append(f'                document.querySelector(".progress-indicator").innerHTML = "Loading places... {progress_percent}%";')
                            html_lines.append(f'            }}')
                        
                        for place in batch:
                            place_type = place.get('place_type', 'unknown')
                            place_counts[place_type] = place_counts.get(place_type, 0) + 1
                            
                            # Create simple labels
                            if place_type == 'petrol':
                                label = f"Fuel {place_counts[place_type]}"
                            elif place_type == 'supermarket':
                                label = f"Market {place_counts[place_type]}"
                            elif place_type == 'bakery':
                                label = f"Bakery {place_counts[place_type]}"
                            elif place_type == 'cafe':
                                label = f"Cafe {place_counts[place_type]}"
                            elif place_type == 'repair':
                                label = f"Repair {place_counts[place_type]}"
                            elif place_type == 'accommodation':
                                label = f"Hotel {place_counts[place_type]}"
                            elif place_type == 'speed_camera':
                                label = f"SpeedCam {place_counts[place_type]}"
                            else:
                                label = f"Place {place_counts.get(place_type, 1)}"
                            
                            config = place.get('config', {})
                            color = config.get('color', 'red')
                            lat = float(place['lat'])
                            lon = float(place['lon'])
                            name = place['base_name'].replace("'", "\\'")  # Escape quotes
                            distance = place['distance_km']
                            
                            # Add marker (simplified for performance)
                            html_lines.append(f'            L.marker([{lat}, {lon}]).addTo(map)')
                            html_lines.append(f'                .bindPopup("<b>{label}</b><br>{name}<br>Distance: {distance} km")')
                            html_lines.append(f'                .bindTooltip("{name}");')  # Show actual place name on hover
                            
                            # Add circles only for smaller datasets to improve performance
                            if len(places_to_show) <= 50:
                                html_lines.append(f'            L.circle([{lat}, {lon}], {{')
                                html_lines.append(f'                color: "{color}",')
                                html_lines.append(f'                fillColor: "{color}",')
                                html_lines.append('                fillOpacity: 0.3,')
                                html_lines.append('                radius: 150')
                                html_lines.append('            }).addTo(map);')
                        
                        # Close setTimeout for batched processing
                        if batch_idx > 0:
                            html_lines.append(f'        }}, {delay});')
                        
                        html_lines.append('')
                    
                    # Remove progress indicator when done (for large datasets)
                    if len(places_to_show) > 30:
                        final_delay = total_batches * 200 + 500
                        html_lines.append(f'        setTimeout(function() {{')
                        html_lines.append(f'            var progressDiv = document.querySelector(".progress-indicator");')
                        html_lines.append(f'            if (progressDiv) progressDiv.remove();')
                        html_lines.append(f'        }}, {final_delay});')
                
                # Close the HTML with better performance and error handling
                places_count = len(places_to_show) if all_places else 0
                final_timeout = 1000 if len(places_to_show) > 50 else 500  # Longer timeout for large datasets
                
                html_lines.extend([
                    '        // Auto-fit map and handle large datasets',
                    '        setTimeout(function() {',
                    '            try {',
                    '                map.invalidateSize();',
                    f'                console.log("Map loaded with {places_count} places");',
                    '            } catch(e) {',
                    '                console.error("Map loading error:", e);',
                    '            }',
                    f'        }}, {final_timeout});',
                    '    </script>',
                    '</body>',
                    '</html>'
                ])
                
                # Write the file
                with open(manual_map_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(html_lines))
                
                # Use manual map instead of folium map
                self.map_html_path = manual_map_path
                total_places = len(all_places)
                
                # Single comprehensive log message for browser map completion
                if all_places and len(all_places) > 50:
                    self.log_message(f"Browser map ready with {places_count} places (limited from {len(all_places)} for performance) - {len(self.stations_data)} fuel, {len(self.supermarkets_data)} markets, {len(self.bakeries_data)} bakeries, {len(self.cafes_data)} cafes, {len(self.repair_data)} repair, {len(self.accommodation_data)} hotels, {len(self.speed_cameras_data)} cameras")
                else:
                    self.log_message(f"Browser map ready with {total_places} places ({len(self.stations_data)} fuel, {len(self.supermarkets_data)} markets, {len(self.bakeries_data)} bakeries, {len(self.cafes_data)} cafes, {len(self.repair_data)} repair, {len(self.accommodation_data)} hotels, {len(self.speed_cameras_data)} cameras)")
                
            except Exception as e:
                self.log_message(f"Error creating map: {e}")
                # Keep original path as fallback
            
            # Simple verification (minimal output)
            try:
                with open(self.map_html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                    marker_count = html_content.count('L.marker(')
                    total_places = len(self.stations_data) + len(self.supermarkets_data) + len(self.bakeries_data) + len(self.cafes_data)
                    if marker_count != total_places:
                        self.log_message(f"Map verification: Expected {total_places} markers, found {marker_count}")
                            
            except Exception as e:
                pass  # Silent verification
            
            # Enable map control buttons
            self.open_map_btn.config(state='normal')
            
        except Exception as e:
            self.log_message(f"Error creating browser map: {str(e)}")
            self.open_map_btn.config(state='disabled')
    
    def get_place_type_config(self, place_type):
        """Get configuration for a specific place type"""
        configs = {
            'petrol': {
                'distance': self.petrol_distance,
                'query': 'node["amenity"="fuel"]',
                'name': 'Petrol Station',
                'emoji': '⛽',
                'color': 'red'
            },
            'supermarket': {
                'distance': self.supermarket_distance,
                'query': 'node["shop"="supermarket"]',
                'name': 'Supermarket',
                'emoji': '🛒',
                'color': 'blue'
            },
            'bakery': {
                'distance': self.bakery_distance,
                'query': 'node["shop"="bakery"]',
                'name': 'Bakery',
                'emoji': '🥖',
                'color': 'orange'
            },
            'cafe': {
                'distance': self.cafe_distance,
                'query': 'node["amenity"~"^(cafe|restaurant|fast_food)$"]',
                'name': 'Café/Restaurant',
                'emoji': '☕',
                'color': 'green'
            },
            'repair': {
                'distance': self.repair_distance,
                'query': 'node["shop"~"^(car_repair|motorcycle)$"]',
                'name': 'Repair Shop',
                'emoji': '🔧',
                'color': 'purple'
            },
            'accommodation': {
                'distance': self.accommodation_distance,
                'query': 'node["tourism"~"^(hotel|motel|guest_house|hostel|camp_site|caravan_site)$"]',
                'name': 'Accommodation',
                'emoji': '🏨',
                'color': 'brown'
            },
            'speed_camera': {
                'distance': tk.StringVar(value="0.05"),  # Fixed small distance for on-track detection
                'query': 'node["highway"="speed_camera"]',
                'name': 'Speed Camera',
                'emoji': '📷',
                'color': 'darkred',
                'on_route_only': True  # Special flag for speed cameras
            }
        }
        return configs.get(place_type, configs['petrol'])
    
    def start_checkbox_processing(self):
        """Start processing based on selected checkboxes"""
        # Determine which place types are selected
        selected_types = []
        if self.petrol_enabled.get():
            selected_types.append('petrol')
        if self.supermarket_enabled.get():
            selected_types.append('supermarket')
        if self.bakery_enabled.get():
            selected_types.append('bakery')
        if self.cafe_enabled.get():
            selected_types.append('cafe')
        if self.repair_enabled.get():
            selected_types.append('repair')
        if self.accommodation_enabled.get():
            selected_types.append('accommodation')
        if self.speed_camera_enabled.get():
            selected_types.append('speed_camera')
        
        if not selected_types:
            messagebox.showwarning("Warning", "Please select at least one place type to search for.")
            return
        
        # Call the existing start_processing method with selected types
        self.start_processing(selected_types)
    
    def stop_processing(self):
        """Stop the current processing"""
        self.processing_cancelled = True
        self.log_message("Processing cancelled by user...")
        self.status_label.config(text="Processing cancelled")
    
    def start_processing(self, place_types=['petrol']):
        # Validate inputs
        if not self.gpx_file_path.get():
            messagebox.showerror("Error", "Please select a GPX file")
            return
        
        # Validate distances for the selected place types (skip speed cameras as they have fixed distance)
        for place_type in place_types:
            if place_type == 'speed_camera':
                continue  # Skip validation for speed cameras as they use fixed distance
                
            distance_var = getattr(self, f"{place_type}_distance")
            if not distance_var.get():
                messagebox.showerror("Error", f"Please enter a distance for {place_type}")
                return
            
            try:
                distance = float(distance_var.get())
                if distance <= 0:
                    messagebox.showerror("Error", f"Distance for {place_type} must be greater than 0")
                    return
            except ValueError:
                messagebox.showerror("Error", f"Distance for {place_type} must be a valid number")
                return
        
        if not self.output_dir.get():
            messagebox.showerror("Error", "Please select an output directory")
            return
        
        # Store the search types for this session
        self.last_search_types = place_types
        
        # Check internet connection before starting
        if not self.check_internet_connection():
            messagebox.showerror("Connection Error", 
                               "No internet connection detected.\n\n"
                               "This application requires internet access to:\n"
                               "• Query OpenStreetMap data (Overpass API)\n"
                               "• Get road routing information (OSRM)\n\n"
                               "Please check your internet connection and try again.")
            return
        
        self.processing_started()
        
        # Clear previous road routes and reset API failure tracking
        self.road_routes = {}
        self.api_failures = {'overpass': 0, 'osrm': 0, 'total_attempts': 0}
        self.api_retries = {'overpass_resolved': 0, 'osrm_resolved': 0}
        self.logged_errors = set()  # Reset logged errors for new processing
        self.processing_cancelled = False
        
        # Start processing in separate thread
        thread = threading.Thread(target=self.process_gpx, args=(place_types,))
        thread.daemon = True
        thread.start()
    
    def processing_started(self):
        """Called when processing starts"""
        # Disable search button and enable stop button, disable create gpx
        self.search_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.create_gpx_button.config(state='disabled')
        
        self.progress.start()
        self.status_label.config(text="Processing GPX file...")
        
        # Disable browser map button during processing
        self.open_map_btn.config(state='disabled')
        
        # Clear previous results
        self.stations_data = []
        self.supermarkets_data = []
        self.bakeries_data = []
        self.cafes_data = []
        self.repair_data = []
        self.accommodation_data = []
        self.speed_cameras_data = []
        # Clear highlighting and removed GUI labels - will show results in popup
        self.highlighted_place = None
        
        # Clear the places treeview
        for item in self.places_tree.get_children():
            self.places_tree.delete(item)
        
        # Remove distance info label if it exists
        if hasattr(self, 'distance_info_label'):
            self.distance_info_label.destroy()
            delattr(self, 'distance_info_label')
    
    def process_gpx(self, place_types=['petrol']):
        try:
            self.log_message(f"Starting GPX processing for: {', '.join(place_types)}...")
            
            # Settings
            gpx_file = self.gpx_file_path.get()
            output_dir = self.output_dir.get()
            chunk_km = 50
            overpass_url = "https://overpass-api.de/api/interpreter"
            
            # Get original filename for output
            original_filename = os.path.splitext(os.path.basename(gpx_file))[0]
            place_type_str = "-".join(place_types)
            output_gpx = os.path.join(output_dir, f"{original_filename}-{place_type_str}.gpx")
            
            self.log_message(f"Reading GPX file: {gpx_file}")
            
            # Read GPX file
            with open(gpx_file, 'r', encoding='utf-8') as f:
                gpx = gpxpy.parse(f)
            
            points = []
            
            if gpx.tracks:
                self.log_message(f"GPX contains {len(gpx.tracks)} track(s).")
                for track_idx, track in enumerate(gpx.tracks, 1):
                    self.log_message(f"  Processing track {track_idx}/{len(gpx.tracks)}: {track.name or 'Unnamed Track'}")
                    for segment in track.segments:
                        for point in segment.points:
                            points.append((point.longitude, point.latitude))
            
            # If no tracks, try routes
            if not points and gpx.routes:
                self.log_message(f"GPX contains {len(gpx.routes)} route(s). Using routes instead.")
                for route in gpx.routes:
                    for point in route.points:
                        points.append((point.longitude, point.latitude))
            
            if not points:
                raise ValueError("No track or route points found in GPX file.")
            
            # Store route points for map
            self.route_points = points
            
            # Calculate total route distance
            total_distance = 0
            for i in range(1, len(points)):
                pt1 = (points[i-1][1], points[i-1][0])  # lat, lon for geopy
                pt2 = (points[i][1], points[i][0])
                total_distance += geodesic(pt1, pt2).km
            
            self.log_message(f"Total route distance: {total_distance:.2f} km")
            
            # Initialize map with route only (no stations yet)
            self.root.after(0, self.update_map)
            
            route_line = LineString(points)
            
            # Split route into chunks
            def split_line_by_distance(line, max_km):
                segments = []
                coords = list(line.coords)
                current_chunk = [coords[0]]
                dist_accum = 0
                
                for i in range(1, len(coords)):
                    pt1 = (coords[i-1][1], coords[i-1][0])
                    pt2 = (coords[i][1], coords[i][0])
                    seg_dist = geodesic(pt1, pt2).km
                    
                    if dist_accum + seg_dist > max_km:
                        segments.append(LineString(current_chunk))
                        current_chunk = [coords[i-1], coords[i]]
                        dist_accum = seg_dist
                    else:
                        current_chunk.append(coords[i])
                        dist_accum += seg_dist
                
                if len(current_chunk) > 1:
                    segments.append(LineString(current_chunk))
                
                return segments
            
            route_segments = split_line_by_distance(route_line, chunk_km)
            self.log_message(f"Processing route in {len(route_segments)} segments...")
            
            # Initialize data containers for all place types
            all_places_raw = {}
            
            # Process each place type
            for place_type in place_types:
                if self.processing_cancelled:
                    self.log_message("Processing cancelled by user")
                    return
                    
                config = self.get_place_type_config(place_type)
                buffer_km = float(config['distance'].get())
                buffer_deg = buffer_km / 111.0  # approx degrees
                
                self.log_message(f"Searching for {config['name']}s within {buffer_km}km...")
                
                # Query Overpass for each segment for this place type
                places_raw = {}
                
                # Use ThreadPoolExecutor for parallel Overpass queries (reduced workers to be gentler on API)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_to_segment = {
                        executor.submit(self.query_overpass_for_segment, seg, buffer_deg, overpass_url, config['query'], place_type): idx 
                        for idx, seg in enumerate(route_segments)
                    }
                    
                    completed = 0
                    for future in as_completed(future_to_segment):
                        if self.processing_cancelled:
                            self.log_message("Processing cancelled by user")
                            return
                            
                        idx = future_to_segment[future]
                        completed += 1
                        
                        try:
                            data = future.result()
                        except Exception as e:
                            self.log_message(f"Error querying Overpass for {place_type} segment {idx+1}: {e}")
                            continue
                        
                        # Collect places without calculating distances yet
                        new_count = 0
                        for element in data.get("elements", []):
                            lat = element["lat"]
                            lon = element["lon"]
                            pt = Point(lon, lat)
                            
                            # Special handling for speed cameras - only find them ON the route
                            if config.get('on_route_only', False):
                                # For speed cameras, check if they're very close to the actual route line
                                distance_to_route = route_segments[idx].distance(pt)
                                # Convert to km (roughly)
                                distance_km = distance_to_route * 111.0
                                # Only include if within the specified distance (usually very small for speed cameras)
                                if distance_km <= buffer_km:
                                    key = (lat, lon, place_type)
                                    if key not in places_raw:
                                        base_name = element.get("tags", {}).get("name", f"Unnamed {config['name']}")
                                        places_raw[key] = {
                                            "base_name": base_name,
                                            "lat": lat,
                                            "lon": lon,
                                            "place_type": place_type,
                                            "config": config
                                        }
                                        new_count += 1
                            else:
                                # Regular buffer check for other place types
                                segment_buffer = route_segments[idx].buffer(buffer_deg)
                                if segment_buffer.contains(pt):
                                    key = (lat, lon, place_type)  # Include place_type in key
                                    if key not in places_raw:
                                        base_name = element.get("tags", {}).get("name", f"Unnamed {config['name']}")
                                        places_raw[key] = {
                                            "base_name": base_name,
                                            "lat": lat,
                                            "lon": lon,
                                            "place_type": place_type,
                                            "config": config
                                        }
                                        new_count += 1
                        
                        if completed % 5 == 0 or completed == len(route_segments):
                            self.log_message(f"   [{completed}/{len(route_segments)}] Found {new_count} new {config['name'].lower()}s.")
                
                # Add to all places
                all_places_raw.update(places_raw)
                self.log_message(f"Collected {len(places_raw)} {config['name'].lower()}s for this place type.")
            
            self.log_message(f"Total collected: {len(all_places_raw)} places. Removing duplicates...")
            
            # Remove duplicate places based on name and location similarity
            deduplicated_places = self.remove_duplicate_places(list(all_places_raw.values()))
            self.log_message(f"After deduplication: {len(deduplicated_places)} places (removed {len(all_places_raw) - len(deduplicated_places)} duplicates)")
            
            if self.processing_cancelled:
                self.log_message("Processing cancelled by user")
                return
            
            # Calculate distances for all places and organize by type
            self.stations_data = []
            self.supermarkets_data = []
            self.bakeries_data = []
            self.cafes_data = []
            self.repair_data = []
            self.accommodation_data = []
            self.speed_cameras_data = []
            
            processed_count = 0
            total_places = len(deduplicated_places)
            
            for place in deduplicated_places:
                if self.processing_cancelled:
                    self.log_message("Processing cancelled by user")
                    return
                
                processed_count += 1
                if processed_count % 10 == 0:  # Progress update every 10 places
                    self.log_message(f"Processed {processed_count}/{total_places} places...")
                # Find nearest point on track
                place_point = Point(place['lon'], place['lat'])
                route_position = route_line.project(place_point)  # Position along route (0.0 to route_length)
                nearest_point = route_line.interpolate(route_position)
                
                # Calculate distance to track
                distance_km = geodesic(
                    (place['lat'], place['lon']),
                    (nearest_point.y, nearest_point.x)
                ).km
                
                # Create enhanced place data
                config = place['config']
                enhanced_place = {
                    "name": f"{config['emoji']} {place['base_name']} ({distance_km:.1f}km)",
                    "base_name": place['base_name'],
                    "lat": place['lat'],
                    "lon": place['lon'],
                    "distance_km": round(distance_km, 3),
                    "route_position": route_position,  # Position along the route for ordering
                    "place_type": place['place_type'],
                    "config": config
                }
                
                # Add to appropriate list based on place type
                if place['place_type'] == 'petrol':
                    self.stations_data.append(enhanced_place)
                elif place['place_type'] == 'supermarket':
                    self.supermarkets_data.append(enhanced_place)
                elif place['place_type'] == 'bakery':
                    self.bakeries_data.append(enhanced_place)
                elif place['place_type'] == 'cafe':
                    self.cafes_data.append(enhanced_place)
                elif place['place_type'] == 'repair':
                    self.repair_data.append(enhanced_place)
                elif place['place_type'] == 'accommodation':
                    self.accommodation_data.append(enhanced_place)
                elif place['place_type'] == 'speed_camera':
                    self.speed_cameras_data.append(enhanced_place)
            
            # Sort all lists by position along route (order of occurrence)
            self.stations_data.sort(key=lambda x: x['route_position'])
            self.supermarkets_data.sort(key=lambda x: x['route_position'])
            self.bakeries_data.sort(key=lambda x: x['route_position'])
            self.cafes_data.sort(key=lambda x: x['route_position'])
            self.repair_data.sort(key=lambda x: x['route_position'])
            self.accommodation_data.sort(key=lambda x: x['route_position'])
            self.speed_cameras_data.sort(key=lambda x: x['route_position'])
            
            total_places = len(self.stations_data) + len(self.supermarkets_data) + len(self.bakeries_data) + len(self.cafes_data) + len(self.repair_data) + len(self.accommodation_data) + len(self.speed_cameras_data)
            self.log_message(f"Distance calculations completed for {total_places} places.")
            self.log_message(f"  ⛽ Petrol stations: {len(self.stations_data)}")
            self.log_message(f"  🛒 Supermarkets: {len(self.supermarkets_data)}")
            self.log_message(f"  🥖 Bakeries: {len(self.bakeries_data)}")
            self.log_message(f"  ☕ Cafés/Restaurants: {len(self.cafes_data)}")
            self.log_message(f"  🔧 Repair Shops: {len(self.repair_data)}")
            self.log_message(f"  🏨 Accommodation: {len(self.accommodation_data)}")
            self.log_message(f"  📷 Speed Cameras: {len(self.speed_cameras_data)}")
            
            # Calculate road routes for all places before updating maps
            if self.processing_cancelled:
                self.log_message("Processing cancelled by user")
                return
                
            self.log_message("Calculating road routes...")
            self.road_routes = {}  # Initialize road routes dictionary
            
            # Combine all places for road route calculation
            all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.accommodation_data + self.speed_cameras_data
            
            route_count = 0
            for place in all_places:
                if self.processing_cancelled:
                    self.log_message("Processing cancelled by user")
                    return
                
                route_count += 1
                if route_count % 5 == 0:  # Progress update every 5 routes
                    self.log_message(f"Calculated {route_count}/{len(all_places)} road routes...")
                # Check if place is close enough to track to skip route calculation
                if place['distance_km'] < 0.2:
                    self.log_message(f"  Skipping route for {place['base_name']}: too close to track ({place['distance_km']:.2f} km)")
                    continue
                
                # Find nearest point on track
                place_point = Point(place['lon'], place['lat'])
                nearest_point = route_line.interpolate(route_line.project(place_point))
                
                # Get actual road route to the place
                road_route = self.get_road_route(
                    nearest_point.y, nearest_point.x,  # Start: nearest route point
                    place['lat'], place['lon']          # End: place
                )
                
                if road_route and len(road_route) > 1:
                    place_key = (place['lat'], place['lon'])
                    self.road_routes[place_key] = road_route
                    self.log_message(f"  Road route found for {place['base_name']}: {len(road_route)} points")
                else:
                    self.log_message(f"  No road route found for {place['base_name']}")
            
            self.log_message(f"Road route calculations completed.")
            
            # Now update the map with all stations and routes
            self.root.after(0, self.update_map)
            self.root.after(0, self.update_results_display)
            
            # Enable the browser map button since we now have complete data
            self.root.after(0, lambda: self.open_map_btn.config(state='normal'))
            
            # Update status to show browser map is ready and enable GPX creation
            self.root.after(0, lambda: self.status_label.config(text="Processing completed - Ready to create GPX"))
            self.root.after(0, lambda: self.create_gpx_button.config(state='normal'))
            
            # Store the original gpx for later GPX generation
            self.original_gpx = gpx
            self.current_output_path = output_gpx
            
            self.log_message("\nProcessing completed successfully!")
            self.log_message("Use 'Create GPX' button to generate GPX file with selected places.")
            
            # Check for API failures and show summary if needed
            self.check_api_failures()
            
        except FileNotFoundError as e:
            error_msg = f"GPX file not found: {str(e)}"
            self.log_message(f"\nFile Error: {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("File Error", 
                "The selected GPX file could not be found.\n\n"
                "Please check that the file exists and try selecting it again."))
        
        except PermissionError as e:
            error_msg = f"Permission denied: {str(e)}"
            self.log_message(f"\nPermission Error: {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("Permission Error", 
                "Permission denied when accessing files.\n\n"
                "Please check that you have read access to the GPX file\n"
                "and write access to the output directory."))
        
        except ValueError as e:
            error_msg = str(e)
            self.log_message(f"\nData Error: {error_msg}")
            if "No track or route points" in error_msg:
                self.root.after(0, lambda: messagebox.showerror("Invalid GPX File", 
                    "No track or route data found in the GPX file.\n\n"
                    "Please select a GPX file that contains track or route information."))
            else:
                self.root.after(0, lambda: messagebox.showerror("Data Error", 
                    f"Invalid data in GPX file:\n\n{error_msg}\n\n"
                    "Please check your GPX file format."))
        
        except requests.exceptions.ConnectionError:
            error_msg = "Network connection error"
            self.log_message(f"\nConnection Error: {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("Connection Error", 
                "Lost internet connection during processing.\n\n"
                "The application needs internet access to query:\n"
                "• OpenStreetMap data (Overpass API)\n"
                "• Road routing information (OSRM)\n\n"
                "Please check your connection and try again."))
        
        except requests.exceptions.Timeout:
            error_msg = "API timeout error"
            self.log_message(f"\nTimeout Error: {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("Timeout Error", 
                "API services are taking too long to respond.\n\n"
                "This may be due to:\n"
                "• Server overload\n"
                "• Very large search area\n"
                "• Slow internet connection\n\n"
                "Try reducing the search distances or try again later."))
        
        except Exception as e:
            error_msg = str(e)
            self.log_message(f"\nUnexpected Error: {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("Unexpected Error", 
                f"An unexpected error occurred:\n\n{error_msg}\n\n"
                "Please check the processing output for more details.\n"
                "If the problem persists, try with a smaller GPX file or reduced search distances."))
        
        finally:
            # Re-enable button and stop progress
            self.root.after(0, self.processing_finished)
    
    def query_overpass_for_segment(self, segment, buffer_deg, overpass_url, query_filter='node["amenity"="fuel"]', place_type='petrol', retry_count=0, is_rate_limit_retry=False):
        """Queries Overpass API for places within a given segment with retry logic."""
        if self.processing_cancelled:
            return {}
            
        buffer_poly = segment.buffer(buffer_deg)
        minx, miny, maxx, maxy = buffer_poly.bounds
        
        query = f"""
        [out:json];
        {query_filter}({miny},{minx},{maxy},{maxx});
        out center;
        """
        
        max_retries = 3
        base_delay = 1  # Base delay in seconds (reduced from 2 to 1)
        
        try:
            # Add delay between API calls to prevent rate limiting
            if retry_count > 0:
                # Use different delays for rate limiting vs normal retries
                if is_rate_limit_retry:
                    # More aggressive delays for rate limiting: 4, 8, 16 seconds
                    delay = base_delay * (2 ** (retry_count + 1)) 
                else:
                    # Gentler delays for normal errors: 2, 4, 8 seconds
                    delay = base_delay * (2 ** retry_count)
                
                # Create unique waiting key to prevent duplicate waiting messages
                wait_key = f"waiting_{place_type}_{retry_count}_{delay}"
                if wait_key not in self.logged_errors:
                    self.log_message(f"Waiting {delay} seconds before retry {retry_count} for {place_type}...")
                    self.logged_errors.add(wait_key)
                
                time.sleep(delay)
            else:
                # Small delay between all API calls to be gentle on server
                time.sleep(0.5)
            
            if self.processing_cancelled:
                return {}
                
            response = requests.post(overpass_url, data={'data': query}, timeout=60)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.ConnectionError:
            self.api_failures['overpass'] += 1
            self.log_message(f"Connection error: Could not connect to Overpass API for {place_type} - check internet connection")
            return {}
        except requests.exceptions.Timeout:
            self.api_failures['overpass'] += 1
            self.log_message(f"Timeout error: Overpass API timeout for {place_type} - server may be overloaded")
            if retry_count < max_retries:
                return self.query_overpass_for_segment(segment, buffer_deg, overpass_url, query_filter, place_type, retry_count + 1)
            return {}
        except requests.exceptions.HTTPError as e:
            self.api_failures['overpass'] += 1
            if e.response.status_code == 429:
                # Create unique error key to prevent duplicate logging
                error_key = f"rate_limit_{place_type}_{retry_count}"
                if error_key not in self.logged_errors:
                    self.log_message(f"Rate limit error: Too many requests to Overpass API for {place_type}")
                    self.logged_errors.add(error_key)
                
                if retry_count < max_retries:
                    # Pass the rate limit flag so the delay calculation is correct
                    if not self.processing_cancelled:
                        result = self.query_overpass_for_segment(segment, buffer_deg, overpass_url, query_filter, place_type, retry_count + 1, is_rate_limit_retry=True)
                        # If retry was successful, track it
                        if result and len(result.get('elements', [])) >= 0:  # Any result means API call succeeded
                            self.api_retries['overpass_resolved'] += 1
                        return result
                else:
                    self.log_message(f"Max retries reached for {place_type} - skipping this segment")
                return {}
            elif e.response.status_code == 504:
                self.log_message(f"Server timeout: Overpass API server timeout for {place_type} - try reducing search area")
                if retry_count < max_retries:
                    return self.query_overpass_for_segment(segment, buffer_deg, overpass_url, query_filter, place_type, retry_count + 1)
            else:
                self.log_message(f"HTTP error: Overpass API error for {place_type} (HTTP {e.response.status_code})")
            return {}
        except requests.exceptions.RequestException as e:
            self.api_failures['overpass'] += 1
            self.log_message(f"Network error: Request failed for {place_type}: {e}")
            if retry_count < max_retries:
                return self.query_overpass_for_segment(segment, buffer_deg, overpass_url, query_filter, place_type, retry_count + 1)
            return {}
        except Exception as e:
            self.api_failures['overpass'] += 1
            self.log_message(f"Unexpected error querying Overpass for {place_type}: {e}")
            return {}
    
    def save_waypoints_only_gpx(self, places_list, output_gpx):
        """Save GPX with place waypoints only (no original track)"""
        # Create new GPX object
        gpx_out = gpxpy.gpx.GPX()
        
        # Set metadata
        gpx_out.name = f"Places Found Along Route"
        gpx_out.description = f"Places found along route within specified distances"
        
        # Group places by type for numbering
        place_counts = {'petrol': 0, 'supermarket': 0, 'bakery': 0, 'cafe': 0, 'repair': 0, 'accommodation': 0, 'speed_camera': 0}
        
        # Add places as waypoints only (no tracks or routes)
        for place in places_list:
            place_type = place.get('place_type', 'unknown')
            config = place.get('config', {})
            
            # Increment counter for this place type
            place_counts[place_type] = place_counts.get(place_type, 0) + 1
            
            # Create waypoint name with place name included
            waypoint_name = self.create_waypoint_name(place, place_type, place_counts[place_type])
            
            wpt = gpxpy.gpx.GPXWaypoint(
                latitude=place["lat"],
                longitude=place["lon"],
                name=waypoint_name,  # Use numbered name instead of actual place name
                description=f"{config.get('name', 'Place')}: {place['base_name']} - Distance from route: {place['distance_km']} km",
                symbol=self.get_garmin_symbol(place_type)
            )
            gpx_out.waypoints.append(wpt)
        
        # Save the places GPX
        with open(output_gpx, "w", encoding="utf-8") as gpxfile:
            gpxfile.write(gpx_out.to_xml())
    
    def save_enhanced_track_gpx(self, original_gpx, places_list, output_gpx):
        """Save GPX with route deviations inserted into original track at correct positions"""
        from shapely.geometry import Point, LineString
        from geopy.distance import geodesic
        
        # Create new GPX object
        gpx_out = gpxpy.gpx.GPX()
        
        # Set metadata
        gpx_out.name = f"Enhanced Route with Places"
        gpx_out.description = f"Original route with deviations inserted at correct positions"
        
        # Create one track
        enhanced_track = gpxpy.gpx.GPXTrack()
        enhanced_track.name = "Enhanced Route with Deviations"
        enhanced_track.description = "Original route with deviations inserted where they branch off"
        enhanced_segment = gpxpy.gpx.GPXTrackSegment()
        
        if self.route_points and places_list:
            # Find where each route deviation should be inserted
            route_insertions = []
            
            for place in places_list:
                place_key = (place['lat'], place['lon'])
                if place_key in self.road_routes:
                    road_route = self.road_routes[place_key]
                    if road_route and len(road_route) > 1:
                        # Find the closest point on original track to the START of the road route
                        route_start = road_route[0]  # First point of the road route
                        
                        closest_distance = float('inf')
                        insertion_index = 0
                        
                        for i, (track_lon, track_lat) in enumerate(self.route_points):
                            distance = geodesic((track_lat, track_lon), (route_start[1], route_start[0])).km
                            if distance < closest_distance:
                                closest_distance = distance
                                insertion_index = i
                        
                        route_insertions.append({
                            'index': insertion_index,
                            'place': place,
                            'route': road_route
                        })
                        self.log_message(f"  Will insert {place['base_name']} deviation at track point {insertion_index}")
            
            # Sort by insertion index to maintain order
            route_insertions.sort(key=lambda x: x['index'])
            
            # Build the enhanced track by going through original points and inserting deviations
            insertion_offset = 0
            current_insertion = 0
            
            for i, (lon, lat) in enumerate(self.route_points):
                # Add the original track point
                enhanced_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon))
                
                # Check if we need to insert any deviations after this point
                while (current_insertion < len(route_insertions) and 
                       route_insertions[current_insertion]['index'] == i):
                    
                    deviation = route_insertions[current_insertion]
                    place = deviation['place']
                    road_route = deviation['route']
                    
                    # Insert the road route deviation
                    for route_point in road_route:
                        enhanced_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                            latitude=route_point[1], longitude=route_point[0]))
                    
                    # Add the place itself
                    enhanced_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                        latitude=place['lat'], longitude=place['lon']))
                    
                    # Return the same way (reverse the road route)
                    for route_point in reversed(road_route):
                        enhanced_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                            latitude=route_point[1], longitude=route_point[0]))
                    
                    self.log_message(f"  Inserted deviation to {place['base_name']}")
                    current_insertion += 1
            
            enhanced_track.segments.append(enhanced_segment)
            gpx_out.tracks.append(enhanced_track)
            self.log_message("  Created enhanced track with inserted deviations")
        
        elif self.route_points:
            # No places, just add original track
            for lon, lat in self.route_points:
                enhanced_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon))
            enhanced_track.segments.append(enhanced_segment)
            gpx_out.tracks.append(enhanced_track)
            self.log_message("  Added original track only (no places selected)")
        
        # Also add all selected places as waypoints for convenience
        place_counts = {'petrol': 0, 'supermarket': 0, 'bakery': 0, 'cafe': 0, 'repair': 0, 'accommodation': 0, 'speed_camera': 0}
        
        for place in places_list:
            place_type = place.get('place_type', 'unknown')
            config = place.get('config', {})
            
            # Increment counter for this place type
            place_counts[place_type] = place_counts.get(place_type, 0) + 1
            
            # Create waypoint name with place name included
            waypoint_name = self.create_waypoint_name(place, place_type, place_counts[place_type])
            
            wpt = gpxpy.gpx.GPXWaypoint(
                latitude=place["lat"],
                longitude=place["lon"],
                name=waypoint_name,
                description=f"{config.get('name', 'Place')}: {place['base_name']} - Distance from route: {place['distance_km']} km",
                symbol=self.get_garmin_symbol(place_type)
            )
            gpx_out.waypoints.append(wpt)
        
        # Save the enhanced GPX
        with open(output_gpx, "w", encoding="utf-8") as gpxfile:
            gpxfile.write(gpx_out.to_xml())
    
    def calculate_station_distances_along_track(self, stations_list):
        """Calculate distances between fuel segments along the track.
        
        Returns distances for:
        1. Route start → First station
        2. Between consecutive stations
        3. Last station → Route end
        
        This gives a complete fuel gap analysis for the entire journey."""
        if len(stations_list) == 0:
            return []
        
        # Sort stations by their position along the track (use pre-calculated route_position)
        track_positions = []
        route_line = LineString(self.route_points)
        
        for station in stations_list:
            # Use the pre-calculated route position if available, otherwise calculate it
            if 'route_position' in station:
                position = station['route_position']
            else:
                station_point = Point(station['lon'], station['lat'])
                position = route_line.project(station_point)
            track_positions.append((position, station))
        
        # Sort by position along track
        track_positions.sort(key=lambda x: x[0])
        
        # Helper function to calculate distance between two positions along the route
        def calculate_route_distance(pos1, pos2):
            if pos1 >= pos2:
                return 0
            
            # Extract track segment between these positions
            segment_points = []
            for point in self.route_points:
                point_obj = Point(point[0], point[1])
                point_pos = route_line.project(point_obj)
                if pos1 <= point_pos <= pos2:
                    segment_points.append(point)
            
            distance_km = 0
            if len(segment_points) > 1:
                for j in range(1, len(segment_points)):
                    pt1 = (segment_points[j-1][1], segment_points[j-1][0])  # lat, lon for geopy
                    pt2 = (segment_points[j][1], segment_points[j][0])
                    distance_km += geodesic(pt1, pt2).km
            
            return distance_km
        
        station_distances = []
        
        # 1. Distance from START of route to FIRST station
        if len(track_positions) > 0:
            first_station = track_positions[0][1]
            first_pos = track_positions[0][0]
            start_distance = calculate_route_distance(0, first_pos)
            
            station_distances.append({
                'from_station': 'ROUTE START',
                'to_station': first_station['base_name'],
                'distance_km': round(start_distance, 2),
                'from_position': 0,
                'to_position': first_pos
            })
        
        # 2. Distances between consecutive stations
        for i in range(1, len(track_positions)):
            prev_station = track_positions[i-1][1]
            curr_station = track_positions[i][1]
            prev_pos = track_positions[i-1][0]
            curr_pos = track_positions[i][0]
            
            distance_km = calculate_route_distance(prev_pos, curr_pos)
            
            station_distances.append({
                'from_station': prev_station['base_name'],
                'to_station': curr_station['base_name'],
                'distance_km': round(distance_km, 2),
                'from_position': prev_pos,
                'to_position': curr_pos
            })
        
        # 3. Distance from LAST station to END of route
        if len(track_positions) > 0:
            last_station = track_positions[-1][1]
            last_pos = track_positions[-1][0]
            route_length = route_line.length
            end_distance = calculate_route_distance(last_pos, route_length)
            
            station_distances.append({
                'from_station': last_station['base_name'],
                'to_station': 'ROUTE END',
                'distance_km': round(end_distance, 2),
                'from_position': last_pos,
                'to_position': route_length
            })
        
        return station_distances
    
    def update_results_display(self):
        """Update the results summary display"""
        total_places = len(self.stations_data) + len(self.supermarkets_data) + len(self.bakeries_data) + len(self.cafes_data) + len(self.repair_data) + len(self.accommodation_data) + len(self.speed_cameras_data)
        
        if total_places > 0:
            # Clear existing items in the places treeview
            for item in self.places_tree.get_children():
                self.places_tree.delete(item)
            # Clear place selections and data
            self.place_selections.clear()
            self.place_data.clear()
            self.highlighted_place = None
            
            # Combine all places and sort by route position (order of occurrence along route)
            all_places = self.stations_data + self.supermarkets_data + self.bakeries_data + self.cafes_data + self.repair_data + self.accommodation_data + self.speed_cameras_data
            all_places.sort(key=lambda x: x['route_position'])
            
            # Populate the places treeview
            for place in all_places:
                place_type = place.get('config', {}).get('name', 'Unknown')
                item_id = self.places_tree.insert('', 'end', values=(
                    "☑",  # Default to checked
                    place_type,
                    place['name'],
                    f"{place['distance_km']:.1f}"
                ))
                # Store place data separately
                self.place_data[item_id] = place
                # Initialize selection state as True (checked)
                self.place_selections[item_id] = True
            
            # Calculate total route distance
            total_distance = 0
            if self.route_points:
                for i in range(1, len(self.route_points)):
                    pt1 = (self.route_points[i-1][1], self.route_points[i-1][0])
                    pt2 = (self.route_points[i][1], self.route_points[i][0])
                    total_distance += geodesic(pt1, pt2).km
            
            # Calculate petrol station distances if any petrol stations were found
            station_distances = None
            if self.stations_data:
                station_distances = self.calculate_station_distances_along_track(self.stations_data)
                if station_distances:
                    max_distance = max(station_distances, key=lambda x: x['distance_km'])
                    min_distance = min(station_distances, key=lambda x: x['distance_km'])
                    
                    # Log the detailed distance information for petrol stations
                    self.log_message(f"\n=== PETROL STATION DISTANCES ALONG TRACK ===")
                    self.log_message(f"Maximum gap: {max_distance['distance_km']} km between {max_distance['from_station']} and {max_distance['to_station']}")
                    self.log_message(f"Minimum gap: {min_distance['distance_km']} km between {min_distance['from_station']} and {min_distance['to_station']}")
                    self.log_message(f"\nDetailed distances:")
                    
                    for dist_info in station_distances:
                        self.log_message(f"  {dist_info['from_station']} → {dist_info['to_station']}: {dist_info['distance_km']} km")
                    
                    # Motorcycle range warning
                    if max_distance['distance_km'] > 200:
                        self.log_message(f"\n⚠️  WARNING: Maximum gap ({max_distance['distance_km']} km) may exceed typical motorcycle range!")
                        self.log_message(f"   Consider planning fuel stops or carrying extra fuel.")
                    elif max_distance['distance_km'] > 150:
                        self.log_message(f"\n⚠️  CAUTION: Maximum gap ({max_distance['distance_km']} km) is close to typical motorcycle range.")
                        self.log_message(f"   Plan fuel stops carefully.")
                    else:
                        self.log_message(f"\n✅ Good: Maximum gap ({max_distance['distance_km']} km) is within typical motorcycle range.")
            
            # Show results in popup
            self.show_results_popup(total_places, total_distance, station_distances)
        else:
            # Clear the places treeview when no places found
            for item in self.places_tree.get_children():
                self.places_tree.delete(item)
            # Clear place selections and data
            self.place_selections.clear()
            self.place_data.clear()
            self.highlighted_place = None
    
    def processing_finished(self):
        # Re-enable search button and disable stop button
        self.search_button.config(state='normal')
        self.stop_button.config(state='disabled')
        # Keep create gpx disabled until new processing completes
        
        self.progress.stop()
        if not self.processing_cancelled:
            self.status_label.config(text="Processing completed")
        else:
            self.status_label.config(text="Processing cancelled")

def main():
    root = tk.Tk()
    app = GPXPetrolFinderEnhancedGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
