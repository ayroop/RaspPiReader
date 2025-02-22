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
        for i in range(1, 5):
            tab = QtWidgets.QWidget()
            form_layout = QtWidgets.QFormLayout(tab)
            self.program_fields[i] = {}
            for field_name in ["order_number", "cycle_id", "quantity", "size", "cycle_location", "dwell_time", "cool_down_temp", "core_temp_setpoint", "temp_ramp", "set_pressure", "maintain_vacuum", "initial_set_cure_temp", "final_set_cure_temp"]:
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
        
        self.saveButton.clicked.connect(self.save_programs)
        self.cancelButton.clicked.connect(self.reject)
        
        self.load_programs()

    def load_programs(self):
        for i in range(1, 5):
            default_program = self.db.session.query(DefaultProgram).filter_by(username=self.current_user, program_number=i).first()
            if default_program:
                for field_name, line_edit in self.program_fields[i].items():
                    value = getattr(default_program, field_name, "")
                    line_edit.setText(str(value))

    def save_programs(self):
        for i in range(1, 5):
            fields = self.program_fields[i]
            default_program = self.db.session.query(DefaultProgram).filter_by(username=self.current_user, program_number=i).first()
            if not default_program:
                default_program = DefaultProgram(
                    username=self.current_user,
                    program_number=i,
                    order_number=fields["order_number"].text().strip(),
                    cycle_id=fields["cycle_id"].text().strip(),
                    quantity=fields["quantity"].text().strip(),
                    size=fields["size"].text().strip(),
                    cycle_location=fields["cycle_location"].text().strip(),
                    dwell_time=fields["dwell_time"].text().strip(),
                    cool_down_temp=fields["cool_down_temp"].text().strip(),
                    core_temp_setpoint=fields["core_temp_setpoint"].text().strip(),
                    temp_ramp=fields["temp_ramp"].text().strip(),
                    set_pressure=fields["set_pressure"].text().strip(),
                    maintain_vacuum=fields["maintain_vacuum"].text().strip(),
                    initial_set_cure_temp=fields["initial_set_cure_temp"].text().strip(),
                    final_set_cure_temp=fields["final_set_cure_temp"].text().strip()
                )
                self.db.session.add(default_program)
            else:
                default_program.order_number = fields["order_number"].text().strip()
                default_program.cycle_id = fields["cycle_id"].text().strip()
                default_program.quantity = fields["quantity"].text().strip()
                default_program.size = fields["size"].text().strip()
                default_program.cycle_location = fields["cycle_location"].text().strip()
                default_program.dwell_time = fields["dwell_time"].text().strip()
                default_program.cool_down_temp = fields["cool_down_temp"].text().strip()
                default_program.core_temp_setpoint = fields["core_temp_setpoint"].text().strip()
                default_program.temp_ramp = fields["temp_ramp"].text().strip()
                default_program.set_pressure = fields["set_pressure"].text().strip()
                default_program.maintain_vacuum = fields["maintain_vacuum"].text().strip()
                default_program.initial_set_cure_temp = fields["initial_set_cure_temp"].text().strip()
                default_program.final_set_cure_temp = fields["final_set_cure_temp"].text().strip()
        self.db.session.commit()
        QtWidgets.QMessageBox.information(self, "Saved", "Default programs saved successfully.")
        self.accept()

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    dlg = DefaultProgramForm()
    dlg.show()
    sys.exit(app.exec_())