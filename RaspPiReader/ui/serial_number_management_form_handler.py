
import logging
import os
import glob
import re
import csv
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices
from RaspPiReader.ui.serial_number_management import Ui_SerialNumberManagementDialog
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleSerialNumber, User, CycleData, CycleReport
from RaspPiReader import pool
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, desc

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
        # List of tuples:
        # (serial_number, added_by, work_order_number, cycle_id, report_link)
        self.all_serials = []
        self.filtered_serials = []
        
        # Track manually assigned report paths
        self.manual_report_assignments = {}
        
        self._setup_ui()
        QTimer.singleShot(100, self.load_all_serials)

    def fix_serial_cycle_consistency(self):
        """
        Ensures that serial numbers sharing the same report file have a consistent
        work order and cycle ID. Optionally can create new report copies to ensure
        each cycle has its own distinct report.
        """
        try:
            records = self.db.session.query(CycleSerialNumber).all()
            groups = {}
            # Build groups keyed by report file path (if available)
            for rec in records:
                if rec.cycle:
                    # Use the helper to get this cycle's report file
                    report = self.find_report_for_cycle(rec.cycle.id)
                    if report:
                        if report not in groups:
                            groups[report] = []
                        groups[report].append(rec)
            
            # Store conflicts for user decision
            conflicts = []
            for report, rec_list in groups.items():
                # Get unique cycles using this report
                cycles = set(rec.cycle.id for rec in rec_list)
                if len(cycles) > 1:
                    conflicts.append((report, cycles))
            
            # If conflicts exist, ask user how to handle them
            if conflicts:
                # Format a descriptive message about the conflicts
                conflict_msg = "The following report files are shared between multiple cycles:\n\n"
                for report, cycles in conflicts:
                    report_name = os.path.basename(report) if isinstance(report, str) else "Embedded HTML"
                    cycle_ids = ", ".join(str(c) for c in sorted(cycles))
                    conflict_msg += f"• {report_name} - Used by cycles: {cycle_ids}\n"
                
                conflict_msg += "\nHow would you like to resolve these conflicts?"
                
                # Setup options
                unified_btn = QtWidgets.QPushButton("Unify Cycles")
                unified_btn.setToolTip("Make all serials with the same report use the same cycle ID")
                
                separate_btn = QtWidgets.QPushButton("Separate Reports")
                separate_btn.setToolTip("Create copies of reports so each cycle has its own unique report file")
                
                cancel_btn = QtWidgets.QPushButton("Cancel")
                
                # Create custom message box
                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setWindowTitle("Report Conflicts")
                msg_box.setText(conflict_msg)
                msg_box.addButton(unified_btn, QtWidgets.QMessageBox.ActionRole)
                msg_box.addButton(separate_btn, QtWidgets.QMessageBox.ActionRole)
                msg_box.addButton(cancel_btn, QtWidgets.QMessageBox.RejectRole)
                
                # Show dialog and get response
                msg_box.exec_()
                clicked_button = msg_box.clickedButton()
                
                fixed = 0
                
                if clicked_button == unified_btn:
                    # Unify approach: Make all serials with the same report use the same cycle
                    for report, rec_list in groups.items():
                        if len(set(rec.cycle.id for rec in rec_list)) <= 1:
                            continue  # Skip if already unified
                            
                        # Choose the first record's cycle data as the baseline
                        baseline_cycle = rec_list[0].cycle
                        for rec in rec_list:
                            # If the cycle data (work order or cycle id) differ, update to baseline
                            if rec.cycle.id != baseline_cycle.id:
                                rec.cycle = baseline_cycle
                                fixed += 1
                    
                    if fixed:
                        self.db.session.commit()
                        QtWidgets.QMessageBox.information(
                            self,
                            "Fix Complete",
                            f"Unified {fixed} serial number relationships."
                        )
                        
                elif clicked_button == separate_btn:
                    # Separate approach: Create copies of reports, one for each cycle
                    reports_dir = os.path.join(os.getcwd(), "reports")
                    
                    for report, cycles in conflicts:
                        # Skip if not a file path
                        if not isinstance(report, str) or not os.path.exists(report):
                            continue
                            
                        # Get all cycles using this report
                        report_cycles = list(cycles)
                        
                        # Keep original file for first cycle
                        first_cycle = report_cycles[0]
                        
                        # For other cycles, create copies of the report
                        for cycle_id in report_cycles[1:]:
                            # Create a new filename for this cycle
                            original_name = os.path.basename(report)
                            file_ext = os.path.splitext(original_name)[1]
                            new_filename = f"cycle_{cycle_id}_{original_name}"
                            new_path = os.path.join(reports_dir, new_filename)
                            
                            # Copy the file
                            import shutil
                            shutil.copy2(report, new_path)
                            
                            # Update database to link the new file to this cycle
                            cycle_report = self.db.session.query(CycleReport).filter_by(cycle_id=cycle_id).first()
                            rel_path = os.path.relpath(new_path, reports_dir)
                            
                            if cycle_report:
                                # Update existing record
                                if file_ext.lower() == '.pdf':
                                    cycle_report.pdf_report_path = rel_path
                                else:
                                    cycle_report.html_report_path = rel_path
                            else:
                                # Create new record
                                new_report = CycleReport(
                                    cycle_id=cycle_id,
                                    pdf_report_path=rel_path if file_ext.lower() == '.pdf' else None,
                                    html_report_path=rel_path if file_ext.lower() != '.pdf' else None
                                )
                                self.db.session.add(new_report)
                            
                            fixed += 1
                    
                    if fixed:
                        self.db.session.commit()
                        QtWidgets.QMessageBox.information(
                            self,
                            "Fix Complete",
                            f"Created {fixed} separate report files for cycles that were previously sharing the same report."
                        )
                
                # Reload display to show changes
                self.load_all_serials()
                    
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Conflicts Found",
                    "No report conflicts were detected."
                )
                
        except Exception as e:
            logger.error(f"Error fixing serial number relationships: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to fix relationships: {e}"
            )
            
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
        
        # Hide the Add, Remove, and Import buttons if available
        if hasattr(self.ui, "addButton"):
            self.ui.addButton.setVisible(False)
        if hasattr(self.ui, "removeButton"):
            self.ui.removeButton.setVisible(False)
        if hasattr(self.ui, "importButton"):
            self.ui.importButton.setVisible(False)
        
        # Add refresh button
        self.refreshButton = QtWidgets.QPushButton("Refresh List")
        self.refreshButton.clicked.connect(self.refresh_serials)
        self.ui.verticalLayout.insertWidget(1, self.refreshButton)
        
        # Add fix relationships buttons
        self.fixRelationshipsButton = QtWidgets.QPushButton("Fix Serial-Cycle Relationships")
        self.fixRelationshipsButton.clicked.connect(self.fix_serial_cycle_relationships)
        self.ui.verticalLayout.insertWidget(2, self.fixRelationshipsButton)
        
        # Add repair report relationships button
        self.repairReportsButton = QtWidgets.QPushButton("Repair All Report Relationships")
        self.repairReportsButton.clicked.connect(self.repair_all_report_relationships)
        self.repairReportsButton.setToolTip("Scan all reports and fix database links to ensure all cycles have correct reports")
        self.ui.verticalLayout.insertWidget(3, self.repairReportsButton)
        
        # Add fix report consistency button
        self.fixConsistencyButton = QtWidgets.QPushButton("Fix Report Consistency")
        self.fixConsistencyButton.clicked.connect(self.fix_serial_cycle_consistency)
        self.fixConsistencyButton.setToolTip("Fix issues where multiple cycles share the same report file")
        self.ui.verticalLayout.insertWidget(4, self.fixConsistencyButton)
        
        # Configure the table for display
        table = self.ui.serialTableWidget
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Serial Number", "Added By", "Work Order", "Cycle ID", "Report Link", "Actions"
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

    def refresh_serials(self):
        """Manually refresh the serial numbers list, clearing all caches."""
        self.load_all_serials()
        QtWidgets.QMessageBox.information(
            self, "Refresh Complete", "Serial number list has been refreshed."
        )
    
    def fix_serial_cycle_relationships(self):
        """Fix serial number to cycle relationships in the database."""
        try:
            # First get all serial numbers
            serial_numbers = self.db.session.query(CycleSerialNumber).all()
            total_serials = len(serial_numbers)
            fixed_count = 0
            
            # Identify and fix issues
            for serial in serial_numbers:
                # Skip placeholder serial numbers
                if serial.serial_number.startswith("PLACEHOLDER_"):
                    continue
                
                # Check if this serial is associated with a cycle
                if not serial.cycle_id:
                    # Try to find a cycle for this serial
                    cycles = self.db.session.query(CycleData).order_by(desc(CycleData.id)).all()
                    for cycle in cycles:
                        # Check if this serial number appears in the CSV report for this cycle
                        cycle_report = self.db.session.query(CycleReport).filter_by(cycle_id=cycle.id).first()
                        if cycle_report:
                            reports_dir = os.path.join(os.getcwd(), "reports")
                            csv_path = None
                            
                            # Try to find the CSV file
                            if cycle_report.pdf_report_path:
                                potential_csv = os.path.join(reports_dir, cycle_report.pdf_report_path.replace('.pdf', '.csv'))
                                if os.path.exists(potential_csv):
                                    csv_path = potential_csv
                            
                            if not csv_path and cycle_report.html_report_path:
                                potential_csv = os.path.join(reports_dir, cycle_report.html_report_path.replace('.html', '.csv'))
                                if os.path.exists(potential_csv):
                                    csv_path = potential_csv
                            
                            # If we found a CSV file, check if the serial number is in it
                            if csv_path and os.path.exists(csv_path):
                                if self.is_serial_in_csv(serial.serial_number, csv_path):
                                    # Associate this serial with this cycle
                                    serial.cycle_id = cycle.id
                                    fixed_count += 1
                                    break
            
            # For serial numbers with 'R' suffix, ensure they have the same cycle as their base serial
            r_serials = [s for s in serial_numbers if s.serial_number.endswith('R')]
            for r_serial in r_serials:
                # Find the base serial (without the R)
                base_serial_num = r_serial.serial_number[:-1]
                base_serial = self.db.session.query(CycleSerialNumber).filter_by(serial_number=base_serial_num).first()
                
                if base_serial and base_serial.cycle_id != r_serial.cycle_id:
                    # Both serials should be part of the same cycle
                    r_serial.cycle_id = base_serial.cycle_id
                    fixed_count += 1
            
            # Save changes
            if fixed_count > 0:
                self.db.session.commit()
                
            # Now reload the view
            self.load_all_serials()
            
            # Show results
            QtWidgets.QMessageBox.information(
                self, 
                "Fix Complete", 
                f"Fixed {fixed_count} serial number relationships out of {total_serials} total serial numbers."
            )
            
        except Exception as e:
            logger.error(f"Error fixing serial number relationships: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to fix relationships: {e}")
    
    def repair_all_report_relationships(self):
        """Scan all reports and fix database relationships to ensure all cycles have correct reports."""
        try:
            # Get all cycles
            cycles = self.db.session.query(CycleData).all()
            reports_dir = os.path.join(os.getcwd(), "reports")
            
            # Get all report files
            all_reports = []
            for ext in ['.pdf', '.html']:
                files = glob.glob(os.path.join(reports_dir, f"*{ext}"))
                all_reports.extend(files)
            
            # Sort reports by newest first
            all_reports.sort(key=os.path.getmtime, reverse=True)
            
            # Track statistics
            total_cycles = len(cycles)
            fixed_cycles = 0
            unmatched_cycles = []
            
            # For each cycle, try to find a matching report
            for cycle in cycles:
                cycle_id = cycle.id
                cycle_found_report = False
                
                # Check if cycle already has a report
                existing_report = self.db.session.query(CycleReport).filter_by(cycle_id=cycle_id).first()
                if existing_report and existing_report.pdf_report_path:
                    pdf_path = os.path.join(reports_dir, existing_report.pdf_report_path)
                    if os.path.exists(pdf_path):
                        # Report exists and is valid
                        cycle_found_report = True
                        continue
                
                # Get serial numbers for this cycle
                cycle_serials = self.db.session.query(CycleSerialNumber).filter_by(cycle_id=cycle_id).all()
                serial_numbers = [s.serial_number for s in cycle_serials if s.serial_number and not s.serial_number.startswith("PLACEHOLDER_")]
                
                # Try to find a report with the cycle ID in the filename
                cycle_id_str = str(cycle_id)
                matched_report = None
                
                # Try different patterns to match reports to this cycle
                for report in all_reports:
                    report_basename = os.path.basename(report)
                    
                    # Skip reports already linked to other cycles
                    already_linked = self.db.session.query(CycleReport).filter(
                        (CycleReport.pdf_report_path == os.path.relpath(report, reports_dir)) |
                        (CycleReport.pdf_report_path == report_basename)
                    ).first()
                    
                    if already_linked and already_linked.cycle_id != cycle_id:
                        continue
                    
                    # Check if report filename contains the cycle ID
                    if f"_{cycle_id_str}_" in report_basename or report_basename.startswith(f"{cycle_id_str}_"):
                        matched_report = report
                        break
                    
                    # If no direct filename match, check the CSV content for serial numbers
                    if serial_numbers:
                        csv_path = report.replace('.pdf', '.csv').replace('.html', '.csv')
                        if os.path.exists(csv_path):
                            try:
                                with open(csv_path, 'r', newline='', errors='ignore') as f:
                                    content = f.read()
                                    # Check if any serial number appears in the CSV
                                    for serial in serial_numbers:
                                        if serial in content:
                                            matched_report = report
                                            break
                                    if matched_report:
                                        break
                            except Exception as e:
                                logger.warning(f"Error reading {csv_path}: {e}")
                
                # If we found a matching report, update the database
                if matched_report:
                    self.update_report_in_database(cycle_id, matched_report)
                    fixed_cycles += 1
                    cycle_found_report = True
                
                # If no report found, add to unmatched list
                if not cycle_found_report:
                    unmatched_cycles.append(cycle_id)
            
            # Show results
            result_message = f"Repair complete: {fixed_cycles} of {total_cycles} cycles now have correct report links."
            if unmatched_cycles:
                result_message += f"\n\nCycles still missing reports: {', '.join(map(str, unmatched_cycles))}"
            
            # Reload the display
            self.load_all_serials()
            
            QtWidgets.QMessageBox.information(
                self,
                "Report Repair Complete",
                result_message
            )
            
        except Exception as e:
            logger.error(f"Error repairing report relationships: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to repair report relationships: {e}"
            )
    
    def is_serial_in_csv(self, serial_number, csv_path):
        """Check if a serial number appears in a CSV file."""
        try:
            with open(csv_path, 'r', newline='', errors='ignore') as f:
                reader = csv.reader(f)
                for row in reader:
                    row_text = ' '.join(row)
                    if serial_number in row_text:
                        return True
            return False
        except Exception as e:
            logger.warning(f"Error checking serial {serial_number} in CSV {csv_path}: {e}")
            return False

    def find_report_for_cycle(self, cycle_id):
        """Find the report file for a specific cycle ID."""
        try:
            # First check the database - the most reliable source of report-cycle associations
            cycle_report = self.db.session.query(CycleReport).filter_by(cycle_id=cycle_id).first()
            reports_dir = os.path.join(os.getcwd(), "reports")

            if cycle_report:
                # Check PDF path first
                if cycle_report.pdf_report_path:
                    pdf_path = os.path.join(reports_dir, cycle_report.pdf_report_path)
                    if os.path.exists(pdf_path):
                        logger.info(f"Found report for cycle {cycle_id} in database PDF path: {pdf_path}")
                        return pdf_path

                # Then check HTML path
                if cycle_report.html_report_path:
                    html_path = os.path.join(reports_dir, cycle_report.html_report_path)
                    if os.path.exists(html_path):
                        logger.info(f"Found report for cycle {cycle_id} in database HTML path: {html_path}")
                        return html_path
                
                # Then check HTML content
                if cycle_report.html_report_content:
                    logger.info(f"Found embedded HTML report content for cycle {cycle_id}")
                    return cycle_report.html_report_content

            # Try to find serial numbers for this cycle
            cycle_serials = self.db.session.query(CycleSerialNumber).filter_by(cycle_id=cycle_id).all()
            serial_numbers = [s.serial_number for s in cycle_serials if s.serial_number and not s.serial_number.startswith("PLACEHOLDER_")]
            
            # If not found in database, look for files that match this cycle ID
            cycle_id_str = str(cycle_id)

            # First, look for exact format matches - most specific pattern first
            exact_patterns = [
                os.path.join(reports_dir, f"{cycle_id_str}_*.pdf"),  # Starts with exact cycle ID
                os.path.join(reports_dir, f"*_{cycle_id_str}.pdf"),  # Ends with exact cycle ID
                os.path.join(reports_dir, f"*_{cycle_id_str}_*.pdf"),  # Contains exact cycle ID with underscores
                os.path.join(reports_dir, f"{cycle_id_str}_*.html"),  # HTML variants
                os.path.join(reports_dir, f"*_{cycle_id_str}.html"),
                os.path.join(reports_dir, f"*_{cycle_id_str}_*.html")
            ]

            for pattern in exact_patterns:
                matches = glob.glob(pattern)
                if matches:
                    # Sort by modification time to get the newest report
                    matches.sort(key=os.path.getmtime, reverse=True)
                    logger.info(f"Found report for cycle {cycle_id} using pattern match: {os.path.basename(matches[0])}")
                    
                    # Update the database to link this report to this cycle
                    self.update_report_in_database(cycle_id, matches[0])
                    
                    return matches[0]

            # If we still haven't found a report, check CSV content for cycle ID or serial numbers
            all_reports = glob.glob(os.path.join(reports_dir, "*.pdf")) + glob.glob(os.path.join(reports_dir, "*.html"))
            
            for report in all_reports:
                # First check filename for exact match with word boundaries
                filename = os.path.basename(report)
                if re.search(r'\b' + re.escape(cycle_id_str) + r'\b', filename):
                    logger.info(f"Found report for cycle {cycle_id} via filename match: {filename}")
                    
                    # Update the database to link this report to this cycle
                    self.update_report_in_database(cycle_id, report)
                    
                    return report
                    
                # Look for a corresponding CSV file
                csv_path = report.replace('.pdf', '.csv').replace('.html', '.csv')
                if os.path.exists(csv_path):
                    try:
                        with open(csv_path, 'r', newline='', errors='ignore') as f:
                            content = f.read()
                            
                            # Look for the cycle ID as a whole word with word boundaries
                            if re.search(r'\b' + re.escape(cycle_id_str) + r'\b', content):
                                # Found a CSV that mentions this cycle ID
                                # Check if this report is already assigned to another cycle
                                existing_cycle = self.db.session.query(CycleReport).filter(
                                    (CycleReport.pdf_report_path == os.path.relpath(report, reports_dir)) |
                                    (CycleReport.html_report_path == os.path.relpath(report, reports_dir))
                                ).first()
                                
                                if not existing_cycle or existing_cycle.cycle_id == cycle_id:
                                    # Report is either not assigned to any cycle or assigned to this cycle
                                    logger.info(f"Found report for cycle {cycle_id} via cycle ID in CSV: {os.path.basename(report)}")
                                    
                                    # Update the database to link this report to this cycle
                                    self.update_report_in_database(cycle_id, report)
                                    
                                    return report
                            
                            # Check if any serial number appears in the CSV
                            if serial_numbers:
                                for serial in serial_numbers:
                                    if serial in content:
                                        logger.info(f"Found report for cycle {cycle_id} via serial {serial} in CSV: {os.path.basename(report)}")
                                        
                                        # Update the database to link this report to this cycle
                                        self.update_report_in_database(cycle_id, report)
                                        
                                        return report
                    except Exception as e:
                        logger.warning(f"Error reading {csv_path}: {e}")

            # If we still can't find a report, check the most recent cycle in the database
            # This is useful when cycle IDs have been renumbered or reassigned
            if cycle_id_str == "1":  # Only for cycle 1, which seems to be a problem case
                try:
                    # Get the newest cycle that has a report
                    newest_report = self.db.session.query(CycleReport).order_by(desc(CycleReport.id)).first()
                    if newest_report and newest_report.pdf_report_path:
                        pdf_path = os.path.join(reports_dir, newest_report.pdf_report_path)
                        if os.path.exists(pdf_path):
                            logger.info(f"Using newest report for cycle {cycle_id} as fallback: {newest_report.pdf_report_path}")
                            
                            # Update the database to link this report to this cycle
                            self.update_report_in_database(cycle_id, pdf_path)
                            
                            return pdf_path
                except Exception as e:
                    logger.error(f"Error checking newest report: {e}")

            # If we get here, we couldn't find a report using any method
            logger.warning(f"No report found for cycle {cycle_id} using any method")
            return None
        except Exception as e:
            logger.error(f"Error finding report for cycle {cycle_id}: {e}", exc_info=True)
            return None

    def load_all_serials(self):
        """
        Loads all serial numbers from the database, showing one serial per row.
        For each serial record, its cycle (if available) is used to fetch the
        corresponding report file using a simple cache so that the same cycle
        always shows the same report.
        """
        try:
            table = self.ui.serialTableWidget
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels([
                "Serial Number", "Added By", "Work Order", "Cycle ID", "Report Link", "Actions"
            ])
            
            # Retrieve serial numbers from the database (newest first)
            records = self.db.session.query(CycleSerialNumber)\
                        .options(
                            joinedload(CycleSerialNumber.cycle)
                            .joinedload(CycleData.user)
                        )\
                        .order_by(desc(CycleSerialNumber.id))\
                        .all()
            
            all_records = []
            # Cache for cycle report lookup so we don't repeatedly search disk for the same cycle
            cycle_report_cache = {}
            
            # Track reports to detect sharing across different cycles
            report_to_cycles = {}
            conflict_reports = set()
            
            # Process each serial record individually
            for record in records:
                # Skip empty or placeholder serial numbers
                if not record.serial_number or record.serial_number.startswith("PLACEHOLDER_"):
                    continue
                serial_text = record.serial_number.strip()
                
                # Default values
                added_by = "Unknown"
                work_order = "N/A"
                cycle_id_display = "N/A"
                report_link = "N/A"
                
                if record.cycle:
                    cycle = record.cycle
                    added_by = cycle.user.username if cycle.user and cycle.user.username else "Unknown"
                    work_order = cycle.order_id if cycle.order_id else "N/A"
                    cycle_id_display = str(cycle.id)
                    
                    # Use cached report if available
                    if cycle.id not in cycle_report_cache:
                        rpt = self.find_report_for_cycle(cycle.id)
                        # Cache the report path, or a "No report" message
                        cycle_report_cache[cycle.id] = rpt if rpt else f"N/A (No report for cycle {cycle.id})"
                    
                    report_link = cycle_report_cache[cycle.id]
                    
                    # Track which reports are being used by which cycles
                    if report_link and not report_link.startswith("N/A"):
                        if report_link not in report_to_cycles:
                            report_to_cycles[report_link] = set()
                        report_to_cycles[report_link].add(cycle.id)
                        
                        # If this report is now linked to multiple cycles, flag it as a conflict
                        if len(report_to_cycles[report_link]) > 1:
                            conflict_reports.add(report_link)
                
                # Append one record per serial
                all_records.append((serial_text, added_by, work_order, cycle_id_display, report_link))
            
            # Optionally sort records by cycle_id (numeric descending) while leaving standalone serials at the top
            def sort_key(item):
                try:
                    return int(item[3])
                except:
                    return 0
            all_records.sort(key=sort_key, reverse=True)
            
            self.all_serials = all_records
            self.filtered_serials = self.all_serials.copy()
            self.update_pagination()
            self.display_current_page()
            
            # If any conflicts were detected, alert the user
            if conflict_reports:
                conflict_details = []
                for report in conflict_reports:
                    cycles = sorted(report_to_cycles[report])
                    report_name = os.path.basename(report)
                    conflict_details.append(f"{report_name} is linked to cycles: {', '.join(map(str, cycles))}")
                
                conflict_message = "Detected report files linked to multiple cycles:\n\n" + "\n".join(conflict_details)
                
                QtWidgets.QMessageBox.warning(
                    self,
                    "Report Conflicts Detected",
                    conflict_message + "\n\nUse the 'Fix Serial-Cycle Relationships' button to resolve these issues."
                )
            
            logger.info(f"Loaded {len(self.all_serials)} serial record(s)")
            
        except Exception as e:
            logger.error(f"Failed to load serial numbers: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load serial numbers: {e}")
    def filter_serials(self):
        """Filter serial numbers based on search text."""
        search_text = self.searchLineEdit.text().strip().lower()
        if not search_text:
            self.filtered_serials = self.all_serials.copy()
        else:
            # Search in serial number, added by, work order, and cycle ID
            self.filtered_serials = [
                s for s in self.all_serials if 
                search_text in s[0].lower() or  # serial number
                search_text in s[1].lower() or  # added by
                search_text in s[2].lower() or  # work order
                search_text in s[3].lower()     # cycle ID
            ]
        self.current_page = 0
        self.update_pagination()
        self.display_current_page()

    def update_pagination(self):
        """Update pagination controls."""
        self.total_pages = max(1, (len(self.filtered_serials) + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, max(0, self.total_pages - 1))
        self.pageLabel.setText(f"Page {self.current_page + 1} of {self.total_pages}")
        self.prevButton.setEnabled(self.current_page > 0)
        self.nextButton.setEnabled(self.current_page < self.total_pages - 1)

    def create_action_button(self, row, text, callback):
        """Create an action button for the given row."""
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(lambda: callback(row))
        return button

    def display_current_page(self):
        """Render the current page in the table widget."""
        table = self.ui.serialTableWidget
        table.setRowCount(0)
        if not self.filtered_serials:
            table.setRowCount(1)
            table.setItem(0, 0, QtWidgets.QTableWidgetItem("No serial numbers found"))
            for col in range(1, 6):
                table.setItem(0, col, QtWidgets.QTableWidgetItem(""))
            return
        
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.filtered_serials))
        page_serials = self.filtered_serials[start_idx:end_idx]
        table.setRowCount(len(page_serials))
        
        # Track which reports are shown for each cycle on this page
        cycle_reports_on_page = {}
        
        for i, (serial, added_by, work_order, cycle_id, report_link) in enumerate(page_serials):
            # Create table items
            serial_item = QtWidgets.QTableWidgetItem(serial)
            added_by_item = QtWidgets.QTableWidgetItem(added_by)
            work_order_item = QtWidgets.QTableWidgetItem(work_order)
            cycle_id_item = QtWidgets.QTableWidgetItem(cycle_id)
            
            # Keep track of which report is shown for this cycle
            if cycle_id != "N/A" and not report_link.startswith("N/A"):
                if cycle_id not in cycle_reports_on_page:
                    cycle_reports_on_page[cycle_id] = report_link
                elif cycle_reports_on_page[cycle_id] != report_link:
                    logger.warning(f"Inconsistent reports for cycle {cycle_id}: {cycle_reports_on_page[cycle_id]} vs {report_link}")
            
            # Create a more user-friendly display for report links
            if report_link.startswith("N/A"):
                report_item = QtWidgets.QTableWidgetItem(report_link)
                # Add a tooltip explaining why no report is available
                report_item.setToolTip(report_link)
            else:
                # Show just the filename, not the full path
                filename = os.path.basename(report_link)
                report_item = QtWidgets.QTableWidgetItem(filename)
                # Make it look like a link
                report_item.setForeground(Qt.blue)
                # Store the full path as data
                report_item.setData(Qt.UserRole, report_link)
                # Add a tooltip that includes cycle ID and serial for clarity
                report_item.setToolTip(f"Click to open report for cycle {cycle_id}, serial {serial}: {filename}")
            
            # Add items to the table
            table.setItem(i, 0, serial_item)
            table.setItem(i, 1, added_by_item)
            table.setItem(i, 2, work_order_item)
            table.setItem(i, 3, cycle_id_item)
            table.setItem(i, 4, report_item)
            
            # Create action buttons
            button_layout = QtWidgets.QHBoxLayout()
            button_layout.setContentsMargins(0, 0, 0, 0)
            
            # Add 'Browse' button to manually select a report
            browse_button = QtWidgets.QPushButton("Browse")
            browse_button.clicked.connect(lambda checked=False, row=i: self.browse_for_report(row))
            button_layout.addWidget(browse_button)
            
            # Add container widget for the layout
            button_container = QtWidgets.QWidget()
            button_container.setLayout(button_layout)
            table.setCellWidget(i, 5, button_container)
        
        # Resize columns to fit content
        table.resizeColumnsToContents()

    def browse_for_report(self, row):
        """Open a file dialog to let the user select a report file for this serial."""
        table = self.ui.serialTableWidget
        
        # Get the serial number and cycle ID
        serial_item = table.item(row, 0)
        cycle_id_item = table.item(row, 3)
        
        if not serial_item or not cycle_id_item:
            return
            
        serial = serial_item.text()
        cycle_id = cycle_id_item.text()
        
        # Open file dialog
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Report files (*.pdf *.html *.csv)")
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                selected_file = selected_files[0]
                
                # Store in manual assignments
                serial_key = f"serial_{serial}_cycle_{cycle_id}"
                self.manual_report_assignments[serial_key] = selected_file
                
                # Update the table cell
                report_item = table.item(row, 4)
                if report_item:
                    filename = os.path.basename(selected_file)
                    report_item.setText(filename)
                    report_item.setData(Qt.UserRole, selected_file)
                    report_item.setForeground(Qt.blue)
                    report_item.setToolTip(f"Click to open report for cycle {cycle_id}, serial {serial}: {filename}")
                
                # Ask if the user wants to update the database
                reply = QtWidgets.QMessageBox.question(
                    self, 
                    "Update Database",
                    f"Do you want to update the database to link this report to cycle {cycle_id}?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                
                if reply == QtWidgets.QMessageBox.Yes:
                    self.update_report_in_database(cycle_id, selected_file)

    def update_report_in_database(self, cycle_id, report_path):
        """Update the CycleReport table to link this report with this cycle."""
        try:
            # Convert cycle_id to integer
            cycle_id = int(cycle_id)
            
            # Get relative path from absolute path
            reports_dir = os.path.join(os.getcwd(), "reports")
            rel_path = os.path.relpath(report_path, reports_dir)
            
            # Check file extension
            is_pdf = report_path.lower().endswith('.pdf')
            
            # Find or create CycleReport
            cycle_report = self.db.session.query(CycleReport).filter_by(cycle_id=cycle_id).first()
            
            if not cycle_report:
                # Create new report record
                cycle_report = CycleReport(
                    cycle_id=cycle_id,
                    pdf_report_path=rel_path if is_pdf else None,
                    html_report_path=rel_path if not is_pdf else None,
                    html_report_content=None  # Initialize HTML content
                )
                self.db.session.add(cycle_report)
            else:
                # Update existing record
                if is_pdf:
                    cycle_report.pdf_report_path = rel_path
                    cycle_report.html_report_path = None  # Clear the HTML path if updating to PDF
                    cycle_report.html_report_content = None  # Clear the HTML content
                else:
                    cycle_report.html_report_path = rel_path
                    cycle_report.pdf_report_path = None  # Clear the PDF path if updating to HTML
                    cycle_report.html_report_content = None  # Clear the HTML content
            
            # Save changes
            self.db.session.commit()
            
            QtWidgets.QMessageBox.information(
                self, 
                "Database Updated", 
                f"Report {os.path.basename(report_path)} has been linked to cycle {cycle_id} in the database."
            )
            
        except Exception as e:
            logger.error(f"Error updating report in database: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                "Database Error", 
                f"Failed to update the database: {e}"
            )

    def cell_clicked(self, row, column):
        """
        Opens the file if the clicked cell is for the Report Link (column 4)
        and the file exists.
        """
        table = self.ui.serialTableWidget
        item = table.item(row, column)
        if item is None:
            return
            
        # Only handle clicks on the Report Link column
        if column != 4:
            return
            
        # Get the stored file path or the text if no path is stored
        file_path = item.data(Qt.UserRole) if item.data(Qt.UserRole) else item.text()
        
        # Get the cycle ID and serial number for this row
        cycle_id_item = table.item(row, 3)
        cycle_id = cycle_id_item.text() if cycle_id_item else "Unknown"
        
        serial_item = table.item(row, 0)
        serial = serial_item.text() if serial_item else "Unknown"
        
        if file_path.startswith("N/A"):
            # Use our browse function to let the user find a report
            self.browse_for_report(row)
            return
            
        if os.path.exists(file_path):
            logger.info(f"Opening report file for cycle {cycle_id}, serial {serial}: {file_path}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            logger.warning(f"Report file not found: {file_path}")
            QtWidgets.QMessageBox.warning(
                self, 
                "Report Not Found", 
                f"File not found:\n{file_path}\n\nWould you like to browse for the report?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            # If user wants to browse for the report
            if QtWidgets.QMessageBox.Yes:
                self.browse_for_report(row)

    def next_page(self):
        """Advance to next page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_current_page()
            self.update_pagination()

    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_current_page()
            self.update_pagination()

    def search_serial(self):
        """Set focus to search field and show message with results."""
        self.searchLineEdit.setFocus()
        search_text = self.searchLineEdit.text().strip()
        self.filter_serials()
        if search_text:
            found_count = len(self.filtered_serials)
            QtWidgets.QMessageBox.information(
                self, "Search Results", f"Found {found_count} serial numbers matching '{search_text}'."
            )
