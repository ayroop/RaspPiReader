from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui.new_cycle import Ui_NewCycle
from RaspPiReader.ui.work_order_form_handler import WorkOrderFormHandler
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
        logger.info("Stop Cycle button clicked")
        # Get the main form instance from the pool 
        main_form = pool.get('main_form')
        if main_form and hasattr(main_form, '_stop'):
            main_form._stop()  # call the shared stop cycle method
        else:
            logger.error("Main form not found, or stop method not available. Cannot stop cycle.")
            QtWidgets.QMessageBox.critical(
                self, "Error", 
                "Unable to stop the cycle. The main form is not available."
            )