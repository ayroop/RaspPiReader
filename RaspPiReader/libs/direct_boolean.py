"""
Direct Boolean Reader module
This module provides a very simple, direct approach to reading boolean values
from PLC coils without any extra abstraction layers.
"""

import logging
from RaspPiReader import pool
from pymodbus.client import ModbusTcpClient

logger = logging.getLogger(__name__)

def read_boolean(address, unit=1):
    """
    Read a boolean/coil value directly from the PLC
    
    Args:
        address (int): The address to read (1-based addressing)
        unit (int): The slave unit ID
        
    Returns:
        bool or None: The boolean value, or None if error
    """
    # Get PLC connection parameters from configuration
    host = pool.config('plc/host', str, '127.0.0.1')
    port = pool.config('plc/tcp_port', int, 502)
    
    # Create a client connection
    client = ModbusTcpClient(host=host, port=port)
    
    try:
        # Connect to the client
        if not client.connect():
            logger.error(f"Failed to connect to PLC at {host}:{port}")
            return None
        
        # Convert to 0-based addressing for Modbus
        modbus_address = address - 1
        
        logger.debug(f"Reading boolean from address {address} (Modbus address {modbus_address})")
        response = client.read_coils(modbus_address, count=1, unit=unit)
        
        if response and not response.isError():
            value = response.bits[0]
            logger.debug(f"Successfully read boolean from address {address}: {value}")
            return value
        else:
            error_msg = str(response) if response else "No response"
            logger.error(f"Error reading boolean from address {address}: {error_msg}")
            return None
    except Exception as e:
        logger.exception(f"Exception reading boolean from address {address}: {e}")
        return None
    finally:
        # Always close the connection
        client.close()

def read_multiple_booleans(addresses, unit=1):
    """
    Read multiple boolean values from the PLC using a single connection
    
    Args:
        addresses (list): List of addresses to read (1-based)
        unit (int): Slave unit ID
        
    Returns:
        dict: Dictionary mapping addresses to values (True, False, or None)
    """
    # Get PLC connection parameters from configuration
    host = pool.config('plc/host', str, '127.0.0.1')
    port = pool.config('plc/tcp_port', int, 502)
    
    client = None
    results = {}
    
    # Initialize results with None for all addresses
    for address in addresses:
        results[address] = None
    
    try:
        # Create a single client for all reads
        client = ModbusTcpClient(host=host, port=port)
        
        # Connect to the client
        if not client.connect():
            logger.error(f"Failed to connect to Modbus server at {host}:{port}")
            return results
        
        # Read each address individually to avoid issues with non-contiguous addresses
        for address in addresses:
            try:
                # Convert to 0-based addressing for Modbus
                modbus_address = address - 1
                
                logger.debug(f"Reading coil at address {address} (Modbus address {modbus_address})")
                response = client.read_coils(modbus_address, count=1, unit=unit)
                
                if response and not response.isError():
                    value = response.bits[0]
                    logger.debug(f"Coil value at address {address}: {value}")
                    results[address] = value
                else:
                    logger.error(f"Error reading coil at address {address}: {response}")
            except Exception as e:
                logger.exception(f"Exception reading coil at address {address}: {e}")
                # Continue with the next address even if this one fails
                
    except Exception as e:
        logger.exception(f"Exception in read_multiple_booleans: {e}")
        
    finally:
        # Always close the client
        if client:
            client.close()
            
    return results

def update_boolean_indicators(main_form):
    """
    Update all boolean indicators on the main form using a single connection
    
    Args:
        main_form: The MainFormHandler instance
    """
    try:
        # Define boolean addresses to read
        boolean_addresses = [464, 465, 466, 467, 468, 469]
        
        # Make sure we have boolean indicators
        if not hasattr(main_form, 'boolIndicator1'):
            _create_boolean_indicators(main_form)
        
        # Read all boolean values at once with a single connection
        values = read_multiple_booleans(boolean_addresses)
        
        # Update each indicator
        for i, address in enumerate(boolean_addresses):
            if i < 6:  # We only have 6 indicators
                indicator_name = f"boolIndicator{i+1}"
                if hasattr(main_form, indicator_name):
                    indicator = getattr(main_form, indicator_name)
                    
                    # Get the value for this address
                    value = values.get(address)
                    
                    # Log the result
                    logger.debug(f"Read Boolean from address {address}: {value}")
                    
                    # Update the indicator
                    if value is None:
                        indicator.setText(f"Bool {i+1}: N/A")
                        indicator.setStyleSheet("color: gray;")
                    elif value is True:
                        indicator.setText(f"Bool {i+1}: ON")
                        indicator.setStyleSheet("color: green;")
                    else:
                        indicator.setText(f"Bool {i+1}: OFF")
                        indicator.setStyleSheet("color: red;")
        
    except Exception as e:
        logger.exception(f"Error updating boolean indicators: {e}")

def _create_boolean_indicators(main_form):
    """
    Create UI elements for boolean indicators if they don't exist
    
    Args:
        main_form: The MainFormHandler instance
    """
    from PyQt5 import QtWidgets, QtCore
    
    try:
        # Get a reference to the form layout for the indicators
        if hasattr(main_form, "boolStatusWidgetContainer") and main_form.boolStatusWidgetContainer:
            indicator_layout = main_form.boolStatusWidgetContainer.layout()
        else:
            # Create a container if it doesn't exist
            main_form.boolStatusWidgetContainer = QtWidgets.QWidget(main_form)
            indicator_layout = QtWidgets.QVBoxLayout(main_form.boolStatusWidgetContainer)
            main_form.boolStatusWidgetContainer.setLayout(indicator_layout)
            
            # Add the container to the central widget
            central_layout = main_form.centralWidget().layout()
            if central_layout is None:
                central_layout = QtWidgets.QVBoxLayout(main_form.centralWidget())
                main_form.centralWidget().setLayout(central_layout)
            central_layout.addWidget(main_form.boolStatusWidgetContainer)
        
        # Create boolean indicators if they don't exist
        for i in range(1, 7):
            indicator_name = f"boolIndicator{i}"
            if not hasattr(main_form, indicator_name):
                # Create a QLabel for each boolean indicator
                indicator = QtWidgets.QLabel(f"Bool {i}: N/A")
                indicator.setStyleSheet("background-color: gray; color: white; border-radius: 5px; padding: 2px;")
                indicator.setAlignment(QtCore.Qt.AlignCenter)
                indicator.setMinimumHeight(25)
                
                # Save reference to the indicator
                setattr(main_form, indicator_name, indicator)
                
                # Add to layout
                indicator_layout.addWidget(indicator)
                
                logger.debug(f"Created boolean indicator: {indicator_name}")
                
    except Exception as e:
        logger.exception(f"Error creating boolean indicators: {e}")
