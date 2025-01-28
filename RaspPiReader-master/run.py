import argparse
import sys

from PyQt5 import QtWidgets
from RaspPiReader import pool
from RaspPiReader.ui.main_form_handler import MainFormHandler


def Main():
    app = QtWidgets.QApplication(sys.argv)
    main_form = MainFormHandler()
    app.exec_()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', type=bool, default=False)
    parser.add_argument('--demo', type=bool, default=False)
    args = parser.parse_args()
    pool.set('debug', args.debug)
    pool.set('demo', args.demo)
    Main()

