from PyQt5 import QtWidgets
from RaspPiReader.ui.program_selection_form import Ui_ProgramSelectionForm
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData, DefaultProgram
from RaspPiReader import pool

class ProgramSelectionFormHandler(QtWidgets.QWidget):
    def __init__(self, work_order, serial_numbers, parent=None):
        super(ProgramSelectionFormHandler, self).__init__(parent)
        self.ui = Ui_ProgramSelectionForm()
        self.ui.setupUi(self)
        self.work_order = work_order
        self.serial_numbers = serial_numbers  # list of (processed) serial numbers
        self.db = Database("sqlite:///local_database.db")
        self.ui.startCycleButton.clicked.connect(self.start_cycle)
        self.ui.cancelButton.clicked.connect(self.close)
        self.ui.programComboBox.currentIndexChanged.connect(self.update_program_info)
        self.update_program_info(self.ui.programComboBox.currentIndex())
    
    def update_program_info(self, index):
        program_index = index + 1
        current_user = pool.get("current_user")
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=current_user, program_number=program_index
        ).first()
        if default_program:
            info_text = (
                f"Cycle ID: {default_program.cycle_id}\n"
                f"Size: {default_program.size}\n"
                f"Location: {default_program.cycle_location}\n"
                f"Dwell Time: {default_program.dwell_time}\n"
                f"Cool Down Temp: {default_program.cool_down_temp}\n"
                f"Core Temp Setpoint: {default_program.core_temp_setpoint}\n"
                f"Temp Ramp: {default_program.temp_ramp}\n"
                f"Set Pressure: {default_program.set_pressure}\n"
                f"Maintain Vacuum: {default_program.maintain_vacuum}\n"
                f"Initial Set Cure Temp: {default_program.initial_set_cure_temp}\n"
                f"Final Set Cure Temp: {default_program.final_set_cure_temp}\n"
            )
        else:
            info_text = "No preset program found for this selection."
        if hasattr(self.ui, "programInfoLabel"):
            self.ui.programInfoLabel.setText(info_text)
    
    def start_cycle(self):
        program_index = self.ui.programComboBox.currentIndex() + 1
        current_user = pool.get("current_user")
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=current_user, program_number=program_index
        ).first()
        if not default_program:
            QtWidgets.QMessageBox.warning(self, "Warning", f"No preset program found for Program {program_index}")
            return
        
        try:
            cycle = CycleData(
                order_id=self.work_order,
                cycle_id=default_program.cycle_id or "",
                quantity=str(len(self.serial_numbers)),
                size=default_program.size or "",
                cycle_location=default_program.cycle_location or "",
                dwell_time=default_program.dwell_time or "0",
                cool_down_temp=float(default_program.cool_down_temp) if default_program.cool_down_temp and default_program.cool_down_temp.strip() else 0.0,
                core_temp_setpoint=float(default_program.core_temp_setpoint) if default_program.core_temp_setpoint and default_program.core_temp_setpoint.strip() else 0.0,
                temp_ramp=float(default_program.temp_ramp) if default_program.temp_ramp and default_program.temp_ramp.strip() else 0.0,
                set_pressure=float(default_program.set_pressure) if default_program.set_pressure and default_program.set_pressure.strip() else 0.0,
                maintain_vacuum=float(default_program.maintain_vacuum) if default_program.maintain_vacuum and default_program.maintain_vacuum.strip() else 0.0,
                initial_set_cure_temp=float(default_program.initial_set_cure_temp) if default_program.initial_set_cure_temp and default_program.initial_set_cure_temp.strip() else 0.0,
                final_set_cure_temp=float(default_program.final_set_cure_temp) if default_program.final_set_cure_temp and default_program.final_set_cure_temp.strip() else 0.0,
                serial_numbers=",".join(self.serial_numbers)
            )
            self.db.session.add(cycle)
            self.db.session.commit()
        except Exception as e:
            self.db.session.rollback()
            QtWidgets.QMessageBox.critical(self, "Database Error", f"Could not save cycle data: {e}")
            return

        QtWidgets.QMessageBox.information(self, "Success", "Cycle started successfully!")
        self.close()