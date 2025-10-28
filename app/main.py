# Copyright 2025 H2so4 Consulting LLC

# Copyright 2025 H2so4 Consulting LLC

import sys
from PySide6 import QtWidgets
from app.controllers import AppController
from app.ui_login import LoginDialog
from app.ui_main import MainWindow
import os


def main():
    # main: entry point for the desktop app. Handles login then opens main window.
    app = QtWidgets.QApplication(sys.argv)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "deid_local.db")
    controller = AppController(db_path=db_path)

    # Show login dialog
    login = LoginDialog(controller)
    result = login.exec()
    if result != QtWidgets.QDialog.Accepted:
        # user canceled / closed login dialog
        return

    # Show main window
    win = MainWindow(controller)
    win.show()

    sys.exit(app.exec())
    # main  # main


if __name__ == "__main__":
    main()
    # __main__ guard  # __main__ guard
