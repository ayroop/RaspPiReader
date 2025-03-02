from PyQt5 import QtWidgets
from RaspPiReader.ui.serial_number_management import Ui_SerialNumberManagementDialog
from RaspPiReader.libs.database import Database
import logging
import pandas as pd
import csv
import os

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

    def load_serials(self):
        # Example: load serials from the first cycle data record
        cycle_data = self.db.get_cycle_data()
        serials = []
        if cycle_data and len(cycle_data) > 0 and cycle_data[0].serial_numbers:
            serials = cycle_data[0].serial_numbers.split(",")
        self.populate_table(serials)

    def populate_table(self, serials):
        table = self.ui.serialTableWidget
        table.setRowCount(0)
        for sn in serials:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(sn))
    
    def add_serial(self):
        table = self.ui.serialTableWidget
        if table.rowCount() >= self.max_serials:
            QtWidgets.QMessageBox.warning(self, "Limit Reached", "Maximum serial numbers reached.")
            return
            
        new_sn, ok = QtWidgets.QInputDialog.getText(self, "Add Serial", "Enter new serial number:")
        if ok and new_sn.strip():
            # Check if serial already exists in the table
            for row in range(table.rowCount()):
                if table.item(row, 0).text() == new_sn.strip():
                    QtWidgets.QMessageBox.warning(self, "Duplicate", "This serial number already exists.")
                    return
                    
            # Check if serial exists in the database
            if self.db.check_duplicate_serial(new_sn.strip()):
                response = QtWidgets.QMessageBox.question(
                    self, "Duplicate Found", 
                    "This serial number exists in the database. Add anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if response == QtWidgets.QMessageBox.No:
                    return
                    
            # Add to table
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(new_sn.strip()))
            logger.info(f"Added serial number: {new_sn.strip()}")
    
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
            self, "Import Serials", "", "CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not file_name:
            return
            
        try:
            serials = []
            
            # Handle different file types
            if file_name.lower().endswith(('.xlsx', '.xls')):
                # Excel import
                df = pd.read_excel(file_name, header=None)
                serials = [str(row[0]).strip() for _, row in df.iterrows() if str(row[0]).strip()]
            elif file_name.lower().endswith('.csv'):
                # CSV import
                with open(file_name, 'r') as f:
                    csv_reader = csv.reader(f)
                    serials = [row[0].strip() for row in csv_reader if row and row[0].strip()]
            
            # Validate and add serials
            if len(serials) > self.max_serials:
                QtWidgets.QMessageBox.warning(
                    self, "Too Many Serials", 
                    f"Found {len(serials)} serial numbers. Maximum allowed is {self.max_serials}."
                )
                return
                
            # Check for duplicates
            duplicates = []
            for sn in serials:
                if self.db.check_duplicate_serial(sn):
                    duplicates.append(sn)
                    
            if duplicates:
                response = QtWidgets.QMessageBox.question(
                    self, "Duplicates Found", 
                    f"Found {len(duplicates)} duplicate serial numbers in the database. Import anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if response == QtWidgets.QMessageBox.No:
                    return
            
            # Add to table
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
            
        # Search in the table first
        table = self.ui.serialTableWidget
        found_in_table = False
        
        for row in range(table.rowCount()):
            if search_text.strip() in table.item(row, 0).text():
                table.selectRow(row)
                table.scrollToItem(table.item(row, 0))
                found_in_table = True
                break
                
        # Search in the database
        cycle_data = self.db.search_serial_number(search_text.strip())
        
        if found_in_table and cycle_data:
            # Found in both places
            QtWidgets.QMessageBox.information(
                self, "Serial Number Found", 
                f"Serial {search_text} found in the current table AND in work order {cycle_data.order_id}."
            )
        elif found_in_table:
            # Only found in table
            QtWidgets.QMessageBox.information(
                self, "Serial Number Found", 
                f"Serial {search_text} found in the current table."
            )
        elif cycle_data:
            # Only found in database
            QtWidgets.QMessageBox.information(
                self, "Serial Number Found", 
                f"Serial {search_text} found in work order {cycle_data.order_id}."
            )
        else:
            # Not found
            QtWidgets.QMessageBox.information(
                self, "Serial Number Not Found", 
                f"Serial {search_text} was not found."
            )