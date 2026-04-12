"""
File Integrity Checker for WHAT-TO-EAT-AGENT
This module provides functionality to check file integrity for incremental ingestion.
"""
import hashlib
import sqlite3
import os
from datetime import datetime
from typing import Dict, Optional


class FileIntegrityChecker:
    """Class responsible for checking file integrity to support incremental ingestion."""

    def __init__(self, db_path: str = "data/db/integrity.db"):
        """
        Initialize the FileIntegrityChecker.

        Args:
            db_path: Path to the SQLite database for storing file hashes
        """
        self.db_path = db_path

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)

        # Initialize the database
        self._init_db()

    def _init_db(self):
        """Initialize the integrity database with required schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create file_hashes table to store file integrity information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_hashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                modified_time REAL NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create indexes for faster lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON file_hashes(file_path)')

        conn.commit()
        conn.close()

    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hash of the file content
        """
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def should_process(self, file_path: str) -> bool:
        """
        Determine if a file should be processed based on its integrity status.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the file should be processed (new, modified, or missing from records)
        """
        if not os.path.exists(file_path):
            return False  # File doesn't exist

        # Get current file information
        current_hash = self._calculate_file_hash(file_path)
        current_size = os.path.getsize(file_path)
        current_modified = os.path.getmtime(file_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if file is already recorded in the database
        cursor.execute(
            "SELECT file_hash, file_size, modified_time FROM file_hashes WHERE file_path = ?",
            (file_path,)
        )
        result = cursor.fetchone()

        conn.close()

        if result is None:
            # File is not in the database, so it's new
            return True

        stored_hash, stored_size, stored_modified = result

        # Check if the file has been modified since last processing
        if (current_hash != stored_hash or
            current_size != stored_size or
            abs(current_modified - stored_modified) > 1):  # 1 second tolerance for modified time
            return True

        # File hasn't changed, no need to process
        return False

    def record_processed(self, file_path: str) -> bool:
        """
        Record that a file has been processed successfully.

        Args:
            file_path: Path to the file that was processed

        Returns:
            True if recording was successful
        """
        if not os.path.exists(file_path):
            return False

        # Get file information
        file_hash = self._calculate_file_hash(file_path)
        file_size = os.path.getsize(file_path)
        modified_time = os.path.getmtime(file_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Insert or update the file record
            cursor.execute('''
                INSERT OR REPLACE INTO file_hashes
                (file_path, file_hash, file_size, modified_time, processed_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (file_path, file_hash, file_size, modified_time, datetime.now()))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error recording processed file: {e}")
            conn.close()
            return False

    def remove_record(self, file_path: str) -> bool:
        """
        Remove a file record from the integrity database.

        Args:
            file_path: Path to the file to remove from records

        Returns:
            True if removal was successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM file_hashes WHERE file_path = ?", (file_path,))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing file record: {e}")
            conn.close()
            return False

    def clear_all_records(self) -> bool:
        """
        Clear all file records from the integrity database.

        Returns:
            True if clearing was successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM file_hashes")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error clearing all records: {e}")
            conn.close()
            return False

    def get_stored_files(self) -> list:
        """
        Get a list of all files currently stored in the integrity database.

        Returns:
            List of file paths that have been processed
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT file_path FROM file_hashes ORDER BY processed_at DESC")
        results = [row[0] for row in cursor.fetchall()]

        conn.close()
        return results