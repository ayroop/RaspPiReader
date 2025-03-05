import logging
from PyQt5 import QtWidgets
from RaspPiReader.ui.serial_number_management import Ui_SerialNumberManagementDialog
from RaspPiReader.libs.database import Database
import pandas as pd
import csv
from datetime import datetime
from RaspPiReader.libs.models import CycleData
logger = logging.getLogger(__name__)

class SerialNumberManagementFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SerialNumberManagementFormHandler, self).__init__(parent)
        self.ui = Ui_SerialNumberManagementDialog()
        self.ui.setupUi(self)
        self.db = Database("sqlite:///local_database.db")
        self.max_serials = 250
        self.load_serials()
        self.ui.addButton.clicked.connect(self.add_serial)
        self.ui.removeButton.clicked.connect(self.remove_serial)
        self.ui.importButton.clicked.connect(self.import_serials)
        self.ui.searchButton.clicked.connect(self.search_serial)
        
        # Add a Save button to the dialog
        self.ui.saveButton = QtWidgets.QPushButton("Save Changes", self)
        self.ui.buttonLayout.addWidget(self.ui.saveButton)
        self.ui.saveButton.clicked.connect(self.save_serials)
        
        # Connect the accepted signal to save serials when OK is clicked
        self.accepted.connect(self.save_serials)

    def load_serials(self):
    # First check for the special "managed serials" record
        managed_serials = self.db.get_managed_serials()
        if managed_serials and managed_serials.serial_numbers:
            # If we have a managed serials record, use it
            serials = [sn.strip() for sn in managed_serials.serial_numbers.split(",") if sn.strip()]
            logger.info(f"Loaded {len(serials)} managed serial numbers")
            self.populate_table(serials)
            return
            
        # Fallback: Get all cycle data records from the database
        logger.info("No managed serials found, loading from all cycle data")
        cycle_data = self.db.get_cycle_data()
        serials = []
        # Extract all serial numbers from all cycle records
        for record in cycle_data:
            if record and record.serial_numbers:
                serials.extend(record.serial_numbers.split(","))
        # Display unique serial numbers (trim whitespace)
        unique_serials = list(set([sn.strip() for sn in serials if sn.strip()]))
        # Enforce max_serials limit
        if len(unique_serials) > self.max_serials:
            unique_serials = unique_serials[:self.max_serials]
            QtWidgets.QMessageBox.information(
                self, "Info",
                f"Only showing the first {self.max_serials} unique serial numbers."
            )
        self.populate_table(unique_serials)

    
    def populate_table(self, serials):
        table = self.ui.serialTableWidget
        table.setRowCount(0)
        for sn in serials:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(sn))
        table.resizeColumnsToContents()

    def add_serial(self):
        table = self.ui.serialTableWidget
        if table.rowCount() >= self.max_serials:
            QtWidgets.QMessageBox.warning(self, "Limit Reached", "Maximum serial numbers reached.")
            return
        new_sn, ok = QtWidgets.QInputDialog.getText(self, "Add Serial", "Enter new serial number:")
        if ok and new_sn.strip():
            new_sn = new_sn.strip()
            # Check if serial already exists in the table
            for row in range(table.rowCount()):
                if table.item(row, 0).text() == new_sn:
                    QtWidgets.QMessageBox.warning(self, "Duplicate", "This serial number already exists.")
                    return
            # Check if serial exists in the database
            if self.db.check_duplicate_serial(new_sn):
                response = QtWidgets.QMessageBox.question(
                    self, "Duplicate Found",
                    "This serial number exists in the database. Add anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if response == QtWidgets.QMessageBox.No:
                    return
            # Add new serial number to table
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(new_sn))
            logger.info(f"Added serial number: {new_sn}")

    def remove_serial(self):
        table = self.ui.serialTableWidget
        selected = table.selectedItems()
        if selected:
            row = selected[0].row()
            sn = table.item(row, 0).text()
            response = QtWidgets.QMessageBox.question(
                self, "Confirm Removal",
                f"Remove serial number {sn}?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if response == QtWidgets.QMessageBox.Yes:
                table.removeRow(row)
                logger.info(f"Removed serial number: {sn}")
        else:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a serial number to remove.")

    def import_serials(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Serials", "",
            "CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not file_name:
            return
        try:
            serials = []
            # Handle Excel files
            if file_name.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_name, header=None)
                serials = [str(row[0]).strip() for _, row in df.iterrows() if str(row[0]).strip()]
            elif file_name.lower().endswith('.csv'):
                with open(file_name, 'r', newline='') as f:
                    csv_reader = csv.reader(f)
                    serials = [row[0].strip() for row in csv_reader if row and row[0].strip()]
            # Validate maximum allowed serial numbers
            if len(serials) > self.max_serials:
                QtWidgets.QMessageBox.warning(
                    self, "Too Many Serials",
                    f"Found {len(serials)} serial numbers. Maximum allowed is {self.max_serials}."
                )
                return
            # Check for duplicate serials in the database
            duplicates = [sn for sn in serials if self.db.check_duplicate_serial(sn)]
            if duplicates:
                response = QtWidgets.QMessageBox.question(
                    self, "Duplicates Found",
                    f"Found {len(duplicates)} duplicate serial numbers in the database. Import anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if response == QtWidgets.QMessageBox.No:
                    return
            # Populate table with imported serials
            self.populate_table(serials)
            QtWidgets.QMessageBox.information(
                self, "Import Complete",
                f"Successfully imported {len(serials)} serial numbers."
            )
            logger.info(f"Imported {len(serials)} serial numbers from {file_name}")
        except Exception as e:
            logger.error(f"Error importing serial numbers: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Import Error",
                f"An error occurred while importing: {str(e)}"
            )

    def search_serial(self):
        search_text, ok = QtWidgets.QInputDialog.getText(
            self, "Search Serial", "Enter serial number to search:"
        )
        if not ok or not search_text.strip():
            return
        search_text = search_text.strip()
        # Search in the table first
        table = self.ui.serialTableWidget
        found_in_table = False
        for row in range(table.rowCount()):
            if search_text in table.item(row, 0).text():
                table.selectRow(row)
                table.scrollToItem(table.item(row, 0))
                found_in_table = True
                break
        # Search in the database
        cycle_data = self.db.search_serial_number(search_text)
        if found_in_table and cycle_data:
            QtWidgets.QMessageBox.information(
                self, "Serial Number Found",
                f"Serial {search_text} found in the current table AND in work order {cycle_data.order_id}."
            )
        elif found_in_table:
            QtWidgets.QMessageBox.information(
                self, "Serial Number Found",
                f"Serial {search_text} found in the current table."
            )
        elif cycle_data:
            QtWidgets.QMessageBox.information(
                self, "Serial Number Found",
                f"Serial {search_text} found in work order {cycle_data.order_id}."
            )
        else:
            QtWidgets.QMessageBox.information(
                self, "Serial Number Not Found",
                f"Serial {search_text} was not found."
            )

    def save_serials(self):
        """Save all serials from the table back to the database"""
        try:
            # Get all serial numbers from the table
            table = self.ui.serialTableWidget
            serials = []
            
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item and item.text().strip():
                    serials.append(item.text().strip())
            
            # Create a new cycle data record just for storing these serials
            # (or update an existing record designated for managed serials)
            managed_serials = self.db.get_managed_serials()
            if managed_serials:
                managed_serials.serial_numbers = ",".join(serials)
                self.db.session.commit()
                logger.info(f"Updated managed serials record with {len(serials)} serial numbers")
            else:
                # Create a new record to store managed serials with a special ID
                from datetime import datetime
                new_record = CycleData(
                    order_id="MANAGED_SERIALS",  # Special identifier
                    cycle_id="REFERENCE_LIST",
                    serial_numbers=",".join(serials),
                    created_at=datetime.now()
                )
                self.db.session.add(new_record)
                self.db.session.commit()
                logger.info(f"Created new managed serials record with {len(serials)} serial numbers")
            
            QtWidgets.QMessageBox.information(
                self, "Success", 
                f"Successfully saved {len(serials)} serial numbers to the database."
            )
            logger.info(f"Saved {len(serials)} serial numbers to the database")
            
        except Exception as e:
            logger.error(f"Error saving serial numbers: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Save Error", 
                f"An error occurred while saving: {str(e)}"
            )