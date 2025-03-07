import logging
import pandas as pd
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from RaspPiReader.ui.serial_number_entry_form import Ui_SerialNumberEntryForm
from RaspPiReader.ui.program_selection_form_handler import ProgramSelectionFormHandler
from RaspPiReader.ui.duplicate_password_dialog_handler import DuplicatePasswordDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData, User
from RaspPiReader import pool

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
        
        # Set button text if not already set in the UI
        self.ui.importExcelButton.setText("Import From Excel")
        self.ui.searchButton.setText("Search")
        self.ui.nextButton.setText("Next")
        self.ui.cancelButton.setText("Cancel")
        
        # Configure the table with placeholder cells
        for row in range(quantity):
            self.ui.serialTableWidget.setItem(row, 0, QtWidgets.QTableWidgetItem(""))
    
    def import_from_excel(self):
        """
        Import serial numbers from an Excel file.
        Excel file should have one column with serial numbers.
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
                f"Serial number '{search_text}' found in database from work order: {result.work_order}"
            )
        else:
            QtWidgets.QMessageBox.information(
                self, "Search Result", 
                f"Serial number '{search_text}' not found."
            )
    
    def next(self):
        """
        Process the entered serial numbers and proceed to the next step.
        Check for duplicates and handle them appropriately.
        """
        # Gather serial numbers from the serialTableWidget
        serials = []
        duplicate_serials = []
        
        for row in range(self.ui.serialTableWidget.rowCount()):
            item = self.ui.serialTableWidget.item(row, 0)
            if item:
                sn = item.text().strip()
                if sn:  # only process non-empty strings
                    serials.append(sn)
                    if self.db.check_duplicate_serial(sn):
                        duplicate_serials.append(sn)
        
        if not serials:
            QtWidgets.QMessageBox.warning(
                self, "Warning", 
                "Please enter at least one serial number."
            )
            return
        
        # If duplicates exist, require supervisor authorization
        if duplicate_serials:
            dialog = DuplicatePasswordDialog(duplicate_serials, self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                user_pwd, sup_pwd = dialog.get_passwords()
                if not self.authenticate_supervisor(user_pwd, sup_pwd):
                    QtWidgets.QMessageBox.critical(
                        self, "Error", 
                        "Invalid credentials for duplicate serial override."
                    )
                    return  # Stop without saving
                
                # Append 'R' to all duplicate serials before saving
                serials = [sn + "R" if sn in duplicate_serials else sn for sn in serials]
                logger.info(f"Serial numbers after overriding duplicates: {serials}")
            else:
                # User canceled duplicate override
                logger.info("User canceled duplicate serial override")
                return
        
        try:
            # Get the current user FIRST
            current_username = pool.get("current_user")
            if not current_username:
                # Try to get username from main_form as fallback
                main_form = pool.get('main_form')
                if main_form and hasattr(main_form, 'user'):
                    current_username = main_form.user.username
                else:
                    QtWidgets.QMessageBox.critical(
                        self, "Error", 
                        "No current user set in session. Please log in again."
                    )
                    return
                    
            # Get the User object from database
            user = self.db.get_user(current_username)
            if not user:
                QtWidgets.QMessageBox.critical(
                    self, "Database Error", 
                    f"User '{current_username}' not found in database."
                )
                return
                
            # Create the cycle data record with the work order and serial numbers
            cycle_data = CycleData(
                order_id=self.work_order,
                serial_numbers=",".join(serials)
            )
            
            # Set the user relationship - this maps to user_id
            cycle_data.user = user
            logger.info(f"Setting user_id to {user.id} for cycle data")
            
            # Now save to database
            success = self.db.add_cycle_data(cycle_data)
            if not success:
                QtWidgets.QMessageBox.critical(
                    self, "Database Error", 
                    "Failed to save cycle data to the database."
                )
                return
            
            # Log transition to program selection
            logger.info(f"Transitioning to program selection with work order {self.work_order} and {len(serials)} serial numbers")
            
            # Store reference to prevent garbage collection
            self.program_form = ProgramSelectionFormHandler(self.work_order, serials, parent=None)  # Change parent to None
            
            # Make sure the window is properly shown with correct size
            self.program_form.setMinimumSize(500, 300)
            self.program_form.show()
            self.program_form.raise_()  # Brings window to front
            self.program_form.activateWindow()  # Gives window focus
            self.hide()  # Hide instead of close to prevent immediate destruction
            
        except Exception as e:
            logger.error(f"Error transitioning to program selection: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Error", 
                f"Failed to proceed to program selection: {str(e)}"
            )

def authenticate_supervisor(self, user_password, supervisor_password):
    """
    Verify the user password and supervisor password for duplicate serial override.
    
    Args:
        user_password (str): The user's password
        supervisor_password (str): The supervisor's password
    
    Returns:
        bool: True if authentication is successful, False otherwise
    """
    try:
        # First verify the user's password
        current_user = pool.get('current_user')
        if not current_user:
            logger.error("No current user found in pool")
            return False
            
        user = self.db.get_user(current_user)
        if not user or user.password != user_password:
            logger.warning(f"Invalid user password for {current_user}")
            return False
        
        # Then verify the supervisor password
        # Look for a user with supervisor privileges (has user_mgmt_page access)
        supervisors = self.db.session.query(User).filter_by(user_mgmt_page=True).all()
        for supervisor in supervisors:
            if supervisor.password == supervisor_password:
                logger.info(f"Supervisor {supervisor.username} authorized duplicate override")
                return True
                
        logger.warning("No supervisor with matching password found")
        return False
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return False


class SerialNumberSearchFormHandler(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SerialNumberSearchFormHandler, self).__init__(parent)
        self.ui = Ui_SerialNumberEntryForm()
        self.ui.setupUi(self)
        
        # Hide the table and next button since we only need search functionality
        self.ui.serialTableWidget.hide()
        self.ui.nextButton.hide()
        self.ui.importExcelButton.hide()
        
        self.setWindowTitle("Search Serial Numbers")
        
        # Connect search and cancel buttons
        self.ui.searchButton.clicked.connect(self.search_serial)
        self.ui.cancelButton.clicked.connect(self.close)
        self.db = Database("sqlite:///local_database.db")
        
        # Set placeholder text for search line edit
        self.ui.searchLineEdit.setPlaceholderText("Enter serial number to search...")
        
        # Set button text
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
        
        # Search in the database
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