from PyQt5 import QtWidgets
from RaspPiReader.libs.database import Database
from RaspPiReader.libs.models import Alarm
from RaspPiReader.ui.alarm_settings_form import AlarmSettingsForm

class AlarmSettingsFormHandler(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AlarmSettingsFormHandler, self).__init__(parent)
        self.form = AlarmSettingsForm(self)
        self.db = Database("sqlite:///local_database.db")
        self.load_alarms()
        # Connect buttons to their actions.
        self.form.addButton.clicked.connect(self.add_alarm)
        self.form.editButton.clicked.connect(self.edit_alarm)
        self.form.removeButton.clicked.connect(self.remove_alarm)
        self.form.exec_()

    def load_alarms(self):
        alarms = self.db.session.query(Alarm).all()
        table = self.form.tableWidget
        table.setRowCount(len(alarms))
        for row, alarm in enumerate(alarms):
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(alarm.address)))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(alarm.alarm_text))
        table.resizeColumnsToContents()

    def add_alarm(self):
        address, ok = QtWidgets.QInputDialog.getText(self, "Add Alarm", "Enter Alarm Address:")
        if ok and address:
            text, ok2 = QtWidgets.QInputDialog.getText(self, "Add Alarm", "Enter Alarm Text:")
            if ok2 and text:
                new_alarm = Alarm(address=address, alarm_text=text)
                self.db.session.add(new_alarm)
                self.db.session.commit()
                self.load_alarms()

    def edit_alarm(self):
        table = self.form.tableWidget
        row = table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Edit Alarm", "Please select an alarm to edit.")
            return
        current_address = table.item(row, 0).text()
        current_text = table.item(row, 1).text()
        new_text, ok = QtWidgets.QInputDialog.getText(self, "Edit Alarm", "Modify Alarm Text:", text=current_text)
        if ok and new_text:
            alarm = self.db.session.query(Alarm).filter_by(address=current_address).first()
            if alarm:
                alarm.alarm_text = new_text
                self.db.session.commit()
                self.load_alarms()

    def remove_alarm(self):
        table = self.form.tableWidget
        row = table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Remove Alarm", "Please select an alarm to remove.")
            return
        address = table.item(row, 0).text()
        confirm = QtWidgets.QMessageBox.question(self, "Confirm Removal",
                                                 f"Remove alarm with address {address}?",
                                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm == QtWidgets.QMessageBox.Yes:
            alarm = self.db.session.query(Alarm).filter_by(address=address).first()
            if alarm:
                self.db.session.delete(alarm)
                self.db.session.commit()
                self.load_alarms()