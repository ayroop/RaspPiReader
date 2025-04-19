import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from RaspPiReader import pool
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm, AlarmMapping
from RaspPiReader.libs.plc_communication import read_holding_register
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class AlarmMonitor:
    """
    Enhanced alarm monitoring system with threshold-based alarms.
    This class handles monitoring of PLC alarms for all channels.
    """
    
    def __init__(self, db: Database):
        """Initialize the alarm monitor."""
        self.db = db
        self.cache: Dict[str, Tuple[str, str]] = {}
        self.last_update = datetime.now()
        self.cache_duration = timedelta(seconds=1)
        self.is_monitoring = False
        self.monitoring_timer = None
        self._active_alarms: Dict[str, List[str]] = {}  # Channel -> List of active alarm messages
        self._last_values: Dict[str, float] = {}  # Channel -> Last read value
        self._error_counts: Dict[str, int] = {}  # Channel -> Consecutive error count
        self.MAX_ERRORS = 3  # Maximum consecutive errors before reporting communication issue
        
    def _get_channel_value(self, channel: str) -> Optional[float]:
        """Get the current value for a channel from the PLC."""
        try:
            # Extract channel number (e.g., 'CH1' -> 1)
            channel_num = int(channel[2:])
            addr_key = f'channel_{channel_num}_address'
            channel_addr = pool.config(addr_key, int, 0)
            
            if channel_addr > 0:
                value = read_holding_register(channel_addr, 1)
                if value is not None:
                    # Apply scaling if configured
                    scale_enabled = pool.config(f'scale{channel_num}', bool, False)
                    decimal_places = pool.config(f'decimal_point{channel_num}', int, 0)
                    if scale_enabled and decimal_places > 0:
                        value = value / (10 ** decimal_places)
                    return float(value)
            return None
        except Exception as e:
            self.db.logger.error(f"Error reading {channel} value: {e}")
            return None
            
    def _check_thresholds(self, channel: str, value: float) -> List[str]:
        """Check if the value exceeds any configured thresholds."""
        active_alarms = []
        try:
            alarm = self.db.session.query(Alarm).filter_by(channel=channel).first()
            if alarm:
                mappings = self.db.session.query(AlarmMapping).filter_by(alarm_id=alarm.id).all()
                for mapping in mappings:
                    if mapping.value == 1 and value < mapping.threshold:  # Low threshold
                        active_alarms.append(mapping.message)
                    elif mapping.value == 2 and value > mapping.threshold:  # High threshold
                        active_alarms.append(mapping.message)
        except Exception as e:
            logger.error(f"Error checking thresholds for {channel}: {e}")
        return active_alarms
        
    def check_alarms(self) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Check all configured channel alarms.
        
        Returns:
            Tuple[bool, Dict[str, List[str]]]: (has_active_alarms, channel_alarms)
            where channel_alarms is a dictionary mapping channels to their active alarm messages.
        """
        has_active_alarms = False
        channel_alarms: Dict[str, List[str]] = {}
        
        try:
            # Get all configured channels
            channels = [f"CH{i}" for i in range(1, 5)]  # CH1 to CH4
            
            for channel in channels:
                value = self._get_channel_value(channel)
                if value is None:
                    continue
                    
                # Store last value for comparison
                self._last_values[channel] = value
                
                # Check thresholds
                active_alarms = self._check_thresholds(channel, value)
                if active_alarms:
                    channel_alarms[channel] = active_alarms
                    has_active_alarms = True
                    # Log alarm activation
                    for alarm_msg in active_alarms:
                        logger.warning(f"Alarm activated - {channel}: {alarm_msg}")
                else:
                    channel_alarms[channel] = []
                    
                # Update active alarms
                self._active_alarms[channel] = channel_alarms[channel]
                    
        except Exception as e:
            logger.error(f"Error checking alarms: {e}")
            
        return has_active_alarms, channel_alarms
        
    def get_alarm_status_text(self) -> str:
        """
        Get formatted alarm status text for display.
        
        Returns:
            str: Formatted alarm status text
        """
        has_alarms, channel_alarms = self.check_alarms()
        
        if not has_alarms:
            return "No Alarms"
            
        # Format active alarms
        alarm_lines = []
        for channel, alarms in channel_alarms.items():
            if alarms:  # Only include channels with active alarms
                current_value = self._last_values.get(channel, 0)
                alarm_lines.extend([f"{channel} ({current_value:.2f}): {msg}" for msg in alarms])
                
        return "ALARMS:\n" + "\n".join(alarm_lines) if alarm_lines else "No Alarms"
        
    def get_alarm_style(self) -> str:
        """
        Get the style for the alarm display.
        
        Returns:
            str: CSS style string
        """
        has_alarms, _ = self.check_alarms()
        if has_alarms:
            return "color: red; font-weight: bold;"
        return "color: green;"

    def get_alarm_status(self, channel: str) -> Tuple[str, str]:
        """Get the current alarm status for a channel"""
        try:
            if not self.is_monitoring:
                return "Monitoring not started", "color: gray;"

            value = self._get_channel_value(channel)
            if value is None:
                return "No data", "color: gray;"

            return self.update_alarm_status(channel, value)
        except Exception as e:
            logger.error(f"Error getting alarm status for {channel}: {e}")
            return "Error", "color: red;"

    def update_alarm_status(self, channel: str, value: float) -> None:
        """Update the alarm status for a channel based on the current value.
        
        Args:
            channel: The channel name (e.g., 'CH1')
            value: The current value to check against the threshold
        """
        try:
            with Session(self.db.engine) as session:
                alarm = session.query(Alarm).filter(
                    Alarm.channel == channel,
                    Alarm.active == True
                ).first()
                
                if alarm and value >= alarm.threshold:
                    alarm.active = False
                    session.commit()
                    self.db.logger.info(f"Alarm triggered for {channel} at value {value}")
                    
        except Exception as e:
            self.db.logger.error(f"Error updating alarm status for {channel}: {str(e)}")

    def start_monitoring(self):
        """Start monitoring alarms"""
        if not self.is_monitoring:
            self.is_monitoring = True
            logger.info("Alarm monitoring started")
            # The actual monitoring is done through the update_alarm_status method
            # which is called by the main form's timer

    def stop_monitoring(self):
        """Stop monitoring alarms"""
        if self.is_monitoring:
            self.is_monitoring = False
            logger.info("Alarm monitoring stopped")
            if self.monitoring_timer:
                self.monitoring_timer.stop()
                self.monitoring_timer = None 