from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import numpy as np
import os
from ..libs.visualization import LiveDataVisualization
from ..libs.models import ChannelConfigSettings, BooleanAddress
from RaspPiReader.libs.plc_communication import read_boolean
from ..libs.database import Database
from .. import pool
import logging

logger = logging.getLogger(__name__)

class VisualizationDashboard(QtWidgets.QWidget):
    """
    A dashboard for displaying real-time PLC data visualizations.
    Supports all 14 CH channels with customizable display properties.
    """
    
    def __init__(self, parent=None):
        super(VisualizationDashboard, self).__init__(parent)
        self.visualization = LiveDataVisualization(update_interval_ms=100)
        self.boolean_visualization = LiveDataVisualization(update_interval_ms=100)
        self.channels_config = {}
        self.boolean_config = {}   
        self.plots = {}
        self.channel_info_widgets = {}   
        self.db = Database("sqlite:///local_database.db")
        self.visualization_active = False
        self.load_channel_config()
        self.setup_ui()
        
    def load_channel_config(self):
        """Load numeric channel configurations and Boolean address settings from the database"""
        try:
            # Load numeric channel configurations (CH1-CH14)
            for i in range(1, 15):
                channel = self.db.session.query(ChannelConfigSettings).filter_by(id=i).first()
                if channel:
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
                        'axis_direction': channel.axis_direction if hasattr(channel, 'axis_direction') else 'L',
                        'color': channel.color if hasattr(channel, 'color') else self.get_default_color(i),
                        'active': channel.active if hasattr(channel, 'active') else True,
                        'min_scale_range': channel.min_scale_range if hasattr(channel, 'min_scale_range') else 0,
                        'max_scale_range': channel.max_scale_range if hasattr(channel, 'max_scale_range') else 100
                    }
                else:
                    # Create default configuration for missing channels
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
                        'axis_direction': 'L',
                        'color': self.get_default_color(i),
                        'active': True,
                        'min_scale_range': 0,
                        'max_scale_range': 100
                    }
                    # Create and save the channel in the database
                    new_channel = ChannelConfigSettings(
                        id=i,
                        address=100 + i,
                        label=f"Channel {i}",
                        pv=0,
                        sv=0,
                        set_point=0,
                        limit_low=0,
                        limit_high=100,
                        decimal_point=0,
                        scale=False,
                        axis_direction='L',
                        color=self.get_default_color(i),
                        active=True,
                        min_scale_range=0,
                        max_scale_range=100
                    )
                    self.db.session.add(new_channel)
            
            self.db.session.commit()
            
            # Load Boolean address configurations (limit to 6)
            boolean_entries = self.db.session.query(BooleanAddress).all()
            if boolean_entries:
                for entry in boolean_entries[:6]:
                    idx = entry.id
                    self.boolean_config[idx] = {
                        'id': idx,
                        'address': entry.address,
                        'label': entry.label
                    }
            else:
                # Fallback defaults for 6 Boolean addresses
                for i in range(1, 7):
                    self.boolean_config[i] = {
                        'id': i,
                        'address': 400 + i,
                        'label': f"LA {i}"
                    }
        except Exception as e:
            print(f"Error loading channel config: {e}")
            # Fallback for numeric channels
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
                    'axis_direction': 'L',
                    'color': self.get_default_color(i),
                    'active': True,
                    'min_scale_range': 0,
                    'max_scale_range': 100
                }
            # Fallback for Boolean addresses
            for i in range(1, 7):
                self.boolean_config[i] = {
                    'id': i,
                    'address': 400 + i,
                    'label': f"LA {i}"
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
        """Setup the dashboard UI components with four tabs: Combined Plot, Plot View, Boolean Data, and Table View"""
        self.main_layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title_label = QtWidgets.QLabel("Live PLC Data Visualization - 14 CH Monitor")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2c3e50;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(title_label)
        
        # Control panel (cycle time, pause, export, etc.)
        self.control_panel = QtWidgets.QHBoxLayout()
        self.cycle_time_label = QtWidgets.QLabel("Cycle Time: 00:00:00")
        self.cycle_time_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #3498db;")
        self.control_panel.addWidget(self.cycle_time_label)
        self.control_panel.addStretch()
        self.btn_pause = QtWidgets.QPushButton("Pause")
        self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.control_panel.addWidget(self.btn_pause)
        self.btn_export = QtWidgets.QPushButton("Export Data")
        self.btn_export.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        self.btn_export.clicked.connect(self.handle_export)
        self.control_panel.addWidget(self.btn_export)
        self.main_layout.addLayout(self.control_panel)
        
        # Tab widget for visualization views
        self.tab_widget = QtWidgets.QTabWidget()
        
        # Combined Plot tab for all 14 channels in one chart
        self.combined_tab = QtWidgets.QWidget()
        self.combined_layout = QtWidgets.QVBoxLayout(self.combined_tab)
        self.combined_plot_widget = pg.PlotWidget()
        self.combined_plot_widget.setBackground('w')
        self.combined_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.combined_plot_widget.enableAutoRange(axis='x')  # Only auto-range x-axis
        self.combined_plot_widget.addLegend()
        
        # Show both left and right axes for combined plot
        self.combined_plot_widget.showAxis('left')
        self.combined_plot_widget.showAxis('right')
        self.combined_plot_widget.setLabel('left', 'Left Axis Values')
        self.combined_plot_widget.setLabel('right', 'Right Axis Values')
        self.combined_plot_widget.setLabel('bottom', 'Time (s)')
        
        # Set fixed ranges for left and right axes
        self.combined_plot_widget.setYRange(-150, 800, padding=0)  # Left axis range
        self.combined_plot_widget.enableAutoRange(axis='y', enable=False)  # Best practice: keep left axis fixed
        
        # Create a second view box for the right axis
        self.right_vb = pg.ViewBox()
        self.combined_plot_widget.scene().addItem(self.right_vb)
        self.combined_plot_widget.getAxis('right').linkToView(self.right_vb)
        self.right_vb.setXLink(self.combined_plot_widget)
        self.right_vb.setYRange(0, 140, padding=0)  # Right axis range
        
        # Update views when resized
        def updateViews():
            self.right_vb.setGeometry(self.combined_plot_widget.getViewBox().sceneBoundingRect())
            self.right_vb.linkedViewChanged(self.combined_plot_widget.getViewBox(), self.right_vb.XAxis)
        
        updateViews()
        self.combined_plot_widget.getViewBox().sigResized.connect(updateViews)
        
        self.combined_layout.addWidget(self.combined_plot_widget)
        # Create a separate LiveDataVisualization instance for combined view
        self.combined_visualization = LiveDataVisualization(update_interval_ms=100)
        # For each channel, add a curve with smoothing enabled
        for i in range(1, 15):
            channel_name = f"ch{i}"
            channel_config = self.channels_config.get(i, {})
            color = channel_config.get('color', self.get_default_color(i))
            label = channel_config.get('label', f"Channel {i}")
            axis_direction = channel_config.get('axis_direction', 'L')
            
            # Add the plot with proper axis configuration
            plot_curve = self.combined_visualization.add_time_series_plot(
                self.combined_plot_widget,
                channel_name,
                color=color,
                line_width=2,
                title=f"{label} ({axis_direction})",
                y_label=None,  # We'll handle axis labels separately
                x_label=None,  # We'll handle axis labels separately
                smooth=True
            )
            
            # Configure axis for this channel based on axis_direction
            if axis_direction == 'R':
                self.right_vb.addItem(plot_curve)
                self.combined_plot_widget.setLabel('right', 'Right Axis Values')
            else:
                self.combined_plot_widget.addItem(plot_curve)
                self.combined_plot_widget.setLabel('left', 'Left Axis Values')
        
        # Plot View tab (existing code, create grid for individual plots)
        self.plot_tab = QtWidgets.QWidget()
        self.plot_layout = QtWidgets.QVBoxLayout(self.plot_tab)
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.plot_grid_widget = QtWidgets.QWidget()
        self.plot_grid_layout = QtWidgets.QGridLayout(self.plot_grid_widget)
        self.create_visualization_grid()  # existing function to create CH1–CH14 plots
        self.main_splitter.addWidget(self.plot_grid_widget)
        self.main_splitter.setSizes([700, 300])
        self.plot_layout.addWidget(self.main_splitter)
        
        # Boolean Data tab (existing code)
        self.boolean_tab = QtWidgets.QWidget()
        self.boolean_layout = QtWidgets.QGridLayout(self.boolean_tab)
        row, col = 0, 0
        for idx in sorted(self.boolean_config.keys()):
            config = self.boolean_config[idx]
            plot_widget = pg.PlotWidget()
            plot_widget.setBackground('w')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.enableAutoRange()
            plot_widget.setYRange(-0.2, 1.2)
            title = f"{config['label']} (Addr {config['address']})"
            color = "#FF0000"
            key = f"bool{idx}"
            self.boolean_visualization.add_time_series_plot(plot_widget, key, color=color, title=title, y_label="Value")
            self.boolean_layout.addWidget(plot_widget, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        # Table View tab (existing code)
        self.table_tab = QtWidgets.QWidget()
        self.table_layout = QtWidgets.QVBoxLayout(self.table_tab)
        self.create_table_view()
        
        # Add tabs in desired order
        self.tab_widget.addTab(self.combined_tab, "Combined Plot")
        self.tab_widget.addTab(self.plot_tab, "Plot View")
        self.tab_widget.addTab(self.boolean_tab, "Boolean Data")
        self.tab_widget.addTab(self.table_tab, "Table View")
        self.main_layout.addWidget(self.tab_widget)
        
        # Status bar and timer for cycle time
        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.showMessage("Ready")
        self.main_layout.addWidget(self.status_bar)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_cycle_time)
        self.cycle_start_time = None
        self.paused = False

    def handle_export(self):
        """Export the combined plot to a PNG file and update the HTML report template."""
        export_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        export_path = os.path.join(export_dir, "plot_export.png")
        
        # Store current view ranges
        left_range = self.combined_plot_widget.getViewBox().viewRange()
        right_range = self.right_vb.viewRange() if hasattr(self, 'right_vb') else None
        
        # Ensure both view boxes are properly sized
        if hasattr(self, 'right_vb'):
            self.right_vb.setGeometry(self.combined_plot_widget.getViewBox().sceneBoundingRect())
            self.right_vb.linkedViewChanged(self.combined_plot_widget.getViewBox(), self.right_vb.XAxis)
            
            # Set fixed ranges for export
            self.combined_plot_widget.setYRange(-150, 800, padding=0)  # Left axis range
            self.right_vb.setYRange(0, 140, padding=0)  # Right axis range
        
        # Export the plot
        if self.combined_visualization.export_chart_image(self.combined_plot_widget, export_path):
            # Restore view ranges
            self.combined_plot_widget.getViewBox().setRange(xRange=left_range[0], yRange=left_range[1])
            if right_range and hasattr(self, 'right_vb'):
                self.right_vb.setRange(xRange=right_range[0], yRange=right_range[1])
            
            QtWidgets.QMessageBox.information(
                self, "Export Success", f"Chart image exported to:\n{export_path}"
            )
            template_path = os.path.join(os.path.dirname(__file__), "result_template.html")
            self.update_report_template(template_path, export_path)
        else:
            QtWidgets.QMessageBox.warning(self, "Export Failed", "Failed to export chart image.")

    def update_report_template(self, template_path, image_path):
        """Updates the HTML report template so that the exported image is shown.
        
        The template should contain the marker <!-- PLOT_IMAGE_PLACEHOLDER -->.
        """
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Insert an <img> tag with the exported PNG image
            img_tag = f'<img src="{image_path}" alt="PLC Combined Plot" width="100%"/>'
            new_content = content.replace("<!-- PLOT_IMAGE_PLACEHOLDER -->", img_tag)
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error updating report template: {e}")

    def create_visualization_grid(self):
        """Create the grid of plots for numeric channels (CH1–CH14)"""
        rows, cols = 4, 4  # 4x4 grid
        for i in range(1, 15):
            row = (i - 1) // cols
            col = (i - 1) % cols
            channel_config = self.channels_config.get(i, {})
            channel_name = f"ch{i}"
            plot_widget = pg.PlotWidget()
            
            # Set title and labels
            title = channel_config.get('label', f"Channel {i}")
            color = channel_config.get('color', self.get_default_color(i))
            axis_direction = channel_config.get('axis_direction', 'L')
            
            # Set Y-range based on axis direction
            if axis_direction == 'R':
                plot_widget.setYRange(0, 140, padding=0)
            else:
                plot_widget.setYRange(-150, 800, padding=0)
            
            # Configure axis labels based on channel configuration
            y_label = f"{title} ({axis_direction})"
            
            # Add the plot with proper axis configuration
            self.visualization.add_time_series_plot(
                plot_widget, 
                channel_name, 
                color=color, 
                title=title, 
                y_label=y_label,
                x_label="Time (s)"
            )
            
            # Show the appropriate axis based on configuration
            if axis_direction == 'R':
                plot_widget.showAxis('right')
                plot_widget.setLabel('right', y_label)
                plot_widget.hideAxis('left')
                plot_widget.setLabel('left', '')
            else:
                plot_widget.showAxis('left')
                plot_widget.setLabel('left', y_label)
                plot_widget.hideAxis('right')
                plot_widget.setLabel('right', '')
            
            # Add channel label
            label = QtWidgets.QLabel(f"CH{i}")
            label.setStyleSheet(f"color: {color}; font-weight: bold;")
            label.setAlignment(QtCore.Qt.AlignCenter)
            
            # Create a container widget for the plot and label
            container = QtWidgets.QWidget()
            container_layout = QtWidgets.QVBoxLayout(container)
            container_layout.addWidget(label)
            container_layout.addWidget(plot_widget)
            
            self.plots[channel_name] = plot_widget
            self.plot_grid_layout.addWidget(container, row, col)
    
    def create_table_view(self):
        """Create a table view for numeric channel data (existing code)"""
        self.data_table = QtWidgets.QTableWidget()
        self.data_table.setColumnCount(12)
        self.data_table.setRowCount(14)
        headers = ["CH", "Address", "Label", "PV", "SV", "Set Point", "Low Limit", "High Limit", "Decimal", "Scale", "Axis", "Color"]
        self.data_table.setHorizontalHeaderLabels(headers)
        for i in range(1, 15):
            channel_config = self.channels_config.get(i, {})
            self.data_table.setItem(i-1, 0, QtWidgets.QTableWidgetItem(f"CH{i}"))
            self.data_table.setItem(i-1, 1, QtWidgets.QTableWidgetItem(str(channel_config.get('address', ''))))
            self.data_table.setItem(i-1, 2, QtWidgets.QTableWidgetItem(channel_config.get('label', f"Channel {i}")))
            self.data_table.setItem(i-1, 3, QtWidgets.QTableWidgetItem("0.0"))
            self.data_table.setItem(i-1, 4, QtWidgets.QTableWidgetItem(str(channel_config.get('sv', 0))))
            self.data_table.setItem(i-1, 5, QtWidgets.QTableWidgetItem(str(channel_config.get('set_point', 0))))
            self.data_table.setItem(i-1, 6, QtWidgets.QTableWidgetItem(str(channel_config.get('limit_low', 0))))
            self.data_table.setItem(i-1, 7, QtWidgets.QTableWidgetItem(str(channel_config.get('limit_high', 100))))
            self.data_table.setItem(i-1, 8, QtWidgets.QTableWidgetItem(str(channel_config.get('decimal_point', 0))))
            self.data_table.setItem(i-1, 9, QtWidgets.QTableWidgetItem("Yes" if channel_config.get('scale', False) else "No"))
            self.data_table.setItem(i-1, 10, QtWidgets.QTableWidgetItem(channel_config.get('axis_direction', 'normal')))
            color_item = QtWidgets.QTableWidgetItem(channel_config.get('color', self.get_default_color(i)))
            color_item.setBackground(QtGui.QColor(channel_config.get('color', self.get_default_color(i))))
            self.data_table.setItem(i-1, 11, color_item)
        self.table_layout.addWidget(self.data_table)
        
    def start_visualization(self):
        """Start numeric and Boolean visualization and cycle timer"""
        self.visualization.start_visualization()
        self.boolean_visualization.start_visualization()  # <-- Start Boolean updates
        if hasattr(self, 'combined_visualization'):
            self.combined_visualization.start_visualization()
        self.cycle_start_time = QtCore.QDateTime.currentDateTime()
        self.timer.start(1000)
        self.btn_pause.setText("Pause")
        self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
        self.paused = False
        self.status_bar.showMessage("Visualization started")
        if not hasattr(self, "boolean_timer"):
            self.boolean_timer = QtCore.QTimer(self)
            self.boolean_timer.timeout.connect(self.update_all_boolean_data)
            self.boolean_timer.start(100)  # update every 100 ms
        self.visualization_active = True
        
    def stop_visualization(self):
        """Stop visualization and timer"""
        self.visualization.stop_visualization()
        self.boolean_visualization.stop_visualization()
        if hasattr(self, 'combined_visualization'):
            self.combined_visualization.stop_visualization()
        if hasattr(self, 'timer'):
            self.timer.stop()
        self.cycle_start_time = None
        self.btn_pause.setText("Pause")
        self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
        self.paused = False
        self.status_bar.showMessage("Visualization stopped")
        self.visualization_active = False
        
    def update_data(self, channel_number, value):
        """
        Update numeric channel data.
        Args:
            channel_number: 1-14 for numeric channels
            value: Current numeric value
        """
        if not self.visualization_active:
            return
        if channel_number < 1 or channel_number > 14:
            return
        channel_config = self.channels_config.get(channel_number, {})
        decimal_places = channel_config.get('decimal_point', 0)
        # Handle negative numbers (convert from unsigned to signed if needed)
        if value > 32767:  # If value is in unsigned range
            value = value - 65536  # Convert to signed 16-bit integer
        if channel_config.get('scale', False):
            low_limit = channel_config.get('limit_low', 0)
            high_limit = channel_config.get('limit_high', 100)
            min_range = channel_config.get('min_scale_range', low_limit)
            max_range = channel_config.get('max_scale_range', high_limit)
            if high_limit != low_limit and max_range != min_range:
                value = min_range + ((value - low_limit) * (max_range - min_range)) / (high_limit - low_limit)
        formatted_value = f"{value:.{decimal_places}f}"
        logger.debug(f"update_data: CH{channel_number} value={value} formatted={formatted_value}")
        channel_name = f"ch{channel_number}"
        
        # Update individual plot
        if channel_name in self.visualization.plots:
            self.visualization.update_data(channel_name, value)
        # Update combined plot
        if hasattr(self, 'combined_visualization') and channel_name in self.combined_visualization.plots:
            axis_direction = channel_config.get('axis_direction', 'L')
            self.combined_visualization.update_data(channel_name, value)
            if axis_direction == 'R':
                self.combined_plot_widget.setLabel('right', 'Right Axis Values')
            else:
                self.combined_plot_widget.setLabel('left', 'Left Axis Values')
        
        # Update channel info display
        if channel_number in self.channel_info_widgets:
            self.channel_info_widgets[channel_number]['pv'].setText(formatted_value)
        
        # Update table view if visible
        if self.tab_widget.currentIndex() == 2:
            pv_item = self.data_table.item(channel_number-1, 3)
            if pv_item:
                pv_item.setText(formatted_value)
        
        try:
            channel = self.db.session.query(ChannelConfigSettings).filter_by(id=channel_number).first()
            if channel:
                channel.pv = value
                self.db.session.commit()
        except Exception as e:
            print(f"Error updating channel PV in database: {e}")
            
    
    def update_boolean_data(self, bool_index, value):
        """
        Update a single Boolean address visualization.
        
        Args:
            bool_index: Boolean address index (corresponding to a key in self.boolean_config)
            value: Boolean value (True/False)
        """
        key = f"bool{bool_index}"
        # If value is None or False, default to 0, else 1 for True
        self.boolean_visualization.update_data(key, 1 if value else 0)

    def update_all_boolean_data(self):
        """
        Loop through each Boolean configuration, retrieve its value dynamically, and update the visualization.
        """
        for bool_index, config in self.boolean_config.items():
            # Retrieve the boolean value dynamically 
            value = self.get_boolean_value(config)
            self.update_boolean_data(bool_index, value)

    def get_boolean_value(self, config):
        """
        Retrieve the current boolean value for the given configuration.
        
        Args:
            config: A dict containing the Boolean address settings. It must include an 'address' key.
        
        Returns:
            bool: True if ON, False if OFF.
        """
        try:
            # Attempt to read Boolean value from PLC.
            from RaspPiReader.libs.plc_communication import read_boolean  # adjust import as needed
            address = config.get('address')
            if address is not None:
                value = read_boolean(address)
                if value is not None:
                    return value
                else:
                    # Log the error and return a default value (e.g., False)
                    print(f"Error reading boolean from address {address}, returning False")
                    return False
        except Exception as e:
            # Log the exception and fall back to a default value
            print(f"Error reading boolean: {e}")
            return False
        # Default to False if no valid address is provided
        return False
        
    def update_channel_settings(self, channel_number, settings):
        """
        Update numeric channel settings and immediately reflect changes in visualization.
        """
        if channel_number < 1 or channel_number > 14 or not settings:
            return
        # Update local configuration
        self.channels_config[channel_number].update(settings)
        try:
            # Update database
            channel = self.db.session.query(ChannelConfigSettings).filter_by(id=channel_number).first()
            if channel:
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
                
                direct_fields = ['address', 'pv', 'sv', 'scale', 'color']
                for field in direct_fields:
                    if field in settings:
                        setattr(channel, field, settings[field])
                
                additional_fields = ['axis_direction', 'active', 'min_scale_range', 'max_scale_range']
                for field in additional_fields:
                    if field in settings:
                        setattr(channel, field, settings[field])
                
                self.db.session.commit()
                
                # Update pool configuration
                for key, value in settings.items():
                    pool.set_config(f'channel_{channel_number}_{key}', value)
                
                # Update visualization immediately
                channel_name = f"ch{channel_number}"
                # Update individual plot
                if channel_name in self.visualization.plots:
                    plot_data = self.visualization.plots.get(channel_name)
                    if plot_data and 'curve' in plot_data:
                        if 'color' in settings:
                            pen = pg.mkPen(color=settings['color'], width=2)
                            plot_data['curve'].setPen(pen)
                        if 'axis_direction' in settings:
                            self.update_plot_axis(channel_number, settings['axis_direction'])
                            # Move curve to correct axis
                            plot_widget = plot_data['widget']
                            y_label = f"{self.channels_config[channel_number].get('label', f'Channel {channel_number}')} ({settings['axis_direction']})"
                            if settings['axis_direction'] == 'R':
                                plot_widget.showAxis('right')
                                plot_widget.setLabel('right', y_label)
                                plot_widget.hideAxis('left')
                                plot_widget.setLabel('left', '')
                            else:
                                plot_widget.showAxis('left')
                                plot_widget.setLabel('left', y_label)
                                plot_widget.hideAxis('right')
                                plot_widget.setLabel('right', '')
                # Update combined plot
                if hasattr(self, 'combined_visualization') and channel_name in self.combined_visualization.plots:
                    combined_plot = self.combined_visualization.plots.get(channel_name)
                    if combined_plot and 'curve' in combined_plot:
                        if 'color' in settings:
                            combined_pen = pg.mkPen(color=settings['color'], width=2)
                            combined_plot['curve'].setPen(combined_pen)
                        if 'axis_direction' in settings:
                            # Remove curve from both axes first
                            try:
                                self.combined_plot_widget.removeItem(combined_plot['curve'])
                            except Exception:
                                pass
                            try:
                                self.right_vb.removeItem(combined_plot['curve'])
                            except Exception:
                                pass
                            # Add to correct axis
                            if settings['axis_direction'] == 'R':
                                self.right_vb.addItem(combined_plot['curve'])
                                self.combined_plot_widget.setLabel('right', 'Right Axis Values')
                            else:
                                self.combined_plot_widget.addItem(combined_plot['curve'])
                                self.combined_plot_widget.setLabel('left', 'Left Axis Values')
                # Update channel info display
                if channel_number in self.channel_info_widgets:
                    widgets = self.channel_info_widgets[channel_number]
                    for key, value in settings.items():
                        if key in widgets:
                            if key == 'scale':
                                widgets[key].setText("Yes" if value else "No")
                            else:
                                widgets[key].setText(str(value))
                
                # Update table view if visible
                if self.tab_widget.currentIndex() == 1:
                    self.update_table_row(channel_number)
                
                # Force immediate update of all visualizations
                self.apply_channel_colors()
                self.update_plots()
                
                self.status_bar.showMessage(f"Updated settings for CH{channel_number}")
                
        except Exception as e:
            print(f"Error updating channel settings in database: {e}")
            self.status_bar.showMessage(f"Error updating settings for CH{channel_number}: {e}")
            
    def update_plot_axis(self, channel_number, axis_direction):
        """Update the plot axis configuration for a channel."""
        channel_name = f"ch{channel_number}"
        if channel_name in self.plots:
            plot_widget = self.plots[channel_name]
            y_label = f"{self.channels_config[channel_number].get('label', f'Channel {channel_number}')} ({axis_direction})"
            if axis_direction == 'R':
                plot_widget.showAxis('right')
                plot_widget.setLabel('right', y_label)
                plot_widget.hideAxis('left')
                plot_widget.setLabel('left', '')
            else:
                plot_widget.showAxis('left')
                plot_widget.setLabel('left', y_label)
                plot_widget.hideAxis('right')
                plot_widget.setLabel('right', '')

    def update_cycle_time(self):
        """Update the cycle time display"""
        if not self.cycle_start_time or self.paused:
            return
        current_time = QtCore.QDateTime.currentDateTime()
        elapsed = self.cycle_start_time.secsTo(current_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        self.cycle_time_label.setText(f"Cycle Time: {hours:02d}:{minutes:02d}:{seconds:02d}")
        
    def toggle_pause(self):
        """Pause or resume the visualization"""
        if self.paused:
            self.visualization.start_visualization()
            self.timer.start(1000)
            self.btn_pause.setText("Pause")
            self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
            self.status_bar.showMessage("Visualization resumed")
        else:
            self.visualization.stop_visualization()
            self.timer.stop()
            self.btn_pause.setText("Resume")
            self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
            self.status_bar.showMessage("Visualization paused")
        self.paused = not self.paused

    def update_plots(self):
        """Update all plots (individual and combined) with the latest data"""
        self.visualization.update_plots()
        if hasattr(self, 'combined_visualization'):
            self.combined_visualization.update_plots()
            # Best practice: re-apply fixed left axis scale after updates
            self.combined_plot_widget.setYRange(-150, 800, padding=0)
            self.combined_plot_widget.enableAutoRange(axis='y', enable=False)
            # Set axis labels if any channel is active on that axis
            left_active = any(cfg.get('axis_direction', 'L') == 'L' and cfg.get('active', True) for cfg in self.channels_config.values())
            right_active = any(cfg.get('axis_direction', 'L') == 'R' and cfg.get('active', True) for cfg in self.channels_config.values())
            if left_active:
                self.combined_plot_widget.setLabel('left', 'Left Axis Values')
            else:
                self.combined_plot_widget.setLabel('left', '')
            if right_active:
                self.combined_plot_widget.setLabel('right', 'Right Axis Values')
            else:
                self.combined_plot_widget.setLabel('right', '')

    def export_data(self):
        """Export visualization data to CSV"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Visualization Data", "", "CSV Files (*.csv);;All Files (*)")
        if file_path:
            success = self.visualization.export_data(file_path)
            self.status_bar.showMessage(f"Data exported to {file_path}" if success else "Failed to export data")
                
    
    def reset(self):
        """Reset the visualization dashboard"""
        self.stop_visualization()
        self.visualization.reset_data()
        if hasattr(self, 'combined_visualization'):
            self.combined_visualization.reset_data()
            self.combined_visualization.update_plots()
            self.combined_plot_widget.setLabel('left', '')
            self.combined_plot_widget.setLabel('right', '')
        self.cycle_time_label.setText("Cycle Time: 00:00:00")
        for channel_number, widgets in self.channel_info_widgets.items():
            widgets['pv'].setText("0.0")
        if self.tab_widget.currentIndex() == 1:
            for i in range(1, 15):
                pv_item = self.data_table.item(i-1, 2)
                if pv_item:
                    pv_item.setText("0.0")
        self.status_bar.showMessage("Visualization reset")
        self.visualization_active = False
        
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
            
            # Update plot color for individual plots
            if channel_name in self.visualization.plots:
                plot_data = self.visualization.plots.get(channel_name)
                if plot_data and 'curve' in plot_data:
                    pen = pg.mkPen(color=color, width=2)
                    plot_data['curve'].setPen(pen)
            
            # Update plot color for combined plot curves
            if hasattr(self, 'combined_visualization') and channel_name in self.combined_visualization.plots:
                combined_plot = self.combined_visualization.plots.get(channel_name)
                if combined_plot and 'curve' in combined_plot:
                    combined_pen = pg.mkPen(color=color, width=2)
                    combined_plot['curve'].setPen(combined_pen)
            
            # Update CH label color in info area
            if i in self.channel_info_widgets:
                ch_label = self.channel_info_widgets[i].get('ch_label')
                if ch_label:
                    ch_label.setStyleSheet(f"color: {color};")
            
            # Update table row if needed
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

    def setup_combined_plot(self):
        """Setup the combined plot with fixed axis scales for left and right axes, and ensure right axis channels use 0-140 scale."""
        # ... existing code to create the combined plot ...
        # Enforce fixed axis scales
        self.combined_plot_widget.setYRange(-150, 800, padding=0)  # Left axis
        if hasattr(self.combined_plot_widget, 'getAxis'):
            right_axis = self.combined_plot_widget.getAxis('right')
            if right_axis:
                # Set right axis scale to 0-140
                self.combined_plot_widget.getViewBox().setYRange(0, 140, padding=0)
        # For each channel, ensure right axis channels are plotted on the right with correct scale
        for ch_num, config in self.channels_config.items():
            if config.get('axis_direction', 'L').strip().upper() == 'R':
                # Plot on right axis, ensure scale is 0-140
                # (If using custom ViewBox, set its range here)
                pass  # Actual plotting code would go here
        # ... rest of setup ...
