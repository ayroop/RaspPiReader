import logging
import os
import glob
import re
import csv
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QCursor  # Fixed: Import QCursor from QtGui, not QtWidgets
from PyQt5.QtGui import QDesktopServices
from RaspPiReader.ui.serial_number_management import Ui_SerialNumberManagementDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleSerialNumber, User, CycleData, CycleReport
from RaspPiReader import pool
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, desc, func, distinct
from sqlalchemy.sql import text

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
        # List of dictionaries for serial information
        self.all_serials = []
        self.filtered_serials = []
        
        # Track manually assigned report paths
        self.manual_report_assignments = {}
        
        self._setup_ui()
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
        self.ui.verticalLayout.addLayout(self.paginationLayout)
        
        # Configure the table for display
        table = self.ui.serialTableWidget
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "Serial Number", "Added By", "Work Order", "Cycle ID", "Reports"
        ])
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        # Connect cellClicked signal so that clicking on report cells opens the file
        table.cellClicked.connect(self.cell_clicked)
        
        # Set an initial placeholder row
        table.setRowCount(1)
        item = QtWidgets.QTableWidgetItem("Loading serial numbers...")
        table.setItem(0, 0, item)

    def showEvent(self, event):
        """Override show event to ensure serial numbers are loaded."""
        super(SerialNumberManagementFormHandler, self).showEvent(event)
        self.load_all_serials()
    
    def load_all_serials(self):
        """
        Load all serial numbers from the database and group them by serial number.
        Each serial number will appear only once in the list.
        """
        try:
            self.all_serials = []
            
            # First, get all unique serial numbers
            unique_serials_query = self.db.session.query(
                CycleSerialNumber.serial_number
            ).distinct().filter(
                ~CycleSerialNumber.serial_number.like("PLACEHOLDER_%")
            ).order_by(
                CycleSerialNumber.serial_number
            )
            
            unique_serials = [row[0] for row in unique_serials_query.all()]
            
            # Now process each unique serial number
            for serial_number in unique_serials:
                # Get all related cycle records for this serial - we only display the first one
                # to avoid showing duplicate serial numbers
                cycle_record = self.db.session.query(
                    CycleSerialNumber.cycle_id,
                    CycleData.order_id,
                    User.username
                ).join(
                    CycleData, CycleSerialNumber.cycle_id == CycleData.id
                ).outerjoin(
                    User, CycleData.user_id == User.id
                ).filter(
                    CycleSerialNumber.serial_number == serial_number
                ).order_by(
                    CycleSerialNumber.id
                ).first()
                
                # Skip if no records found
                if not cycle_record:
                    continue
                
                # Extract data from the first cycle record
                cycle_id, order_id, username = cycle_record
                
                # Get the report links for this cycle
                reports = []
                
                # Find report HTML path
                html_path = self.find_specific_report_for_cycle(cycle_id, "html")
                if html_path:
                    reports.append({"type": "html", "path": html_path})
                
                # Find report PDF path
                pdf_path = self.find_specific_report_for_cycle(cycle_id, "pdf")
                if pdf_path:
                    reports.append({"type": "pdf", "path": pdf_path})
                
                # Create a record for this serial number
                self.all_serials.append({
                    'serial_number': serial_number,
                    'added_by': username if username else "Unknown",
                    'work_order': order_id if order_id else "Not specified",
                    'cycle_id': str(cycle_id) if cycle_id else "Not assigned",
                    'reports': reports
                })
            
            # Update the filtered serials (initially all serials)
            self.filtered_serials = self.all_serials.copy()
            
            # Update the page count and display
            self.update_page_count()
            self.display_current_page()
            
        except Exception as e:
            logger.error(f"Error loading serial numbers: {e}")
            import traceback
            logger.error(traceback.format_exc())
            table = self.ui.serialTableWidget
            table.setRowCount(1)
            table.setItem(0, 0, QtWidgets.QTableWidgetItem(f"Error: {str(e)}"))
            
    def update_page_count(self):
        """Update the total page count based on the filtered serials list."""
        if self.filtered_serials:
            self.total_pages = (len(self.filtered_serials) + self.page_size - 1) // self.page_size
        else:
            self.total_pages = 1
        self.current_page = min(self.current_page, max(0, self.total_pages - 1))
        self.pageLabel.setText(f"Page {self.current_page + 1} of {self.total_pages}")
        
    def display_current_page(self):
        """Display the current page of serial numbers."""
        table = self.ui.serialTableWidget
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.filtered_serials))
        
        if not self.filtered_serials or start_idx >= len(self.filtered_serials):
            table.setRowCount(1)
            table.setItem(0, 0, QtWidgets.QTableWidgetItem("No serial numbers found"))
            for col in range(1, table.columnCount()):
                table.setItem(0, col, QtWidgets.QTableWidgetItem(""))
            return
        
        page_serials = self.filtered_serials[start_idx:end_idx]
        table.setRowCount(len(page_serials))
        
        for row, serial_info in enumerate(page_serials):
            # Serial number
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(serial_info['serial_number']))
            
            # Added by
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(serial_info['added_by']))
            
            # Work order
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(serial_info['work_order']))
            
            # Cycle ID
            table.setItem(row, 3, QtWidgets.QTableWidgetItem(serial_info['cycle_id']))
            
            # Report links - add links to PDF/HTML reports if available
            if serial_info['reports']:
                report_text = []
                for report in serial_info['reports']:
                    report_type = report['type'].upper()
                    report_text.append(f"{report_type}")
                
                report_cell = QtWidgets.QTableWidgetItem(" / ".join(report_text))
                report_cell.setData(Qt.UserRole, serial_info['reports'])
                report_cell.setForeground(Qt.blue)
                report_cell.setFlags(report_cell.flags() | Qt.ItemIsUserCheckable)
                table.setItem(row, 4, report_cell)
            else:
                table.setItem(row, 4, QtWidgets.QTableWidgetItem("No reports"))
                
        # Resize columns to content
        table.resizeColumnsToContents()
        # But set a minimum width for the serial number column
        if table.columnWidth(0) < 150:
            table.setColumnWidth(0, 150)
            
    def prev_page(self):
        """Go to the previous page of results."""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_current_page()
            self.pageLabel.setText(f"Page {self.current_page + 1} of {self.total_pages}")
            
    def next_page(self):
        """Go to the next page of results."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_current_page()
            self.pageLabel.setText(f"Page {self.current_page + 1} of {self.total_pages}")
            
    def filter_serials(self):
        """Filter the serial numbers list based on the search text."""
        search_text = self.searchLineEdit.text().strip().lower()
        
        if not search_text:
            self.filtered_serials = self.all_serials.copy()
        else:
            self.filtered_serials = [
                serial for serial in self.all_serials
                if (search_text in serial['serial_number'].lower() or
                    search_text in serial['added_by'].lower() or
                    search_text in serial['work_order'].lower() or
                    search_text in serial['cycle_id'].lower())
            ]
            
        self.current_page = 0
        self.update_page_count()
        self.display_current_page()
        
    def search_serial(self):
        """Perform search when the search button is clicked."""
        self.filter_serials()
        
    def cell_clicked(self, row, column):
        """Handle cell clicks, particularly for report links."""
        table = self.ui.serialTableWidget
        item = table.item(row, column)
        
        # Check if this is a report link cell
        if column == 4 and item and item.data(Qt.UserRole):
            reports = item.data(Qt.UserRole)
            
            if len(reports) == 1:
                # Single report, open it directly
                self.open_report(reports[0])
            else:
                # Multiple reports, show selection menu
                menu = QtWidgets.QMenu(self)
                for report in reports:
                    report_type = report['type'].upper()
                    action = menu.addAction(f"View {report_type} Report")
                    action.setData(report)
                
                # Show the menu at the table cell position
                # Fixed: Use the correct way to get menu position
                pos = table.viewport().mapToGlobal(table.visualRect(table.model().index(row, column)).center())
                selected_action = menu.exec_(pos)
                if selected_action:
                    self.open_report(selected_action.data())
    
    def open_report(self, report_data):
        """Open a report file."""
        try:
            if not report_data or 'path' not in report_data:
                QtWidgets.QMessageBox.warning(
                    self, "Missing Report", "Report file path is missing."
                )
                return
                
            report_path = report_data['path']
            
            # Check if the file exists
            if not os.path.exists(report_path):
                QtWidgets.QMessageBox.warning(
                    self, "File Not Found", f"Report file not found at: {report_path}"
                )
                return
                
            # Log before opening
            logger.info(f"Opening report file: {report_path}")
                
            # Open the file with the default application - using direct method for compatibility
            url = QUrl.fromLocalFile(report_path)
            logger.info(f"Opening URL: {url.toString()}")
            
            # Explicitly try both methods for compatibility
            success = QDesktopServices.openUrl(url)
            
            if not success:
                # Try alternative approach if opening failed
                logger.warning(f"First method failed to open {report_path}, trying alternative...")
                import subprocess
                import platform
                
                system = platform.system()
                if system == 'Windows':
                    os.startfile(report_path)
                elif system == 'Darwin':  # macOS
                    subprocess.call(('open', report_path))
                else:  # Linux and others
                    subprocess.call(('xdg-open', report_path))
                
                logger.info(f"Attempted to open file using {system} native method")
            else:
                logger.info(f"Successfully opened the file using QDesktopServices")
            
        except Exception as e:
            logger.error(f"Error opening report: {e}")
            import traceback
            logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Failed to open report: {e}"
            )

    def find_specific_report_for_cycle(self, cycle_id, report_type):
        """
        Find a specific type of report file (PDF/HTML) for a cycle.
        
        Args:
            cycle_id: The cycle ID to find the report for
            report_type: Either 'pdf' or 'html'
            
        Returns:
            Full path to the report file if found, None otherwise
        """
        try:
            # Check for the report in the database
            cycle_report = self.db.session.query(CycleReport).filter_by(cycle_id=cycle_id).first()
            reports_dir = os.path.join(os.getcwd(), "reports")
            
            if cycle_report:
                # Log the cycle report details to debug
                logger.info(f"Found CycleReport for cycle {cycle_id}: {cycle_report.__dict__}")
                
                # Handle both old and new schema
                if report_type.lower() == 'pdf':
                    # Try new schema first
                    if hasattr(cycle_report, 'pdf_report_path') and cycle_report.pdf_report_path:
                        pdf_path = os.path.join(reports_dir, cycle_report.pdf_report_path)
                        if os.path.exists(pdf_path):
                            logger.info(f"Found PDF report via database path: {pdf_path}")
                            return pdf_path
                    
                    # Try old schema
                    if hasattr(cycle_report, 'report_file_path') and cycle_report.report_file_path:
                        if cycle_report.report_file_path.lower().endswith('.pdf'):
                            pdf_path = os.path.join(reports_dir, cycle_report.report_file_path)
                            if os.path.exists(pdf_path):
                                logger.info(f"Found PDF report via legacy path: {pdf_path}")
                                return pdf_path
                
                elif report_type.lower() == 'html':
                    # Try new schema first
                    if hasattr(cycle_report, 'html_report_path') and cycle_report.html_report_path:
                        html_path = os.path.join(reports_dir, cycle_report.html_report_path)
                        if os.path.exists(html_path):
                            logger.info(f"Found HTML report via database path: {html_path}")
                            return html_path
            
            # If not found in database, search for files with cycle ID in the name
            cycle_id_str = str(cycle_id)
            
            # Log directory info
            logger.info(f"Searching for {report_type} files in directory: {reports_dir}")
            if not os.path.exists(reports_dir):
                logger.warning(f"Reports directory doesn't exist: {reports_dir}")
                os.makedirs(reports_dir, exist_ok=True)
            
            # Search for files with this pattern: *_cycle_id_* or cycle_id_* with correct extension
            pattern = f"*{cycle_id_str}*.{report_type.lower()}"
            matching_files = glob.glob(os.path.join(reports_dir, pattern))
            
            # Log what we found
            logger.info(f"Found {len(matching_files)} {report_type} files matching pattern '{pattern}'")
            for f in matching_files:
                logger.info(f"  - {f}")
            
            if matching_files:
                # Sort by modification time to get the newest first
                matching_files.sort(key=os.path.getmtime, reverse=True)
                logger.info(f"Using newest matching {report_type} file: {matching_files[0]}")
                return matching_files[0]
                
            # Last resort: search in all files for any with the cycle ID in the name
            all_files = glob.glob(os.path.join(reports_dir, f"*.{report_type.lower()}"))
            for file_path in all_files:
                file_name = os.path.basename(file_path)
                if cycle_id_str in file_name:
                    logger.info(f"Found {report_type} file containing cycle ID in name: {file_path}")
                    return file_path
                    
            logger.warning(f"No {report_type} report found for cycle {cycle_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding {report_type} report for cycle {cycle_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
