import logging
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from RaspPiReader.ui.visualization_dashboard import VisualizationDashboard
from RaspPiReader.libs.visualization import LiveDataVisualization
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import PlotData, ChannelConfigSettings
from RaspPiReader.libs.plc_communication import modbus_comm

logger = logging.getLogger(__name__)

def safe_int(val, default=0):
    """
    Safely converts a value to an integer.
    If the value is already an int, it is returned directly.
    Otherwise, it is converted to a string, unwanted characters like '<' and '>' are removed,
    and then cast to int. On failure, the default value is returned.
    """
    try:
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(val)
        s = str(val)
        for ch in ['<', '>']:
            s = s.replace(ch, '')
        s = s.strip()
        return int(s)
    except (ValueError, TypeError):
        return default

def safe_float(val, default=0.0):
    """
    Safely converts a value to a float.
    If the value is already a float/int, it is converted accordingly.
    Otherwise, it is converted to a string, unwanted characters are removed,
    and then cast to float. On failure, the default value is returned.
    """
    try:
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val)
        for ch in ['<', '>']:
            s = s.replace(ch, '')
        s = s.strip()
        return float(s)
    except (ValueError, TypeError):
        return default

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
        # Initialize PLC communication for use in read_channel_data
        self.plc_comm = modbus_comm

        self.dashboard = None
        self.dock_widget = None
        self.data_collection_timer = QtCore.QTimer()
        self.data_collection_timer.timeout.connect(self.collect_data)
        self.is_active = False
        self.db = Database("sqlite:///local_database.db")
        self.cycle_id = None
        self.channel_configs = {}
        self.load_channel_configs()
        if self.dashboard is not None:
            self.dashboard.update()
        else:
            logger.warning("Visualization dashboard is not set. Skipping dashboard update.")
        logger.info("VisualizationManager initialized")
    
    def load_channel_configs(self):
        """Load all channel configurations from the database and convert numeric fields safely"""
        try:
            for i in range(1, 15):  # 14 channels
                channel = self.db.session.query(ChannelConfigSettings).filter_by(id=i).first()
                if channel:
                    self.channel_configs[i] = {
                        'id': i,
                        'label': channel.label,
                        'address': safe_int(channel.address, 0),
                        'pv': safe_float(channel.pv, 0),
                        'sv': safe_float(channel.sv, 0),
                        'set_point': safe_float(channel.set_point, 0),
                        'limit_low': safe_float(channel.limit_low, 0),
                        'limit_high': safe_float(channel.limit_high, 0),
                        'decimal_point': safe_int(channel.decimal_point, 0),
                        'scale': bool(channel.scale),
                        'axis_direction': channel.axis_direction,
                        'color': channel.color,
                        'active': bool(channel.active),
                        'min_scale_range': safe_float(channel.min_scale_range, 0),
                        'max_scale_range': safe_float(channel.max_scale_range, 0)
                    }
                    logger.debug(f"Loaded channel config: {self.channel_configs[i]}")
                else:
                    logger.warning(f"No configuration found for CH{i}")
        except Exception as e:
            logger.error(f"Error loading channel configurations: {e}")
    
    def scale_value(self, value, min_scale, max_scale, limit_low, limit_high):
        """
        Scales the raw value read from PLC to a new range based on provided limits.
        
        Args:
            value: The raw integer value.
            min_scale: The minimum value of the source scale.
            max_scale: The maximum value of the source scale.
            limit_low: The lower limit of the target scale.
            limit_high: The upper limit of the target scale.
        
        Returns:
            Scaled value as a float.
        """
        value = safe_float(value, 0.0)
        limit_low = safe_float(limit_low, 0.0)
        limit_high = safe_float(limit_high, 0.0)
        raw_min = 0.0
        raw_max = 32767.0
        # Only scale if the range is non-zero
        if (limit_high - limit_low) != 0:
            try:
                scaled = limit_low + (value - raw_min) * (limit_high - limit_low) / (raw_max - raw_min)
                return scaled
            except Exception as e:
                logger.error(f"Error scaling value: {e}")
                return value
        else:
            # If limits are not set (or equal), skip scaling
            logger.debug("Scaling skipped because limit_high equals limit_low")
            return value
           
    def read_channel_data(self, channel_config):
        """
        Read channel data using dictionary access for configuration.
        Uses the same reading functions as in collect_data so that real PLC values are retrieved.
        """
        try:
            address = safe_int(channel_config['address']) - 1
            if channel_config.get('label', '').upper().startswith("LA"):
                from RaspPiReader.libs.plc_communication import read_coil
                value = read_coil(address, 1)
            else:
                from RaspPiReader.libs.plc_communication import read_holding_register
                value = read_holding_register(address, 1)
                
            if value is not None:
                if isinstance(value, list) and len(value) > 0:
                    value = value[0]
                if channel_config.get('scale'):
                    value = self.scale_value(
                        value, 
                        channel_config['min_scale_range'], 
                        channel_config['max_scale_range'],
                        channel_config['limit_low'],
                        channel_config['limit_high']
                    )
                return value
            return None
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
            self.dashboard = VisualizationDashboard()
            self.dock_widget = QtWidgets.QDockWidget("Live PLC Data Visualization", parent_window)
            self.dock_widget.setWidget(self.dashboard)
            self.dock_widget.setFeatures(
                QtWidgets.QDockWidget.DockWidgetMovable | 
                QtWidgets.QDockWidget.DockWidgetFloatable
            )
            parent_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_widget)
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
        self.load_channel_configs()
        self.dock_widget.show()
        self.dashboard.start_visualization()
        self.start_data_collection()
        logger.info(f"Visualization started for cycle ID: {cycle_id}")
    
    def stop_visualization(self):
        """Stop the visualization"""
        if self.dashboard is None:
            return
        self.is_active = False
        self.stop_data_collection()
        self.dashboard.stop_visualization()
        logger.info("Visualization stopped")
    
    def start_data_collection(self):
        """Start the data collection timer"""
        if not self.data_collection_timer.isActive():
            self.data_collection_timer.start(500)
            logger.info("Data collection started")
    
    def stop_data_collection(self):
        """Stop the data collection timer"""
        if self.data_collection_timer.isActive():
            self.data_collection_timer.stop()
            logger.info("Data collection stopped")
    
    def collect_data(self):
        if not self.is_active or self.dashboard is None:
            return
        try:
            from RaspPiReader.libs.plc_communication import read_holding_register, read_coil
            for channel_number in range(1, 15):
                try:
                    channel_config = self.channel_configs.get(channel_number)
                    if channel_config and channel_config.get('address', 0):
                        address = safe_int(channel_config['address']) - 1
                        if channel_config.get('label', '').upper().startswith("LA"):
                            value = read_coil(address, 1)
                        else:
                            value = read_holding_register(address, 1)
                        logger.debug(f"Raw value read from PLC for CH{channel_number}: {value}")
                        if value is not None:
                            if isinstance(value, list) and len(value) > 0:
                                value = value[0]
                            numeric_value = safe_int(value)
                            if not channel_config.get('label', '').upper().startswith("LA"):
                                decimal_point = safe_int(channel_config.get('decimal_point', 0))
                                if decimal_point > 0:
                                    numeric_value = safe_float(numeric_value) / (10 ** decimal_point)
                                if channel_config.get('scale', False):
                                    raw_min = 0
                                    raw_max = 32767
                                    limit_low = safe_float(channel_config.get('limit_low', 0))
                                    limit_high = safe_float(channel_config.get('limit_high', 0))
                                    if (limit_high - limit_low) != 0:
                                        numeric_value = limit_low + (numeric_value - raw_min) * (limit_high - limit_low) / (raw_max - raw_min)
                                    else:
                                        logger.debug(f"Scaling skipped for CH{channel_number} because limit_high equals limit_low")
                            self.dashboard.update_data(channel_number, numeric_value)
                            self.store_plot_data(f"ch{channel_number}", numeric_value)
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
                cycle_id=self.cycle_id
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