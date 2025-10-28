# Copyright 2025 H2so4 Consulting LLC

from PySide6 import QtWidgets, QtCore


class LoginDialog(QtWidgets.QDialog):
    # LoginDialog: modal dialog that lets a user log in or create a new account.

    def __init__(self, controller, parent=None):
        # __init__: build username/password fields and login/create buttons.
        super().__init__(parent)
        self.controller = controller

        self.setWindowTitle("Deid Login")

        # Layout
        layout = QtWidgets.QVBoxLayout(self)

        # Username
        user_row = QtWidgets.QHBoxLayout()
        user_label = QtWidgets.QLabel("Username:")
        self.user_edit = QtWidgets.QLineEdit()
        user_row.addWidget(user_label)
        user_row.addWidget(self.user_edit)

        # Password
        pass_row = QtWidgets.QHBoxLayout()
        pass_label = QtWidgets.QLabel("Password:")
        self.pass_edit = QtWidgets.QLineEdit()
        self.pass_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        pass_row.addWidget(pass_label)
        pass_row.addWidget(self.pass_edit)

        # Status label (for errors)
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color: red;")

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.login_btn = QtWidgets.QPushButton("Login")
        self.create_btn = QtWidgets.QPushButton("Create User")
        btn_row.addStretch()
        btn_row.addWidget(self.login_btn)
        btn_row.addWidget(self.create_btn)

        layout.addLayout(user_row)
        layout.addLayout(pass_row)
        layout.addWidget(self.status_label)
        layout.addLayout(btn_row)

        # Wire signals
        self.login_btn.clicked.connect(self._on_login_clicked)
        self.create_btn.clicked.connect(self._on_create_clicked)
        # __init__  # LoginDialog.__init__

    def _on_login_clicked(self):
        # _on_login_clicked: try to login with provided username/password. If success, accept().
        username = self.user_edit.text().strip()
        password = self.pass_edit.text().strip()

        ok = self.controller.login(username, password)
        if not ok:
            self.status_label.setText("Login failed. Check credentials or create user.")
            return

        self.accept()
        # _on_login_clicked  # LoginDialog._on_login_clicked

    def _on_create_clicked(self):
        # _on_create_clicked: create a new user with provided username/password and log them in.
        username = self.user_edit.text().strip()
        password = self.pass_edit.text().strip()

        if not username or not password:
            self.status_label.setText("Username and password required.")
            return

        try:
            self.controller.create_user(username, password)
        except Exception as e:
            self.status_label.setText(f"Error creating user: {e}")
            return

        # successful create_user() already logs us in and sets controller._current_user_id
        self.accept()
        # _on_create_clicked  # LoginDialog._on_create_clicked

# LoginDialog
