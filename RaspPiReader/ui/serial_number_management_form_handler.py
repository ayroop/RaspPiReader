import logging
from PyQt5 import QtWidgets
from RaspPiReader.ui.serial_number_management import Ui_SerialNumberManagementDialog
from RaspPiReader.libs.database import Database
import pandas as pd
from PyQt5.QtCore import Qt
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
        
        # Connect button signals
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
        """Load managed serial numbers from the database."""
        # First check for the special "managed serials" record
        managed_serials = self.db.get_managed_serials()
        if managed_serials and managed_serials.serial_numbers:
            serials = managed_serials.serial_numbers.split(',')
            self.populate_table(serials)
            logger.info(f"Loaded {len(serials)} managed serial numbers")
            return
            
        # Fallback: Get all cycle data records from the database
        all_serials = []
        cycles = self.db.get_cycle_data()
        for cycle in cycles:
            if cycle.serial_numbers:
                all_serials.extend(cycle.serial_numbers.split(','))
        
        # Remove duplicates and sort
        all_serials = sorted(list(set(all_serials)))
        self.populate_table(all_serials)
        logger.info(f"Loaded {len(all_serials)} unique serial numbers from all cycle data")

    def populate_table(self, serials):
        """Populate the table with serial numbers."""
        self.ui.serialTableWidget.setRowCount(len(serials))
        for row, serial in enumerate(serials):
            item = QtWidgets.QTableWidgetItem(serial)
            self.ui.serialTableWidget.setItem(row, 0, item)
        self.ui.serialTableWidget.resizeColumnsToContents()

    def add_serial(self):
        """Add a new serial number."""
        current_count = self.ui.serialTableWidget.rowCount()
        
        if current_count >= self.max_serials:
            QtWidgets.QMessageBox.warning(
                self, "Warning", 
                f"Maximum number of serial numbers ({self.max_serials}) reached."
            )
            return
            
        serial, ok = QtWidgets.QInputDialog.getText(
            self, "Add Serial Number", 
            "Enter new serial number:"
        )
        
        if ok and serial:
            # Check if serial already exists in the table
            for row in range(self.ui.serialTableWidget.rowCount()):
                if self.ui.serialTableWidget.item(row, 0).text() == serial:
                    QtWidgets.QMessageBox.warning(
                        self, "Duplicate", 
                        f"Serial number {serial} already exists in the list."
                    )
                    return
                    
            # Add the new serial
            self.ui.serialTableWidget.setRowCount(current_count + 1)
            item = QtWidgets.QTableWidgetItem(serial)
            self.ui.serialTableWidget.setItem(current_count, 0, item)
            logger.info(f"Added serial number: {serial}")

    def remove_serial(self):
        """Remove selected serial number(s)."""
        selected_rows = set()
        for item in self.ui.serialTableWidget.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            QtWidgets.QMessageBox.warning(
                self, "Selection Required", 
                "Please select one or more serial numbers to remove."
            )
            return
            
        # Confirm deletion
        confirm = QtWidgets.QMessageBox.question(
            self, "Confirm Removal", 
            f"Are you sure you want to remove {len(selected_rows)} serial numbers?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if confirm == QtWidgets.QMessageBox.Yes:
            # Remove rows in reverse order to avoid index shifting problems
            for row in sorted(selected_rows, reverse=True):
                serial = self.ui.serialTableWidget.item(row, 0).text()
                self.ui.serialTableWidget.removeRow(row)
                logger.info(f"Removed serial number: {serial}")

    def import_serials(self):
        """Import serial numbers from Excel or CSV file."""
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Serial Numbers", "", 
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_name:
            return
            
        try:
            # Determine file type and read
            if file_name.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_name, header=None)
            elif file_name.lower().endswith('.csv'):
                df = pd.read_csv(file_name, header=None)
            else:
                QtWidgets.QMessageBox.critical(
                    self, "Error", 
                    "Unsupported file format. Please use Excel or CSV."
                )
                return
                
            # Check if data exceeds maximum
            if len(df) > self.max_serials:
                QtWidgets.QMessageBox.warning(
                    self, "Warning", 
                    f"File contains {len(df)} serial numbers, but maximum allowed is {self.max_serials}. "
                    "Only the first {self.max_serials} will be imported."
                )
                df = df.iloc[:self.max_serials]
                
            # Extract serial numbers from first column
            imported_serials = [str(x).strip() for x in df.iloc[:, 0].tolist()]
            
            # Update table
            self.ui.serialTableWidget.setRowCount(0)
            self.populate_table(imported_serials)
            logger.info(f"Imported {len(imported_serials)} serial numbers from {file_name}")
            
        except Exception as e:
            logger.error(f"Error importing file: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Import Error", 
                f"Failed to import data: {str(e)}"
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