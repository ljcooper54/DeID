# Copyright 2025 H2so4 Consulting LLC

import os
from typing import List
from datetime import datetime, date
from PySide6 import QtWidgets, QtCore
from .controllers import AppController


class MainWindow(QtWidgets.QMainWindow):
    # MainWindow: main desktop UI after login. Manages project selection, file list with status,
    # obscuring/restoring flows, and global/project sensitive-name lists.

    def __init__(self, controller: AppController):
        # __init__: build widgets, wire handlers, sync initial UI from controller.
        super().__init__()
        self.controller = controller

        self.setWindowTitle("Deid - H2so4 Consulting LLC")
        self.resize(1100, 700)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        main_v = QtWidgets.QVBoxLayout(central)

        # ===== Project selection row =====
        project_row = QtWidgets.QHBoxLayout()
        self.project_combo = QtWidgets.QComboBox()
        self.project_new_btn = QtWidgets.QPushButton("New Project...")

        project_row.addWidget(QtWidgets.QLabel("Project:"))
        project_row.addWidget(self.project_combo, 1)
        project_row.addWidget(self.project_new_btn)

        main_v.addLayout(project_row)

        # ===== Split view =====
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_v.addWidget(splitter, 1)

        # ---------- LEFT PANE ----------
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)

        left_layout.addWidget(QtWidgets.QLabel("Files in Project"))

        self.files_table = QtWidgets.QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["File Name", "Last Used", "Obscured"])
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.files_table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.files_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        left_layout.addWidget(self.files_table, 1)

        file_btn_row = QtWidgets.QHBoxLayout()
        self.btn_add_files = QtWidgets.QPushButton("Add Files...")
        self.btn_obscure = QtWidgets.QPushButton("Obscure (Selected / Pick)...")
        self.btn_restore = QtWidgets.QPushButton("Restore (Selected / Pick)...")

        file_btn_row.addWidget(self.btn_add_files)
        file_btn_row.addWidget(self.btn_obscure)
        file_btn_row.addWidget(self.btn_restore)
        file_btn_row.addStretch()
        left_layout.addLayout(file_btn_row)

        splitter.addWidget(left_widget)

        # ---------- RIGHT PANE ----------
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)

        global_group = QtWidgets.QGroupBox("My Global Sensitive Names (All Projects)")
        global_layout = QtWidgets.QVBoxLayout(global_group)

        self.global_list = QtWidgets.QListWidget()
        global_layout.addWidget(self.global_list)

        global_btn_row = QtWidgets.QHBoxLayout()
        self.btn_global_add = QtWidgets.QPushButton("Add...")
        self.btn_global_delete = QtWidgets.QPushButton("Delete")
        self.btn_global_import = QtWidgets.QPushButton("Import File...")
        global_btn_row.addWidget(self.btn_global_add)
        global_btn_row.addWidget(self.btn_global_delete)
        global_btn_row.addWidget(self.btn_global_import)
        global_btn_row.addStretch()
        global_layout.addLayout(global_btn_row)

        project_group = QtWidgets.QGroupBox("Project-Specific Sensitive Names")
        project_layout = QtWidgets.QVBoxLayout(project_group)

        self.project_list = QtWidgets.QListWidget()
        project_layout.addWidget(self.project_list)

        project_btn_row = QtWidgets.QHBoxLayout()
        self.btn_proj_add = QtWidgets.QPushButton("Add...")
        self.btn_proj_delete = QtWidgets.QPushButton("Delete")
        self.btn_proj_import = QtWidgets.QPushButton("Import File...")
        project_btn_row.addWidget(self.btn_proj_add)
        project_btn_row.addWidget(self.btn_proj_delete)
        project_btn_row.addWidget(self.btn_proj_import)
        project_btn_row.addStretch()
        project_layout.addLayout(project_btn_row)

        right_layout.addWidget(global_group)
        right_layout.addWidget(project_group)
        right_layout.addStretch()

        splitter.addWidget(right_widget)

        # ===== Activity log =====
        main_v.addWidget(QtWidgets.QLabel("Activity Log"))
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(160)
        main_v.addWidget(self.log_box)

        # Status bar copyright
        self.statusBar().showMessage("© 2025 H2so4 Consulting LLC — All Rights Reserved")

        # ----- Wire signals -----
        self.project_new_btn.clicked.connect(self._on_new_project)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)

        self.btn_add_files.clicked.connect(self._on_add_files)
        self.btn_obscure.clicked.connect(self._on_obscure_file)
        self.btn_restore.clicked.connect(self._on_restore_file)

        self.btn_global_add.clicked.connect(self._on_global_add)
        self.btn_global_delete.clicked.connect(self._on_global_delete)
        self.btn_global_import.clicked.connect(self._on_global_import)

        self.btn_proj_add.clicked.connect(self._on_project_add)
        self.btn_proj_delete.clicked.connect(self._on_project_delete)
        self.btn_proj_import.clicked.connect(self._on_project_import)

        # Initial sync
        self._refresh_projects()
        self._refresh_names_lists()
        self._refresh_files_table()
        # __init__  # MainWindow.__init__

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_selected_file_paths(self) -> List[str]:
        # _get_selected_file_paths: return the "File Name" column of selected rows.
        paths: List[str] = []
        for idx in self.files_table.selectionModel().selectedRows():
            row = idx.row()
            item = self.files_table.item(row, 0)
            if item:
                paths.append(item.text())
        # end for
        return paths
        # _get_selected_file_paths  # MainWindow._get_selected_file_paths

    def _format_last_used(self, iso_timestamp: str) -> str:
        # _format_last_used: convert an ISO timestamp from DB to a friendly display string.
        # Rules:
        #   - If it's today (same date), show: "Today, 11:12 AM"
        #   - Otherwise: "M/D/YYYY, 5:12 PM"
        if not iso_timestamp:
            return ""

        try:
            dt = datetime.fromisoformat(iso_timestamp)
        except Exception:
            # if for some reason it's not ISO, just show raw
            return iso_timestamp

        today = date.today()
        if dt.date() == today:
            return dt.strftime("Today, %-I:%M %p") if os.name != "nt" else dt.strftime("Today, %I:%M %p").lstrip("0")
        else:
            # Windows strftime doesn't support %-I, so we strip leading zero manually
            stamp = dt.strftime("%-m/%-d/%Y, %-I:%M %p") if os.name != "nt" else dt.strftime("%m/%d/%Y, %I:%M %p")
            # on Windows (os.name == "nt"), %m and %d are zero-padded, so trim them:
            if os.name == "nt":
                # "08/04/2025, 01:05 PM" -> "8/4/2025, 1:05 PM"
                mm, rest = stamp.split("/", 1)
                mm = mm.lstrip("0")
                dd, rest2 = rest.split("/", 1)
                dd = dd.lstrip("0")
                rest_fixed = rest2
                # rest2 now looks like "2025, 01:05 PM"
                yyyy, timepart = rest2.split(",", 1)
                # fix hour
                timepart = timepart.strip()
                if timepart[0] == "0":
                    timepart = timepart[1:]
                stamp = f"{mm}/{dd}/{yyyy}, {timepart}"
            return stamp
        # _format_last_used  # MainWindow._format_last_used

    def _refresh_projects(self):
        # _refresh_projects: reload combo box from controller, sync to active project.
        self.project_combo.blockSignals(True)
        self.project_combo.clear()

        projects = []
        try:
            projects = self.controller.list_projects()
        except Exception as e:
            self._append_log(f"[ERR] list_projects failed: {e}")
            projects = []

        active_pid = self.controller.get_current_project_id()
        active_index = -1

        for i, row in enumerate(projects):
            pid = row["id"]
            pname = row["name"]
            self.project_combo.addItem(pname, pid)
            if active_pid is not None and pid == active_pid:
                active_index = i
        # end for

        if active_index >= 0:
            self.project_combo.setCurrentIndex(active_index)
        else:
            if projects:
                first_pid = projects[0]["id"]
                try:
                    self.controller.select_project(int(first_pid))
                    self.project_combo.setCurrentIndex(0)
                    self._append_log(f"[OK] Defaulted to first project id {first_pid}")
                except Exception as e:
                    self._append_log(f"[ERR] auto-select project failed: {e}")

        self.project_combo.blockSignals(False)
        # _refresh_projects  # MainWindow._refresh_projects

    def _refresh_files_table(self):
        # _refresh_files_table: repopulate the file table from controller.list_project_files().
        self.files_table.setRowCount(0)

        pid = self.controller.get_current_project_id()
        if pid is None:
            return

        try:
            rows = self.controller.list_project_files()
        except Exception as e:
            self._append_log(f"[ERR] list_project_files failed: {e}")
            return

        self.files_table.setRowCount(len(rows))

        for r_i, row in enumerate(rows):
            # Column 0: File Name (display_name)
            display_name = row["display_name"]

            # Column 1: Last Used (friendly timestamp)
            raw_last_used = row["last_used_at"]
            friendly_last_used = self._format_last_used(raw_last_used)

            # Column 2: Obscured (last_obscured_path or blank)
            obscured_path = row["last_obscured_path"] if "last_obscured_path" in row.keys() else None
            obscured_display = obscured_path if obscured_path else ""

            self.files_table.setItem(
                r_i, 0, QtWidgets.QTableWidgetItem(display_name)
            )
            self.files_table.setItem(
                r_i, 1, QtWidgets.QTableWidgetItem(friendly_last_used)
            )
            self.files_table.setItem(
                r_i, 2, QtWidgets.QTableWidgetItem(obscured_display)
            )
        # end for

        self.files_table.resizeColumnsToContents()
        # _refresh_files_table  # MainWindow._refresh_files_table

    def _refresh_names_lists(self):
        # _refresh_names_lists: reload user-global and project-scoped sensitive names.
        self.global_list.clear()
        self.project_list.clear()

        try:
            gnames = self.controller.list_user_names()
            for n in gnames:
                self.global_list.addItem(n)
        except Exception as e:
            self._append_log(f"[ERR] list_user_names failed: {e}")

        pid = self.controller.get_current_project_id()
        if pid is not None:
            try:
                pnames = self.controller.list_project_names()
                for n in pnames:
                    self.project_list.addItem(n)
            except Exception as e:
                self._append_log(f"[ERR] list_project_names failed: {e}")
        # _refresh_names_lists  # MainWindow._refresh_names_lists

    def _append_log(self, msg: str):
        # _append_log: append a message to the bottom log.
        self.log_box.appendPlainText(msg)
        # _append_log  # MainWindow._append_log

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_new_project(self):
        # _on_new_project: prompt for project name, create/select it, refresh UI.
        pname, ok = QtWidgets.QInputDialog.getText(
            self,
            "New Project",
            "Project Name:"
        )
        if not ok or not pname.strip():
            return

        try:
            pid = self.controller.create_project(pname.strip(), notes="")
            self._append_log(f"[OK] Created project '{pname.strip()}' (id {pid})")
        except Exception as e:
            self._append_log(f"[ERR] create_project failed: {e}")
            return

        self._refresh_projects()
        self._refresh_names_lists()
        self._refresh_files_table()
        # _on_new_project  # MainWindow._on_new_project

    def _on_project_changed(self, index: int):
        # _on_project_changed: user picked a different project, so update controller and refresh.
        if index < 0:
            return
        pid = self.project_combo.itemData(index)
        if pid is None:
            return

        try:
            self.controller.select_project(int(pid))
            self._append_log(f"[OK] Switched to project id {pid}")
        except Exception as e:
            self._append_log(f"[ERR] select_project failed: {e}")
            return

        self._refresh_names_lists()
        self._refresh_files_table()
        # _on_project_changed  # MainWindow._on_project_changed

    def _on_add_files(self):
        # _on_add_files: let user attach one or more source files to this project.
        dlg = QtWidgets.QFileDialog(self, "Add Files to Project")
        dlg.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        dlg.setNameFilter(
            "All Supported (*.txt *.docx *.xlsx *.pptx *.pdf);;"
            "Text (*.txt);;Word (*.docx);;Excel (*.xlsx);;PowerPoint (*.pptx);;PDF (*.pdf);;All Files (*.*)"
        )

        if not dlg.exec():
            return

        file_paths = dlg.selectedFiles()
        if not file_paths:
            return

        try:
            self.controller.add_files_to_current_project(file_paths)
            self._append_log(f"[OK] Added {len(file_paths)} file(s) to project.")
            self._refresh_files_table()
        except Exception as e:
            self._append_log(f"[ERR] add_files_to_current_project failed: {e}")
        # _on_add_files  # MainWindow._on_add_files

    def _on_obscure_file(self):
        # _on_obscure_file: if rows are selected, obscure those files. Otherwise prompt.
        file_paths = self._get_selected_file_paths()

        if not file_paths:
            fpaths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self,
                "Select file(s) to obscure",
                "",
                "All Supported (*.txt *.docx *.xlsx *.pptx *.pdf);;"
                "Text (*.txt);;Word (*.docx);;Excel (*.xlsx);;PowerPoint (*.pptx);;PDF (*.pdf);;All Files (*.*)"
            )
            file_paths = fpaths

        if not file_paths:
            return

        try:
            outpaths = self.controller.obscure_files(file_paths)
            for op in outpaths:
                self._append_log(f"[OK] Obscured -> {op}")
            self._refresh_files_table()
        except Exception as e:
            self._append_log(f"[ERR] obscure_files failed: {e}")
        # _on_obscure_file  # MainWindow._on_obscure_file

    def _on_restore_file(self):
        # _on_restore_file: if rows are selected, try to restore those.
        # Otherwise prompt for obscured file(s).
        file_paths = self._get_selected_file_paths()

        if not file_paths:
            fpaths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self,
                "Select obscured file(s) to restore",
                "",
                "Text (*.txt *.obscured.txt *.restored.txt);;All Files (*.*)"
            )
            file_paths = fpaths

        if not file_paths:
            return

        try:
            outpaths = self.controller.restore_files(file_paths)
            for op in outpaths:
                self._append_log(f"[OK] Restored -> {op}")
        except Exception as e:
            self._append_log(f"[ERR] restore_files failed: {e}")
        # _on_restore_file  # MainWindow._on_restore_file

    def _on_global_add(self):
        # _on_global_add: prompt and add one new global forced-redaction string.
        name_text, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Global Sensitive Name",
            "Name or identifier to always redact in ALL projects:"
        )
        if not ok or not name_text.strip():
            return

        try:
            self.controller.import_user_names_list_from_values([name_text.strip()])
            self._append_log(f"[OK] Added global sensitive name '{name_text.strip()}'")
            self._refresh_names_lists()
        except Exception as e:
            self._append_log(f"[ERR] add global name failed: {e}")
        # _on_global_add  # MainWindow._on_global_add

    def _on_global_delete(self):
        # _on_global_delete: delete the selected global forced-redaction string.
        item = self.global_list.currentItem()
        if not item:
            return
        name_text = item.text()

        try:
            self.controller.delete_user_name(name_text)
            self._append_log(f"[OK] Deleted global sensitive name '{name_text}'")
            self._refresh_names_lists()
        except Exception as e:
            self._append_log(f"[ERR] delete global name failed: {e}")
        # _on_global_delete  # MainWindow._on_global_delete

    def _on_global_import(self):
        # _on_global_import: bulk import newline-delimited global names.
        fpath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Global Names",
            "",
            "Text Files (*.txt);;All Files (*.*)"
        )
        if not fpath:
            return

        try:
            self.controller.import_user_names_list(fpath)
            self._append_log(f"[OK] Imported global names from {fpath}")
            self._refresh_names_lists()
        except Exception as e:
            self._append_log(f"[ERR] import global names failed: {e}")
        # _on_global_import  # MainWindow._on_global_import

    def _on_project_add(self):
        # _on_project_add: prompt and add one project-only forced-redaction string.
        name_text, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Project Sensitive Name",
            "Name or identifier to always redact ONLY in this project:"
        )
        if not ok or not name_text.strip():
            return

        try:
            self.controller.import_project_names_list_from_values([name_text.strip()])
            self._append_log(f"[OK] Added project sensitive name '{name_text.strip()}'")
            self._refresh_names_lists()
        except Exception as e:
            self._append_log(f"[ERR] add project name failed: {e}")
        # _on_project_add  # MainWindow._on_project_add

    def _on_project_delete(self):
        # _on_project_delete: delete the selected project-only forced-redaction string.
        item = self.project_list.currentItem()
        if not item:
            return
        name_text = item.text()

        try:
            self.controller.delete_project_name(name_text)
            self._append_log(f"[OK] Deleted project sensitive name '{name_text}'")
            self._refresh_names_lists()
        except Exception as e:
            self._append_log(f"[ERR] delete project name failed: {e}")
        # _on_project_delete  # MainWindow._on_project_delete

    def _on_project_import(self):
        # _on_project_import: bulk import newline-delimited project names.
        fpath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Project Names",
            "",
            "Text Files (*.txt);;All Files (*.*)"
        )
        if not fpath:
            return

        try:
            self.controller.import_project_names_list(fpath)
            self._append_log(f"[OK] Imported project names from {fpath}")
            self._refresh_names_lists()
        except Exception as e:
            self._append_log(f"[ERR] import project names failed: {e}")
        # _on_project_import  # MainWindow._on_project_import

# MainWindow
