import logging
import pandas as pd
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from RaspPiReader.ui.serial_number_entry_form import Ui_SerialNumberEntryForm
from RaspPiReader.ui.program_selection_form_handler import ProgramSelectionFormHandler
from RaspPiReader.ui.duplicate_password_dialog_handler import DuplicatePasswordDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData, CycleSerialNumber, User
from RaspPiReader import pool
from RaspPiReader.utils.virtual_keyboard import setup_virtual_keyboard

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
        self.ui.cancelButton.clicked.connect(self.on_cancel)
        self.db = Database("sqlite:///local_database.db")
        
        # Set placeholder text for search line edit
        self.ui.searchLineEdit.setPlaceholderText("Enter serial number to search...")
        
        # Setup virtual keyboard for the search input
        setup_virtual_keyboard(self.ui.searchLineEdit)
        
        # Set button text if not already set in the UI
        self.ui.importExcelButton.setText("Import From Excel")
        self.ui.searchButton.setText("Search")
        self.ui.nextButton.setText("Next")
        self.ui.cancelButton.setText("Cancel")
        
        # Configure the table with placeholder cells and setup virtual keyboard for each cell
        for row in range(quantity):
            item = QtWidgets.QTableWidgetItem("")
            self.ui.serialTableWidget.setItem(row, 0, item)
            # Create a QLineEdit for each cell and setup virtual keyboard
            line_edit = QtWidgets.QLineEdit()
            setup_virtual_keyboard(line_edit)
            self.ui.serialTableWidget.setCellWidget(row, 0, line_edit)

    def import_from_excel(self):
        """
        Import serial numbers from an Excel or CSV file.
        The file should have serial numbers in the first column.
        """
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Serial Numbers", "", 
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_name:
            return
            
        try:
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
                
            # Check if data exceeds maximum quantity
            if len(df) > self.quantity:
                QtWidgets.QMessageBox.warning(
                    self, "Warning", 
                    f"File contains {len(df)} serial numbers, but maximum allowed is {self.quantity}. "
                    f"Only the first {self.quantity} will be imported."
                )
                df = df.iloc[:self.quantity]
                
            # Extract serial numbers from first column
            imported_serials = [str(x).strip() for x in df.iloc[:, 0].tolist()]
            
            # Update table with imported serial numbers
            for row, serial in enumerate(imported_serials):
                if row < self.quantity:
                    self.ui.serialTableWidget.setItem(row, 0, QtWidgets.QTableWidgetItem(serial))
            
            logger.info(f"Imported {len(imported_serials)} serial numbers from {file_name}")
            
        except Exception as e:
            logger.error(f"Error importing file: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Import Error", 
                f"Failed to import data: {str(e)}"
            )

    def search_serial(self):
        search_text = self.ui.searchLineEdit.text().strip()
        if not search_text:
            return
            
        # Search in the current table first
        found_in_table = False
        for row in range(self.ui.serialTableWidget.rowCount()):
            item = self.ui.serialTableWidget.item(row, 0)
            if item and item.text().strip() == search_text:
                # Highlight the found item
                self.ui.serialTableWidget.setCurrentItem(item)
                self.ui.serialTableWidget.scrollToItem(item)
                found_in_table = True
                break
        
        if found_in_table:
            QtWidgets.QMessageBox.information(
                self, "Search Result", 
                f"Serial number '{search_text}' found in current entries."
            )
            return
        
        # If not found in the table, search in the database
        result = self.db.search_serial_number(search_text)
        if result:
            QtWidgets.QMessageBox.information(
                self, "Search Result", 
                f"Serial number '{search_text}' found in database from work order: {result.order_id}"
            )
        else:
            QtWidgets.QMessageBox.information(
                self, "Search Result", 
                f"Serial number '{search_text}' not found."
            )
    
   
    def next(self):
        # Gather serial numbers from the table
        entered_serials = []
        for row in range(self.ui.serialTableWidget.rowCount()):
            item = self.ui.serialTableWidget.item(row, 0)
            if item:
                sn = item.text().strip()
                if sn:  # Only process non-empty strings
                    entered_serials.append(sn)

        if not entered_serials:
            QtWidgets.QMessageBox.warning(
                self, "Warning", "Please enter at least one serial number."
            )
            return

        # Determine which unique serials already exist in the database (duplicates)
        unique_serials = set(entered_serials)
        duplicate_set = set(sn for sn in unique_serials if self.db.check_duplicate_serial(sn))

        # If duplicates exist, require supervisor authorization
        if duplicate_set:
            dialog = DuplicatePasswordDialog(sorted(list(duplicate_set)), self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                sup_username, sup_password = dialog.get_credentials()
                if not self.authenticate_supervisor(sup_username, sup_password):
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Error",
                        "Invalid supervisor credentials for duplicate serial override."
                    )
                    return  # Abort without saving
            else:
                return

        # Finalize the list of serials to be saved:
        # For duplicate serials, we want one original and one override (only if not already in the DB)
        final_serials = []
        for sn in unique_serials:
            if sn in duplicate_set:
                final_serials.append(sn)         # original
                final_serials.append(sn + "R")     # override
            else:
                final_serials.append(sn)  # non-duplicate serial added as-is

        logger.info(f"Final serial numbers to be saved: {final_serials}")

        try:
            # Get current user from pool
            current_username = pool.get("current_user")
            if not current_username:
                main_form = pool.get('main_form')
                if main_form and hasattr(main_form, "user"):
                    current_username = main_form.user.username
                else:
                    QtWidgets.QMessageBox.critical(
                        self, "Error", "No current user set in session. Please log in again."
                    )
                    return

            user = self.db.get_user(current_username)
            if not user:
                QtWidgets.QMessageBox.critical(
                    self, "Database Error", f"User '{current_username}' not found in database."
                )
                return

            # Create a new cycle data record
            cycle_data = CycleData(
                order_id=self.work_order,
                quantity=len(final_serials)
            )
            cycle_data.user = user
            logger.info(f"Setting user_id to {user.id} for cycle data")

            success = self.db.add_cycle_data(cycle_data)
            if not success:
                QtWidgets.QMessageBox.critical(
                    self, "Database Error", "Failed to save cycle data to the database."
                )
                return

            # Save each serial number while enforcing uniqueness
            for sn in final_serials:
                # Check if this serial already exists in the system:
                existing = self.db.session.query(CycleSerialNumber).filter_by(serial_number=sn).first()
                if not existing:
                    record = CycleSerialNumber(cycle_id=cycle_data.id, serial_number=sn)
                    self.db.session.add(record)
            self.db.session.commit()
            logger.info("Cycle serial numbers stored successfully.")

            # Reload the cycle with its joined report so that subsequent queries/template rendering can access cycle.report
            from RaspPiReader.libs.models import CycleReport
            updated_cycle = self.db.session.query(CycleData)\
                .outerjoin(CycleReport, CycleData.id == CycleReport.cycle_id)\
                .filter(CycleData.id == cycle_data.id)\
                .one_or_none()
            if updated_cycle:
                self.current_cycle = updated_cycle

            # Transition to Program Selection
            logger.info(f"Transitioning to program selection with work order {self.work_order} and {len(final_serials)} serial numbers")
            self.program_form = ProgramSelectionFormHandler(self.work_order, final_serials, self.quantity, parent=None)
            self.program_form.setMinimumSize(500, 300)
            self.program_form.show()
            self.program_form.raise_()
            self.program_form.activateWindow()
            self.hide()

        except Exception as e:
            logger.error(f"Error transitioning to program selection: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Failed to proceed to program selection: {str(e)}"
            )

    def authenticate_supervisor(self, supervisor_username, supervisor_password):
        """
        Verify the supervisor credentials. Returns True if a user with the given username exists,
        has a role of 'Supervisor' (case-insensitive) and the password matches.
        """
        try:
            sup = self.db.get_user(supervisor_username)
            if sup and sup.role.lower() == "supervisor" and sup.password == supervisor_password:
                logger.info(f"Supervisor {sup.username} authorized duplicate override")
                return True
            logger.warning("Supervisor authentication failed")
            return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def on_cancel(self):
        """Handle form cancellation"""
        logger.info("Serial number entry form cancelled")
        
        # Reset menu items in main form
        main_form = pool.get('main_form')
        if main_form:
            main_form.actionStart.setEnabled(True)
            main_form.actionStop.setEnabled(False)
        
        # Clear any cycle data that might have been set
        pool.set("current_cycle", None)
        
        # Close the form
        self.close()

