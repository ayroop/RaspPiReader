import logging
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from RaspPiReader.ui.visualization_dashboard import VisualizationDashboard
from RaspPiReader.libs.visualization import LiveDataVisualization
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import PlotData, ChannelConfigSettings
from RaspPiReader import pool

logger = logging.getLogger(__name__)

class VisualizationManager:
    """
    Manages visualization integration with the main application.
    This class coordinates visualization start/stop with cycle actions,
    handles data collection and storage, and manages the visualization dashboard.
    Now supports all 14 PLC channels with database configuration.
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
        self.channel_configs = {}
        self.load_channel_configs()
        logger.info("VisualizationManager initialized")
    
    def load_channel_configs(self):
        """Load all channel configurations from the database"""
        try:
            for i in range(1, 15):  # 14 channels
                channel = self.db.session.query(ChannelConfigSettings).filter_by(id=i).first()
                if channel:
                    self.channel_configs[i] = {
                        'id': i,
                        'label': channel.label,
                        'address': channel.address,
                        'pv': channel.pv,
                        'sv': channel.sv,
                        'sp': channel.set_point,
                        'limit_low': channel.limit_low,  # Ensure this is used correctly
                        'limit_high': channel.limit_high,  # Ensure this is used correctly
                        'decimal_point': channel.dec_point,
                        'scale': channel.scale,
                        'axis_direction': channel.axis_direction,
                        'color': channel.color,
                        'active': channel.active,
                        'min_scale_range': channel.min_scale_range,
                        'max_scale_range': channel.max_scale_range
                    }
                    logger.debug(f"Loaded config for CH{i} - Address: {channel.address}")
                else:
                    logger.warning(f"No configuration found for CH{i}")
        except Exception as e:
            logger.error(f"Error loading channel configurations: {e}")
    
    def read_channel_data(self, channel_config):
        """
        Read channel data using dictionary access for configuration
        """
        try:
            value = self.plc_comm.read_value(channel_config['address'])
            
            # Apply scaling if needed
            if channel_config['scale']:
                # Convert using dictionary access
                scaled_value = self.scale_value(
                    value, 
                    channel_config['min_scale_range'], 
                    channel_config['max_scale_range'],
                    channel_config['limit_low'],
                    channel_config['limit_high']
                )
                return scaled_value
            else:
                return value
                
        except Exception as e:
            logger.error(f"Error reading {channel_config['label']}: {str(e)}")
            return None
    
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
        
        # Reload channel configurations in case they've changed
        self.load_channel_configs()
        
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
        Collect data from PLC for all 14 channels and update visualization.
        This method is called by the data collection timer.
        """
        if not self.is_active or self.dashboard is None:
            return
        
        try:
            # Get PLC communication functionality
            from RaspPiReader.libs.plc_communication import read_holding_register
            
            # Read values for all 14 channels
            for channel_number in range(1, 15):
                try:
                    channel_config = self.channel_configs.get(channel_number)
                    
                    if channel_config and 'address' in channel_config and channel_config['address']:
                        # Read value from PLC using the configured address
                        value = read_holding_register(channel_config['address'], 1)
                        
                        if value is not None:
                            # Apply decimal point and scaling if configured
                            if channel_config['decimal_point'] > 0:
                                value = value / (10 ** channel_config['decimal_point'])
                            
                            if channel_config['scale']:
                                # Apply custom scaling logic if needed
                                # Example: Map raw value to a specified range
                                if 'limit_low' in channel_config and 'limit_high' in channel_config:
                                    # This is a basic linear scaling example
                                    raw_min = 0
                                    raw_max = 32767  # Typical for 16-bit registers
                                    value = channel_config['limit_low'] + (value - raw_min) * (
                                        channel_config['limit_high'] - channel_config['limit_low']) / (raw_max - raw_min)
                            
                            # Update visualization dashboard
                            self.dashboard.update_data(channel_number, value)
                            
                            # Store in database
                            self.store_plot_data(f"ch{channel_number}", value)
                    else:
                        logger.warning(f"No address configured for CH{channel_number}")
                        
                except Exception as e:
                    logger.error(f"Error reading CH{channel_number}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error collecting visualization data: {str(e)}")
    
    def store_plot_data(self, channel, value):
        """
        Store plot data in the database.
        
        Args:
            channel: Channel name/identifier
            value: Channel value
        """
        try:
            plot_data = PlotData(
                timestamp=datetime.now(),
                channel=channel,
                value=value,
                cycle_id=self.cycle_id  # Associate with current cycle if available
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
