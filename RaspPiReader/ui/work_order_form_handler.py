from PyQt5 import QtWidgets
from RaspPiReader.ui.work_order_form import Ui_WorkOrderForm
from RaspPiReader.ui.serial_number_entry_form_handler import SerialNumberEntryFormHandler
import logging

logger = logging.getLogger(__name__)

class WorkOrderFormHandler(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(WorkOrderFormHandler, self).__init__(parent)
        self.ui = Ui_WorkOrderForm()
        self.ui.setupUi(self)
        # Ensure that the quantitySpinBox maximum is set to 250 (set in your .ui design)
        self.ui.quantitySpinBox.setMaximum(250)
        self.ui.nextButton.clicked.connect(self.next)
        self.ui.cancelButton.clicked.connect(self.close)
    
    def next(self):
        work_order = self.ui.workOrderLineEdit.text().strip()
        quantity = self.ui.quantitySpinBox.value()
        
        if not work_order:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter a work order number.")
            return
            
        if quantity <= 0:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter a product quantity greater than zero.")
            return
        
        # Launch Serial Number Entry form, passing the work order and quantity
        logger.info(f"Starting serial number entry for work order {work_order} with quantity {quantity}")
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