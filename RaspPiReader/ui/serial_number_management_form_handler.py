import logging
import os
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer
from RaspPiReader.ui.serial_number_management import Ui_SerialNumberManagementDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData
from RaspPiReader import pool

# Set up logger
logger = logging.getLogger(__name__)

class SerialNumberManagementFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SerialNumberManagementFormHandler, self).__init__(parent)
        self.ui = Ui_SerialNumberManagementDialog()
        self.ui.setupUi(self)
        self.db = Database("sqlite:///local_database.db")
        self.page_size = 50  # Number of records per page
        self.current_page = 0
        self.total_pages = 0
        self.all_serials = []
        self.filtered_serials = []
        
        # Set up the user interface
        self._setup_ui()
        
        # Load data immediately
        QTimer.singleShot(100, self.load_all_serials)

    def _setup_ui(self):
        """Set up the user interface components"""
        # Add search field at the top
        self.searchLayout = QtWidgets.QHBoxLayout()
        self.searchLineEdit = QtWidgets.QLineEdit()
        self.searchLineEdit.setPlaceholderText("Search serial numbers...")
        self.searchLineEdit.textChanged.connect(self.filter_serials)
        self.searchLayout.addWidget(self.searchLineEdit)
        self.searchButton = QtWidgets.QPushButton("Search")
        self.searchButton.clicked.connect(self.search_serial)
        self.searchLayout.addWidget(self.searchButton)
        self.ui.verticalLayout.insertLayout(0, self.searchLayout)
        
        # Set up pagination controls
        self.paginationLayout = QtWidgets.QHBoxLayout()
        
        self.prevButton = QtWidgets.QPushButton("← Previous")
        self.prevButton.clicked.connect(self.prev_page)
        
        self.pageLabel = QtWidgets.QLabel("Loading...")
        self.pageLabel.setAlignment(Qt.AlignCenter)
        
        self.nextButton = QtWidgets.QPushButton("Next →")
        self.nextButton.clicked.connect(self.next_page)
        
        self.paginationLayout.addWidget(self.prevButton)
        self.paginationLayout.addWidget(self.pageLabel)
        self.paginationLayout.addWidget(self.nextButton)
        
        # Add pagination layout to main layout
        self.ui.verticalLayout.addLayout(self.paginationLayout)
        
        # Hide the Add, Remove, and Import buttons
        if hasattr(self.ui, "addButton"):
            self.ui.addButton.setVisible(False)
        if hasattr(self.ui, "removeButton"):
            self.ui.removeButton.setVisible(False)
        if hasattr(self.ui, "importButton"):
            self.ui.importButton.setVisible(False)
        
        # Configure table for better display
        table = self.ui.serialTableWidget
        table.setColumnCount(2)  # Two columns: Serial Number and Added By
        table.setHorizontalHeaderLabels(["Serial Number", "Added By"])
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        
        # Show a "Loading..." message
        table.setRowCount(1)
        item = QtWidgets.QTableWidgetItem("Loading serial numbers...")
        table.setItem(0, 0, item)
    
    def showEvent(self, event):
        """Override the show event to ensure serial numbers are loaded"""
        super(SerialNumberManagementFormHandler, self).showEvent(event)
        # Ensure serial numbers are loaded when the form becomes visible
        self.load_all_serials()
    
    def load_all_serials(self):
        """Load all serial numbers from cycle data in the database"""
        try:
            logger.info("Loading serial numbers from database...")
            self.ui.serialTableWidget.setRowCount(1)
            self.ui.serialTableWidget.setItem(0, 0, QtWidgets.QTableWidgetItem("Loading..."))
            
            # Query all cycle data records that have serial numbers
            results = self.db.session.query(CycleData).filter(CycleData.serial_numbers != None).all()
            
            self.all_serials = []
            for cycle in results:
                if cycle.serial_numbers:
                    serials = cycle.serial_numbers.split(',')
                    # Use the proper field name that stores the user who added the serial
                    username = getattr(cycle, 'added_by', "").strip()
                    # Ensure the added_by field exists and matches an existing user in the database
                    if not username:
                        logger.warning(f"Cycle ID {cycle.id} is missing the added_by field. Skipping record.")
                        continue
                    user = self.db.session.query(User).filter(User.username == username).first()
                    if not user:
                        logger.warning(f"Cycle ID {cycle.id} has an invalid added_by value ('{username}'). Skipping record.")
                        continue
                    for serial in serials:
                        serial = serial.strip()
                        if serial:
                            # Store tuple of (serial_number, valid username)
                            self.all_serials.append((serial, user.username))
            
            # Sort serials alphanumerically and update the filtered_serials copy
            self.all_serials.sort(key=lambda x: x[0])
            self.filtered_serials = self.all_serials.copy()
            
            # Update pagination and display
            self.update_pagination()
            self.display_current_page()
            
            logger.info(f"Loaded {len(self.all_serials)} unique serial numbers")
            
            if not self.all_serials:
                self.ui.serialTableWidget.setRowCount(1)
                self.ui.serialTableWidget.setItem(0, 0, QtWidgets.QTableWidgetItem("No serial numbers found"))
                self.ui.serialTableWidget.setItem(0, 1, QtWidgets.QTableWidgetItem(""))
                        
        except Exception as e:
            logger.error(f"Error loading serial numbers: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                "Error Loading Serial Numbers",
                f"Failed to load serial numbers: {str(e)}"
            )
    
    def filter_serials(self):
        """Filter serial numbers based on search text"""
        search_text = self.searchLineEdit.text().strip().lower()
        
        if not search_text:
            self.filtered_serials = self.all_serials.copy()
        else:
            self.filtered_serials = [s for s in self.all_serials if search_text in s[0].lower()]
        
        # Reset to first page and update display
        self.current_page = 0
        self.update_pagination()
        self.display_current_page()
    
    def update_pagination(self):
        """Update pagination controls and state"""
        self.total_pages = max(1, (len(self.filtered_serials) + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, max(0, self.total_pages - 1))
        
        # Update page label
        self.pageLabel.setText(f"Page {self.current_page + 1} of {self.total_pages}")
        
        # Enable/disable navigation buttons
        self.prevButton.setEnabled(self.current_page > 0)
        self.nextButton.setEnabled(self.current_page < self.total_pages - 1)
    
    def display_current_page(self):
        """Display the current page of serial numbers in the table"""
        table = self.ui.serialTableWidget
        table.setRowCount(0)  # Clear table

        if not self.filtered_serials:
            table.setRowCount(1)
            table.setItem(0, 0, QtWidgets.QTableWidgetItem("No serial numbers found"))
            table.setItem(0, 1, QtWidgets.QTableWidgetItem(""))
            return

        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.filtered_serials))
        page_serials = self.filtered_serials[start_idx:end_idx]
        table.setRowCount(len(page_serials))
        
        for i, (serial, username) in enumerate(page_serials):
            # Add serial number item
            serial_item = QtWidgets.QTableWidgetItem(serial)
            table.setItem(i, 0, serial_item)
            
            # Add username item (always the stored username)
            username_item = QtWidgets.QTableWidgetItem(username)
            table.setItem(i, 1, username_item)

        # Resize columns to content
        table.resizeColumnsToContents()
    
    def next_page(self):
        """Go to the next page"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_current_page()
            self.update_pagination()
    
    def prev_page(self):
        """Go to the previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_current_page()
            self.update_pagination()
    
    def search_serial(self):
        """Focus on the search field and show search results"""
        self.searchLineEdit.setFocus()
        search_text = self.searchLineEdit.text().strip()
        
        # Filter the serials again (in case filter_serials wasn't called)
        self.filter_serials()
        
        # Show results message if there's search text
        if search_text:
            found_count = len(self.filtered_serials)
            QtWidgets.QMessageBox.information(
                self, 
                "Search Results", 
                f"Found {found_count} serial numbers matching '{search_text}'."
            )