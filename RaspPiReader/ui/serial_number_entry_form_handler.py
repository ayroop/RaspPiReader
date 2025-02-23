from PyQt5 import QtWidgets
from RaspPiReader.ui.serial_number_entry_form import Ui_SerialNumberEntryForm  # generated from serial_number_entry_form.ui
from RaspPiReader.ui.program_selection_form_handler import ProgramSelectionFormHandler
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Product
from RaspPiReader.ui.duplicate_password_dialog import DuplicatePasswordDialog

class SerialNumberEntryFormHandler(QtWidgets.QWidget):
    def __init__(self, work_order, quantity, parent=None):
        super(SerialNumberEntryFormHandler, self).__init__(parent)
        self.ui = Ui_SerialNumberEntryForm()  # note: no module prefix here
        self.ui.setupUi(self)
        self.work_order = work_order
        self.quantity = quantity
        # Set the table to have "quantity" rows
        self.ui.serialTableWidget.setRowCount(quantity)
        self.ui.importExcelButton.clicked.connect(self.import_from_excel)
        self.ui.nextButton.clicked.connect(self.next)
        self.ui.cancelButton.clicked.connect(self.close)
        self.db = Database("sqlite:///local_database.db")
    
    def import_from_excel(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Serial Numbers", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_name:
            import pandas as pd  # ensure pandas is imported
            df = pd.read_excel(file_name)
            if len(df) != self.quantity:
                QtWidgets.QMessageBox.warning(
                    self, "Warning",
                    f"Expected {self.quantity} serial numbers, but found {len(df)}."
                )
                return
            for i in range(self.quantity):
                serial_val = str(df.iloc[i, 0]).strip()
                self.ui.serialTableWidget.setItem(i, 0, QtWidgets.QTableWidgetItem(serial_val))
    
    def next(self):
        serial_numbers = []
        # Read each row from the table and verify entries.
        for i in range(self.quantity):
            item = self.ui.serialTableWidget.item(i, 0)
            if item:
                val = item.text().strip()
                if not val:
                    QtWidgets.QMessageBox.warning(self, "Warning", "All serial fields must be filled.")
                    return
                if val in serial_numbers:
                    QtWidgets.QMessageBox.warning(self, "Warning", f"Duplicate serial number entered: {val}")
                    return
                serial_numbers.append(val)
            else:
                QtWidgets.QMessageBox.warning(self, "Warning", "All serial fields must be filled.")
                return
        
        # Check against the database for duplicate serial numbers in Product table.
        db_duplicates = []
        for sn in serial_numbers:
            existing = self.db.session.query(Product).filter_by(serial_number=sn).first()
            if existing:
                db_duplicates.append(sn)
        
        if db_duplicates:
            dlg = DuplicatePasswordDialog(db_duplicates)
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                # Append an "R" to duplicate serial numbers if authorized.
                serial_numbers = [sn + "R" if sn in db_duplicates else sn for sn in serial_numbers]
            else:
                return  # Do not proceed if not authorized.
        
        # Proceed to program selection form.
        self.program_form = ProgramSelectionFormHandler(self.work_order, serial_numbers)
        self.program_form.show()
        self.close()