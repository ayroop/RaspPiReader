"""
Integration code to update the main form with boolean values from the PLC.
This revised version uses a fixed set of six boolean addresses and calls the PLCBooleanReader directly
to read all boolean values and update the UI indicators.
"""

import logging
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer
from RaspPiReader.libs.plc_boolean_reader import PLCBooleanReader
from RaspPiReader import pool

logger = logging.getLogger(__name__)

class BooleanValueUpdater:
    """
    A utility class to update boolean indicators on the main form.
    """

    def __init__(self, main_form):
        """
        Initialize the updater with a reference to the main form.
        Args:
            main_form: The main form instance that contains UI elements to update.
        """
        self.main_form = main_form
        self.boolean_reader = None
        self.update_timer = None
        # Lists for 6 boolean addresses and their corresponding labels (default if not configured)
        self.boolean_addresses = [1, 17, 33, 49, 65, 81]
        self.boolean_labels = [f"Bool {i}" for i in range(1, 7)]
        self.indicators = []   # UI indicator widgets (e.g., QLabel)
    
    def initialize(self):
        """
        Initialize the boolean updater with connection parameters from the application settings.
        Creates the PLCBooleanReader and loads the boolean addresses.
        Starts the update timer.
        Returns True if successfully initialized, otherwise False.
        """
        try:
            connection_type = pool.config('plc/connection_type', str, 'tcp')
            connection_params = {}
            
            if connection_type == 'tcp':
                connection_params = {
                    'host': pool.config('plc/host', str, '127.0.0.1'),
                    'port': pool.config('plc/tcp_port', int, 502),
                    'timeout': pool.config('plc/timeout', float, 1.0),
                    # Uncomment and set this if your PLC coil addresses are offset
                    # 'address_offset': pool.config('plc/address_offset', int, 0)
                }
            else:  # RTU
                connection_params = {
                    'port': pool.config('plc/port', str, 'COM1'),
                    'baudrate': pool.config('plc/baudrate', int, 9600),
                    'bytesize': pool.config('plc/bytesize', int, 8),
                    'parity': pool.config('plc/parity', str, 'N'),
                    'stopbits': pool.config('plc/stopbits', float, 1.0)
                }
            
            # Create the boolean reader instance with the given connection parameters.
            self.boolean_reader = PLCBooleanReader(
                connection_type=connection_type,
                connection_params=connection_params
            )
            
            # Load boolean addresses from configuration if available. Limit to max 6.
            self._load_boolean_addresses()
            
            # Initialize the UI indicators (e.g., QLabel or other)
            self._initialize_indicators()
            
            # Set up the update timer to refresh boolean statuses periodically.
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_boolean_values)
            self.update_timer.start(1000)  # update every second

            logger.info("Boolean value updater initialized")
            return True

        except Exception as e:
            logger.error(f"Error initializing boolean updater: {e}")
            return False

    def _load_boolean_addresses(self):
        """
        Load boolean addresses and labels from application settings.
        If configuration is missing, defaults to [1, 17, 33, 49, 65, 81].
        """
        try:
            addresses = []
            labels = []
            for i in range(1, 7):
                address_key = f"plc/bool_address_{i}"
                label_key = f"plc/bool_label_{i}"
                addr = pool.config(address_key, int, 0)
                lbl = pool.config(label_key, str, f"Bool {i}")
                if addr > 0:
                    addresses.append(addr)
                    labels.append(lbl)
                    logger.debug(f"Loaded boolean address {addr} with label '{lbl}'")
                else:
                    logger.warning(f"No configuration found for {address_key}, using default")
                    # use the default value if not configured
                    defaults = [1, 17, 33, 49, 65, 81]
                    addresses = defaults
                    labels = [f"Bool {i}" for i in range(1, 7)]
                    break

            self.boolean_addresses = addresses
            self.boolean_labels = labels
            logger.info(f"Loaded {len(self.boolean_addresses)} boolean addresses")
        except Exception as e:
            logger.error(f"Error loading boolean addresses: {e}")
            # Fall back to defaults
            self.boolean_addresses = [1, 17, 33, 49, 65, 81]
            self.boolean_labels = [f"Bool {i}" for i in range(1, 7)]

    def _initialize_indicators(self):
        """
        Initialize references to UI indicator elements on the main form.
        The expected naming is either boolIndicator1 ... boolIndicator6
        or alternatively lblBool1 ... lblBool6.
        """
        try:
            self.indicators = []
            for i in range(1, 7):
                indicator_name = f"boolIndicator{i}"
                if hasattr(self.main_form, indicator_name):
                    indicator = getattr(self.main_form, indicator_name)
                    self.indicators.append(indicator)
                    logger.debug(f"Found boolean indicator UI element: {indicator_name}")
                else:
                    # As fallback, try alternative naming: lblBool{i}
                    alt_name = f"lblBool{i}"
                    if hasattr(self.main_form, alt_name):
                        indicator = getattr(self.main_form, alt_name)
                        self.indicators.append(indicator)
                        logger.debug(f"Found boolean indicator UI element: {alt_name}")
                    else:
                        self.indicators.append(None)
                        logger.warning(f"Boolean indicator UI element not found for index {i}")
        except Exception as e:
            logger.error(f"Error initializing boolean indicators: {e}")

    def update_boolean_values(self):
        """
        Update the status of boolean indicators on the UI.
        Uses the PLCBooleanReader to read all six boolean values,
        then updates each corresponding indicator (if present).
        """
        try:
            # Read all boolean values using the boolean reader. This returns a dict with keys 1-6.
            plc_results = self.boolean_reader.read_all_boolean_values(unit=1)
            logger.debug(f"PLC boolean results: {plc_results}")
            # Loop through each address index [1,6] and update the corresponding UI element.
            for index in range(1, 7):
                value = plc_results.get(index)
                # Decide status text
                if value is None:
                    status_text = f"{self.boolean_labels[index-1]}: N/A"
                else:
                    status_text = f"{self.boolean_labels[index-1]}: {'ON' if value else 'OFF'}"
                # Update indicator if available
                if index-1 < len(self.indicators) and self.indicators[index-1] is not None:
                    indicator = self.indicators[index-1]
                    if isinstance(indicator, QtWidgets.QLabel):
                        indicator.setText(status_text)
                    # Additional widget types can be handled here
                logger.debug(f"Updated boolean indicator {index} with status: {status_text}")
        except Exception as e:
            logger.error(f"Error updating boolean values: {e}")

    def stop(self):
        """
        Stop the boolean value updater. Stops the update timer and disconnects the PLC reader.
        """
        if self.update_timer:
            self.update_timer.stop()
        if self.boolean_reader:
            self.boolean_reader.disconnect()
        
        logger.info("Boolean value updater stopped")