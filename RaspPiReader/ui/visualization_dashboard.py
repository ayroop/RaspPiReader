from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import numpy as np
import os
from ..libs.visualization import LiveDataVisualization

class VisualizationDashboard(QtWidgets.QWidget):
    """
    A dashboard for displaying real-time PLC data visualizations.
    Supports multiple visualization types and layouts.
    """
    
    def __init__(self, parent=None):
        super(VisualizationDashboard, self).__init__(parent)
        self.visualization = LiveDataVisualization(update_interval_ms=100)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the dashboard UI components"""
        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title_label = QtWidgets.QLabel("Live PLC Data Visualization")
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
        
        # Visualization grid
        self.grid_layout = QtWidgets.QGridLayout()
        self.create_visualization_grid()
        self.main_layout.addLayout(self.grid_layout)
        
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
        """Create the grid of visualization widgets"""
        # Time series plots
        self.temperature_plot = pg.PlotWidget()
        self.pressure_plot = pg.PlotWidget()
        self.flow_plot = pg.PlotWidget()
        self.position_plot = pg.PlotWidget()
        
        # Add plots to visualization engine
        self.visualization.add_time_series_plot(
            self.temperature_plot, 
            "temperature", 
            color="#e74c3c", 
            title="Temperature", 
            y_label="Temperature (°C)"
        )
        
        self.visualization.add_time_series_plot(
            self.pressure_plot, 
            "pressure", 
            color="#3498db", 
            title="Pressure", 
            y_label="Pressure (bar)"
        )
        
        self.visualization.add_time_series_plot(
            self.flow_plot, 
            "flow_rate", 
            color="#2ecc71", 
            title="Flow Rate", 
            y_label="Flow (L/min)"
        )
        
        self.visualization.add_time_series_plot(
            self.position_plot, 
            "position", 
            color="#9b59b6", 
            title="Position", 
            y_label="Position (mm)"
        )
        
        # Add plots to grid
        self.grid_layout.addWidget(self.temperature_plot, 0, 0)
        self.grid_layout.addWidget(self.pressure_plot, 0, 1)
        self.grid_layout.addWidget(self.flow_plot, 1, 0)
        self.grid_layout.addWidget(self.position_plot, 1, 1)
        
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
        
    def update_data(self, parameter_name, value):
        """Update data for a specific parameter"""
        self.visualization.update_data(parameter_name, value)
        
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
        self.status_bar.showMessage("Visualization reset")