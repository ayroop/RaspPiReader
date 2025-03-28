"""
Test script to verify the direct boolean reading approach.
This test script uses the direct_boolean module to read boolean values.
"""

import logging
import sys
import os
import time

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger()

def test_direct_boolean():
    """Test reading boolean values directly"""
    try:
        # Import the direct boolean reader module
        from RaspPiReader.libs.direct_boolean import read_boolean
        
        # Define boolean addresses to test
        addresses = [1, 17, 33, 49, 65, 81]
        
        # Check PLC connection parameters
        from RaspPiReader import pool
        host = pool.config('plc/host', str, '127.0.0.1')
        port = pool.config('plc/tcp_port', int, 502)
        
        log.info(f"PLC connection parameters: Host={host}, Port={port}")
        
        # Test network connectivity
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            if result == 0:
                log.info(f"Port {port} is open on host {host}")
            else:
                log.error(f"Port {port} is not accessible on host {host}. Error code: {result}")
            sock.close()
        except Exception as e:
            log.error(f"Network test failed: {e}")
        
        # Read each address
        for address in addresses:
            log.info(f"Reading boolean at address {address}...")
            value = read_boolean(address)
            log.info(f"Boolean value at address {address}: {value}")
            time.sleep(0.5)  # Brief pause between reads
            
    except ImportError as e:
        log.error(f"Import error: {e}")
        log.info("Checking module structure...")
        
        try:
            import RaspPiReader
            log.info(f"RaspPiReader module found at: {RaspPiReader.__file__}")
            
            # List modules in libs
            import pkgutil
            log.info("Modules in RaspPiReader.libs:")
            for _, name, _ in pkgutil.iter_modules(RaspPiReader.libs.__path__):
                log.info(f"  - {name}")
                
        except Exception as e2:
            log.error(f"Error inspecting modules: {e2}")
            
    except Exception as e:
        log.exception(f"Error: {e}")

def test_boolean_reader_class():
    """Test reading boolean values using the DirectBooleanReader class"""
    try:
        # Import the boolean reader class
        from RaspPiReader.libs.direct_boolean_reader import DirectBooleanReader
        
        # Define boolean addresses to test
        addresses = [1, 17, 33, 49, 65, 81]
        
        # Create reader instance
        reader = DirectBooleanReader()
        log.info(f"Created DirectBooleanReader with host={reader.host}, port={reader.port}")
        
        # Test connection
        if reader.connect():
            log.info("Successfully connected to PLC")
            
            # Read each address
            for address in addresses:
                log.info(f"Reading boolean at address {address} (class method)...")
                value = reader.read_boolean(address)
                log.info(f"Boolean value at address {address}: {value}")
                time.sleep(0.5)  # Brief pause between reads
                
            # Test reading multiple values at once
            log.info("Reading multiple booleans at once...")
            values = reader.read_multiple_booleans(addresses)
            for addr, value in values.items():
                log.info(f"Multiple read - Boolean value at address {addr}: {value}")
        else:
            log.error("Failed to connect to PLC")
            
    except Exception as e:
        log.exception(f"Error in class test: {e}")

if __name__ == "__main__":
    log.info("=========== Testing direct boolean module ===========")
    test_direct_boolean()
    
    log.info("\n=========== Testing DirectBooleanReader class ===========")
    test_boolean_reader_class()
