
from genericpath import isfile
from os import path, getenv, remove
from shutil import copy

from PyQt5 import QtCore, QtWidgets

from .google_auth_help_form import GoogleAuthHelpForm


class GoogleAuthForm(QtWidgets.QMainWindow):
    def setupUi(self, parent):
        self.form_parent = parent
        self.setObjectName("GoogleAuth")
        self.resize(482, 80)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setObjectName("label")
        self.horizontalLayout_2.addWidget(self.label)
        self.pathLineEdit = QtWidgets.QLineEdit(self.centralwidget)
        self.pathLineEdit.setObjectName("pathLineEdit")
        self.horizontalLayout_2.addWidget(self.pathLineEdit)
        self.browsePushButton = QtWidgets.QPushButton(self.centralwidget)
        self.browsePushButton.setObjectName("browsePushButton")
        self.horizontalLayout_2.addWidget(self.browsePushButton)
        self.gridLayout.addLayout(self.horizontalLayout_2, 0, 0, 1, 1)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.submitPushButton = QtWidgets.QPushButton(self.centralwidget)
        self.submitPushButton.setObjectName("submitPushButton")
        self.horizontalLayout.addWidget(self.submitPushButton)
        self.helpPushButton = QtWidgets.QPushButton(self.centralwidget)
        self.helpPushButton.setObjectName("helpPushButton")
        self.horizontalLayout.addWidget(self.helpPushButton)
        self.cancelPushButton = QtWidgets.QPushButton(self.centralwidget)
        self.cancelPushButton.setObjectName("cancelPushButton")
        self.horizontalLayout.addWidget(self.cancelPushButton)
        self.gridLayout.addLayout(self.horizontalLayout, 1, 0, 1, 1)
        spacerItem1 = QtWidgets.QSpacerItem(20, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout.addItem(spacerItem1, 2, 0, 1, 1)
        self.setCentralWidget(self.centralwidget)
        self.browsePushButton.clicked.connect(self.get_path)
        self.cancelPushButton.clicked.connect(self.close)
        self.submitPushButton.clicked.connect(self.save_file)

        self.helpPushButton.clicked.connect(self.show_help)
        self.retranslateUi()
        QtCore.QMetaObject.connectSlotsByName(self)

    def get_path(self):
        self.cred_path = QtWidgets.QFileDialog.\
            getOpenFileNames(self, "Select credentional file", QtCore.QDir.currentPath(), "JSON Files (*.json)")
        if self.cred_path:
            self.pathLineEdit.setText(self.cred_path[0][0])
        
        
    def show_help(self):
        self.help_form = GoogleAuthHelpForm()
        self.help_form.setupUi()
        self.help_form.show()

    def save_file(self):
        source_cred_path =  self.pathLineEdit.text()
        if source_cred_path and isfile(source_cred_path):
            cred_path = path.join(getenv('LOCALAPPDATA'), r"RasbPiReader\credentials")
            dest_cred_path = path.join(cred_path, 'google_drive.json')
            dest_token_path = path.join(cred_path, 'token.json')
            for f in [dest_token_path, dest_cred_path]:
                if path.exists(f):
                    remove(f)
            copy(source_cred_path, path.join(cred_path, 'google_drive.json'))

        self.close()

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate("GoogleAuth", "Google API credentials required"))
        self.label.setText(_translate("GoogleAuth", "Credential file path:"))
        self.browsePushButton.setText(_translate("GoogleAuth", "Browse"))
        self.submitPushButton.setText(_translate("GoogleAuth", "Submit"))
        self.helpPushButton.setText(_translate("GoogleAuth", "Help"))
        self.cancelPushButton.setText(_translate("GoogleAuth", "Cancel"))
