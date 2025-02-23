from PyQt5 import QtWidgets

class AlarmSettingsForm(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AlarmSettingsForm, self).__init__(parent)
        self.setWindowTitle("Alarm Management")
        self.resize(500, 400)
        self.setupUi()

    def setupUi(self):
        layout = QtWidgets.QVBoxLayout(self)
        # Table to display alarms with 2 columns: Address and Alarm Text
        self.tableWidget = QtWidgets.QTableWidget(self)
        self.tableWidget.setColumnCount(2)
        self.tableWidget.setHorizontalHeaderLabels(["Address", "Alarm Text"])
        layout.addWidget(self.tableWidget)

        # Buttons to add, edit, remove alarms
        btnLayout = QtWidgets.QHBoxLayout()
        self.addButton = QtWidgets.QPushButton("Add")
        self.editButton = QtWidgets.QPushButton("Edit")
        self.removeButton = QtWidgets.QPushButton("Remove")
        btnLayout.addWidget(self.addButton)
        btnLayout.addWidget(self.editButton)
        btnLayout.addWidget(self.removeButton)
        layout.addLayout(btnLayout)