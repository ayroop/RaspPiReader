import time
from PyQt5 import QtCore, QtWidgets
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
        self.max_points = 1000  # maximum number of data points to store per channel
        
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
                             line_width=2, title=None, y_label=None, x_label="Time (s)", smooth=False):
        # Initialize data buffer if not exist
        if parameter_name not in self.data_buffers:
            self.data_buffers[parameter_name] = {'timestamps': [], 'values': []}
        
        # Configure plot widget
        plot_widget.setBackground('w')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.enableAutoRange()
        
        # Set axis labels if provided
        if y_label:
            plot_widget.setLabel('left', y_label)
        if x_label:
            plot_widget.setLabel('bottom', x_label)
        
        # Configure pen with the specified color and width
        pen = pg.mkPen(color=color, width=line_width)
        
        # Create the plot curve with the specified title
        plot_curve = plot_widget.plot([], [], pen=pen, name=title)
        
        # Store plot configuration
        self.plots[parameter_name] = {
            'widget': plot_widget,
            'curve': plot_curve,
            'smooth': smooth,
            'color': color,
            'title': title,
            'y_label': y_label,
            'x_label': x_label
        }
        
        return plot_curve  # Return the plot curve item
    
    def smooth_data(self, data, window=5):
        if len(data) >= window:
            return np.convolve(data, np.ones(window)/window, mode='valid')
        return data
    
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
        buffer = self.data_buffers[parameter_name]
        buffer['timestamps'].append(current_time)
        buffer['values'].append(value)
        
        # Limit buffer size to self.max_points
        if len(buffer['timestamps']) > self.max_points:
            buffer['timestamps'] = buffer['timestamps'][-self.max_points:]
            buffer['values'] = buffer['values'][-self.max_points:]
        
    def update_plots(self):
        """Update all plot visualizations with the latest data"""
        if not self.active:
            return
        for param_name, plot_info in self.plots.items():
            if param_name not in self.data_buffers:
                continue
            timestamps = self.data_buffers[param_name]['timestamps']
            values = self.data_buffers[param_name]['values']
            if not timestamps or not values:
                continue
            # If smoothing is enabled use the moving average
            if plot_info.get('smooth'):
                smoothed = self.smooth_data(values)
                # Adjust timestamps to match the smoothed data length
                ts = timestamps[-len(smoothed):]
                plot_info['curve'].setData(ts, smoothed)
            else:
                plot_info['curve'].setData(timestamps, values)
    
    def export_chart_image(self, plot_widget, save_path):
        """
        Export the given plot widget as an image saved to save_path.
        Returns True if export succeeded.
        
        This method now uses pyqtgraph's ImageExporter to capture the complete plot,
        including axis labels and all graphics items, to ensure a proper final report image.
        """
        try:
            from pyqtgraph.exporters import ImageExporter
            # Process any pending GUI events to guarantee all rendering is complete
            QtCore.QCoreApplication.processEvents()
            
            # Get the plot item
            plot_item = plot_widget.getPlotItem()
            
            # Create a temporary scene to capture both axes
            scene = QtWidgets.QGraphicsScene()
            
            # Add the main plot item to the scene
            scene.addItem(plot_item)
            
            # If there's a right axis view box, add it to the scene
            if hasattr(plot_widget, 'right_vb'):
                scene.addItem(plot_widget.right_vb)
            
            # Create exporter with the scene
            exporter = ImageExporter(scene)
            
            # Set exporter parameters
            exporter.parameters()['width'] = plot_widget.width()
            exporter.parameters()['height'] = plot_widget.height()
            exporter.parameters()['antialias'] = True
            
            # Export the image
            exporter.export(save_path)
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error exporting chart image: {e}")
            return False
        
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
                    try:
                        idx = param_data['timestamps'].index(timestamp)
                        value = param_data['values'][idx]
                    except ValueError:
                        value = ''  # No data for this timestamp
                    row.append(value)
                writer.writerow(row)
                
        return True
