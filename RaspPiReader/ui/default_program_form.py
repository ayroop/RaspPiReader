import sys
from PyQt5 import QtWidgets
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import DefaultProgram
from RaspPiReader import pool

class DefaultProgramForm(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(DefaultProgramForm, self).__init__(parent)
        self.setWindowTitle("Default Programs Management")
        self.resize(600, 500)
        self.db = Database("sqlite:///local_database.db")
        self.current_user = pool.get('current_user') or "Unknown"
        self.layout = QtWidgets.QVBoxLayout(self)
        self.tabWidget = QtWidgets.QTabWidget(self)
        self.layout.addWidget(self.tabWidget)
        self.program_fields = {}  # Will hold QLineEdits for each program
        
        # Create tabs for Programs 1 to 4
        for i in range(1, 5):
            tab = QtWidgets.QWidget()
            form = QtWidgets.QFormLayout(tab)
            fields = {}
            fields["dwell_time"] = QtWidgets.QLineEdit()
            fields["set_core_temp"] = QtWidgets.QLineEdit()
            fields["cool_down_ramp"] = QtWidgets.QLineEdit()
            fields["set_temp_ramp"] = QtWidgets.QLineEdit()
            fields["set_pressure"] = QtWidgets.QLineEdit()
            fields["initial_set_cure_temp"] = QtWidgets.QLineEdit()
            fields["final_set_cure_temp"] = QtWidgets.QLineEdit()
            form.addRow("Dwell Time:", fields["dwell_time"])
            form.addRow("Set Core Temperature:", fields["set_core_temp"])
            form.addRow("Cool Down Ramp:", fields["cool_down_ramp"])
            form.addRow("Set Temperature Ramp:", fields["set_temp_ramp"])
            form.addRow("Set Pressure:", fields["set_pressure"])
            form.addRow("Initial Set Cure Temperature:", fields["initial_set_cure_temp"])
            form.addRow("Final Set Cure Temperature:", fields["final_set_cure_temp"])
            self.program_fields[i] = fields
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
        # Default example values
        default_values = {
            1: {"dwell_time": "value a", "set_core_temp": "value b", "cool_down_ramp": "value c",
                "set_temp_ramp": "value d", "set_pressure": "value p1", "initial_set_cure_temp": "value i1", "final_set_cure_temp": "value f1"},
            2: {"dwell_time": "value x", "set_core_temp": "value y", "cool_down_ramp": "value z",
                "set_temp_ramp": "value a1", "set_pressure": "value p2", "initial_set_cure_temp": "value i2", "final_set_cure_temp": "value f2"},
            3: {"dwell_time": "value x2", "set_core_temp": "value y2", "cool_down_ramp": "value z2",
                "set_temp_ramp": "value a2", "set_pressure": "value p3", "initial_set_cure_temp": "value i3", "final_set_cure_temp": "value f3"},
            4: {"dwell_time": "value x4", "set_core_temp": "value y4", "cool_down_ramp": "value z4",
                "set_temp_ramp": "value a4", "set_pressure": "value p4", "initial_set_cure_temp": "value i4", "final_set_cure_temp": "value f4"},
        }
        # For each program, try to load saved values
        for prog_num in range(1, 5):
            prog = self.db.session.query(DefaultProgram).filter_by(username=self.current_user, program_number=prog_num).first()
            if prog:
                data = {
                    "dwell_time": prog.dwell_time,
                    "set_core_temp": prog.set_core_temp,
                    "cool_down_ramp": prog.cool_down_ramp,
                    "set_temp_ramp": prog.set_temp_ramp,
                    "set_pressure": prog.set_pressure,
                    "initial_set_cure_temp": prog.initial_set_cure_temp,
                    "final_set_cure_temp": prog.final_set_cure_temp,
                }
            else:
                data = default_values[prog_num]
            fields = self.program_fields[prog_num]
            fields["dwell_time"].setText(data["dwell_time"])
            fields["set_core_temp"].setText(data["set_core_temp"])
            fields["cool_down_ramp"].setText(data["cool_down_ramp"])
            fields["set_temp_ramp"].setText(data["set_temp_ramp"])
            fields["set_pressure"].setText(data["set_pressure"])
            fields["initial_set_cure_temp"].setText(data["initial_set_cure_temp"])
            fields["final_set_cure_temp"].setText(data["final_set_cure_temp"])

    def save_programs(self):
        # Save or update a default program for each tab
        for prog_num in range(1, 5):
            fields = self.program_fields[prog_num]
            dwell_time = fields["dwell_time"].text().strip()
            set_core_temp = fields["set_core_temp"].text().strip()
            cool_down_ramp = fields["cool_down_ramp"].text().strip()
            set_temp_ramp = fields["set_temp_ramp"].text().strip()
            set_pressure = fields["set_pressure"].text().strip()
            initial_set_cure_temp = fields["initial_set_cure_temp"].text().strip()
            final_set_cure_temp = fields["final_set_cure_temp"].text().strip()
            prog = self.db.session.query(DefaultProgram).filter_by(username=self.current_user, program_number=prog_num).first()
            if not prog:
                prog = DefaultProgram(
                    username=self.current_user,
                    program_number=prog_num,
                    dwell_time=dwell_time,
                    set_core_temp=set_core_temp,
                    cool_down_ramp=cool_down_ramp,
                    set_temp_ramp=set_temp_ramp,
                    set_pressure=set_pressure,
                    initial_set_cure_temp=initial_set_cure_temp,
                    final_set_cure_temp=final_set_cure_temp
                )
                self.db.session.add(prog)
            else:
                prog.dwell_time = dwell_time
                prog.set_core_temp = set_core_temp
                prog.cool_down_ramp = cool_down_ramp
                prog.set_temp_ramp = set_temp_ramp
                prog.set_pressure = set_pressure
                prog.initial_set_cure_temp = initial_set_cure_temp
                prog.final_set_cure_temp = final_set_cure_temp
        self.db.session.commit()
        QtWidgets.QMessageBox.information(self, "Saved", "Default programs saved successfully.")
        self.accept()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    dlg = DefaultProgramForm()
    dlg.show()
    sys.exit(app.exec_())