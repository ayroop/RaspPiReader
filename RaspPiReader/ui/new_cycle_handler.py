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
        # Record the cycle start time so that MainFormHandler can detect an active cycle.
        self.cycle_start_time = datetime.now()
        # Store this cycle as the current active cycle
        
        pool.set("current_cycle", self)
        self.work_order_form = WorkOrderFormHandler()
        self.work_order_form.show()

    def stop_cycle(self):
        logger.info("Stop Cycle button clicked")
        if hasattr(self, "cycle_start_time"):
            self.cycle_end_time = datetime.now()
            duration = self.cycle_end_time - self.cycle_start_time
            logger.info(f"Cycle stopped; duration: {str(duration).split('.')[0]}")
        else:
            logger.warning("Cycle start time not set; cannot compute duration")
        
        pool.set("current_cycle", None)