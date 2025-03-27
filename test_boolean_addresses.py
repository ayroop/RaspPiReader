"""
Test script to verify the direct boolean reading approach.
This test script uses the minimal direct_boolean module to read boolean values.
"""

import logging
import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

def test_direct_boolean():
    """Test reading boolean values directly"""
    try:
        # Import the direct boolean reader module
        from RaspPiReader.libs.direct_boolean import read_boolean
        
        # Define boolean addresses to test
        addresses = [464, 465, 466, 467, 468, 469]
        
        # Read each address
        for address in addresses:
            log.info(f"Reading boolean at address {address}...")
            value = read_boolean(address)
            log.info(f"Boolean value at address {address}: {value}")
            
    except Exception as e:
        log.exception(f"Error: {e}")

if __name__ == "__main__":
    log.info("Testing direct boolean reading")
    test_direct_boolean()