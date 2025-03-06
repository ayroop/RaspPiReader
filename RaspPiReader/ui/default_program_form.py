from PyQt5 import QtWidgets
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import DefaultProgram
from RaspPiReader import pool

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
        # Removed "order_number" and "quantity" fields
        fields_to_include = [
            "cycle_id", "size", "cycle_location", "dwell_time", "cool_down_temp",
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