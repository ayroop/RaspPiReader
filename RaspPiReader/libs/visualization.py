import time
from PyQt5 import QtCore
import pyqtgraph as pg
import numpy as np
from typing import Dict, List, Any, Optional

class LiveDataVisualization:
    """
    Handles real-time visualization of PLC data during a cycle.
    Provides multiple visualization types and manages data buffering.
    """
    def __init__(self, update_interval_ms=100):
        """
        Initialize the visualization module.
        
        Args:
            update_interval_ms: Update interval in milliseconds
        """
        self.data_buffers = {}  # Store time-series data for each parameter
        self.plots = {}  # Store plot widgets for each visualization
        self.update_interval = update_interval_ms
        self.start_time = None
        self.active = False
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plots)
        
    def start_visualization(self):
        """Start the visualization and data collection"""
        self.active = True
        self.start_time = time.time()
        self.timer.start(self.update_interval)
        
    def stop_visualization(self):
        """Stop the visualization and data collection"""
        self.active = False
        self.timer.stop()
        
    def reset_data(self):
        """Clear all data buffers"""
        for key in self.data_buffers:
            self.data_buffers[key] = {'timestamps': [], 'values': []}
            
    def add_time_series_plot(self, plot_widget, parameter_name, color='#1f77b4', 
                             line_width=2, title=None, y_label=None, x_label="Time (s)"):
        """
        Add a time series plot for a specific parameter.
        
        Args:
            plot_widget: pyqtgraph PlotWidget to use
            parameter_name: Name of the parameter to plot
            color: Line color
            line_width: Line width
            title: Plot title
            y_label: Y-axis label
            x_label: X-axis label
        """
        if parameter_name not in self.data_buffers:
            self.data_buffers[parameter_name] = {'timestamps': [], 'values': []}
            
        # Configure plot
        plot_widget.setBackground('w')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        if title:
            plot_widget.setTitle(title)
        if y_label:
            plot_widget.setLabel('left', y_label)
        if x_label:
            plot_widget.setLabel('bottom', x_label)
        
        # Create plot item
        pen = pg.mkPen(color=color, width=line_width)
        plot_curve = plot_widget.plot([], [], pen=pen)
        
        self.plots[parameter_name] = {
            'widget': plot_widget,
            'curve': plot_curve
        }
    
    def add_gauge_visualization(self, gauge_widget, parameter_name, min_value=0, max_value=100):
        """
        Add a gauge visualization for a specific parameter.
        
        Args:
            gauge_widget: Custom gauge widget or third-party gauge
            parameter_name: Name of the parameter to visualize
            min_value: Minimum value for the gauge
            max_value: Maximum value for the gauge
        """
        if parameter_name not in self.data_buffers:
            self.data_buffers[parameter_name] = {'timestamps': [], 'values': []}
            
        gauge_widget.setMinimum(min_value)
        gauge_widget.setMaximum(max_value)
        
        self.plots[parameter_name] = {
            'widget': gauge_widget,
            'type': 'gauge'
        }
    
    def update_data(self, parameter_name: str, value: float):
        """
        Update the data buffer with a new value.
        
        Args:
            parameter_name: Name of the parameter to update
            value: New value
        """
        if not self.active:
            return
            
        if parameter_name not in self.data_buffers:
            self.data_buffers[parameter_name] = {'timestamps': [], 'values': []}
            
        current_time = time.time() - self.start_time
        self.data_buffers[parameter_name]['timestamps'].append(current_time)
        self.data_buffers[parameter_name]['values'].append(value)
        
    def update_plots(self):
        """Update all plot visualizations with the latest data"""
        if not self.active:
            return
            
        for param_name, plot_data in self.plots.items():
            if param_name not in self.data_buffers:
                continue
                
            # Get data for this parameter
            timestamps = self.data_buffers[param_name]['timestamps']
            values = self.data_buffers[param_name]['values']
            
            if not timestamps or not values:
                continue
                
            # Check plot type and update accordingly
            if 'curve' in plot_data:  # Time series plot
                plot_data['curve'].setData(timestamps, values)
            elif 'type' in plot_data and plot_data['type'] == 'gauge':
                # Update gauge with the latest value
                if values:
                    plot_data['widget'].setValue(values[-1])
    
    def export_data(self, file_path: str):
        """
        Export collected data to a CSV file.
        
        Args:
            file_path: Path to save the CSV file
        """
        import csv
        
        # Prepare all timestamps in a unified list
        all_timestamps = set()
        for param_data in self.data_buffers.values():
            all_timestamps.update(param_data['timestamps'])
        all_timestamps = sorted(all_timestamps)
        
        # Prepare the CSV header
        header = ['timestamp'] + list(self.data_buffers.keys())
        
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            
            # Write each row of data
            for timestamp in all_timestamps:
                row = [timestamp]
                for param_name in self.data_buffers.keys():
                    param_data = self.data_buffers[param_name]
                    # Find the closest value for this timestamp
                    try:
                        idx = param_data['timestamps'].index(timestamp)
                        value = param_data['values'][idx]
                    except ValueError:
                        value = ''  # No data for this timestamp
                    row.append(value)
                writer.writerow(row)
                
        return True