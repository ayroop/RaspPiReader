from PyQt5 import QtWidgets
from datetime import datetime
from RaspPiReader.ui.program_selection_form import Ui_ProgramSelectionForm
from RaspPiReader.ui.start_cycle_form_handler import StartCycleFormHandler
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
        
        # Set window title and initial/minimum size to ensure a proper appearance.
        self.setWindowTitle(f"Select Program for Order: {work_order}")
        self.resize(800, 600)
        self.setMinimumSize(800, 600)
        
        # Set an overall stylesheet to increase font sizes.
        self.setStyleSheet("QWidget { font-size: 16px; }")
        
        # Set label text if not already set in the UI.
        if hasattr(self.ui, "programLabel"):
            self.ui.programLabel.setText("Select Program:")
        
        # Populate program items if needed.
        self.populate_program_combo()
        
        # Set button text if not provided in the UI.
        if hasattr(self.ui, "startCycleButton"):
            self.ui.startCycleButton.setText("Start Cycle")
        if hasattr(self.ui, "cancelButton"):
            self.ui.cancelButton.setText("Cancel")
        
        # Connect signals.
        self.ui.startCycleButton.clicked.connect(self.start_cycle)
        self.ui.cancelButton.clicked.connect(self.close)
        self.ui.programComboBox.currentIndexChanged.connect(self.update_program_info)
        
        # Update program info initially.
        self.update_program_info(self.ui.programComboBox.currentIndex())
    
    def populate_program_combo(self):
        """Ensure the combo box has the correct program items."""
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
        
        # Build an HTML table for better presentation.
        if default_program:
            info_text = f"""
            <div style="font-family:Arial; font-size:16px; margin:10px;">
                <h3 style="margin-bottom:10px;">Program {program_index} Settings</h3>
                <table border="1" cellspacing="0" cellpadding="4" style="border-collapse: collapse; width:100%;">
                    <tr style="background-color:#f0f0f0;">
                        <th align="left">Field</th>
                        <th align="left">Value</th>
                    </tr>
                    <tr><td>Size</td><td>{default_program.size or 'N/A'}</td></tr>
                    <tr><td>Cycle Location</td><td>{default_program.cycle_location or 'N/A'}</td></tr>
                    <tr><td>Dwell Time</td><td>{default_program.dwell_time or 'N/A'}</td></tr>
                    <tr><td>Core Temperature</td><td>{default_program.core_temp_setpoint or 'N/A'}°C</td></tr>
                    <tr><td>Cool Down Temperature</td><td>{default_program.cool_down_temp or 'N/A'}°C</td></tr>
                    <tr><td>Temperature Ramp</td><td>{default_program.temp_ramp or 'N/A'}°C/min</td></tr>
                    <tr><td>Set Pressure</td><td>{default_program.set_pressure or 'N/A'} kPa</td></tr>
                    <tr><td>Maintain Vacuum</td><td>{default_program.maintain_vacuum or 'N/A'} %</td></tr>
                    <tr><td>Initial Set Cure Temp</td><td>{default_program.initial_set_cure_temp or 'N/A'}°C</td></tr>
                    <tr><td>Final Set Cure Temp</td><td>{default_program.final_set_cure_temp or 'N/A'}°C</td></tr>
                </table>
            </div>
            """
        else:
            info_text = f"""
            <div style="font-family:Arial; font-size:16px; margin:10px;">
                <h3>Program {program_index}</h3>
                <p>No default settings found for this program.</p>
            </div>
            """
        # Ensure the programInfoLabel widget is updated within the method.
        if hasattr(self.ui, "programInfoLabel"):
            self.ui.programInfoLabel.setMinimumWidth(500)
            self.ui.programInfoLabel.setMinimumHeight(400)
            self.ui.programInfoLabel.setText(info_text)
    
    def start_cycle(self):
        logger.info("Start Cycle button pressed")
        program_index = self.ui.programComboBox.currentIndex() + 1
        current_user = pool.get("current_user")
        
        # Query DefaultProgram record for current user and program_index (unchanged logic)
        default_program = self.db.session.query(DefaultProgram).filter_by(
            username=current_user, program_number=program_index
        ).first()
        if not default_program:
            QtWidgets.QMessageBox.warning(
                self, "Warning", f"No default program found for Program {program_index}"
            )
            return
        
        user = self.db.session.query(User).filter_by(username=current_user).first()
        if not user:
            QtWidgets.QMessageBox.critical(self, "Database Error", "Logged-in user not found.")
            return

        try:
            # Convert fields as needed.
            core_temp_setpoint = float(default_program.core_temp_setpoint)
            cool_down_temp = float(default_program.cool_down_temp)
            set_pressure = float(default_program.set_pressure)
            maintain_vacuum = bool(int(default_program.maintain_vacuum))
            initial_set_cure_temp = float(default_program.initial_set_cure_temp)
            final_set_cure_temp = float(default_program.final_set_cure_temp)
            
            # Create new cycle record with supported fields.
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
            
            # Save each serial number
            for sn in self.serial_numbers:
                sn = sn.strip()
                if sn:
                    existing = self.db.session.query(CycleSerialNumber).filter_by(serial_number=sn).first()
                    if existing:
                        logger.warning(f"Serial number {sn} already exists. Skipping insertion.")
                        continue
                    record = CycleSerialNumber(cycle_id=new_cycle.id, serial_number=sn)
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
        
        # Retrieve the active StartCycleFormHandler instance from the pool and start the cycle.
        start_cycle_form = pool.get("start_cycle_form")
        if start_cycle_form:
            start_cycle_form.start_cycle()
        
        QtWidgets.QMessageBox.information(self, "Success", "Cycle started successfully!")
        self.close()