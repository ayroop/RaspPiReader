from PyQt5 import QtWidgets
from RaspPiReader.ui.work_order_form import Ui_WorkOrderForm
from RaspPiReader.ui.serial_number_entry_form_handler import SerialNumberEntryFormHandler
import logging
from RaspPiReader.libs import plc_communication
from RaspPiReader.libs.communication import dataReader
from RaspPiReader import pool
from PyQt5.QtWidgets import QMessageBox
# Import database and models for work order uniqueness check
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData
from RaspPiReader.utils.virtual_keyboard import setup_virtual_keyboard

logger = logging.getLogger(__name__)

class WorkOrderFormHandler(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(WorkOrderFormHandler, self).__init__(parent)
        self.ui = Ui_WorkOrderForm()  # Make sure your UI file no longer pre-populates order/quantity
        self.ui.setupUi(self)
        self.ui.quantitySpinBox.setMaximum(250)
        self.ui.nextButton.clicked.connect(self.on_next)
        self.ui.cancelButton.clicked.connect(self.on_cancel)
        
        # Setup virtual keyboard for the work order input
        setup_virtual_keyboard(self.ui.workOrderLineEdit)
    
    def on_cancel(self):
        """Handle form cancellation"""
        logger.info("Work order form cancelled")
        
        # Reset menu items in main form
        main_form = pool.get('main_form')
        if main_form:
            main_form.actionStart.setEnabled(True)
            main_form.actionStop.setEnabled(False)
        
        # Clear any cycle data that might have been set
        pool.set("current_cycle", None)
        
        # Close the form
        self.close()
    
    def on_next(self):
        work_order = self.ui.workOrderLineEdit.text().strip()
        quantity = self.ui.quantitySpinBox.value()

        if not work_order:
            QMessageBox.warning(self, "Input Error", "Please enter a Work Order Number")
            return
        if quantity <= 0:
            QMessageBox.warning(self, "Input Error", "Product quantity must be at least 1")
            return

        # Check uniqueness: query the database for an existing cycle with this work order
        db = Database("sqlite:///local_database.db")
        existing_cycle = db.session.query(CycleData).filter(CycleData.order_id == work_order).first()
        if existing_cycle:
            QMessageBox.warning(self, "Duplicate Work Order", "This work order already exists. Please enter a unique work order number.")
            return

        logger.info(f"Starting serial number entry for work order {work_order} with quantity {quantity}")

        # Update both the in‑memory registry and QSettings (pool)
        pool.set("order_id", work_order)
        pool.set("quantity", quantity)
        pool.set_config("order_id", work_order)
        pool.set_config("quantity", quantity)

        # Then launch the Serial Number Entry form.
        self.serial_form = SerialNumberEntryFormHandler(work_order, quantity)
        self.serial_form.show()
        self.close()
    
    def _start(self):
        """Start reading data"""
        # First make sure communication is properly set up
        if not plc_communication.is_connected():
            # Try to initialize PLC communication
            success = plc_communication.initialize_plc_communication()
            if not success:
                QMessageBox.critical(self, "Connection Error",
                                    "Failed to connect to PLC. Please check your connection settings.")
                return

        # Start the data reader
        dataReader.start()
        
        # Update the UI to reflect the current connection type
        self.update_connection_status_display()
        
        # Start the data reading timer
        self.timer.start(1000)
        self.running = True