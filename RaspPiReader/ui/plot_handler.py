import pyqtgraph as pg
import numpy as np
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
import logging
import os

logger = logging.getLogger(__name__)

class InitiatePlotWidget:
    """
    A class to handle creating and updating plots for the PLC Integration system.
    This implementation provides better layout management, data handling, and proper cleanup.
    """
    
    def __init__(self, active_channels=None, parent_layout=None, legend_layout=None, headers=None):
        """
        Initialize the plot widget with specified channels, layouts and headers.
        
        Args:
            active_channels (list): List of active channel numbers (e.g. [1, 2, 3])
            parent_layout (QLayout): Layout to add the plot widget to
            legend_layout (QLayout): Layout to add the legend widget to
            headers (list): List of header texts for the plot
        """
        self.active_channels = active_channels or []
        self.headers = headers or []
        self.plot_items = {}
        self.plot_data = {}
        self.legend_items = {}
        self.plot_widget = None
        self.left_plot = None  # This is required for compatibility
        self.legend_widget = None
        self.legend = None  # This is required for compatibility
        self.update_timer = None
        self.parent_layout = parent_layout
        self.legend_layout = legend_layout
        
        # Log initialization parameters
        logger.info(f"Initializing plot with {len(active_channels)} active channels")
        
        # Initialize plot data for each active channel
        for ch in self.active_channels:
            channel_name = f"CH{ch}"
            self.plot_data[channel_name] = {
                'x': [],
                'y': []
            }
        
        # Create the plot widget and add to parent layout
        self._create_plot_widget()
        self._create_legend_widget()
        
        # Start an update timer for smoother plot updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(1000)  # Update every second
        
        logger.info(f"Plot widget initialized with {len(active_channels)} active channels")
    
    def _create_plot_widget(self):
        """Create the plot widget with appropriate settings"""
        try:
            # Set background to white and other properties
            pg.setConfigOption('background', 'w')
            pg.setConfigOption('foreground', 'k')
            
            # Create plot widget
            self.plot_widget = pg.PlotWidget()
            self.left_plot = self.plot_widget  # Assign to left_plot for compatibility
            self.plot_widget.setBackground('w')
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            
            # Set labels and titles
            self.plot_widget.setLabel('left', 'Value')
            self.plot_widget.setLabel('bottom', 'Time (minutes)')
            self.plot_widget.setTitle('Channel Readings vs. Time')
            
            # Force the plot to have a reasonable size
            self.plot_widget.setMinimumHeight(300)
            self.plot_widget.setMinimumWidth(400)
            
            # Add to parent layout if provided
            if self.parent_layout:
                logger.info(f"Adding plot widget to parent layout (type: {type(self.parent_layout).__name__})")
                
                # Try different ways to add to the layout
                try:
                    if hasattr(self.parent_layout, 'addWidget'):
                        self.parent_layout.addWidget(self.plot_widget)
                    elif hasattr(self.parent_layout, 'addItem'):
                        self.parent_layout.addItem(self.plot_widget)
                    else:
                        logger.error(f"Parent layout doesn't have addWidget or addItem method: {type(self.parent_layout)}")
                        # Try another approach - find the parent widget and add directly
                        if hasattr(self.parent_layout, 'parentWidget'):
                            parent = self.parent_layout.parentWidget()
                            if parent:
                                logger.info(f"Found parent widget: {parent}")
                                parent.layout().addWidget(self.plot_widget)
                except Exception as layout_error:
                    logger.error(f"Error adding to layout: {layout_error}")
                    # Last resort - if we can't add to layout, create our own window
                    self.plot_widget.show()
            else:
                logger.warning("No parent layout provided, plot widget won't be displayed automatically")
                # As a fallback, show the plot widget in its own window
                self.plot_widget.show()
            
            # Make sure the plot takes up sufficient space and is visible
            self.plot_widget.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, 
                QtWidgets.QSizePolicy.Expanding
            )
            
            # Create a legend for the plot
            self.legend = self.plot_widget.addLegend()
            
            # Create plot items for each active channel with different colors
            colors = ['r', 'g', 'b', 'c', 'm', 'y', (255, 165, 0), (128, 0, 128)]
            for i, ch in enumerate(self.active_channels):
                channel_name = f"CH{ch}"
                color_index = i % len(colors)
                channel_color = colors[color_index]
                
                # Use channel label from headers if available
                channel_label = self.headers[ch-1] if ch-1 < len(self.headers) else channel_name
                
                self.plot_items[channel_name] = self.plot_widget.plot(
                    [], [], 
                    pen=pg.mkPen(color=channel_color, width=2),
                    name=channel_label
                )
                
            logger.info("Plot widget created successfully")
        
        except Exception as e:
            logger.error(f"Error creating plot widget: {e}")
    
    def _create_legend_widget(self):
        """Create a legend widget for the plot if a legend layout is provided"""
        try:
            if not self.legend_layout:
                logger.info("No legend layout provided, skipping legend widget creation")
                return
                
            self.legend_widget = QtWidgets.QWidget()
            legend_box_layout = QtWidgets.QVBoxLayout(self.legend_widget)
            legend_box_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create labeled color boxes for each channel
            colors = ['red', 'green', 'blue', 'cyan', 'magenta', 'yellow', 'orange', 'purple']
            for i, ch in enumerate(self.active_channels):
                channel_name = f"CH{ch}"
                channel_label = self.headers[ch-1] if ch-1 < len(self.headers) else channel_name
                
                # Create horizontal layout for this legend item
                item_layout = QtWidgets.QHBoxLayout()
                
                # Create colored box
                color_box = QtWidgets.QFrame()
                color_box.setFrameShape(QtWidgets.QFrame.Box)
                color_box.setStyleSheet(f"background-color: {colors[i % len(colors)]};")
                color_box.setFixedSize(16, 16)
                
                # Create label
                label = QtWidgets.QLabel(channel_label)
                
                # Add to item layout
                item_layout.addWidget(color_box)
                item_layout.addWidget(label)
                item_layout.addStretch()
                
                # Add to legend layout
                legend_box_layout.addLayout(item_layout)
                
                # Store reference to legend item
                self.legend_items[channel_name] = (color_box, label)
            
            # Add stretch to make legend items bunch at top
            legend_box_layout.addStretch()
            
            # Add to parent legend layout
            if hasattr(self.legend_layout, 'addWidget'):
                self.legend_layout.addWidget(self.legend_widget)
            elif hasattr(self.legend_layout, 'addItem'):
                # Some layouts use addItem instead of addWidget
                self.legend_layout.addItem(self.legend_widget)
            else:
                logger.error("Legend layout doesn't have addWidget or addItem method")
                
            logger.info("Legend widget created successfully")
            
        except Exception as e:
            logger.error(f"Error creating legend widget: {e}")
    
    def update_plot_data(self, new_data_points):
        """
        Update the plot data with new data points.
        
        Args:
            new_data_points (list): List of dictionaries with 'channel' and 'value' keys
                Example: [{'channel': 'CH1', 'value': 123.4}, {'channel': 'CH2', 'value': 456.7}]
        """
        try:
            if not self.active_channels:
                logger.warning("No active channels defined for plot update")
                return
                
            # Get the first active channel as reference
            first_channel = f"CH{self.active_channels[0]}"
            current_time = len(self.plot_data.get(first_channel, {}).get('x', []))
            
            # Process each data point
            for data_point in new_data_points:
                channel = data_point.get('channel')
                value = data_point.get('value')
                
                if channel in self.plot_data and value is not None:
                    # Add the new data point
                    self.plot_data[channel]['x'].append(current_time)
                    self.plot_data[channel]['y'].append(value)
                    logger.debug(f"Added data point for {channel}: time={current_time}, value={value}")
            
            # Don't update the plot directly here - let the timer handle it
            # This prevents too frequent updates which can slow down the UI
        except Exception as e:
            logger.error(f"Error updating plot data: {e}")
    
    def update_plot(self):
        """Update the plot with the latest data"""
        try:
            # Update each plot item with its data
            for channel, item in self.plot_items.items():
                if channel in self.plot_data:
                    x_data = np.array(self.plot_data[channel]['x'])
                    y_data = np.array(self.plot_data[channel]['y'])
                    
                    if len(x_data) > 0:
                        item.setData(x_data, y_data)
                        logger.debug(f"Updated plot for {channel} with {len(x_data)} points")
            
            # Update the view to show all data
            self.plot_widget.autoRange()
            
        except Exception as e:
            logger.error(f"Error updating plot: {e}")
    
    def clear(self):
        """Clear all plot data"""
        try:
            for channel in self.plot_data:
                self.plot_data[channel]['x'] = []
                self.plot_data[channel]['y'] = []
            
            # Update the plot to show the cleared data
            self.update_plot()
            logger.info("Plot data cleared")
            
        except Exception as e:
            logger.error(f"Error clearing plot: {e}")
    
    def export_plot(self, file_path):
        """
        Export the plot as an image file
        
        Args:
            file_path (str): Full path to save the image
        """
        try:
            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Export as image
            exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
            exporter.export(file_path)
            logger.info(f"Plot exported to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting plot: {e}")
            return False
    
    def cleanup(self):
        """Clean up all resources used by the plot"""
        try:
            # Stop the update timer
            if self.update_timer and self.update_timer.isActive():
                self.update_timer.stop()
            
            # Clear all plot items
            for item in self.plot_items.values():
                if self.plot_widget:
                    self.plot_widget.removeItem(item)
            
            # Clear data and references
            self.plot_items = {}
            self.plot_data = {}
            
            # Remove widgets from layouts
            if self.plot_widget and self.parent_layout:
                if hasattr(self.parent_layout, 'removeWidget'):
                    self.parent_layout.removeWidget(self.plot_widget)
                self.plot_widget.deleteLater()
                self.plot_widget = None
                self.left_plot = None
            
            if self.legend_widget and self.legend_layout:
                if hasattr(self.legend_layout, 'removeWidget'):
                    self.legend_layout.removeWidget(self.legend_widget)
                self.legend_widget.deleteLater()
                self.legend_widget = None
                
            logger.info("Plot resources cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during plot cleanup: {e}")