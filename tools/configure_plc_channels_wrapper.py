#!/usr/bin/env python
"""
Wrapper for PLC Channel Configuration Helper

This script wraps the configure_plc_channels.py script with proper error handling
to prevent application crashes.
"""

import sys
import os
import traceback
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='plc_configuration.log',
    filemode='a'
)
logger = logging.getLogger('PLCConfigWrapper')

def main():
    """Main function with error handling wrapper"""
    try:
        # Add project root to path for imports
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.append(project_root)
        
        # Import the configuration helper
        from tools.configure_plc_channels import PLCConfigHelper
        
        # Create application
        app = QApplication(sys.argv)
        
        # Create and show the configuration helper
        window = PLCConfigHelper()
        window.show()
        
        # Run the application
        sys.exit(app.exec_())
    except Exception as e:
        # Log the error
        logger.critical(f"Fatal error in PLC configuration: {str(e)}")
        logger.critical(traceback.format_exc())
        
        # Show error message
        if QApplication.instance():
            QMessageBox.critical(
                None,
                "Fatal Error",
                f"A critical error occurred in the PLC configuration tool:\n\n{str(e)}\n\n"
                f"See plc_configuration.log for details."
            )
        else:
            # If QApplication doesn't exist yet, create it
            app = QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Fatal Error",
                f"A critical error occurred in the PLC configuration tool:\n\n{str(e)}\n\n"
                f"See plc_configuration.log for details."
            )
        
        # Exit with error code
        sys.exit(1)

if __name__ == "__main__":
    main()