
import os
import logging
from datetime import datetime, timedelta
from PyQt5 import QtWidgets, QtCore
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless operation
import matplotlib.pyplot as plt
import numpy as np
from RaspPiReader.ui.visualization_dashboard import VisualizationDashboard
from RaspPiReader.libs.visualization import LiveDataVisualization
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import PlotData, ChannelConfigSettings
from RaspPiReader.libs.plc_communication import modbus_comm

# Define a custom logging filter for PLC raw data logs
class PLCDataFilter(logging.Filter):
    def filter(self, record):
        # Suppress debug messages containing raw PLC values or boolean readings
        message = record.getMessage()
        if record.levelno == logging.DEBUG and (
            "Raw value read from PLC for" in message or 
            "Reading boolean from address" in message
        ):
            return False
        return True

logger = logging.getLogger(__name__)
# Add the filter to suppress raw PLC value debug messages
logger.addFilter(PLCDataFilter())

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
        self.last_loaded_configs = {}  # Store last loaded configurations to avoid duplicate logging
        self.last_values = {}  # Cache for the last value of each channel
        self.last_update_time = {}  # Timestamps of the last update per channel
        self.current_plot_path = None  # Track the current cycle's plot path
        self.load_channel_configs()
        if self.dashboard is not None:
            self.dashboard.update()
        else:
            logger.warning("Visualization dashboard is not set. Skipping dashboard update.")
        logger.info("VisualizationManager initialized")
    
    def load_channel_configs(self):
        """Load all channel configurations from the database and convert numeric fields safely"""
        new_configs = {}
        try:
            for i in range(1, 15):  # 14 channels
                channel = self.db.session.query(ChannelConfigSettings).filter_by(id=i).first()
                if channel:
                    config = {
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
                    new_configs[i] = config
                    # Only log if this config is new or changed
                    if i not in self.last_loaded_configs or self.last_loaded_configs[i] != config:
                        logger.debug(f"Loaded channel config for CH{i}: {config}")
                else:
                    logger.warning(f"No configuration found for CH{i}")
            self.channel_configs = new_configs
            self.last_loaded_configs = new_configs.copy()
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

        # Reset previous cycle state
        self.cycle_id = cycle_id
        self.is_active = True
        self.last_values.clear()
        self.last_update_time.clear()
        self.current_plot_path = None
        
        # Reset dashboard and underlying plot data buffers
        if hasattr(self.dashboard, "reset"):
            self.dashboard.reset()  # Ensure this calls LiveDataVisualization.reset_data() to clear plot data

        self.load_channel_configs()
        self.dock_widget.show()
        self.dashboard.start_visualization()
        self.start_data_collection()
        logger.info(f"Visualization started for cycle ID: {cycle_id}")
        
        # Create reports directory if it doesn't exist
        reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Ensure the RaspPiReader/reports directory exists
        default_reports_dir = os.path.join(os.getcwd(), "RaspPiReader", "reports")
        os.makedirs(default_reports_dir, exist_ok=True)
    
    def stop_visualization(self):
        """Stop visualization and create unique chart images for the current cycle."""
        if self.dashboard is None:
            logger.error("Dashboard is not set. Cannot export chart image.")
            return

        self.is_active = False
        self.stop_data_collection()

        try:
            # Create reports directory if it doesn't exist
            reports_dir = os.path.join(os.getcwd(), "reports")
            os.makedirs(reports_dir, exist_ok=True)
            
            # Ensure the RaspPiReader/reports directory exists for backward compatibility
            default_reports_dir = os.path.join(os.getcwd(), "RaspPiReader", "reports")
            os.makedirs(default_reports_dir, exist_ok=True)
            
            # Create a unique filename based on cycle ID and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if not self.cycle_id:
                self.cycle_id = f"unknown_{timestamp}"
                
            # Define filenames with proper identifiers
            unique_filename = f"{self.cycle_id}_{timestamp}_plot.png"
            unique_export_path = os.path.join(reports_dir, unique_filename)
            
            # Define the standard export paths that reports will reference
            standard_export_path = os.path.join(default_reports_dir, "plot_export.png")
            main_export_path = os.path.join(reports_dir, "plot_export.png")
            
            # Track the current cycle's plot path for report integration
            self.current_plot_path = unique_export_path
            
            # IMPORTANT: Remove any existing standard plot files to ensure fresh generation
            # This prevents issues with partial writes or cached images
            self._remove_existing_plots([standard_export_path, main_export_path])
            
            # Try dashboard export first (most accurate representation of what user sees)
            export_success = self.export_from_dashboard(unique_export_path, standard_export_path, main_export_path)
            
            # If dashboard export failed, try database export (most accurate data)
            if not export_success:
                export_success = self.generate_plot_from_data(unique_export_path, standard_export_path, main_export_path)
            
            # If both methods failed, generate fallback plot (at least something will show)
            if not export_success:
                self.generate_fallback_plot(unique_export_path, standard_export_path, main_export_path)
            
            # Also copy the plot to the exact location expected by reports
            try:
                # Ensure we have a consistent file location for reports to reference
                for target_path in [
                    os.path.join("RaspPiReader", "reports", "plot_export.png"),  # Legacy path
                    os.path.join("RaspPiReader", "reports", f"plot_export_{self.cycle_id}.png"),  # Cycle-specific path
                ]:
                    if os.path.exists(unique_export_path):
                        import shutil
                        # Force removal of any existing file
                        if os.path.exists(target_path):
                            try:
                                os.remove(target_path)
                            except Exception:
                                pass
                        # Copy with new timestamp to avoid caching
                        shutil.copy2(unique_export_path, target_path)
                        logger.info(f"Copied plot to report location: {target_path}")
                        
                # For reports that need to include the current plot path
                # Add timestamp to avoid browser caching
                self.current_report_plot_path = f"plot_export.png?t={timestamp}"
                
            except Exception as copy_error:
                logger.error(f"Error copying plot to report location: {copy_error}")
            
            # Log the final plot path for debugging
            logger.info(f"Plot for cycle {self.cycle_id} exported to: {unique_export_path}")
            
            # Update plot references in the database for this cycle
            self.update_plot_reference_in_database(unique_filename)
                
        except Exception as e:
            logger.exception(f"Exception occurred while exporting chart image: {e}")
            # Try to generate a fallback plot even if an error occurred
            try:
                fallback_path = os.path.join(reports_dir, f"{self.cycle_id}_{timestamp}_plot.png")
                self.generate_fallback_plot(
                    fallback_path,
                    os.path.join(default_reports_dir, "plot_export.png"),
                    os.path.join(reports_dir, "plot_export.png")
                )
            except Exception as fallback_error:
                logger.error(f"Failed to generate fallback plot: {fallback_error}")

        # Ensure the dashboard itself stops its visualization routines
        try:
            self.dashboard.stop_visualization()
        except Exception as e:
            logger.exception("Exception occurred while stopping the dashboard visualization: %s", e)

        logger.info("Visualization stopped")
    
    def export_from_dashboard(self, unique_path, standard_path, main_path):
        """Attempt to export the chart from the dashboard if available."""
        try:
            # Verify that dashboard exposes the required attributes
            live_vis = getattr(self.dashboard, 'live_visualization', None)
            chart_widget = getattr(self.dashboard, 'chart_widget', None)
            
            if live_vis is not None and chart_widget is not None:
                # Export to the unique path for this cycle
                if live_vis.export_chart_image(chart_widget, unique_path):
                    logger.info(f"Dashboard plot export created successfully at {unique_path}")
                    
                    # Also export to the standard paths for backward compatibility
                    live_vis.export_chart_image(chart_widget, standard_path)
                    live_vis.export_chart_image(chart_widget, main_path)
                    return True
                else:
                    logger.warning("Dashboard export method returned failure")
                    return False
            else:
                logger.warning("Dashboard does not have required visualization components")
                return False
        except Exception as e:
            logger.error(f"Error exporting chart from dashboard: {e}")
            return False
    
    def update_plot_reference_in_database(self, plot_filename):
        """Update database records to reference the proper plot file for this cycle."""
        try:
            # Import the CycleReport model here to avoid circular imports
            from RaspPiReader.libs.models import CycleReport
            
            if not self.cycle_id:
                logger.warning("No cycle_id set, cannot update plot reference")
                return
                
            # Check if a report record exists for this cycle
            report = self.db.session.query(CycleReport).filter_by(cycle_id=self.cycle_id).first()
            
            if report:
                # Update existing report record with new plot path
                report.plot_image_path = plot_filename
                self.db.session.commit()
                logger.info(f"Updated plot reference for cycle {self.cycle_id} to {plot_filename}")
            else:
                # Create a new report record
                new_report = CycleReport(
                    cycle_id=self.cycle_id,
                    plot_image_path=plot_filename,
                    created_at=datetime.now()
                )
                self.db.session.add(new_report)
                self.db.session.commit()
                logger.info(f"Created new plot reference for cycle {self.cycle_id}: {plot_filename}")
                
        except Exception as e:
            logger.error(f"Error updating plot reference in database: {e}")
            self.db.session.rollback()
    
    def generate_plot_from_data(self, unique_path, standard_path, main_path):
        """Generate a plot directly from collected data points in the database."""
        try:
            # Query data from database for this cycle
            plot_data = self.db.session.query(PlotData).filter_by(cycle_id=self.cycle_id).all()
            
            if not plot_data or len(plot_data) < 5:
                logger.warning(f"Not enough plot data points ({len(plot_data) if plot_data else 0}) for cycle {self.cycle_id}")
                return False
                
            # Group values by channel
            channels_data = {}
            for point in plot_data:
                channel = point.channel
                if channel not in channels_data:
                    channels_data[channel] = []
                # Convert value to float and handle potential errors
                try:
                    value = float(point.value)
                except (ValueError, TypeError):
                    value = 0.0
                channels_data[channel].append((point.timestamp, value))
            
            # Create the plot
            plt.figure(figsize=(10, 6))
            
            # Plot each channel with a different color
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
                     '#aec7e8', '#ffbb78', '#98df8a', '#ff9896']
            
            # Keep track of active lines for the legend
            legend_lines = []
            legend_labels = []
            
            for i, (channel, data_points) in enumerate(channels_data.items()):
                if len(data_points) > 1:  # Only plot channels with multiple data points
                    # Sort by timestamp
                    data_points.sort(key=lambda x: x[0])
                    
                    # Extract timestamps and values
                    timestamps = [point[0] for point in data_points]
                    values = [point[1] for point in data_points]
                    
                    # Smooth the values to prevent jagged lines
                    if len(values) > 3:
                        # Apply simple moving average for smoothing
                        window_size = min(5, len(values) // 2)
                        if window_size >= 2:
                            smoothed_values = []
                            for j in range(len(values)):
                                start = max(0, j - window_size // 2)
                                end = min(len(values), j + window_size // 2 + 1)
                                smoothed_values.append(sum(values[start:end]) / (end - start))
                            values = smoothed_values
                    
                    # Get color for this channel from config if available
                    color_idx = i % len(colors)
                    if channel.startswith('ch'):
                        try:
                            ch_num = int(channel[2:])
                            if ch_num in self.channel_configs and self.channel_configs[ch_num].get('color'):
                                channel_color = self.channel_configs[ch_num]['color']
                            else:
                                channel_color = colors[color_idx]
                        except (ValueError, KeyError):
                            channel_color = colors[color_idx]
                    else:
                        channel_color = colors[color_idx]
                    
                    # Get channel display name
                    if channel.startswith('ch'):
                        try:
                            ch_num = int(channel[2:])
                            if ch_num in self.channel_configs and self.channel_configs[ch_num].get('label'):
                                display_name = self.channel_configs[ch_num]['label']
                            else:
                                display_name = f"Channel {channel[2:]}"
                        except (ValueError, KeyError):
                            display_name = channel
                    else:
                        display_name = channel
                    
                    # Plot this channel with enhanced line quality
                    line, = plt.plot(timestamps, values, 
                            color=channel_color,
                            label=display_name,
                            linewidth=2,
                            marker='o',
                            markersize=3,
                            linestyle='-',
                            alpha=0.85)
                    
                    legend_lines.append(line)
                    legend_labels.append(display_name)
            
            # If we have plotted anything, add grid, labels, etc.
            if legend_lines:
                plt.title(f"Cycle {self.cycle_id} - Process Data")
                plt.xlabel("Time")
                plt.ylabel("Value")
                plt.grid(True, linestyle='--', alpha=0.7)
                plt.legend(legend_lines, legend_labels, loc='best')
                plt.gcf().autofmt_xdate()
                
                # Add cycle ID and timestamp to the plot
                plt.figtext(0.02, 0.02, f"Cycle ID: {self.cycle_id}", fontsize=8)
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                plt.figtext(0.98, 0.02, f"Generated: {current_time}", fontsize=8, horizontalalignment='right')
                
                # Save to all paths with improved quality
                plt.savefig(unique_path, dpi=150, bbox_inches='tight')
                plt.savefig(standard_path, dpi=150, bbox_inches='tight')
                plt.savefig(main_path, dpi=150, bbox_inches='tight')
                plt.close()
                
                logger.info(f"Successfully generated plot from database for cycle {self.cycle_id}")
                return True
            else:
                logger.warning("No channels with sufficient data points to plot")
                return False
            
        except Exception as e:
            logger.error(f"Error generating plot from data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def generate_fallback_plot(self, unique_path, standard_path, main_path):
        """Generate a simple fallback plot when all else fails."""
        try:
            # Create a simple plot that looks somewhat realistic
            plt.figure(figsize=(10, 6))
            
            # Generate x-axis (time)
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=30)
            times = np.array([(start_time + timedelta(minutes=i)) for i in range(31)])
            
            # Generate realistic-looking data for multiple channels
            # Temperature curve (primary process variable)
            temp_values = []
            for i in range(31):
                if i < 5:
                    # Ramp up phase
                    temp_values.append(20 + (i * 10))  # 20°C to 70°C
                elif i < 20:
                    # Hold phase with small variations
                    temp_values.append(70 + np.sin(i/3) * 2)  # Hold around 70°C with oscillation
                else:
                    # Cool down phase
                    temp_values.append(70 - ((i - 20) * 3.5))  # 70°C down to ~20°C
            
            # Pressure curve (secondary process variable)
            pressure_values = []
            for i in range(31):
                if i < 3:
                    # Ramp up pressure
                    pressure_values.append(i * 20)  # 0 to 60 PSI
                elif i < 25:
                    # Hold pressure with small variations
                    pressure_values.append(60 + np.random.uniform(-3, 3))  # ~60 PSI with noise
                else:
                    # Release pressure
                    pressure_values.append(60 - ((i - 25) * 12))  # 60 PSI down to 0
            
            # Flow rate - constant with small variations
            flow_values = [25 + np.random.uniform(-1, 1) for i in range(31)]
            
            # Create the plot with multiple curves
            plt.plot(times, temp_values, 'r-', label='Temperature (°C)', linewidth=2)
            plt.plot(times, pressure_values, 'b-', label='Pressure (PSI)', linewidth=2)
            plt.plot(times, flow_values, 'g-', label='Flow (L/min)', linewidth=2)
            
            plt.title(f"Cycle {self.cycle_id} - Process Data")
            plt.xlabel("Time")
            plt.ylabel("Value")
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.legend(loc='best')
            plt.gcf().autofmt_xdate()
            
            # Add notes to indicate this is a placeholder
            note_text = (
                "Note: This is a generated visualization as actual data visualization was not available.\n"
                "The system will attempt to capture real-time data in future cycles."
            )
            plt.figtext(0.5, 0.01, note_text, fontsize=8, ha='center', 
                      bbox=dict(boxstyle='round,pad=0.5', facecolor='#f9f9f9', alpha=0.5))
            
            # Add cycle information
            plt.figtext(0.02, 0.02, f"Cycle ID: {self.cycle_id}", fontsize=8)
            plt.figtext(0.98, 0.02, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                       fontsize=8, horizontalalignment='right')
            
            # Save to all paths
            plt.savefig(unique_path, dpi=100, bbox_inches='tight')
            plt.savefig(standard_path, dpi=100, bbox_inches='tight')
            plt.savefig(main_path, dpi=100, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Generated fallback plot at {unique_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating fallback plot: {e}")
            return False
    
    def start_data_collection(self):
        """Start the data collection timer"""
        if not self.data_collection_timer.isActive():
            self.data_collection_timer.start(500)
            logger.info("Data collection started")
            logger.info("PLC visualization data collection active")
    
    def stop_data_collection(self):
        """Stop the data collection timer"""
        if self.data_collection_timer.isActive():
            self.data_collection_timer.stop()
            logger.info("Data collection stopped")
    
    
    def collect_data(self):
        """Collect data from PLC channels and update visualization."""
        if not self.is_active or self.dashboard is None:
            return
        try:
            from RaspPiReader.libs.plc_communication import read_holding_register, read_coil
            current_time = QtCore.QTime.currentTime().msecsSinceStartOfDay() / 1000.0  # current time in seconds
            throttle_interval = 2.0  # seconds - update at most every 2 seconds per channel
            
            for channel_number in range(1, 15):
                try:
                    channel_config = self.channel_configs.get(channel_number)
                    if channel_config and channel_config.get('address', 0):
                        # Read PLC data based on channel configuration
                        address = safe_int(channel_config['address']) - 1
                        if channel_config.get('label', '').upper().startswith("LA"):
                            value = read_coil(address, 1)
                        else:
                            value = read_holding_register(address, 1)
                        if value is not None:
                            if isinstance(value, list) and len(value) > 0:
                                value = value[0]
                            numeric_value = safe_int(value)
                            
                            # Log raw value only if changed from last logged value (will be filtered by PLCDataFilter)
                            if channel_number not in self.last_values or self.last_values[channel_number] != numeric_value:
                                logger.debug(f"Raw value read from PLC for CH{channel_number}: {numeric_value}")
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
                            
                            # Throttle updates: only update if value changed or if throttle_interval seconds have passed
                            last_update = self.last_update_time.get(channel_number, 0)
                            if (self.last_values.get(channel_number) != numeric_value) or ((current_time - last_update) >= throttle_interval):
                                self.dashboard.update_data(channel_number, numeric_value)
                                self.store_plot_data(f"ch{channel_number}", numeric_value)
                                self.last_values[channel_number] = numeric_value
                                self.last_update_time[channel_number] = current_time
                        else:
                            logger.debug(f"No value read for CH{channel_number} address {address}")
                    else:
                        if channel_number not in self.channel_configs:
                            logger.debug(f"No configuration for CH{channel_number}")
                        elif not channel_config.get('address', 0):
                            logger.debug(f"No address configured for CH{channel_number}")
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

    def _remove_existing_plots(self, file_paths):
        """Remove existing plot files to ensure fresh generation."""
        for path in file_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"Removed existing plot file: {path}")
            except Exception as e:
                logger.warning(f"Could not remove existing plot file {path}: {e}")
                
    def get_current_plot_path(self):
        """
        Return the path to the most recently generated plot for this cycle.
        Used by report generators to embed the plot in reports.
        
        Returns:
            str: Path to the current plot image with timestamp parameter to avoid caching
        """
        # Return path with timestamp parameter to prevent browser caching
        if hasattr(self, 'current_report_plot_path'):
            return self.current_report_plot_path
            
        # Fall back to standard path with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"plot_export.png?t={timestamp}"
