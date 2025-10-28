# Copyright 2025 H2so4 Consulting LLC

import sqlite3
from datetime import datetime
from typing import Optional, List
import bcrypt
from .models import EntityCategory


class Persistence:
    # Persistence: thin SQLite data access layer for users, projects, mappings, project files,
    # pseudonym counters, forced-redaction names, and audit history.

    def __init__(self, db_path: str):
        # __init__: open SQLite connection, set row_factory, and ensure schema/migrations exist.
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        # __init__  # Persistence.__init__

    def _exec(self, sql: str, params: tuple = ()) -> None:
        # _exec: helper to execute a write query and commit.
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        # _exec  # Persistence._exec

    def _query_one(self, sql: str, params: tuple = ()):
        # _query_one: helper to fetch a single row.
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()
        # _query_one  # Persistence._query_one

    def _query_all(self, sql: str, params: tuple = ()):
        # _query_all: helper to fetch all rows.
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
        # _query_all  # Persistence._query_all

    def _init_schema(self) -> None:
        # _init_schema: create or migrate all necessary tables.

        # user_account: local auth + last_project_id we restore on login
        self._exec("""
        CREATE TABLE IF NOT EXISTS user_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_project_id INTEGER,
            FOREIGN KEY(last_project_id) REFERENCES project(id)
        );
        """)

        # try to backfill last_project_id for legacy DBs
        try:
            self._exec("ALTER TABLE user_account ADD COLUMN last_project_id INTEGER;")
        except Exception:
            pass

        # project: each belongs to one owner
        self._exec("""
        CREATE TABLE IF NOT EXISTS project (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            notes TEXT,
            UNIQUE(owner_user_id, name),
            FOREIGN KEY(owner_user_id) REFERENCES user_account(id)
        );
        """)

        # project_file: remembers which files are associated with each project
        # last_obscured_path is the most recent "Obscured_..." file we generated for that source file
        self._exec("""
        CREATE TABLE IF NOT EXISTS project_file (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            file_path_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            last_used_at TEXT NOT NULL,
            last_obscured_path TEXT,
            FOREIGN KEY(project_id) REFERENCES project(id)
        );
        """)

        # backfill columns for legacy DBs
        try:
            self._exec("ALTER TABLE project_file ADD COLUMN last_obscured_path TEXT;")
        except Exception:
            pass

        # entity_mapping: persistent, immutable mapping original_value -> pseudonym
        self._exec("""
        CREATE TABLE IF NOT EXISTS entity_mapping (
            id TEXT PRIMARY KEY,
            project_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            original_value TEXT NOT NULL,
            pseudonym TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(project_id, original_value),
            FOREIGN KEY(project_id) REFERENCES project(id)
        );
        """)

        # category_counter: tracks running counters per category per project
        self._exec("""
        CREATE TABLE IF NOT EXISTS category_counter (
            project_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            last_index INTEGER NOT NULL,
            PRIMARY KEY (project_id, category),
            FOREIGN KEY(project_id) REFERENCES project(id)
        );
        """)

        # replacement_history: audit trail of obscure runs
        self._exec("""
        CREATE TABLE IF NOT EXISTS replacement_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            input_hash TEXT NOT NULL,
            output_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES project(id)
        );
        """)

        # user_known_name: global forced-redaction names for a user
        self._exec("""
        CREATE TABLE IF NOT EXISTS user_known_name (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, name_text),
            FOREIGN KEY(user_id) REFERENCES user_account(id)
        );
        """)

        # project_known_name: project-specific forced-redaction names
        self._exec("""
        CREATE TABLE IF NOT EXISTS project_known_name (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(project_id, name_text),
            FOREIGN KEY(project_id) REFERENCES project(id)
        );
        """)
        # _init_schema  # Persistence._init_schema

    # ---------------------------------------------------------------------
    # USERS
    # ---------------------------------------------------------------------

    def create_user(self, username: str, password: str) -> int:
        # create_user: create a new user with hashed password, return user_id.
        now = datetime.now().isoformat()
        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        self._exec(
            "INSERT INTO user_account (username, password_hash, created_at, last_project_id) "
            "VALUES (?,?,?,NULL)",
            (username, pw_hash.decode("utf-8"), now),
        )
        row = self._query_one(
            "SELECT id FROM user_account WHERE username=?",
            (username,)
        )
        return int(row["id"])
        # create_user  # Persistence.create_user

    def validate_login(self, username: str, password: str) -> Optional[int]:
        # validate_login: check plaintext password vs stored bcrypt hash.
        row = self._query_one(
            "SELECT id, password_hash FROM user_account WHERE username=?",
            (username,)
        )
        if not row:
            return None

        stored_hash = row["password_hash"].encode("utf-8")
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return int(row["id"])
        return None
        # validate_login  # Persistence.validate_login

    def get_last_project_for_user(self, user_id: int) -> Optional[int]:
        # get_last_project_for_user: return the user's last active project_id, or None.
        row = self._query_one(
            "SELECT last_project_id FROM user_account WHERE id=?",
            (user_id,)
        )
        if not row:
            return None
        val = row["last_project_id"]
        if val is None:
            return None
        return int(val)
        # get_last_project_for_user  # Persistence.get_last_project_for_user

    def set_last_project_for_user(self, user_id: int, project_id: Optional[int]) -> None:
        # set_last_project_for_user: update the last_project_id for this user.
        self._exec(
            "UPDATE user_account SET last_project_id=? WHERE id=?",
            (project_id, user_id)
        )
        # set_last_project_for_user  # Persistence.set_last_project_for_user

    # ---------------------------------------------------------------------
    # PROJECTS
    # ---------------------------------------------------------------------

    def create_project(self, owner_user_id: int, name: str, notes: str = "") -> int:
        # create_project: insert a new project for this user, return its project_id.
        now = datetime.now().isoformat()
        self._exec(
            "INSERT INTO project (owner_user_id, name, created_at, notes) VALUES (?,?,?,?)",
            (owner_user_id, name, now, notes),
        )
        row = self._query_one(
            "SELECT id FROM project WHERE owner_user_id=? AND name=?",
            (owner_user_id, name),
        )
        return int(row["id"])
        # create_project  # Persistence.create_project

    def list_projects_for_user(self, owner_user_id: int) -> List[sqlite3.Row]:
        # list_projects_for_user: list all projects for a given user.
        return self._query_all(
            "SELECT * FROM project WHERE owner_user_id=? ORDER BY created_at ASC",
            (owner_user_id,)
        )
        # list_projects_for_user  # Persistence.list_projects_for_user

    def get_project_owner(self, project_id: int) -> int:
        # get_project_owner: return owner_user_id for this project.
        row = self._query_one(
            "SELECT owner_user_id FROM project WHERE id=?",
            (project_id,)
        )
        if not row:
            raise RuntimeError("Project not found.")
        return int(row["owner_user_id"])
        # get_project_owner  # Persistence.get_project_owner

    # ---------------------------------------------------------------------
    # PROJECT FILES
    # ---------------------------------------------------------------------

    def upsert_project_file(self,
                            project_id: int,
                            file_path_hash: str,
                            display_name: str,
                            obscured_path: Optional[str] = None) -> None:
        # upsert_project_file: insert/update a record for (project_id, file_path_hash).
        # We always update last_used_at to "now".
        # If obscured_path is given, we also track last_obscured_path.
        now = datetime.now().isoformat()

        row = self._query_one(
            "SELECT id FROM project_file WHERE project_id=? AND file_path_hash=?",
            (project_id, file_path_hash)
        )

        if row:
            if obscured_path is not None:
                self._exec(
                    "UPDATE project_file "
                    "SET last_used_at=?, display_name=?, last_obscured_path=? "
                    "WHERE id=?",
                    (now, display_name, obscured_path, row["id"])
                )
            else:
                self._exec(
                    "UPDATE project_file "
                    "SET last_used_at=?, display_name=? "
                    "WHERE id=?",
                    (now, display_name, row["id"])
                )
        else:
            self._exec(
                "INSERT INTO project_file "
                "(project_id, file_path_hash, display_name, last_used_at, last_obscured_path) "
                "VALUES (?,?,?,?,?)",
                (project_id, file_path_hash, display_name, now, obscured_path)
            )
        # upsert_project_file  # Persistence.upsert_project_file

    def update_project_file_after_obscure(self,
                                          project_id: int,
                                          source_display_name: str,
                                          source_hash: str,
                                          new_obscured_path: str) -> None:
        # update_project_file_after_obscure: after obscuring a file, record the path
        # to the obscured file + bump last_used_at.
        now = datetime.now().isoformat()
        row = self._query_one(
            "SELECT id FROM project_file WHERE project_id=? AND file_path_hash=?",
            (project_id, source_hash)
        )

        if row:
            self._exec(
                "UPDATE project_file "
                "SET last_used_at=?, last_obscured_path=?, display_name=? "
                "WHERE id=?",
                (now, new_obscured_path, source_display_name, row["id"])
            )
        else:
            # if somehow the file wasn't inserted yet, insert now
            self._exec(
                "INSERT INTO project_file "
                "(project_id, file_path_hash, display_name, last_used_at, last_obscured_path) "
                "VALUES (?,?,?,?,?)",
                (project_id, source_hash, source_display_name, now, new_obscured_path)
            )
        # update_project_file_after_obscure  # Persistence.update_project_file_after_obscure

    def list_project_files(self, project_id: int) -> List[sqlite3.Row]:
        # list_project_files: list all files associated with a project, newest activity first.
        return self._query_all(
            "SELECT * FROM project_file WHERE project_id=? ORDER BY last_used_at DESC",
            (project_id,)
        )
        # list_project_files  # Persistence.list_project_files

    # ---------------------------------------------------------------------
    # ENTITY MAPPING
    # ---------------------------------------------------------------------

    def get_mapping(self, project_id: int, original_value: str):
        # get_mapping: fetch mapping row if this project already has pseudonym for original_value.
        return self._query_one(
            "SELECT * FROM entity_mapping WHERE project_id=? AND original_value=?",
            (project_id, original_value)
        )
        # get_mapping  # Persistence.get_mapping

    def insert_mapping(self,
                       entity_id: str,
                       project_id: int,
                       category: EntityCategory,
                       original_value: str,
                       pseudonym: str) -> None:
        # insert_mapping: create a new mapping (original_value -> pseudonym) for this project.
        now = datetime.now().isoformat()
        self._exec(
            "INSERT INTO entity_mapping "
            "(id, project_id, category, original_value, pseudonym, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (entity_id, project_id, category.value, original_value, pseudonym, now)
        )
        # insert_mapping  # Persistence.insert_mapping

    def get_all_mappings_for_project(self, project_id: int):
        # get_all_mappings_for_project: return all mapping rows for restore.
        return self._query_all(
            "SELECT * FROM entity_mapping WHERE project_id=?",
            (project_id,)
        )
        # get_all_mappings_for_project  # Persistence.get_all_mappings_for_project

    # ---------------------------------------------------------------------
    # CATEGORY COUNTER
    # ---------------------------------------------------------------------

    def get_last_index(self, project_id: int, category: EntityCategory) -> int:
        # get_last_index: return last_index for this category in this project, default 0.
        row = self._query_one(
            "SELECT last_index FROM category_counter WHERE project_id=? AND category=?",
            (project_id, category.value)
        )
        if row:
            return int(row["last_index"])
        return 0
        # get_last_index  # Persistence.get_last_index

    def set_last_index(self, project_id: int,
                       category: EntityCategory,
                       new_index: int) -> None:
        # set_last_index: update or insert last_index for this category in this project.
        row = self._query_one(
            "SELECT last_index FROM category_counter WHERE project_id=? AND category=?",
            (project_id, category.value)
        )
        if row:
            self._exec(
                "UPDATE category_counter SET last_index=? WHERE project_id=? AND category=?",
                (new_index, project_id, category.value)
            )
        else:
            self._exec(
                "INSERT INTO category_counter (project_id, category, last_index) VALUES (?,?,?)",
                (project_id, category.value, new_index)
            )
        # set_last_index  # Persistence.set_last_index

    # ---------------------------------------------------------------------
    # HISTORY
    # ---------------------------------------------------------------------

    def record_history(self, project_id: int,
                       input_hash: str,
                       output_hash: str) -> None:
        # record_history: log an anonymization run for audit.
        now = datetime.now().isoformat()
        self._exec(
            "INSERT INTO replacement_history (project_id, input_hash, output_hash, timestamp) "
            "VALUES (?,?,?,?)",
            (project_id, input_hash, output_hash, now)
        )
        # record_history  # Persistence.record_history

    # ---------------------------------------------------------------------
    # USER / PROJECT FORCED NAMES
    # ---------------------------------------------------------------------

    def add_user_known_name(self, user_id: int, name_text: str) -> None:
        # add_user_known_name: add a string to this user's global always-redact list.
        now = datetime.now().isoformat()
        self._exec(
            "INSERT OR IGNORE INTO user_known_name (user_id, name_text, created_at) "
            "VALUES (?,?,?)",
            (user_id, name_text.strip(), now)
        )
        # add_user_known_name  # Persistence.add_user_known_name

    def list_user_known_names(self, user_id: int) -> List[str]:
        # list_user_known_names: return all user-global forced-redaction strings.
        rows = self._query_all(
            "SELECT name_text FROM user_known_name WHERE user_id=? "
            "ORDER BY name_text COLLATE NOCASE ASC",
            (user_id,)
        )
        return [r["name_text"] for r in rows]
        # list_user_known_names  # Persistence.list_user_known_names

    def delete_user_known_name(self, user_id: int, name_text: str) -> None:
        # delete_user_known_name: remove a string from user's global always-redact list.
        self._exec(
            "DELETE FROM user_known_name WHERE user_id=? AND name_text=?",
            (user_id, name_text)
        )
        # delete_user_known_name  # Persistence.delete_user_known_name

    def add_project_known_name(self, project_id: int, name_text: str) -> None:
        # add_project_known_name: add a string to this project's forced-redaction list.
        now = datetime.now().isoformat()
        self._exec(
            "INSERT OR IGNORE INTO project_known_name (project_id, name_text, created_at) "
            "VALUES (?,?,?)",
            (project_id, name_text.strip(), now)
        )
        # add_project_known_name  # Persistence.add_project_known_name

    def list_project_known_names(self, project_id: int) -> List[str]:
        # list_project_known_names: return all forced-redaction strings for this project.
        rows = self._query_all(
            "SELECT name_text FROM project_known_name WHERE project_id=? "
            "ORDER BY name_text COLLATE NOCASE ASC",
            (project_id,)
        )
        return [r["name_text"] for r in rows]
        # list_project_known_names  # Persistence.list_project_known_names

    def delete_project_known_name(self, project_id: int, name_text: str) -> None:
        # delete_project_known_name: remove a string from this project's forced-redaction list.
        self._exec(
            "DELETE FROM project_known_name WHERE project_id=? AND name_text=?",
            (project_id, name_text)
        )
        # delete_project_known_name  # Persistence.delete_project_known_name

# Persistence
