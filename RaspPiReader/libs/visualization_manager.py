import logging
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from RaspPiReader.ui.visualization_dashboard import VisualizationDashboard
from RaspPiReader.libs.visualization import LiveDataVisualization
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import PlotData
from RaspPiReader import pool

logger = logging.getLogger(__name__)

class VisualizationManager:
    """
    Manages visualization integration with the main application.
    This class coordinates visualization start/stop with cycle actions,
    handles data collection and storage, and manages the visualization dashboard.
    """
    
    _instance = None
    
    @classmethod
    def instance(cls):
        """
        Singleton pattern to ensure only one visualization manager exists.
        
        Returns:
            VisualizationManager: The singleton instance
        """
        if cls._instance is None:
            cls._instance = VisualizationManager()
        return cls._instance
    
    def __init__(self):
        """Initialize the visualization manager"""
        self.dashboard = None
        self.dock_widget = None
        self.data_collection_timer = QtCore.QTimer()
        self.data_collection_timer.timeout.connect(self.collect_data)
        self.is_active = False
        self.db = Database("sqlite:///local_database.db")
        self.cycle_id = None
        logger.info("VisualizationManager initialized")
    
    def setup_dashboard(self, parent_window):
        """
        Create and set up the visualization dashboard.
        
        Args:
            parent_window: The main window that will host the dashboard
        """
        if self.dashboard is None:
            # Create the dashboard
            self.dashboard = VisualizationDashboard()
            
            # Create a dock widget to host the dashboard
            self.dock_widget = QtWidgets.QDockWidget("Live PLC Data Visualization", parent_window)
            self.dock_widget.setWidget(self.dashboard)
            self.dock_widget.setFeatures(
                QtWidgets.QDockWidget.DockWidgetMovable | 
                QtWidgets.QDockWidget.DockWidgetFloatable
            )
            
            # Add the dock widget to the main window
            parent_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_widget)
            
            # Hide dock widget initially (will show when cycle starts)
            self.dock_widget.hide()
            logger.info("Visualization dashboard created")
    
    def start_visualization(self, cycle_id=None):
        """
        Start the visualization with the current cycle.
        
        Args:
            cycle_id: Optional ID of the current cycle for data association
        """
        if self.dashboard is None:
            logger.warning("Cannot start visualization - dashboard not created")
            return
        
        self.cycle_id = cycle_id
        self.is_active = True
        
        # Show the dashboard
        self.dock_widget.show()
        
        # Start the dashboard visualization
        self.dashboard.start_visualization()
        
        # Start data collection timer
        self.start_data_collection()
        
        logger.info(f"Visualization started for cycle ID: {cycle_id}")
    
    def stop_visualization(self):
        """Stop the visualization"""
        if self.dashboard is None:
            return
        
        self.is_active = False
        
        # Stop data collection
        self.stop_data_collection()
        
        # Stop the dashboard visualization
        self.dashboard.stop_visualization()
        
        logger.info("Visualization stopped")
    
    def start_data_collection(self):
        """Start the data collection timer"""
        if not self.data_collection_timer.isActive():
            # Collect data every 500ms
            self.data_collection_timer.start(500)
            logger.info("Data collection started")
    
    def stop_data_collection(self):
        """Stop the data collection timer"""
        if self.data_collection_timer.isActive():
            self.data_collection_timer.stop()
            logger.info("Data collection stopped")
    
    def collect_data(self):
        """
        Collect data from PLC and update visualization.
        This method is called by the data collection timer.
        """
        if not self.is_active or self.dashboard is None:
            return
        
        try:
            # Get PLC communication instance from pool
            from RaspPiReader.libs.plc_communication import read_holding_register
            
            # Define channels to read (addresses for temperature, pressure, etc.)
            # These should match the parameter names used in the visualization dashboard
            channels = {
                "temperature": pool.config('temperature_address', int, 100),
                "pressure": pool.config('pressure_address', int, 102),
                "flow_rate": pool.config('flow_rate_address', int, 104),
                "position": pool.config('position_address', int, 106)
            }
            
            # Read values from PLC
            for channel_name, address in channels.items():
                try:
                    # Read value from PLC
                    value = read_holding_register(address, 1)
                    
                    if value is not None:
                        # Update visualization
                        self.dashboard.update_data(channel_name, value)
                        
                        # Store in database
                        self.store_plot_data(channel_name, value)
                except Exception as e:
                    logger.error(f"Error reading {channel_name} at address {address}: {e}")
            
        except Exception as e:
            logger.error(f"Error collecting visualization data: {e}")
    
    def store_plot_data(self, channel, value):
        """
        Store plot data in the database.
        
        Args:
            channel: Channel name
            value: Channel value
        """
        try:
            plot_data = PlotData(
                timestamp=datetime.now(),
                channel=channel,
                value=value
            )
            self.db.session.add(plot_data)
            self.db.session.commit()
        except Exception as e:
            logger.error(f"Error storing plot data: {e}")
            self.db.session.rollback()
    
    def toggle_dashboard_visibility(self):
        """Toggle visibility of the visualization dashboard"""
        if self.dock_widget:
            if self.dock_widget.isVisible():
                self.dock_widget.hide()
                logger.info("Visualization dashboard hidden")
            else:
                self.dock_widget.show()
                logger.info("Visualization dashboard shown")
    
    def reset_visualization(self):
        """Reset the visualization dashboard"""
        if self.dashboard:
            self.dashboard.reset()
            logger.info("Visualization reset")