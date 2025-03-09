import logging
import os
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer
from RaspPiReader.ui.serial_number_management import Ui_SerialNumberManagementDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleSerialNumber, User  
from RaspPiReader import pool

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
        self.all_serials = []       # List of tuples: (serial_number, added_by)
        self.filtered_serials = []
        
        # Set up the user interface components
        self._setup_ui()
        
        # Load data immediately (small delay to allow UI initialization)
        QTimer.singleShot(100, self.load_all_serials)

    def _setup_ui(self):
        """Set up the user interface components."""
        # Add search field at the top of the vertical layout
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
        
        # Add the pagination layout to the main vertical layout
        self.ui.verticalLayout.addLayout(self.paginationLayout)
        
        # Hide the Add, Remove, and Import buttons if available
        if hasattr(self.ui, "addButton"):
            self.ui.addButton.setVisible(False)
        if hasattr(self.ui, "removeButton"):
            self.ui.removeButton.setVisible(False)
        if hasattr(self.ui, "importButton"):
            self.ui.importButton.setVisible(False)
        
        # Configure the table for better display – two columns: Serial Number and Added By
        table = self.ui.serialTableWidget
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Serial Number", "Added By"])
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        
        # Show a "Loading..." message in the table initially
        table.setRowCount(1)
        item = QtWidgets.QTableWidgetItem("Loading serial numbers...")
        table.setItem(0, 0, item)

    def showEvent(self, event):
        """Override the show event to ensure serial numbers are loaded."""
        super(SerialNumberManagementFormHandler, self).showEvent(event)
        self.load_all_serials()
    
    def load_all_serials(self):
        try:
            table = self.ui.serialTableWidget
            # Ensure the table has 2 columns
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Serial Number", "Added By"])
            
            records = self.db.session.query(CycleSerialNumber).all()
            self.all_serials = []
            for record in records:
                if record.serial_number and record.serial_number.strip() != "":
                    # Retrieve added_by username if available (modify according to your model)
                    added_by = "Unknown"
                    if hasattr(record, "cycle") and record.cycle and hasattr(record.cycle, "user") and record.cycle.user:
                        added_by = record.cycle.user.username
                    self.all_serials.append((record.serial_number.strip(), added_by))
            table.setRowCount(len(self.all_serials))
            for idx, (sn, user) in enumerate(self.all_serials):
                table.setItem(idx, 0, QtWidgets.QTableWidgetItem(sn))
                table.setItem(idx, 1, QtWidgets.QTableWidgetItem(user))
            table.resizeColumnsToContents()
            logger.info(f"Loaded {len(self.all_serials)} serial numbers")
        except Exception as e:
            logger.error(f"Failed to load serial numbers: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load serial numbers: {e}")
    
    def filter_serials(self):
        """Filter serial numbers based on the search text."""
        search_text = self.searchLineEdit.text().strip().lower()
        if not search_text:
            self.filtered_serials = self.all_serials.copy()
        else:
            self.filtered_serials = [s for s in self.all_serials if search_text in s[0].lower()]
        # Reset to the first page and update display
        self.current_page = 0
        self.update_pagination()
        self.display_current_page()
    
    def update_pagination(self):
        """Update pagination controls based on the filtered serial numbers."""
        self.total_pages = max(1, (len(self.filtered_serials) + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, max(0, self.total_pages - 1))
        
        # Update the page label
        self.pageLabel.setText(f"Page {self.current_page + 1} of {self.total_pages}")
        
        # Enable or disable the navigation buttons based on current page
        self.prevButton.setEnabled(self.current_page > 0)
        self.nextButton.setEnabled(self.current_page < self.total_pages - 1)
    
    def display_current_page(self):
        """Display the current page of serial numbers in the table widget."""
        table = self.ui.serialTableWidget
        table.setRowCount(0)  # Clear previous rows

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
            # Add the serial number cell
            serial_item = QtWidgets.QTableWidgetItem(serial)
            table.setItem(i, 0, serial_item)
            # Add the "Added By" cell
            username_item = QtWidgets.QTableWidgetItem(username)
            table.setItem(i, 1, username_item)
        table.resizeColumnsToContents()
    
    def next_page(self):
        """Advance to the next page if available."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_current_page()
            self.update_pagination()
    
    def prev_page(self):
        """Return to the previous page if available."""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_current_page()
            self.update_pagination()
    
    def search_serial(self):
        """Set focus on the search field and show a message with results."""
        self.searchLineEdit.setFocus()
        search_text = self.searchLineEdit.text().strip()
        self.filter_serials()
        if search_text:
            found_count = len(self.filtered_serials)
            QtWidgets.QMessageBox.information(
                self, 
                "Search Results", 
                f"Found {found_count} serial numbers matching '{search_text}'."
            )