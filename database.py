"""
Database Module for Email Generation History
Uses SQLite database instead of JSON for better performance and scalability
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import os

# Database file path
DB_FILE = "data/email_history.db"


class EmailHistoryDB:
    """SQLite-based database for email generation history"""

    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self._init_database()

    def _init_database(self):
        """Initialize database and create tables if they don't exist"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Create sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                email_address TEXT NOT NULL,
                thread_subject TEXT,
                intent TEXT,
                subject TEXT,
                email_body TEXT,
                tone TEXT DEFAULT 'professional',
                selected_email_index INTEGER,
                email_goal TEXT,
                thread_email_count INTEGER DEFAULT 0,
                last_modified TEXT NOT NULL,
                is_new_email BOOLEAN DEFAULT 0
            )
        ''')

        # Create statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_generations INTEGER DEFAULT 0
            )
        ''')

        # Initialize statistics if not exists
        cursor.execute('SELECT COUNT(*) FROM statistics')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO statistics (total_generations) VALUES (0)')

        conn.commit()
        conn.close()

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_file)

    def save_generation(self, session_data: Dict) -> str:
        """
        Save email generation to history

        Args:
            session_data: Dictionary containing:
                - email_address: str
                - thread_subject: str
                - intent: str
                - subject: str
                - email: str
                - tone: str
                - selected_email_index: Optional[int]
                - email_goal: Optional[str]
                - thread_email_count: int
                - is_new_email: bool

        Returns:
            session_id: Unique identifier for this generation
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create session entry
        session_id = f"session_{int(datetime.now().timestamp() * 1000)}"
        timestamp = datetime.now().isoformat()

        try:
            cursor.execute('''
                INSERT INTO sessions (
                    session_id, timestamp, email_address, thread_subject,
                    intent, subject, email_body, tone, selected_email_index,
                    email_goal, thread_email_count, last_modified, is_new_email
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                timestamp,
                session_data.get("email_address", ""),
                session_data.get("thread_subject", ""),
                session_data.get("intent", ""),
                session_data.get("subject", ""),
                session_data.get("email", ""),
                session_data.get("tone", "professional"),
                session_data.get("selected_email_index"),
                session_data.get("email_goal", ""),
                session_data.get("thread_email_count", 0),
                timestamp,
                session_data.get("is_new_email", False)
            ))

            # Update total generations
            cursor.execute('UPDATE statistics SET total_generations = total_generations + 1')

            conn.commit()
            print(f"✅ Saved generation to database: {session_id}")

        except Exception as e:
            print(f"❌ Error saving to database: {e}")
            conn.rollback()
            raise

        finally:
            conn.close()

        return session_id

    def update_session(self, session_id: str, updated_data: Dict) -> bool:
        """
        Update an existing session with edited email content

        Args:
            session_id: Session identifier
            updated_data: Dictionary with fields to update (subject, email_body, etc.)

        Returns:
            True if updated successfully, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build UPDATE query dynamically based on provided fields
            update_fields = []
            values = []

            if "subject" in updated_data:
                update_fields.append("subject = ?")
                values.append(updated_data["subject"])

            if "email_body" in updated_data:
                update_fields.append("email_body = ?")
                values.append(updated_data["email_body"])

            if "email_goal" in updated_data:
                update_fields.append("email_goal = ?")
                values.append(updated_data["email_goal"])

            if "tone" in updated_data:
                update_fields.append("tone = ?")
                values.append(updated_data["tone"])

            if not update_fields:
                print("⚠️ No fields to update")
                return False

            # Always update last_modified
            update_fields.append("last_modified = ?")
            values.append(datetime.now().isoformat())

            # Add session_id to values
            values.append(session_id)

            query = f"UPDATE sessions SET {', '.join(update_fields)} WHERE session_id = ?"
            cursor.execute(query, values)

            if cursor.rowcount > 0:
                conn.commit()
                print(f"✅ Updated session: {session_id}")
                return True
            else:
                print(f"⚠️ Session not found: {session_id}")
                return False

        except Exception as e:
            print(f"❌ Error updating session: {e}")
            conn.rollback()
            return False

        finally:
            conn.close()

    def get_all_sessions(self, limit: int = 50) -> List[Dict]:
        """
        Get all sessions from history

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT session_id, timestamp, email_address, thread_subject,
                       intent, subject, email_body, tone, selected_email_index,
                       email_goal, thread_email_count, last_modified, is_new_email
                FROM sessions
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()

            sessions = []
            for row in rows:
                sessions.append({
                    "session_id": row[0],
                    "timestamp": row[1],
                    "email_address": row[2],
                    "thread_subject": row[3],
                    "intent": row[4],
                    "subject": row[5],
                    "email_body": row[6],
                    "tone": row[7],
                    "selected_email_index": row[8],
                    "email_goal": row[9],
                    "thread_email_count": row[10],
                    "last_modified": row[11],
                    "is_new_email": bool(row[12])
                })

            return sessions

        except Exception as e:
            print(f"❌ Error fetching sessions: {e}")
            return []

        finally:
            conn.close()

    def get_session_by_id(self, session_id: str) -> Optional[Dict]:
        """
        Get specific session by ID

        Args:
            session_id: Session identifier

        Returns:
            Session dictionary or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT session_id, timestamp, email_address, thread_subject,
                       intent, subject, email_body, tone, selected_email_index,
                       email_goal, thread_email_count, last_modified, is_new_email
                FROM sessions
                WHERE session_id = ?
            ''', (session_id,))

            row = cursor.fetchone()

            if row:
                return {
                    "session_id": row[0],
                    "timestamp": row[1],
                    "email_address": row[2],
                    "thread_subject": row[3],
                    "intent": row[4],
                    "subject": row[5],
                    "email_body": row[6],
                    "tone": row[7],
                    "selected_email_index": row[8],
                    "email_goal": row[9],
                    "thread_email_count": row[10],
                    "last_modified": row[11],
                    "is_new_email": bool(row[12])
                }

            return None

        except Exception as e:
            print(f"❌ Error fetching session: {e}")
            return None

        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from history

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))

            if cursor.rowcount > 0:
                # Update total generations
                cursor.execute('UPDATE statistics SET total_generations = total_generations - 1')
                conn.commit()
                print(f"✅ Deleted session: {session_id}")
                return True
            else:
                print(f"⚠️ Session not found: {session_id}")
                return False

        except Exception as e:
            print(f"❌ Error deleting session: {e}")
            conn.rollback()
            return False

        finally:
            conn.close()

    def clear_all_history(self) -> bool:
        """
        Clear all history

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM sessions')
            cursor.execute('UPDATE statistics SET total_generations = 0')
            conn.commit()
            print("✅ Cleared all history")
            return True

        except Exception as e:
            print(f"❌ Error clearing history: {e}")
            conn.rollback()
            return False

        finally:
            conn.close()

    def get_stats(self) -> Dict:
        """
        Get statistics about history

        Returns:
            Dictionary with stats
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get total generations
            cursor.execute('SELECT total_generations FROM statistics')
            total_generations = cursor.fetchone()[0]

            # Get current sessions count
            cursor.execute('SELECT COUNT(*) FROM sessions')
            current_sessions = cursor.fetchone()[0]

            # Get intent breakdown
            cursor.execute('''
                SELECT intent, COUNT(*) as count
                FROM sessions
                GROUP BY intent
            ''')
            intent_rows = cursor.fetchall()
            intent_breakdown = {row[0]: row[1] for row in intent_rows}

            # Get last generation timestamp
            cursor.execute('SELECT timestamp FROM sessions ORDER BY timestamp DESC LIMIT 1')
            last_row = cursor.fetchone()
            last_generation = last_row[0] if last_row else None

            return {
                "total_generations": total_generations,
                "current_sessions": current_sessions,
                "intent_breakdown": intent_breakdown,
                "last_generation": last_generation
            }

        except Exception as e:
            print(f"❌ Error fetching stats: {e}")
            return {
                "total_generations": 0,
                "current_sessions": 0,
                "intent_breakdown": {},
                "last_generation": None
            }

        finally:
            conn.close()


# Global database instance
db = EmailHistoryDB()


def save_generation(session_data: Dict) -> str:
    """Wrapper function to save generation"""
    return db.save_generation(session_data)


def update_session(session_id: str, updated_data: Dict) -> bool:
    """Wrapper function to update session"""
    return db.update_session(session_id, updated_data)


def get_all_sessions(limit: int = 50) -> List[Dict]:
    """Wrapper function to get all sessions"""
    return db.get_all_sessions(limit)


def get_session_by_id(session_id: str) -> Optional[Dict]:
    """Wrapper function to get session by ID"""
    return db.get_session_by_id(session_id)


def delete_session(session_id: str) -> bool:
    """Wrapper function to delete session"""
    return db.delete_session(session_id)


def clear_all_history() -> bool:
    """Wrapper function to clear all history"""
    return db.clear_all_history()


def get_stats() -> Dict:
    """Wrapper function to get stats"""
    return db.get_stats()