class SerialNumberSearchFormHandler(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SerialNumberSearchFormHandler, self).__init__(parent)
        self.ui = Ui_SerialNumberEntryForm()
        self.ui.setupUi(self)
        
        # Hide the table and next button for search functionality only
        self.ui.serialTableWidget.hide()
        self.ui.nextButton.hide()
        self.ui.importExcelButton.hide()
        
        self.setWindowTitle("Search Serial Numbers")
        
        # Connect search and cancel buttons
        self.ui.searchButton.clicked.connect(self.search_serial)
        self.ui.cancelButton.clicked.connect(self.close)
        self.db = Database("sqlite:///local_database.db")
        
        # Set placeholder text and button text
        self.ui.searchLineEdit.setPlaceholderText("Enter serial number to search...")
        self.ui.searchButton.setText("Search")
        self.ui.cancelButton.setText("Close")
    
    def search_serial(self):
        """
        Search for a serial number in the database.
        """
        search_text = self.ui.searchLineEdit.text().strip()
        if not search_text:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter a serial number to search.")
            return
        
        result = self.db.search_serial_number(search_text)
        if result:
            QtWidgets.QMessageBox.information(
                self, "Serial Found", 
                f"Serial number {search_text} found in order {result.order_id} started on {result.cycle_start}."
            )
        else:
            QtWidgets.QMessageBox.information(
                self, "Serial Not Found", 
                f"Serial number {search_text} not found in the database."
            )
