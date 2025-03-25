"""
Integration code to update the main form with boolean values from PLC
This can be integrated into your existing main form class
"""

import logging
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer
from RaspPiReader.libs.plc_boolean_reader import PLCBooleanReader
from RaspPiReader import pool

logger = logging.getLogger(__name__)

class BooleanValueUpdater:
    """
    A utility class to update boolean indicators on the main form
    """
    
    def __init__(self, main_form):
        """
        Initialize the updater with a reference to the main form
        
        Args:
            main_form: The main form instance that contains UI elements to update
        """
        self.main_form = main_form
        self.boolean_reader = None
        self.update_timer = None
        self.boolean_addresses = []
        self.boolean_labels = []
        self.indicators = []
        self.is_updating = False
        
    def initialize(self):
        """Initialize the boolean updater with connection parameters from the application settings"""
        try:
            connection_type = pool.config('plc/connection_type', str, 'tcp')
            connection_params = {}
            
            if connection_type == 'tcp':
                connection_params = {
                    'host': pool.config('plc/host', str, '127.0.0.1'),
                    'port': pool.config('plc/tcp_port', int, 502),
                    'timeout': pool.config('plc/timeout', float, 1.0)
                }
            else:  # RTU
                connection_params = {
                    'port': pool.config('plc/port', str, 'COM1'),
                    'baudrate': pool.config('plc/baudrate', int, 9600),
                    'bytesize': pool.config('plc/bytesize', int, 8),
                    'parity': pool.config('plc/parity', str, 'N'),
                    'stopbits': pool.config('plc/stopbits', float, 1.0)
                }
            
            # Ensure the boolean addresses are updated correctly
            for i in range(1, 15):  # 14 channels
                channel_config = self.channels_config.get(i)
                if channel_config:
                    logger.info(f"Bool Address {i}: {channel_config['address']} - {channel_config['label']} - {channel_config['pv']}")
                else:
                    logger.warning(f"No configuration found for Bool Address {i}")
        except Exception as e:
            logger.error(f"Error initializing boolean updater: {e}")
            
            # Create the boolean reader
            self.boolean_reader = PLCBooleanReader(
                connection_type=connection_type,
                connection_params=connection_params
            )
            
            # Load boolean addresses from settings
            self._load_boolean_addresses()
            
            # Initialize the UI indicators
            self._initialize_indicators()
            
            # Set up the update timer
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_boolean_values)
            
            # Start with a longer interval initially
            self.update_timer.start(1000)  # 1 second initial update interval
            
            logger.info("Boolean value updater initialized")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing boolean updater: {e}")
            return False
    
    def _load_boolean_addresses(self):
        """
        Load boolean addresses from application settings
        """
        try:
            # Clear existing addresses
            self.boolean_addresses = []
            self.boolean_labels = []
            
            # Load boolean addresses - these should match the addresses you mentioned
            # Bool Address 1: 1 - Label 1
            # Bool Address 2: 17 - Label 2
            # etc.
            
            for i in range(1, 7):  # For addresses 1-6
                address_key = f"plc/bool_address_{i}"
                label_key = f"plc/bool_label_{i}"
                
                address = pool.config(address_key, int, 0)
                label = pool.config(label_key, str, f"Bool {i}")
                
                # Only add non-zero addresses
                if address > 0:
                    self.boolean_addresses.append(address)
                    self.boolean_labels.append(label)
                    logger.debug(f"Loaded boolean address {address} with label '{label}'")
            
            # If no addresses were found in the configuration, use the default ones
            if not self.boolean_addresses:
                default_addresses = [1, 17, 33, 49, 65, 81]
                for i, addr in enumerate(default_addresses, 1):
                    self.boolean_addresses.append(addr)
                    self.boolean_labels.append(f"Bool {i}")
                logger.info("Using default boolean addresses")
            
            logger.info(f"Loaded {len(self.boolean_addresses)} boolean addresses")
            
        except Exception as e:
            logger.error(f"Error loading boolean addresses: {e}")
            # Fall back to default addresses if loading fails
            self.boolean_addresses = [1, 17, 33, 49, 65, 81]
            self.boolean_labels = ["Bool 1", "Bool 2", "Bool 3", "Bool 4", "Bool 5", "Bool 6"]
    
    def _initialize_indicators(self):
        """
        Initialize the UI indicators for boolean values
        """
        try:
            # Clear existing indicators
            self.indicators = []
            
            # Find all boolean indicator UI elements on the main form
            # The naming convention could be something like self.main_form.boolIndicator1, etc.
            
            for i in range(1, 7):  # For indicators 1-6
                # Try to find the indicator by name
                indicator_name = f"boolIndicator{i}"
                if hasattr(self.main_form, indicator_name):
                    indicator = getattr(self.main_form, indicator_name)
                    self.indicators.append(indicator)
                    logger.debug(f"Found boolean indicator UI element: {indicator_name}")
                else:
                    # If indicator not found, add None as a placeholder
                    self.indicators.append(None)
                    logger.warning(f"Boolean indicator UI element not found: {indicator_name}")
                    
            # Alternative way to find indicators with different naming convention
            # If your indicators have a different naming pattern, use this pattern instead
            # For example, if they're named lblBool1, lblBool2, etc.
            if all(ind is None for ind in self.indicators):
                self.indicators = []
                for i in range(1, 7):
                    indicator_name = f"lblBool{i}"
                    if hasattr(self.main_form, indicator_name):
                        indicator = getattr(self.main_form, indicator_name)
                        self.indicators.append(indicator)
                    else:
                        self.indicators.append(None)
                        
            # If we still don't have any indicators, log a warning
            if all(ind is None for ind in self.indicators):
                logger.warning("No boolean indicator UI elements were found on the main form")
                
        except Exception as e:
            logger.error(f"Error initializing boolean indicators: {e}")
    
    def update_boolean_values(self):
        """
        Update the boolean values from the PLC and refresh the UI
        """
        if self.is_updating or not self.boolean_addresses:
            return
            
        self.is_updating = True
        try:
            # Read all boolean values at once
            boolean_values = self.boolean_reader.read_boolean_values(self.boolean_addresses)
            
            # Update UI elements with the values
            for i, address in enumerate(self.boolean_addresses):
                if i < len(self.indicators) and self.indicators[i] is not None:
                    value = boolean_values.get(address)
                    indicator = self.indicators[i]
                    
                    # Update the indicator based on the boolean value
                    if value is True:
                        self._set_indicator_on(indicator, self.boolean_labels[i])
                    elif value is False:
                        self._set_indicator_off(indicator, self.boolean_labels[i])
                    else:
                        self._set_indicator_error(indicator, self.boolean_labels[i])
            
            # Once successful, reduce the update interval for efficiency
            if self.update_timer.interval() > 500:
                self.update_timer.setInterval(500)  # Update every 500ms after initial success
                
        except Exception as e:
            logger.error(f"Error updating boolean values: {e}")
            # If there's an error, increase the update interval to reduce load
            if self.update_timer.interval() < 5000:
                self.update_timer.setInterval(5000)  # Reduce to every 5 seconds when errors occur
        finally:
            self.is_updating = False
    
    def _set_indicator_on(self, indicator, label):
        """
        Set the indicator to ON state
        
        Args:
            indicator: UI element to update
            label: Label text
        """
        try:
            # Determine what type of indicator we have
            if isinstance(indicator, QtWidgets.QLabel):
                indicator.setText(f"{label}: ON")
                indicator.setStyleSheet("background-color: green; color: white; border-radius: 5px; padding: 2px;")
            elif hasattr(indicator, 'setChecked'):  # For QCheckBox or similar
                indicator.setChecked(True)
                if hasattr(indicator, 'setText'):
                    indicator.setText(f"{label}: ON")
            elif hasattr(indicator, 'setValue'):  # For QProgressBar or similar
                indicator.setValue(100)
                if hasattr(indicator, 'setFormat'):
                    indicator.setFormat(f"{label}: ON")
        except Exception as e:
            logger.error(f"Error setting indicator ON: {e}")
    
    def _set_indicator_off(self, indicator, label):
        """
        Set the indicator to OFF state
        
        Args:
            indicator: UI element to update
            label: Label text
        """
        try:
            if isinstance(indicator, QtWidgets.QLabel):
                indicator.setText(f"{label}: OFF")
                indicator.setStyleSheet("background-color: red; color: white; border-radius: 5px; padding: 2px;")
            elif hasattr(indicator, 'setChecked'):
                indicator.setChecked(False)
                if hasattr(indicator, 'setText'):
                    indicator.setText(f"{label}: OFF")
            elif hasattr(indicator, 'setValue'):
                indicator.setValue(0)
                if hasattr(indicator, 'setFormat'):
                    indicator.setFormat(f"{label}: OFF")
        except Exception as e:
            logger.error(f"Error setting indicator OFF: {e}")
    
    def _set_indicator_error(self, indicator, label):
        """
        Set the indicator to ERROR state
        
        Args:
            indicator: UI element to update
            label: Label text
        """
        try:
            if isinstance(indicator, QtWidgets.QLabel):
                indicator.setText(f"{label}: N/A")
                indicator.setStyleSheet("background-color: gray; color: white; border-radius: 5px; padding: 2px;")
            elif hasattr(indicator, 'setChecked'):
                # Some widgets don't have a third state, so we'll just use off
                indicator.setChecked(False)
                if hasattr(indicator, 'setText'):
                    indicator.setText(f"{label}: N/A")
            elif hasattr(indicator, 'setValue'):
                indicator.setValue(0)
                if hasattr(indicator, 'setFormat'):
                    indicator.setFormat(f"{label}: N/A")
        except Exception as e:
            logger.error(f"Error setting indicator ERROR: {e}")
    
    def stop(self):
        """
        Stop the boolean value updater
        """
        if self.update_timer:
            self.update_timer.stop()
        
        if self.boolean_reader:
            self.boolean_reader.disconnect()