from PyQt5 import QtWidgets
from datetime import datetime
from RaspPiReader.ui.program_selection_form import Ui_ProgramSelectionForm
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import CycleData, DefaultProgram, User, CycleSerialNumber
from RaspPiReader import pool
import logging

logger = logging.getLogger(__name__)

class ProgramSelectionFormHandler(QtWidgets.QWidget):
    def __init__(self, work_order, serial_numbers, parent=None):
        super(ProgramSelectionFormHandler, self).__init__(parent)
        self.ui = Ui_ProgramSelectionForm()
        self.ui.setupUi(self)
        self.work_order = work_order
        self.serial_numbers = serial_numbers  # list of (processed) serial numbers
        self.db = Database("sqlite:///local_database.db")
        
        # Set window title
        self.setWindowTitle(f"Select Program for Order: {work_order}")
        
        # Set label text if not in the UI
        if hasattr(self.ui, "programLabel"):
            self.ui.programLabel.setText("Select Program:")
        
        # Populate program items if needed
        self.populate_program_combo()
        
        # Set button text if not in the UI
        if hasattr(self.ui, "startCycleButton"):
            self.ui.startCycleButton.setText("Start Cycle")
        if hasattr(self.ui, "cancelButton"):
            self.ui.cancelButton.setText("Cancel")
        
        # Connect signals
        self.ui.startCycleButton.clicked.connect(self.start_cycle)
        self.ui.cancelButton.clicked.connect(self.close)
        self.ui.programComboBox.currentIndexChanged.connect(self.update_program_info)
        
        # Update program info initially
        self.update_program_info(self.ui.programComboBox.currentIndex())
    
    def populate_program_combo(self):
        """Ensure the combo box has the correct program items"""
        if self.ui.programComboBox.count() == 0:
            self.ui.programComboBox.addItem("Program 1")
            self.ui.programComboBox.addItem("Program 2")
            self.ui.programComboBox.addItem("Program 3")
            self.ui.programComboBox.addItem("Program 4")
    
    def update_program_info(self, index):
        program_index = index + 1
        current_user = pool.get("current_user")
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=current_user, program_number=program_index
        ).first()
        
        info_text = ""
        if default_program:
            # Format program info
            info_text = (
                f"<b>Program {program_index} Settings:</b><br>"
                f"Core Temperature: {default_program.core_temp_setpoint}°C<br>"
                f"Cool Down Temperature: {default_program.cool_down_temp}°C<br>"
                f"Temperature Ramp: {default_program.temp_ramp}°C/min<br>"
                f"Set Pressure: {default_program.set_pressure} kPa<br>"
                f"Maintain Vacuum: {default_program.maintain_vacuum} min"
            )
        else:
            info_text = f"<b>Program {program_index}</b><br>No default settings found for this program."
        
        if hasattr(self.ui, "programInfoLabel"):
            self.ui.programInfoLabel.setText(info_text)
    
    def start_cycle(self):
        program_index = self.ui.programComboBox.currentIndex() + 1
        current_user = pool.get("current_user")
        # Query DefaultProgram using current username and selected program index
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=current_user, program_number=program_index
        ).first()
        
        if not default_program:
            QtWidgets.QMessageBox.warning(
                self, "Warning", f"No default program found for Program {program_index}"
            )
            return
        
        # Query the User record for the logged-in user
        user = self.db.session.query(User).filter_by(username=current_user).first()
        if not user:
            QtWidgets.QMessageBox.critical(self, "Database Error", "Logged-in user not found.")
            return

        try:
            # Explicitly convert numeric/default fields to the proper Python types:
            core_temp_setpoint = float(default_program.core_temp_setpoint)
            cool_down_temp = float(default_program.cool_down_temp)
            # Omit temp_ramp if CycleData does not support it
            set_pressure = float(default_program.set_pressure)
            # Convert maintain_vacuum to a boolean (if stored as a numeric string such as "233")
            maintain_vacuum = bool(int(default_program.maintain_vacuum))
            initial_set_cure_temp = float(default_program.initial_set_cure_temp)
            final_set_cure_temp = float(default_program.final_set_cure_temp)
            
            # Create the cycle record using only supported fields
            new_cycle = CycleData(
                order_id=self.work_order,
                quantity=len(self.serial_numbers),
                core_temp_setpoint=core_temp_setpoint,
                cool_down_temp=cool_down_temp,
                set_pressure=set_pressure,
                maintain_vacuum=maintain_vacuum,
                initial_set_cure_temp=initial_set_cure_temp,
                final_set_cure_temp=final_set_cure_temp
            )
            new_cycle.user = user
            self.db.session.add(new_cycle)
            self.db.session.commit()
            self.cycle_record = new_cycle
            
            # Save individual serial numbers into the normalized table
            for sn in self.serial_numbers:
                if sn.strip():
                    record = CycleSerialNumber(cycle_id=new_cycle.id, serial_number=sn.strip())
                    self.db.session.add(record)
            self.db.session.commit()
            
            logger.info(f"New cycle created: Order {self.work_order}, Program {program_index}, {len(self.serial_numbers)} serial numbers")
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Database error creating cycle: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Database Error", f"Could not save cycle data: {str(e)}"
            )
            return

        QtWidgets.QMessageBox.information(self, "Success", "Cycle started successfully!")
        self.close()