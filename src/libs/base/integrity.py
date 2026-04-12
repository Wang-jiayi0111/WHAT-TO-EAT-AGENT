"""
Database Integrity Checker for WHAT-TO-EAT-AGENT
This module provides functionality to manage and validate database schemas
for user profiles, inventory tracking, and BM25 index databases.
"""

import os
import sqlite3
from typing import Dict, Any

class DatabaseIntegrityChecker:
    """Class responsible for managing database schemas and integrity checks."""

    def __init__(self):
        """Initialize the DatabaseIntegrityChecker."""
        self.db_paths = {
            'user_profiles': 'data/db/user_profiles.db',
            'inventory': 'data/db/inventory.db',
            'bm25_index': 'data/db/bm25_index.db'
        }

    def initialize_databases(self) -> Dict[str, bool]:
        """
        Initialize all required databases and create necessary tables.

        Returns:
            Dict[str, bool]: Status of initialization for each database
        """
        results = {}

        # Create data/db directory if it doesn't exist
        os.makedirs('data/db', exist_ok=True)

        # Initialize user profiles database
        results['user_profiles'] = self._initialize_user_profiles_db()

        # Initialize inventory database
        results['inventory'] = self._initialize_inventory_db()

        # Initialize BM25 index database
        results['bm25_index'] = self._initialize_bm25_index_db()

        return results

    def _initialize_user_profiles_db(self) -> bool:
        """Initialize user profiles database with required schema."""
        try:
            conn = sqlite3.connect(self.db_paths['user_profiles'])
            cursor = conn.cursor()

            # Create user_profiles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT,
                    dietary_restrictions TEXT,
                    preferred_cuisines TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON user_profiles(user_id)')

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error initializing user profiles DB: {e}")
            return False

    def _initialize_inventory_db(self) -> bool:
        """Initialize inventory database with required schema."""
        try:
            conn = sqlite3.connect(self.db_paths['inventory'])
            cursor = conn.cursor()

            # Create inventory table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    unit TEXT,
                    expiry_date DATE,
                    category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_item ON inventory(user_id, item_name)')

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error initializing inventory DB: {e}")
            return False

    def _initialize_bm25_index_db(self) -> bool:
        """Initialize BM25 index database with required schema."""
        try:
            conn = sqlite3.connect(self.db_paths['bm25_index'])
            cursor = conn.cursor()

            # Create bm25_index table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bm25_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_id ON bm25_index(doc_id)')

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error initializing BM25 index DB: {e}")
            return False

    def validate_database_integrity(self) -> Dict[str, Dict[str, Any]]:
        """
        Validate the integrity of all databases.

        Returns:
            Dict[str, Dict[str, Any]]: Validation results for each database
        """
        results = {}

        # Validate user profiles database
        results['user_profiles'] = self._validate_user_profiles_db()

        # Validate inventory database
        results['inventory'] = self._validate_inventory_db()

        # Validate BM25 index database
        results['bm25_index'] = self._validate_bm25_index_db()

        return results

    def _validate_user_profiles_db(self) -> Dict[str, Any]:
        """Validate user profiles database schema."""
        try:
            conn = sqlite3.connect(self.db_paths['user_profiles'])
            cursor = conn.cursor()

            # Check if table exists and has correct columns
            cursor.execute("PRAGMA table_info(user_profiles)")
            columns = cursor.fetchall()

            expected_columns = [
                ('id', 'INTEGER'),
                ('user_id', 'TEXT'),
                ('name', 'TEXT'),
                ('email', 'TEXT'),
                ('dietary_restrictions', 'TEXT'),
                ('preferred_cuisines', 'TEXT'),
                ('created_at', 'TIMESTAMP'),
                ('updated_at', 'TIMESTAMP')
            ]

            column_names = [col[1] for col in columns]
            missing_columns = []
            for expected_col in expected_columns:
                if expected_col[0] not in column_names:
                    missing_columns.append(expected_col[0])

            conn.close()
            return {
                'valid': len(missing_columns) == 0,
                'missing_columns': missing_columns,
                'columns_count': len(columns)
            }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }

    def _validate_inventory_db(self) -> Dict[str, Any]:
        """Validate inventory database schema."""
        try:
            conn = sqlite3.connect(self.db_paths['inventory'])
            cursor = conn.cursor()

            # Check if table exists and has correct columns
            cursor.execute("PRAGMA table_info(inventory)")
            columns = cursor.fetchall()

            expected_columns = [
                ('id', 'INTEGER'),
                ('user_id', 'TEXT'),
                ('item_name', 'TEXT'),
                ('quantity', 'REAL'),
                ('unit', 'TEXT'),
                ('expiry_date', 'DATE'),
                ('category', 'TEXT'),
                ('created_at', 'TIMESTAMP'),
                ('updated_at', 'TIMESTAMP')
            ]

            column_names = [col[1] for col in columns]
            missing_columns = []
            for expected_col in expected_columns:
                if expected_col[0] not in column_names:
                    missing_columns.append(expected_col[0])

            conn.close()
            return {
                'valid': len(missing_columns) == 0,
                'missing_columns': missing_columns,
                'columns_count': len(columns)
            }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }

    def _validate_bm25_index_db(self) -> Dict[str, Any]:
        """Validate BM25 index database schema."""
        try:
            conn = sqlite3.connect(self.db_paths['bm25_index'])
            cursor = conn.cursor()

            # Check if table exists and has correct columns
            cursor.execute("PRAGMA table_info(bm25_index)")
            columns = cursor.fetchall()

            expected_columns = [
                ('id', 'INTEGER'),
                ('doc_id', 'TEXT'),
                ('content', 'TEXT'),
                ('metadata', 'TEXT'),
                ('created_at', 'TIMESTAMP')
            ]

            column_names = [col[1] for col in columns]
            missing_columns = []
            for expected_col in expected_columns:
                if expected_col[0] not in column_names:
                    missing_columns.append(expected_col[0])

            conn.close()
            return {
                'valid': len(missing_columns) == 0,
                'missing_columns': missing_columns,
                'columns_count': len(columns)
            }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }