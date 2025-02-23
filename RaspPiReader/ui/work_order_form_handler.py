from PyQt5 import QtWidgets
from RaspPiReader.ui.work_order_form import Ui_WorkOrderForm  # auto-generated from work_order_form.ui via pyuic5
from RaspPiReader.ui.serial_number_entry_form_handler import SerialNumberEntryFormHandler

class WorkOrderFormHandler(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(WorkOrderFormHandler, self).__init__(parent)
        self.ui = Ui_WorkOrderForm()  # ← Use direct reference (no module prefix)
        self.ui.setupUi(self)
        self.ui.nextButton.clicked.connect(self.next)
        self.ui.cancelButton.clicked.connect(self.close)
    
    def next(self):
        work_order = self.ui.workOrderLineEdit.text().strip()
        quantity = self.ui.quantitySpinBox.value()
        if not work_order:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter a work order number.")
            return
        # Create and show the serial numbers entry form (pass work_order and quantity)
        self.serial_form = SerialNumberEntryFormHandler(work_order, quantity)
        self.serial_form.show()
        self.close()