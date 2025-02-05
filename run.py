# filepath: /c:/DEV/Python/PLC Integration/src1-main/src1-main/RaspPiReader-master/run.py
import argparse
import sys

from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui.login_form_handler import LoginFormHandler
from RaspPiReader.ui.main_form_handler import MainFormHandler

def Main():
    app = QtWidgets.QApplication(sys.argv)
    login_form = LoginFormHandler()
    login_form.show()
    app.exec_()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', type=bool, default=False)
    parser.add_argument('--demo', type=bool, default=False)
    args = parser.parse_args()
    pool.set('debug', args.debug)
    pool.set('demo', args.demo)
    Main()