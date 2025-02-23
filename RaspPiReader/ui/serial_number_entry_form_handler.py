from PyQt5 import QtWidgets
from RaspPiReader.ui.serial_number_entry_form import Ui_SerialNumberEntryForm
from RaspPiReader.ui.program_selection_form_handler import ProgramSelectionFormHandler
from RaspPiReader.ui.duplicate_password_dialog import DuplicatePasswordDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData
class SerialNumberEntryFormHandler(QtWidgets.QWidget):
    def __init__(self, work_order, quantity, parent=None):
        super(SerialNumberEntryFormHandler, self).__init__(parent)
        self.ui = Ui_SerialNumberEntryForm()
        self.ui.setupUi(self)
        self.work_order = work_order
        self.quantity = quantity
        # Set the table row count to the product quantity
        self.ui.serialTableWidget.setRowCount(quantity)
        # Connect Excel import, search, next, and cancel buttons.
        self.ui.importExcelButton.clicked.connect(self.import_from_excel)
        self.ui.searchButton.clicked.connect(self.search_serial)
        self.ui.nextButton.clicked.connect(self.next)
        self.ui.cancelButton.clicked.connect(self.close)
        self.db = Database("sqlite:///local_database.db")
    
    def import_from_excel(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Serial Numbers", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_name:
            import pandas as pd
            df = pd.read_excel(file_name, header=None)
            if len(df) != self.quantity:
                QtWidgets.QMessageBox.warning(
                    self, "Warning",
                    f"Expected {self.quantity} serial numbers, but found {len(df)} in the file."
                )
                return
            for i in range(self.quantity):
                serial_val = str(df.iloc[i, 0]).strip()
                self.ui.serialTableWidget.setItem(i, 0, QtWidgets.QTableWidgetItem(serial_val))
    
    def search_serial(self):
        sn = self.ui.searchLineEdit.text().strip()
        if not sn:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter a serial number to search.")
            return
        # Assume the Database class provides a search_serial_number(sn) method.
        result = self.db.search_serial_number(sn)
        if result:
            QtWidgets.QMessageBox.information(self, "Search Result", f"Serial {sn} found in the database.")
        else:
            QtWidgets.QMessageBox.information(self, "Search Result", f"Serial {sn} not found.")
    
    def next(self):
        serial_numbers = []
        # Collect and validate serial numbers from each row in serialTableWidget
        for row in range(self.ui.serialTableWidget.rowCount()):
            item = self.ui.serialTableWidget.item(row, 0)
            if item:
                sn = item.text().strip()
                if not sn:
                    QtWidgets.QMessageBox.warning(self, "Warning", "All serial fields must be filled.")
                    return
                if sn in serial_numbers:
                    QtWidgets.QMessageBox.warning(self, "Warning", f"Duplicate serial number entered: {sn}")
                    return
                serial_numbers.append(sn)
            else:
                QtWidgets.QMessageBox.warning(self, "Warning", "All serial fields must be filled.")
                return
        
        # Check for duplicate serials already in the database.
        db_duplicates = []
        for sn in serial_numbers:
            if self.db.check_duplicate_serial(sn):
                db_duplicates.append(sn)
        if db_duplicates:
            dlg = DuplicatePasswordDialog(db_duplicates)
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                # For duplicates found in the DB, append an "R"
                serial_numbers = [f"{sn}R" if sn in db_duplicates else sn for sn in serial_numbers]
            else:
                # If password check not authorized, do not proceed.
                return
        
        # Proceed to Program Selection form passing work order and the serial numbers list.
        self.program_form = ProgramSelectionFormHandler(self.work_order, serial_numbers)
        self.program_form.show()
        self.close()
class SerialNumberSearchFormHandler(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SerialNumberSearchFormHandler, self).__init__(parent)
        self.setWindowTitle("Search Serial Number")
        self.layout = QtWidgets.QVBoxLayout(self)
        self.searchLineEdit = QtWidgets.QLineEdit(self)
        self.searchLineEdit.setPlaceholderText("Enter serial number to search")
        self.layout.addWidget(self.searchLineEdit)
        self.searchButton = QtWidgets.QPushButton("Search", self)
        self.layout.addWidget(self.searchButton)
        self.resultLabel = QtWidgets.QLabel("", self)
        self.layout.addWidget(self.resultLabel)
        self.searchButton.clicked.connect(self.search_serial)
        self.db = Database("sqlite:///local_database.db")

    def search_serial(self):
        sn = self.searchLineEdit.text().strip()
        if not sn:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter a serial number.")
            return
        # Query cycles whose serial_numbers field contains the serial.
        cycle = self.db.session.query(CycleData).filter(CycleData.serial_numbers.like(f"%{sn}%")).first()
        if cycle:
            self.resultLabel.setText(f"Found cycle Order: {cycle.order_id}. Reports are in the reports folder.")
        else:
            self.resultLabel.setText("No cycle found with that serial number.")