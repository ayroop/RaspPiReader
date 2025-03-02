import logging
from PyQt5 import QtWidgets
from RaspPiReader.ui.serial_number_entry_form import Ui_SerialNumberEntryForm
from RaspPiReader.ui.program_selection_form_handler import ProgramSelectionFormHandler
from RaspPiReader.ui.duplicate_password_dialog import DuplicatePasswordDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData

logger = logging.getLogger(__name__)

class SerialNumberEntryFormHandler(QtWidgets.QWidget):
    def __init__(self, work_order, quantity, parent=None):
        super(SerialNumberEntryFormHandler, self).__init__(parent)
        self.ui = Ui_SerialNumberEntryForm()
        self.ui.setupUi(self)
        self.work_order = work_order
        self.quantity = quantity
        self.setWindowTitle(f"Enter Serial Numbers for Order: {work_order}")
        
        # Set the table row count to the product quantity
        self.ui.serialTableWidget.setRowCount(quantity)
        
        # Connect Excel import, search, next, and cancel buttons.
        self.ui.importExcelButton.clicked.connect(self.import_from_excel)
        self.ui.searchButton.clicked.connect(self.search_serial)
        self.ui.nextButton.clicked.connect(self.next)
        self.ui.cancelButton.clicked.connect(self.close)
        self.db = Database("sqlite:///local_database.db")
        
        # Set placeholder text for search line edit
        self.ui.searchLineEdit.setPlaceholderText("Enter serial number to search...")
        
        # Set button text if not in the UI
        self.ui.importExcelButton.setText("Import From Excel")
        self.ui.searchButton.setText("Search")
        self.ui.nextButton.setText("Next")
        self.ui.cancelButton.setText("Cancel")
    
    def import_from_excel(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Serial Numbers", "", 
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*)"
        )
        if file_name:
            try:
                # Handle different file types
                if file_name.lower().endswith(('.xlsx', '.xls')):
                    import pandas as pd
                    df = pd.read_excel(file_name, header=None)
                    if len(df) != self.quantity:
                        QtWidgets.QMessageBox.warning(
                            self, "Warning",
                            f"Expected {self.quantity} serial numbers, but found {len(df)} in the file."
                        )
                        return
                    
                    # Clear existing table data
                    self.ui.serialTableWidget.clearContents()
                    
                    # Fill the table with serial numbers from Excel
                    for i in range(self.quantity):
                        serial_val = str(df.iloc[i, 0]).strip()
                        self.ui.serialTableWidget.setItem(i, 0, QtWidgets.QTableWidgetItem(serial_val))
                elif file_name.lower().endswith('.csv'):
                    import csv
                    with open(file_name, 'r') as f:
                        csv_reader = csv.reader(f)
                        rows = list(csv_reader)
                        if len(rows) != self.quantity:
                            QtWidgets.QMessageBox.warning(
                                self, "Warning",
                                f"Expected {self.quantity} serial numbers, but found {len(rows)} in the file."
                            )
                            return
                        
                        # Clear existing table data
                        self.ui.serialTableWidget.clearContents()
                        
                        # Fill the table with serial numbers from CSV
                        for i in range(self.quantity):
                            serial_val = str(rows[i][0]).strip()
                            self.ui.serialTableWidget.setItem(i, 0, QtWidgets.QTableWidgetItem(serial_val))
                        
                QtWidgets.QMessageBox.information(
                    self, "Import Successful", 
                    f"{self.quantity} serial numbers imported successfully."
                )
            except Exception as e:
                logger.error(f"Error importing from file: {e}")
                QtWidgets.QMessageBox.critical(
                    self, "Import Error", 
                    f"Error importing serial numbers: {str(e)}"
                )
    
    def search_serial(self):
        sn = self.ui.searchLineEdit.text().strip()
        if not sn:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter a serial number to search.")
            return
        
        # Search for the serial number in the database
        result = self.db.search_serial_number(sn)
        
        if result:
            # Format the date nicely
            created_date = result.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(result, 'created_at') and result.created_at else "Unknown date"
            
            # Show detailed information about the found serial
            QtWidgets.QMessageBox.information(
                self, "Serial Number Found",
                f"Serial number {sn} was found in:\n\n" +
                f"Work Order: {result.order_id}\n" +
                f"Cycle ID: {result.cycle_id}\n" +
                f"Created: {created_date}\n" +
                f"Quantity: {result.quantity if hasattr(result, 'quantity') else 'Unknown'}"
            )
        else:
            QtWidgets.QMessageBox.information(
                self, "Serial Number Not Found",
                f"Serial number {sn} was not found in the database."
            )
    
    def next(self):
        serial_numbers = []
        table = self.ui.serialTableWidget
        
        # Collect all entered serial numbers
        for i in range(table.rowCount()):
            item = table.item(i, 0)
            if item and item.text().strip():
                serial_numbers.append(item.text().strip())
        
        # Validate quantity
        if len(serial_numbers) != self.quantity:
            QtWidgets.QMessageBox.warning(
                self, "Warning", 
                f"Please enter {self.quantity} serial numbers. Currently have {len(serial_numbers)}."
            )
            return
        
        # Check for duplicate serial numbers in the current entry
        if len(serial_numbers) != len(set(serial_numbers)):
            QtWidgets.QMessageBox.warning(
                self, "Warning", 
                "Duplicate serial numbers detected in your input. Please correct before proceeding."
            )
            return
        
        # Check for duplicates in the database
        duplicate_serials = []
        for sn in serial_numbers:
            if self.db.check_duplicate_serial(sn):
                duplicate_serials.append(sn)
        
        if duplicate_serials:
            # Show duplicate password dialog for authorization
            dialog = DuplicatePasswordDialog(duplicate_serials, self)
            if dialog.exec_() != QtWidgets.QDialog.Accepted:
                return  # User cancelled or authorization failed
        
        # Proceed to program selection
        self.program_form = ProgramSelectionFormHandler(self.work_order, serial_numbers, self)
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
        result = self.db.search_serial_number(sn)
        
        if result:
            self.resultLabel.setText(f"Found in work order: {result.order_id}. Cycle ID: {result.cycle_id}")
            QtWidgets.QMessageBox.information(
                self, "Serial Number Found",
                f"Serial number {sn} found in work order {result.order_id}."
            )
        else:
            self.resultLabel.setText("No cycle found with that serial number.")
            QtWidgets.QMessageBox.information(
                self, "Serial Number Not Found",
                f"Serial number {sn} was not found in the database."
            )