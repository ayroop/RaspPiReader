from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui.new_cycle import Ui_NewCycle
from RaspPiReader.ui.work_order_form_handler import WorkOrderFormHandler
from datetime import datetime  
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData
from RaspPiReader.libs.cycle_finalization import finalize_cycle
from PyQt5.QtWidgets import QMessageBox

import logging

logger = logging.getLogger(__name__)

class NewCycleHandler(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(NewCycleHandler, self).__init__(parent)
        self.ui = Ui_NewCycle()
        self.ui.setupUi(self)
        self.ui.startCycleButton.clicked.connect(self.start_cycle)
        self.ui.stopCycleButton.clicked.connect(self.stop_cycle)

    def start_cycle(self):
        logger.info("Start Cycle button clicked - launching Work Order Form")
        # Open the Work Order Form to begin the workflow
        self.work_order_form = WorkOrderFormHandler()
        self.work_order_form.show()

    def stop_cycle(self):
        """Handle stopping the cycle and generating reports"""
        logger.info("Stop Cycle button clicked")
        
        try:
            main_form = pool.get('main_form')
            if main_form:
                # Delegate to the main form's stop method
                main_form._stop()  # This will handle all the cycle stopping logic
                logger.info("Cycle stop delegated to main form")
            else:
                logger.error("Main form not found in pool")
                QtWidgets.QMessageBox.warning(
                    self, "Warning", 
                    "Could not stop cycle - main form not found."
                )
        except Exception as e:
            logger.error(f"Error stopping cycle: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Error", 
                f"Failed to stop cycle: {str(e)}"
            )