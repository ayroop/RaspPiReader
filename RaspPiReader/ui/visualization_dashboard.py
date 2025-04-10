
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import numpy as np
import os
from ..libs.visualization import LiveDataVisualization
from ..libs.models import ChannelConfigSettings, BooleanAddress
from RaspPiReader.libs.plc_communication import read_boolean
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
        self.boolean_visualization = LiveDataVisualization(update_interval_ms=100)
        self.channels_config = {}
        self.boolean_config = {}   
        self.plots = {}
        self.channel_info_widgets = {}   
        self.db = Database("sqlite:///local_database.db")
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
                        'axis_direction': channel.axis_direction if hasattr(channel, 'axis_direction') else 'normal',
                        'color': channel.color if hasattr(channel, 'color') else self.get_default_color(i),
                        'active': channel.active if hasattr(channel, 'active') else True,
                        'min_scale_range': channel.min_scale_range if hasattr(channel, 'min_scale_range') else 0,
                        'max_scale_range': channel.max_scale_range if hasattr(channel, 'max_scale_range') else 100
                    }
            # Load Boolean address configurations (limit to 6)
            boolean_entries = self.db.session.query(BooleanAddress).all()
            if boolean_entries:
                for entry in boolean_entries[:6]:
                    # Use entry.id as the Boolean index (or assign sequentially)
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
                        'address': 400 + i,  # Example fallback address
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
                    'axis_direction': 'normal',
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
        self.combined_plot_widget.enableAutoRange()
        self.combined_plot_widget.addLegend()
        self.combined_layout.addWidget(self.combined_plot_widget)
        # Create a separate LiveDataVisualization instance for combined view
        self.combined_visualization = LiveDataVisualization(update_interval_ms=100)
        # For each channel, add a curve with smoothing enabled (so the curve updates are not “jumpy” every 2 seconds)
        for i in range(1, 15):
            channel_name = f"ch{i}"
            channel_config = self.channels_config.get(i, {})
            color = channel_config.get('color', self.get_default_color(i))
            label = channel_config.get('label', f"Channel {i}")
            self.combined_visualization.add_time_series_plot(
                self.combined_plot_widget,
                channel_name,
                color=color,
                line_width=2,
                title=label,
                y_label="Value" if i == 1 else None,
                x_label="Time (s)" if i == 1 else None,
                smooth=True  # Enable smoothing for a better visual appearance
            )
        
        # Plot View tab (existing code, create grid for individual plots)
        self.plot_tab = QtWidgets.QWidget()
        self.plot_layout = QtWidgets.QVBoxLayout(self.plot_tab)
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.plot_grid_widget = QtWidgets.QWidget()
        self.plot_grid_layout = QtWidgets.QGridLayout(self.plot_grid_widget)
        self.create_visualization_grid()  # existing function to create CH1–CH14 plots
        self.channel_info_widget = QtWidgets.QWidget()
        self.channel_info_layout = QtWidgets.QVBoxLayout(self.channel_info_widget)
        self.create_channel_info_area()
        self.main_splitter.addWidget(self.plot_grid_widget)
        self.main_splitter.addWidget(self.channel_info_widget)
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
        if self.combined_visualization.export_chart_image(self.combined_plot_widget, export_path):
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
        rows, cols = 4, 4  # 4x4 grid (2 empty spots)
        for i in range(1, 15):
            row = (i - 1) // cols
            col = (i - 1) % cols
            channel_config = self.channels_config.get(i, {})
            channel_name = f"ch{i}"
            plot_widget = pg.PlotWidget()
            title = channel_config.get('label', f"Channel {i}")
            color = channel_config.get('color', self.get_default_color(i))
            # Set Y-range from configuration if available
            plot_widget.setYRange(channel_config.get('min_scale_range', 0),
                                  channel_config.get('max_scale_range', 100))
            self.visualization.add_time_series_plot(plot_widget, channel_name, color=color, title=title, y_label=title)
            self.plots[channel_name] = plot_widget
            self.plot_grid_layout.addWidget(plot_widget, row, col)
    
    def create_channel_info_area(self):
        """Create a scrollable area with channel info (numeric channels)"""
        header_layout = QtWidgets.QHBoxLayout()
        headers = ["CH", "Address", "Label", "PV", "SV", "Set Point", "Low Limit", "High Limit", "Decimal", "Scale", "Axis", "Color"]
        for header_text in headers:
            label = QtWidgets.QLabel(header_text)
            label.setStyleSheet("font-weight: bold;")
            header_layout.addWidget(label)
        self.channel_info_layout.addLayout(header_layout)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        for i in range(1, 15):
            channel_config = self.channels_config.get(i, {})
            row_layout = QtWidgets.QHBoxLayout()
            ch_label = QtWidgets.QLabel(f"CH{i}")
            ch_label.setStyleSheet(f"color: {channel_config.get('color', '#000000')};")
            row_layout.addWidget(ch_label)
            address_label = QtWidgets.QLabel(str(channel_config.get('address', '')))
            row_layout.addWidget(address_label)
            label_label = QtWidgets.QLabel(channel_config.get('label', f"Channel {i}"))
            row_layout.addWidget(label_label)
            pv_label = QtWidgets.QLabel("0.0")
            row_layout.addWidget(pv_label)
            sv_label = QtWidgets.QLabel(str(channel_config.get('sv', 0)))
            row_layout.addWidget(sv_label)
            setpoint_label = QtWidgets.QLabel(str(channel_config.get('set_point', 0)))
            row_layout.addWidget(setpoint_label)
            low_label = QtWidgets.QLabel(str(channel_config.get('limit_low', 0)))
            row_layout.addWidget(low_label)
            high_label = QtWidgets.QLabel(str(channel_config.get('limit_high', 100)))
            row_layout.addWidget(high_label)
            decimal_label = QtWidgets.QLabel(str(channel_config.get('decimal_point', 0)))
            row_layout.addWidget(decimal_label)
            scale_label = QtWidgets.QLabel("Yes" if channel_config.get('scale', False) else "No")
            row_layout.addWidget(scale_label)
            axis_label = QtWidgets.QLabel(channel_config.get('axis_direction', 'normal'))
            row_layout.addWidget(axis_label)
            color_box = QtWidgets.QLabel()
            color_box.setFixedSize(16, 16)
            color = channel_config.get('color', self.get_default_color(i))
            color_box.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
            row_layout.addWidget(color_box)
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
        # NEW: start combined visualization updates
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
        
    def stop_visualization(self):
        """Stop visualization and timer"""
        self.visualization.stop_visualization()
        self.boolean_visualization.stop_visualization()  # <-- Stop Boolean updates
        self.timer.stop()
        self.cycle_start_time = None
        self.btn_pause.setText("Pause")
        self.btn_pause.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
        self.paused = False
        self.status_bar.showMessage("Visualization stopped")
        
    def update_data(self, channel_number, value):
        """
        Update numeric channel data.
        Args:
            channel_number: 1-14 for numeric channels
            value: Current numeric value
        """
        if channel_number < 1 or channel_number > 14:
            return
        channel_config = self.channels_config.get(channel_number, {})
        decimal_places = channel_config.get('decimal_point', 0)
        if channel_config.get('scale', False):
            low_limit = channel_config.get('limit_low', 0)
            high_limit = channel_config.get('limit_high', 100)
            min_range = channel_config.get('min_scale_range', low_limit)
            max_range = channel_config.get('max_scale_range', high_limit)
            if high_limit != low_limit and max_range != min_range:
                value = min_range + ((value - low_limit) * (max_range - min_range)) / (high_limit - low_limit)
        formatted_value = f"{value:.{decimal_places}f}"
        channel_name = f"ch{channel_number}"
        self.visualization.update_data(channel_name, value)
        # NEW: also update combined plot data
        if hasattr(self, 'combined_visualization'):
            self.combined_visualization.update_data(channel_name, value)
        if channel_number in self.channel_info_widgets:
            self.channel_info_widgets[channel_number]['pv'].setText(formatted_value)
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
        Update numeric channel settings (existing code remains unchanged)
        """
        if channel_number < 1 or channel_number > 14 or not settings:
            return
        self.channels_config[channel_number].update(settings)
        try:
            channel = self.db.session.query(ChannelConfigSettings).filter_by(id=channel_number).first()
            if channel:
                field_mapping = {'name': 'label', 'set_point': 'set_point', 'low_limit': 'limit_low', 'high_limit': 'limit_high', 'dec_point': 'decimal_point'}
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
                self.status_bar.showMessage(f"Updated settings for CH{channel_number}")
                if 'color' in settings:
                    channel_name = f"ch{channel_number}"
                    if channel_name in self.visualization.plots:
                        plot_data = self.visualization.plots.get(channel_name)
                        if plot_data and 'curve' in plot_data:
                            pen = pg.mkPen(color=settings['color'], width=2)
                            plot_data['curve'].setPen(pen)
                if channel_number in self.channel_info_widgets:
                    widgets = self.channel_info_widgets[channel_number]
                    for key, value in settings.items():
                        if key in widgets:
                            if key == 'scale':
                                widgets[key].setText("Yes" if value else "No")
                            else:
                                widgets[key].setText(str(value))
                if self.tab_widget.currentIndex() == 2:
                    self.update_table_row(channel_number)
        except Exception as e:
            print(f"Error updating channel settings in database: {e}")
            self.status_bar.showMessage(f"Error updating settings for CH{channel_number}: {e}")
    
    def update_table_row(self, channel_number):
        # (Existing code for table row updating)
        if channel_number < 1 or channel_number > 14:
            return
        channel_config = self.channels_config.get(channel_number, {})
        row = channel_number - 1
        name_item = self.data_table.item(row, 1)
        if name_item:
            name_item.setText(channel_config.get('name', f"Channel {channel_number}"))
        sv_item = self.data_table.item(row, 3)
        if sv_item:
            sv_item.setText(str(channel_config.get('sv', 0)))
        setpoint_item = self.data_table.item(row, 4)
        if setpoint_item:
            setpoint_item.setText(str(channel_config.get('set_point', 0)))
        low_item = self.data_table.item(row, 5)
        if low_item:
            low_item.setText(str(channel_config.get('low_limit', 0)))
        high_item = self.data_table.item(row, 6)
        if high_item:
            high_item.setText(str(channel_config.get('high_limit', 100)))
        decimal_item = self.data_table.item(row, 7)
        if decimal_item:
            decimal_item.setText(str(channel_config.get('dec_point', 0)))
        scale_item = self.data_table.item(row, 8)
        if scale_item:
            scale_item.setText("Yes" if channel_config.get('scale', False) else "No")
        color = channel_config.get('color', "#ffffff")
        color_with_alpha = QtGui.QColor(color)
        color_with_alpha.setAlpha(40)
        for col in range(9):
            item = self.data_table.item(row, col)
            if item:
                item.setBackground(color_with_alpha)
        
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

    # NEW: Delegate method to support external calls to update_plots
    def update_plots(self):
        """
        Delegate update_plots call to the LiveDataVisualization instance.
        This method avoids the attribute error on the VisualizationDashboard object.
        """
        self.visualization.update_plots()
        
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
        # NEW: reset combined visualization data if available
        if hasattr(self, 'combined_visualization'):
            self.combined_visualization.reset_data()
        self.cycle_time_label.setText("Cycle Time: 00:00:00")
        for channel_number, widgets in self.channel_info_widgets.items():
            widgets['pv'].setText("0.0")
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
            
            # Update plot color for individual plots (existing)
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
