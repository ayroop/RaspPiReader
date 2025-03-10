import logging
import random
import time
from PyQt5 import QtWidgets
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import DefaultProgram
from RaspPiReader import pool

# Set up logger
logger = logging.getLogger(__name__)

class DefaultProgramForm(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(DefaultProgramForm, self).__init__(parent)
        self.setWindowTitle("Default Programs Management")
        self.resize(650, 500)
        self.db = Database("sqlite:///local_database.db")
        self.current_user = pool.get('current_user') or "Unknown"
        self.layout = QtWidgets.QVBoxLayout(self)
        self.tabWidget = QtWidgets.QTabWidget(self)
        self.layout.addWidget(self.tabWidget)
        self.program_fields = {}  # Will hold QLineEdits for each program

        # Create tabs for Programs 1 to 4
        fields_to_include = [
            "size", "cycle_location", "dwell_time", "cool_down_temp",
            "core_temp_setpoint", "temp_ramp", "set_pressure", "maintain_vacuum",
            "initial_set_cure_temp", "final_set_cure_temp"
        ]
        
        for i in range(1, 5):
            tab = QtWidgets.QWidget()
            form_layout = QtWidgets.QFormLayout(tab)
            self.program_fields[i] = {}
            for field_name in fields_to_include:
                label = QtWidgets.QLabel(field_name.replace("_", " ").title())
                line_edit = QtWidgets.QLineEdit()
                form_layout.addRow(label, line_edit)
                self.program_fields[i][field_name] = line_edit
            self.tabWidget.addTab(tab, f"Program {i}")
        
        # Add Save and Cancel buttons
        self.buttonLayout = QtWidgets.QHBoxLayout()
        self.saveButton = QtWidgets.QPushButton("Save")
        self.cancelButton = QtWidgets.QPushButton("Cancel")
        self.buttonLayout.addWidget(self.saveButton)
        self.buttonLayout.addWidget(self.cancelButton)
        self.layout.addLayout(self.buttonLayout)
        
        # Connect the buttons to their handlers
        self.saveButton.clicked.connect(self.save_programs)
        self.cancelButton.clicked.connect(self.reject)
        
        # Load existing program data
        self.load_programs()
    
    def generate_cycle_id(self):
        """Generate a unique cycle ID based on timestamp and random number"""
        timestamp = int(time.time())
        random_digits = random.randint(1000, 9999)
        return f"{timestamp}{random_digits}"

    def load_programs(self):
        """Load saved program data from the database into the UI"""
        try:
            for prog_num, fields in self.program_fields.items():
                # Get the default program settings for this user and program number
                program = self.db.session.query(DefaultProgram).filter_by(
                    program_number=prog_num,
                    username=self.current_user
                ).first()
                
                if program:
                    logger.info(f"Loading program {prog_num} data for user {self.current_user}")
                    # Update the fields with values from the database
                    for field, widget in fields.items():
                        if hasattr(program, field):
                            value = getattr(program, field)
                            if value is not None:
                                if isinstance(widget, QtWidgets.QLineEdit):
                                    widget.setText(str(value))
        except Exception as e:
            logger.error(f"Error loading program data: {e}")
            QtWidgets.QMessageBox.warning(
                self, 
                "Data Loading Error",
                f"Could not load saved program data: {str(e)}"
            )
    
    def save_programs(self):
        """Gather data from each tab and save to the database."""
        try:
            for prog_num, fields in self.program_fields.items():
                # Retrieve an existing record for this program number and username, or create a new one
                program = self.db.session.query(DefaultProgram).filter_by(
                    program_number=prog_num,
                    username=self.current_user
                ).first()
                
                if not program:
                    program = DefaultProgram()
                    # Auto-generate cycle_id for new programs
                    program.cycle_id = self.generate_cycle_id()
                
                # Set required fields (ensure no NULL values for NOT NULL columns)
                program.username = self.current_user
                program.program_number = prog_num
                program.order_number = f"ORD-{prog_num}"
                
                # Set a default for quantity if required
                if hasattr(program, "quantity") and getattr(program, "quantity") is None:
                    program.quantity = 1
                
                # Save field data from the UI into the record
                for field, widget in fields.items():
                    if isinstance(widget, QtWidgets.QLineEdit):
                        setattr(program, field, widget.text())
                
                self.db.session.add(program)
            
            self.db.session.commit()
            QtWidgets.QMessageBox.information(self, "Success", "Default programs saved successfully.")
            self.accept()  # Close the dialog after successful save
        except Exception as e:
            self.db.session.rollback()
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save default programs:\n{e}")