import logging
import os
from datetime import datetime

def setup_logging():
    """Configure logging for the entire application"""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Define log file name with timestamp
    log_file = os.path.join(logs_dir, f'rasppi_reader_{datetime.now().strftime("%Y%m%d")}.log')
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    # Set specific log levels for different modules
    logging.getLogger('pymodbus').setLevel(logging.WARNING)
    logging.getLogger('RaspPiReader.libs.communication').setLevel(logging.DEBUG)
    
    logging.info("Logging initialized")