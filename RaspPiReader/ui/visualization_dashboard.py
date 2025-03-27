
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import numpy as np
import os
from ..libs.visualization import LiveDataVisualization
from ..libs.models import ChannelConfigSettings
from ..libs.database import Database
from .. import pool

class VisualizationDashboard(QtWidgets.QWidget):
    """
    A dashboard for displaying real-time PLC data visualizations.
    Supports all 14 CH channels with customizable display properties.
    """
    
    def __init__(self, parent=None):
        super(VisualizationDashboard, self).__init__(parent)
        self.visualization = LiveDataVisualization(update_interval_ms=100)
        self.channels_config = {}
        self.plots = {}
        self.channel_info_widgets = {}
        self.db = Database("sqlite:///local_database.db")
        self.load_channel_config()
        self.setup_ui()
        
    def load_channel_config(self):
        """Load all channel configurations from the database"""
        try:
            for i in range(1, 15):  # 14 channels
                channel = self.db.session.query(ChannelConfigSettings).filter_by(id=i).first()
                if channel:
                    # Use the correct field names from the model
                    self.channels_config[i] = {
                        'id': i,
                        'label': channel.label if hasattr(channel, 'label') else f"Channel {i}",
                        'address': channel.address,
                        'pv': channel.pv or 0,
                        'sv': channel.sv or 0,
                        'set_point': channel.set_point or 0,
                        'limit_low': channel.limit_low or 0,
                        'limit_high': channel.limit_high or 100,
                        'decimal_point': channel.decimal_point or 0,
                        'scale': channel.scale or False,
                        'axis_direction': channel.axis_direction if hasattr(channel, 'axis_direction') else 'normal',
                        'color': channel.color if hasattr(channel, 'color') else self.get_default_color(i),
                        'active': channel.active if hasattr(channel, 'active') else True,
                        'min_scale_range': channel.min_scale_range if hasattr(channel, 'min_scale_range') else 0,
                        'max_scale_range': channel.max_scale_range if hasattr(channel, 'max_scale_range') else 100
                    }
        except Exception as e:
            print(f"Error loading channel config: {e}")
            # Create default config if db fails
            for i in range(1, 15):
                self.channels_config[i] = {
                    'id': i,
                    'label': f"Channel {i}",
                    'address': 100 + i,
                    'pv': 0,
                    'sv': 0,
                    'set_point': 0,
                    'limit_low': 0,
                    'limit_high': 100,
                    'decimal_point': 0,
                    'scale': False,
                    'axis_direction': 'normal',
                    'color': self.get_default_color(i),
                    'active': True,
                    'min_scale_range': 0,
                    'max_scale_range': 100
                }
    
    def get_default_color(self, channel_number):
        """Get a default color based on channel type"""
        if channel_number <= 8:  # Vacuum Gauges (CH1-CH8)
            return "#3498db"  # Blue
        elif channel_number <= 12:  # Temperature (CH9-CH12)
            return "#e74c3c"  # Red
        else:  # Pressure & System Vacuum (CH13-CH14)
            return "#2ecc71"  # Green
        
    def setup_ui(self):
        """Setup the dashboard UI components"""
        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title_label = QtWidgets.QLabel("Live PLC Data Visualization - 14 CH Monitor")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2c3e50;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(title_label)
        
        # Control panel
        self.control_panel = QtWidgets.QHBoxLayout()
        
        # Cycle time display
        self.cycle_time_label = QtWidgets.QLabel("Cycle Time: 00:00:00")
        self.cycle_time_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #3498db;")
        self.control_panel.addWidget(self.cycle_time_label)
        
        # Spacer
        self.control_panel.addStretch()
        
        # Control buttons
        self.btn_pause = QtWidgets.QPushButton("Pause")
        self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.control_panel.addWidget(self.btn_pause)
        
        self.btn_export = QtWidgets.QPushButton("Export Data")
        self.btn_export.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        self.btn_export.clicked.connect(self.export_data)
        self.control_panel.addWidget(self.btn_export)
        
        self.main_layout.addLayout(self.control_panel)
        
        # Create tab widget for different visualization views
        self.tab_widget = QtWidgets.QTabWidget()
        
        # Create the plot view tab
        self.plot_tab = QtWidgets.QWidget()
        self.plot_layout = QtWidgets.QVBoxLayout(self.plot_tab)
        
        # Splitter for plot area and channel info
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        # Plot grid container
        self.plot_grid_widget = QtWidgets.QWidget()
        self.plot_grid_layout = QtWidgets.QGridLayout(self.plot_grid_widget)
        self.create_visualization_grid()
        
        # Channel info area
        self.channel_info_widget = QtWidgets.QWidget()
        self.channel_info_layout = QtWidgets.QVBoxLayout(self.channel_info_widget)
        self.create_channel_info_area()
        
        # Add widgets to splitter
        self.main_splitter.addWidget(self.plot_grid_widget)
        self.main_splitter.addWidget(self.channel_info_widget)
        self.main_splitter.setSizes([700, 300])  # Set initial sizes
        
        self.plot_layout.addWidget(self.main_splitter)
        
        # Create the table view tab (shows all channel data in a table)
        self.table_tab = QtWidgets.QWidget()
        self.table_layout = QtWidgets.QVBoxLayout(self.table_tab)
        self.create_table_view()
        
        # Add tabs to tab widget
        self.tab_widget.addTab(self.plot_tab, "Plot View")
        self.tab_widget.addTab(self.table_tab, "Table View")
        
        self.main_layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.showMessage("Ready")
        self.main_layout.addWidget(self.status_bar)
        
        # Timer for updating cycle time
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_cycle_time)
        self.cycle_start_time = None
        self.paused = False
        
    def create_visualization_grid(self):
        """Create the grid of visualization plots for all 14 channels"""
        rows, cols = 4, 4  # 4x4 grid to display 14 plots (with 2 empty spots)
        
        # Create plots for each channel
        for i in range(1, 15):
            row = (i - 1) // cols
            col = (i - 1) % cols
            
            channel_config = self.channels_config.get(i, {})
            channel_name = f"ch{i}"
            
            # Create plot widget
            plot_widget = pg.PlotWidget()
            
            # Configure plot with channel settings
            title = channel_config.get('label', f"Channel {i}")
            color = channel_config.get('color', self.get_default_color(i))
            
            # Set Y-axis range if configured
            min_range = channel_config.get('min_scale_range', 0)
            max_range = channel_config.get('max_scale_range', 100)
            if min_range is not None and max_range is not None:
                plot_widget.setYRange(min_range, max_range)
            
            # Add the plot to the visualization system
            self.visualization.add_time_series_plot(
                plot_widget,
                channel_name,
                color=color,
                title=title,
                y_label=title
            )
            
            # Store the plot widget for later reference
            self.plots[channel_name] = plot_widget
            
            # Add plot to grid
            self.plot_grid_layout.addWidget(plot_widget, row, col)
    
    def create_channel_info_area(self):
        """Create an area to display live channel information"""
        # Add header
        header_layout = QtWidgets.QHBoxLayout()
        headers = ["CH", "Address", "Label", "PV", "SV", "Set Point", "Low Limit", 
                  "High Limit", "Decimal", "Scale", "Axis", "Color"]
        
        for header_text in headers:
            label = QtWidgets.QLabel(header_text)
            label.setStyleSheet("font-weight: bold;")
            header_layout.addWidget(label)
        
        self.channel_info_layout.addLayout(header_layout)
        
        # Create scrollable area for channel info
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        
        # Create a row for each channel
        for i in range(1, 15):
            channel_config = self.channels_config.get(i, {})
            row_layout = QtWidgets.QHBoxLayout()
            
            # Channel number
            ch_label = QtWidgets.QLabel(f"CH{i}")
            ch_label.setStyleSheet(f"color: {channel_config.get('color', '#000000')};")
            row_layout.addWidget(ch_label)
            
            # Address
            address_label = QtWidgets.QLabel(str(channel_config.get('address', '')))
            row_layout.addWidget(address_label)
            
            # Channel label
            label_label = QtWidgets.QLabel(channel_config.get('label', f"Channel {i}"))
            row_layout.addWidget(label_label)
            
            # Process Value (PV)
            pv_label = QtWidgets.QLabel("0.0")
            row_layout.addWidget(pv_label)
            
            # Set Value (SV)
            sv_label = QtWidgets.QLabel(str(channel_config.get('sv', 0)))
            row_layout.addWidget(sv_label)
            
            # Set Point
            setpoint_label = QtWidgets.QLabel(str(channel_config.get('set_point', 0)))
            row_layout.addWidget(setpoint_label)
            
            # Low Limit
            low_label = QtWidgets.QLabel(str(channel_config.get('limit_low', 0)))
            row_layout.addWidget(low_label)
            
            # High Limit
            high_label = QtWidgets.QLabel(str(channel_config.get('limit_high', 100)))
            row_layout.addWidget(high_label)
            
            # Decimal Places
            decimal_label = QtWidgets.QLabel(str(channel_config.get('decimal_point', 0)))
            row_layout.addWidget(decimal_label)
            
            # Scale
            scale_label = QtWidgets.QLabel("Yes" if channel_config.get('scale', False) else "No")
            row_layout.addWidget(scale_label)
            
            # Axis Direction
            axis_label = QtWidgets.QLabel(channel_config.get('axis_direction', 'normal'))
            row_layout.addWidget(axis_label)
            
            # Color
            color_box = QtWidgets.QLabel()
            color_box.setFixedSize(16, 16)
            color = channel_config.get('color', self.get_default_color(i))
            color_box.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
            row_layout.addWidget(color_box)
            
            # Store labels for updating
            self.channel_info_widgets[i] = {
                'address': address_label,
                'label': label_label,
                'pv': pv_label,
                'sv': sv_label,
                'set_point': setpoint_label,
                'limit_low': low_label,
                'limit_high': high_label,
                'decimal_point': decimal_label,
                'scale': scale_label,
                'axis_direction': axis_label,
                'color': color_box
            }
            
            scroll_layout.addLayout(row_layout)
        
        scroll_area.setWidget(scroll_content)
        self.channel_info_layout.addWidget(scroll_area)
    
    def create_table_view(self):
        """Create a table view to display all channel data"""
        self.data_table = QtWidgets.QTableWidget()
        self.data_table.setColumnCount(12)
        self.data_table.setRowCount(14)
        
        headers = ["CH", "Address", "Label", "PV", "SV", "Set Point", "Low Limit", 
                  "High Limit", "Decimal", "Scale", "Axis", "Color"]
        self.data_table.setHorizontalHeaderLabels(headers)
        
        # Populate table with channel data
        for i in range(1, 15):
            channel_config = self.channels_config.get(i, {})
            
            # Channel number
            ch_item = QtWidgets.QTableWidgetItem(f"CH{i}")
            self.data_table.setItem(i-1, 0, ch_item)
            
            # Address
            address_item = QtWidgets.QTableWidgetItem(str(channel_config.get('address', '')))
            self.data_table.setItem(i-1, 1, address_item)
            
            # Label
            label_item = QtWidgets.QTableWidgetItem(channel_config.get('label', f"Channel {i}"))
            self.data_table.setItem(i-1, 2, label_item)
            
            # PV (process value)
            pv_item = QtWidgets.QTableWidgetItem("0.0")
            self.data_table.setItem(i-1, 3, pv_item)
            
            # SV (set value)
            sv_item = QtWidgets.QTableWidgetItem(str(channel_config.get('sv', 0)))
            self.data_table.setItem(i-1, 4, sv_item)
            
            # Set Point
            setpoint_item = QtWidgets.QTableWidgetItem(str(channel_config.get('set_point', 0)))
            self.data_table.setItem(i-1, 5, setpoint_item)
            
            # Low Limit
            low_item = QtWidgets.QTableWidgetItem(str(channel_config.get('limit_low', 0)))
            self.data_table.setItem(i-1, 6, low_item)
            
            # High Limit
            high_item = QtWidgets.QTableWidgetItem(str(channel_config.get('limit_high', 100)))
            self.data_table.setItem(i-1, 7, high_item)
            
            # Decimal Places
            decimal_item = QtWidgets.QTableWidgetItem(str(channel_config.get('decimal_point', 0)))
            self.data_table.setItem(i-1, 8, decimal_item)
            
            # Scale
            scale_item = QtWidgets.QTableWidgetItem("Yes" if channel_config.get('scale', False) else "No")
            self.data_table.setItem(i-1, 9, scale_item)
            
            # Axis Direction
            axis_item = QtWidgets.QTableWidgetItem(channel_config.get('axis_direction', 'normal'))
            self.data_table.setItem(i-1, 10, axis_item)
            
            # Color (just showing the color name/value)
            color_item = QtWidgets.QTableWidgetItem(channel_config.get('color', self.get_default_color(i)))
            color_item.setBackground(QtGui.QColor(channel_config.get('color', self.get_default_color(i))))
            self.data_table.setItem(i-1, 11, color_item)
            
            # Set row color as a slight tint based on channel color
            color = QtGui.QColor(channel_config.get('color', self.get_default_color(i)))
            color.setAlpha(40)  # Make it very transparent
            for col in range(11):  # Don't apply to the color column
                item = self.data_table.item(i-1, col)
                if item:
                    item.setBackground(color)
        
        self.table_layout.addWidget(self.data_table)
        
    def start_visualization(self):
        """Start the visualization"""
        self.visualization.start_visualization()
        self.cycle_start_time = QtCore.QDateTime.currentDateTime()
        self.timer.start(1000)  # Update cycle time every second
        self.btn_pause.setText("Pause")
        self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
        self.paused = False
        self.status_bar.showMessage("Visualization started")
        
    def stop_visualization(self):
        """Stop the visualization"""
        self.visualization.stop_visualization()
        self.timer.stop()
        self.cycle_start_time = None
        self.btn_pause.setText("Pause")
        self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
        self.paused = False
        self.status_bar.showMessage("Visualization stopped")
        
    def update_data(self, channel_number, value):
        """
        Update data for a specific channel
        
        Args:
            channel_number: The channel number (1-14)
            value: The current value for the channel
        """
        if channel_number < 1 or channel_number > 14:
            return
            
        # Format value based on decimal places setting
        channel_config = self.channels_config.get(channel_number, {})
        decimal_places = channel_config.get('decimal_point', 0)
        
        # Apply scaling if configured
        if channel_config.get('scale', False):
            # If scaling is enabled, map the raw value to the range
            low_limit = channel_config.get('limit_low', 0)
            high_limit = channel_config.get('limit_high', 100)
            min_range = channel_config.get('min_scale_range', low_limit)
            max_range = channel_config.get('max_scale_range', high_limit)
            
            # Apply the scaling formula only if the ranges are valid
            if high_limit != low_limit and max_range != min_range:
                value = min_range + ((value - low_limit) * (max_range - min_range)) / (high_limit - low_limit)
        
        # Format the value with proper decimal places
        formatted_value = f"{value:.{decimal_places}f}"
        
        # Update the visualization with channel data
        channel_name = f"ch{channel_number}"
        self.visualization.update_data(channel_name, value)
        
        # Update channel info display
        if channel_number in self.channel_info_widgets:
            self.channel_info_widgets[channel_number]['pv'].setText(formatted_value)
        
        # Update table view if it's visible
        if self.tab_widget.currentIndex() == 1:  # Table view
            pv_item = self.data_table.item(channel_number-1, 3)  # Column 3 is PV
            if pv_item:
                pv_item.setText(formatted_value)
        
        # Update the database with current PV
        try:
            channel = self.db.session.query(ChannelConfigSettings).filter_by(id=channel_number).first()
            if channel:
                channel.pv = value
                self.db.session.commit()
        except Exception as e:
            print(f"Error updating channel PV in database: {e}")
    
    def update_channel_settings(self, channel_number, settings):
        """
        Update the settings for a specific channel, both in memory and in the database.
        This method should be called when the user changes channel settings from the settings dialog.
        
        Args:
            channel_number: The channel number (1-14)
            settings: Dictionary with the new settings
        """
        if channel_number < 1 or channel_number > 14 or not settings:
            return
        
        # Update in-memory configuration
        self.channels_config[channel_number].update(settings)
        
        # Update database
        try:
            channel = self.db.session.query(ChannelConfigSettings).filter_by(id=channel_number).first()
            if channel:
                # Update the channel fields with the new settings
                if 'label' in settings:
                    channel.label = settings['label']
                if 'address' in settings:
                    channel.address = settings['address']
                if 'sv' in settings:
                    channel.sv = settings['sv']
                if 'set_point' in settings:
                    channel.set_point = settings['set_point']
                if 'limit_low' in settings:
                    channel.limit_low = settings['limit_low']
                if 'limit_high' in settings:
                    channel.limit_high = settings['limit_high']
                if 'decimal_point' in settings:
                    channel.decimal_point = settings['decimal_point']
                if 'scale' in settings:
                    channel.scale = settings['scale']
                if 'axis_direction' in settings:
                    channel.axis_direction = settings['axis_direction']
                if 'color' in settings:
                    channel.color = settings['color']
                if 'active' in settings:
                    channel.active = settings['active']
                if 'min_scale_range' in settings:
                    channel.min_scale_range = settings['min_scale_range']
                if 'max_scale_range' in settings:
                    channel.max_scale_range = settings['max_scale_range']
                
                self.db.session.commit()
                self.status_bar.showMessage(f"Updated settings for CH{channel_number}")
                
                # Update plot appearance if color changed
                if 'color' in settings:
                    channel_name = f"ch{channel_number}"
                    if channel_name in self.plots:
                        # Update plot color in visualization system
                        plot_widget = self.plots[channel_name]
                        plot_data = self.visualization.plots.get(channel_name)
                        if plot_data and 'curve' in plot_data:
                            pen = pg.mkPen(color=settings['color'], width=2)
                            plot_data['curve'].setPen(pen)
                
                # Update labels in the channel info display
                if channel_number in self.channel_info_widgets:
                    widgets = self.channel_info_widgets[channel_number]
                    for key, value in settings.items():
                        if key in widgets:
                            if key == 'color':
                                widgets[key].setStyleSheet(f"background-color: {value}; border: 1px solid black;")
                            elif key == 'scale':
                                widgets[key].setText("Yes" if value else "No")
                            else:
                                widgets[key].setText(str(value))
                
                # Update table view if it's visible
                if self.tab_widget.currentIndex() == 1:
                    self.update_table_row(channel_number)
                
        except Exception as e:
            print(f"Error updating channel settings in database: {e}")
            self.status_bar.showMessage(f"Error updating settings for CH{channel_number}: {e}")
    
    def update_table_row(self, channel_number):
        """Update a specific row in the table view"""
        if channel_number < 1 or channel_number > 14:
            return
            
        channel_config = self.channels_config.get(channel_number, {})
        row = channel_number - 1
        
        # Address
        address_item = self.data_table.item(row, 1)
        if address_item:
            address_item.setText(str(channel_config.get('address', '')))
        
        # Label
        label_item = self.data_table.item(row, 2)
        if label_item:
            label_item.setText(channel_config.get('label', f"Channel {channel_number}"))
        
        # SV
        sv_item = self.data_table.item(row, 4)
        if sv_item:
            sv_item.setText(str(channel_config.get('sv', 0)))
        
        # Set Point
        sp_item = self.data_table.item(row, 5)
        if sp_item:
            sp_item.setText(str(channel_config.get('set_point', 0)))
        
        # Low Limit
        low_item = self.data_table.item(row, 6)
        if low_item:
            low_item.setText(str(channel_config.get('limit_low', 0)))
        
        # High Limit
        high_item = self.data_table.item(row, 7)
        if high_item:
            high_item.setText(str(channel_config.get('limit_high', 100)))
        
        # Decimal Places
        decimal_item = self.data_table.item(row, 8)
        if decimal_item:
            decimal_item.setText(str(channel_config.get('decimal_point', 0)))
        
        # Scale
        scale_item = self.data_table.item(row, 9)
        if scale_item:
            scale_item.setText("Yes" if channel_config.get('scale', False) else "No")
        
        # Axis Direction
        axis_item = self.data_table.item(row, 10)
        if axis_item:
            axis_item.setText(channel_config.get('axis_direction', 'normal'))
        
        # Color
        color_item = self.data_table.item(row, 11)
        if color_item:
            color = channel_config.get('color', self.get_default_color(channel_number))
            color_item.setText(color)
            color_item.setBackground(QtGui.QColor(color))
        
    def update_cycle_time(self):
        """Update the cycle time display"""
        if not self.cycle_start_time or self.paused:
            return
            
        current_time = QtCore.QDateTime.currentDateTime()
        elapsed = self.cycle_start_time.secsTo(current_time)
        
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        time_str = f"Cycle Time: {hours:02d}:{minutes:02d}:{seconds:02d}"
        self.cycle_time_label.setText(time_str)
        
    def toggle_pause(self):
        """Pause or resume the visualization"""
        if self.paused:
            # Resume
            self.visualization.start_visualization()
            self.timer.start(1000)
            self.btn_pause.setText("Pause")
            self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
            self.status_bar.showMessage("Visualization resumed")
        else:
            # Pause
            self.visualization.stop_visualization()
            self.timer.stop()
            self.btn_pause.setText("Resume")
            self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
            self.status_bar.showMessage("Visualization paused")
            
        self.paused = not self.paused
        
    def export_data(self):
        """Export the visualization data to a file"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Visualization Data",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            success = self.visualization.export_data(file_path)
            if success:
                self.status_bar.showMessage(f"Data exported to {file_path}")
            else:
                self.status_bar.showMessage("Failed to export data")
                
    
    def reset(self):
        """Reset the visualization dashboard"""
        self.stop_visualization()
        self.visualization.reset_data()
        self.cycle_time_label.setText("Cycle Time: 00:00:00")
        
        # Reset all PV displays
        for channel_number, widgets in self.channel_info_widgets.items():
            widgets['pv'].setText("0.0")
        
        # Reset table view
        if self.tab_widget.currentIndex() == 1:
            for i in range(1, 15):
                pv_item = self.data_table.item(i-1, 2)
                if pv_item:
                    pv_item.setText("0.0")
        
        self.status_bar.showMessage("Visualization reset")
        
    def update_channel_settings(self, channel_number, settings):
        """
        Update the settings for a specific channel, both in memory and in the database.
        This method should be called when the user changes channel settings from the settings dialog.
        
        Args:
            channel_number: The channel number (1-14)
            settings: Dictionary with the new settings
        """
        if channel_number < 1 or channel_number > 14 or not settings:
            return
        
        # Update in-memory configuration
        self.channels_config[channel_number].update(settings)
        
        # Update database
        try:
            channel = self.db.session.query(ChannelConfigSettings).filter_by(id=channel_number).first()
            if channel:
                # Update the channel fields with the new settings
                # Map the field names used in the UI to the database model field names
                field_mapping = {
                    'name': 'label',
                    'set_point': 'set_point',
                    'low_limit': 'limit_low',
                    'high_limit': 'limit_high',
                    'dec_point': 'decimal_point'
                }
                
                for ui_field, db_field in field_mapping.items():
                    if ui_field in settings:
                        setattr(channel, db_field, settings[ui_field])
                
                # Fields that have the same name
                direct_fields = ['address', 'pv', 'sv', 'scale', 'color']
                for field in direct_fields:
                    if field in settings:
                        setattr(channel, field, settings[field])
                
                # Additional fields from model that might be in settings
                additional_fields = ['axis_direction', 'active', 'min_scale_range', 'max_scale_range']
                for field in additional_fields:
                    if field in settings:
                        setattr(channel, field, settings[field])
                
                self.db.session.commit()
                self.status_bar.showMessage(f"Updated settings for CH{channel_number}")
                
                # Update plot appearance if color changed
                if 'color' in settings:
                    channel_name = f"ch{channel_number}"
                    if channel_name in self.visualization.plots:
                        # Update plot color in visualization system
                        plot_data = self.visualization.plots.get(channel_name)
                        if plot_data and 'curve' in plot_data:
                            pen = pg.mkPen(color=settings['color'], width=2)
                            plot_data['curve'].setPen(pen)
                
                # Update channel info display
                if channel_number in self.channel_info_widgets:
                    widgets = self.channel_info_widgets[channel_number]
                    for key, value in settings.items():
                        if key in widgets:
                            if key == 'scale':
                                widgets[key].setText("Yes" if value else "No")
                            else:
                                widgets[key].setText(str(value))
                
                # Update table view if it's visible
                if self.tab_widget.currentIndex() == 1:
                    self.update_table_row(channel_number)
                
        except Exception as e:
            print(f"Error updating channel settings in database: {e}")
            self.status_bar.showMessage(f"Error updating settings for CH{channel_number}: {e}")
    
    def update_table_row(self, channel_number):
        """Update a specific row in the table view"""
        if channel_number < 1 or channel_number > 14:
            return
            
        channel_config = self.channels_config.get(channel_number, {})
        row = channel_number - 1
        
        # Name/Label
        name_item = self.data_table.item(row, 1)
        if name_item:
            name_item.setText(channel_config.get('name', f"Channel {channel_number}"))
        
        # SV
        sv_item = self.data_table.item(row, 3)
        if sv_item:
            sv_item.setText(str(channel_config.get('sv', 0)))
        
        # Set Point
        setpoint_item = self.data_table.item(row, 4)
        if setpoint_item:
            setpoint_item.setText(str(channel_config.get('set_point', 0)))
        
        # Low Limit
        low_item = self.data_table.item(row, 5)
        if low_item:
            low_item.setText(str(channel_config.get('low_limit', 0)))
        
        # High Limit
        high_item = self.data_table.item(row, 6)
        if high_item:
            high_item.setText(str(channel_config.get('high_limit', 100)))
        
        # Decimal Places
        decimal_item = self.data_table.item(row, 7)
        if decimal_item:
            decimal_item.setText(str(channel_config.get('dec_point', 0)))
        
        # Scale
        scale_item = self.data_table.item(row, 8)
        if scale_item:
            scale_item.setText("Yes" if channel_config.get('scale', False) else "No")
        
        # Update row colors if color changed
        color = channel_config.get('color', "#ffffff")
        color_with_alpha = QtGui.QColor(color)
        color_with_alpha.setAlpha(40)  # Make it more transparent
        
        for col in range(9):
            item = self.data_table.item(row, col)
            if item:
                item.setBackground(color_with_alpha)
    
    def apply_channel_colors(self):
        """Apply channel colors to the respective plots and UI elements"""
        for i in range(1, 15):
            channel_config = self.channels_config.get(i, {})
            color = channel_config.get('color', self.get_default_color(i))
            channel_name = f"ch{i}"
            
            # Update plot color
            if channel_name in self.visualization.plots:
                plot_data = self.visualization.plots.get(channel_name)
                if plot_data and 'curve' in plot_data:
                    pen = pg.mkPen(color=color, width=2)
                    plot_data['curve'].setPen(pen)
            
            # Update CH label color in info area
            if i in self.channel_info_widgets:
                ch_label = self.channel_info_widgets[i].get('ch_label')
                if ch_label:
                    ch_label.setStyleSheet(f"color: {color};")
            
            # Update table row
            if self.tab_widget.currentIndex() == 1:
                self.update_table_row(i)
                
    def get_default_color(self, channel_number):
        """Get a default color based on channel type"""
        if channel_number <= 8:  # Vacuum Gauges (CH1-CH8)
            return "#3498db"  # Blue
        elif channel_number <= 12:  # Temperature (CH9-CH12)
            return "#e74c3c"  # Red
        else:  # Pressure & System Vacuum (CH13-CH14)
            return "#2ecc71"  # Green
