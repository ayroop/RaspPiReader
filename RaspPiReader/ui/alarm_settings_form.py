from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox, QPushButton
from PyQt5.QtCore import Qt
import logging
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm, AlarmMapping

logger = logging.getLogger(__name__)

class AlarmSettingsForm(QDialog):
    def __init__(self, parent=None):
        super(AlarmSettingsForm, self).__init__(parent)
        self.setWindowTitle("Alarm Settings")
        self.setMinimumWidth(800)
        
        # Create main layout
        layout = QVBoxLayout(self)
        
        # Create table widget for alarms
        self.tableWidget = QtWidgets.QTableWidget()
        self.tableWidget.setColumnCount(4)
        self.tableWidget.setHorizontalHeaderLabels(["Channel", "Threshold Value", "Alarm Message", "Active"])
        self.tableWidget.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tableWidget)

        # Create button layout
        button_layout = QHBoxLayout()
        
        # Add buttons
        self.addButton = QPushButton("Add")
        self.editButton = QPushButton("Edit")
        self.removeButton = QPushButton("Remove")
        self.saveButton = QPushButton("Save")
        
        button_layout.addWidget(self.addButton)
        button_layout.addWidget(self.editButton)
        button_layout.addWidget(self.removeButton)
        button_layout.addWidget(self.saveButton)
        
        layout.addLayout(button_layout)
        
        # Set layout
        self.setLayout(layout)
        
        # Initialize database
        self.db = Database("sqlite:///local_database.db")
        
        # Connect button signals
        self.addButton.clicked.connect(self.add_alarm)
        self.editButton.clicked.connect(self.edit_alarm)
        self.removeButton.clicked.connect(self.remove_alarm)
        self.saveButton.clicked.connect(self.save_settings)
        
        # Load existing settings
        self.load_settings()
    
    def add_alarm(self):
        """Add a new alarm row to the table"""
        row = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row)
        
        # Add channel combo box
        channel_combo = QtWidgets.QComboBox()
        channel_combo.addItems([f"CH{i}" for i in range(1, 15)])
        self.tableWidget.setCellWidget(row, 0, channel_combo)
        
        # Add threshold spin box
        threshold_spin = QDoubleSpinBox()
        threshold_spin.setRange(-999999, 999999)
        threshold_spin.setDecimals(2)
        self.tableWidget.setCellWidget(row, 1, threshold_spin)
        
        # Add message line edit
        message_edit = QLineEdit()
        self.tableWidget.setCellWidget(row, 2, message_edit)
        
        # Add active checkbox
        active_check = QtWidgets.QCheckBox()
        active_check.setChecked(True)
        self.tableWidget.setCellWidget(row, 3, active_check)
    
    def edit_alarm(self):
        """Edit the selected alarm"""
        current_row = self.tableWidget.currentRow()
        if current_row >= 0:
            # Get current values
            channel = self.tableWidget.cellWidget(current_row, 0).currentText()
            threshold = self.tableWidget.cellWidget(current_row, 1).value()
            message = self.tableWidget.cellWidget(current_row, 2).text()
            active = self.tableWidget.cellWidget(current_row, 3).isChecked()
            
            # Create edit dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Edit Alarm")
            layout = QVBoxLayout(dialog)
            
            # Channel selection
            channel_layout = QHBoxLayout()
            channel_layout.addWidget(QLabel("Channel:"))
            channel_combo = QtWidgets.QComboBox()
            channel_combo.addItems([f"CH{i}" for i in range(1, 15)])
            channel_combo.setCurrentText(channel)
            channel_layout.addWidget(channel_combo)
            layout.addLayout(channel_layout)
            
            # Threshold value
            threshold_layout = QHBoxLayout()
            threshold_layout.addWidget(QLabel("Threshold:"))
            threshold_spin = QDoubleSpinBox()
            threshold_spin.setRange(-999999, 999999)
            threshold_spin.setDecimals(2)
            threshold_spin.setValue(threshold)
            threshold_layout.addWidget(threshold_spin)
            layout.addLayout(threshold_layout)
            
            # Message
            message_layout = QHBoxLayout()
            message_layout.addWidget(QLabel("Message:"))
            message_edit = QLineEdit()
            message_edit.setText(message)
            message_layout.addWidget(message_edit)
            layout.addLayout(message_layout)
            
            # Active checkbox
            active_check = QtWidgets.QCheckBox("Active")
            active_check.setChecked(active)
            layout.addWidget(active_check)
            
            # Buttons
            button_layout = QHBoxLayout()
            save_button = QPushButton("Save")
            cancel_button = QPushButton("Cancel")
            button_layout.addWidget(save_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            # Connect signals
            save_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)
            
            if dialog.exec_() == QDialog.Accepted:
                # Update table with new values
                self.tableWidget.cellWidget(current_row, 0).setCurrentText(channel_combo.currentText())
                self.tableWidget.cellWidget(current_row, 1).setValue(threshold_spin.value())
                self.tableWidget.cellWidget(current_row, 2).setText(message_edit.text())
                self.tableWidget.cellWidget(current_row, 3).setChecked(active_check.isChecked())
    
    def remove_alarm(self):
        """Remove the selected alarm"""
        current_row = self.tableWidget.currentRow()
        if current_row >= 0:
            self.tableWidget.removeRow(current_row)
    
    def load_settings(self):
        """Load existing alarm settings from database"""
        try:
            alarms = self.db.session.query(Alarm).all()
            self.tableWidget.setRowCount(len(alarms))
            
            for row, alarm in enumerate(alarms):
                # Channel
                channel_combo = QtWidgets.QComboBox()
                channel_combo.addItems([f"CH{i}" for i in range(1, 15)])
                channel_combo.setCurrentText(alarm.channel)
                self.tableWidget.setCellWidget(row, 0, channel_combo)
                
                # Threshold
                threshold_spin = QDoubleSpinBox()
                threshold_spin.setRange(-999999, 999999)
                threshold_spin.setDecimals(2)
                threshold_spin.setValue(alarm.threshold)
                self.tableWidget.setCellWidget(row, 1, threshold_spin)
                
                # Message
                message_edit = QLineEdit()
                message_edit.setText(alarm.alarm_text)
                self.tableWidget.setCellWidget(row, 2, message_edit)
                
                # Active
                active_check = QtWidgets.QCheckBox()
                active_check.setChecked(alarm.active)
                self.tableWidget.setCellWidget(row, 3, active_check)
            
            self.tableWidget.resizeColumnsToContents()
            
        except Exception as e:
            logger.error(f"Error loading alarm settings: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load alarm settings: {str(e)}")
    
    def save_settings(self):
        """Save alarm settings to database"""
        try:
            # Clear existing alarms
            self.db.session.query(Alarm).delete()
            
            # Save new alarms
            for row in range(self.tableWidget.rowCount()):
                channel = self.tableWidget.cellWidget(row, 0).currentText()
                threshold = self.tableWidget.cellWidget(row, 1).value()
                alarm_text = self.tableWidget.cellWidget(row, 2).text()
                active = self.tableWidget.cellWidget(row, 3).isChecked()
                
                # Validate required fields
                if not channel:
                    raise ValueError(f"Channel is required for row {row + 1}")
                if threshold is None:
                    raise ValueError(f"Threshold value is required for {channel}")
                if not alarm_text:
                    raise ValueError(f"Alarm message is required for {channel}")
                
                alarm = Alarm(
                    channel=channel,
                    threshold=threshold,
                    alarm_text=alarm_text,
                    active=active
                )
                self.db.session.add(alarm)
            
            # Commit changes
            self.db.session.commit()
            logger.info("Alarm settings saved successfully")
            QtWidgets.QMessageBox.information(self, "Success", "Alarm settings saved successfully")
            
        except ValueError as e:
            self.db.session.rollback()
            logger.error(f"Validation error saving alarm settings: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save alarm settings: {str(e)}")
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error saving alarm settings: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save alarm settings: {str(e)}")