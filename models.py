"""
NutriSense AI — Database Models (SQLite)

Provides persistent storage for:
    - User accounts (signup/login)
    - Weight tracking entries
    - Daily food logs
    - Water intake
"""

import os
import sqlite3
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from werkzeug.security import generate_password_hash, check_password_hash

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "nutrisense.db")


def get_db() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            age INTEGER DEFAULT 25,
            height REAL DEFAULT 170,
            weight REAL DEFAULT 70,
            gender TEXT DEFAULT 'male',
            goal TEXT DEFAULT 'maintain',
            activity TEXT DEFAULT 'moderate',
            target_weight REAL DEFAULT 0,
            target_cal INTEGER DEFAULT 2000,
            protein_target INTEGER DEFAULT 50,
            carbs_target INTEGER DEFAULT 250,
            fat_target INTEGER DEFAULT 55,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS weight_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            weight_kg REAL NOT NULL,
            bmi REAL,
            note TEXT DEFAULT '',
            recorded_at DATE DEFAULT (date('now')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS food_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            qty REAL NOT NULL,
            cal INTEGER NOT NULL,
            protein REAL NOT NULL,
            carbs REAL NOT NULL,
            fat REAL NOT NULL,
            emoji TEXT DEFAULT '🍽️',
            logged_at DATE DEFAULT (date('now')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS water_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            glasses INTEGER DEFAULT 0,
            log_date DATE DEFAULT (date('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, log_date)
        );

        CREATE TABLE IF NOT EXISTS exercise_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            duration_min INTEGER NOT NULL,
            cal_burned INTEGER NOT NULL,
            category TEXT DEFAULT 'general',
            logged_at DATE DEFAULT (date('now')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# User Operations
# ---------------------------------------------------------------------------
def create_user(name: str, email: str, password: str) -> Optional[int]:
    """Create a new user. Returns user ID or None if email exists."""
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email.lower().strip(), generate_password_hash(password))
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """Verify email/password. Returns user dict or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
    ).fetchone()
    conn.close()
    if row and check_password_hash(row["password_hash"], password):
        return dict(row)
    return None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_profile(user_id: int, **kwargs) -> bool:
    """Update user profile fields."""
    allowed = {
        "name", "age", "height", "weight", "gender", "goal",
        "activity", "target_weight", "target_cal",
        "protein_target", "carbs_target", "fat_target"
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False
    fields["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    conn = get_db()
    conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return True


def get_total_users() -> int:
    """Get total number of registered users."""
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    conn.close()
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Weight Tracking
# ---------------------------------------------------------------------------
def add_weight_entry(user_id: int, weight_kg: float, height: float,
                     note: str = "") -> int:
    """Add a weight entry and return entry ID."""
    bmi = round(weight_kg / (height / 100) ** 2, 1) if height > 0 else 0
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO weight_entries (user_id, weight_kg, bmi, note) VALUES (?, ?, ?, ?)",
        (user_id, weight_kg, bmi, note)
    )
    # Also update user's current weight
    conn.execute(
        "UPDATE users SET weight = ?, updated_at = ? WHERE id = ?",
        (weight_kg, datetime.now().isoformat(), user_id)
    )
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()
    return entry_id


def get_weight_history(user_id: int, limit: int = 30) -> List[Dict]:
    """Get weight history for a user, most recent first."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM weight_entries WHERE user_id = ?
           ORDER BY recorded_at DESC, id DESC LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weight_stats(user_id: int) -> Dict:
    """Get weight statistics for a user."""
    conn = get_db()
    first = conn.execute(
        "SELECT weight_kg FROM weight_entries WHERE user_id = ? ORDER BY recorded_at ASC, id ASC LIMIT 1",
        (user_id,)
    ).fetchone()
    latest = conn.execute(
        "SELECT weight_kg, bmi FROM weight_entries WHERE user_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    count = conn.execute(
        "SELECT COUNT(*) as cnt FROM weight_entries WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    stats = {"entries": count["cnt"] if count else 0}
    if first and latest:
        stats["first_weight"] = first["weight_kg"]
        stats["current_weight"] = latest["weight_kg"]
        stats["current_bmi"] = latest["bmi"]
        stats["total_change"] = round(latest["weight_kg"] - first["weight_kg"], 1)
    return stats


# ---------------------------------------------------------------------------
# Food Log
# ---------------------------------------------------------------------------
def save_food_entry(user_id: int, food_name: str, qty: float,
                    cal: int, protein: float, carbs: float,
                    fat: float, emoji: str = "🍽️") -> int:
    """Save a food log entry."""
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO food_logs
           (user_id, food_name, qty, cal, protein, carbs, fat, emoji)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, food_name, qty, cal, protein, carbs, fat, emoji)
    )
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()
    return entry_id


def get_food_log_today(user_id: int) -> List[Dict]:
    """Get today's food log for a user."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM food_logs WHERE user_id = ? AND logged_at = date('now')
           ORDER BY created_at ASC""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_food_log_today(user_id: int):
    """Clear today's food log."""
    conn = get_db()
    conn.execute(
        "DELETE FROM food_logs WHERE user_id = ? AND logged_at = date('now')",
        (user_id,)
    )
    conn.commit()
    conn.close()


def get_weekly_calories(user_id: int) -> List[Dict]:
    """Get daily calorie totals for the past 7 days."""
    conn = get_db()
    rows = conn.execute(
        """SELECT logged_at, SUM(cal) as total_cal
           FROM food_logs WHERE user_id = ?
           AND logged_at >= date('now', '-6 days')
           GROUP BY logged_at ORDER BY logged_at ASC""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_food_entry(entry_id: int, user_id: int):
    """Delete a specific food log entry (owned by user)."""
    conn = get_db()
    conn.execute(
        "DELETE FROM food_logs WHERE id = ? AND user_id = ?",
        (entry_id, user_id)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Water Tracking
# ---------------------------------------------------------------------------
def get_water_today(user_id: int) -> int:
    """Get today's water intake."""
    conn = get_db()
    row = conn.execute(
        "SELECT glasses FROM water_logs WHERE user_id = ? AND log_date = date('now')",
        (user_id,)
    ).fetchone()
    conn.close()
    return row["glasses"] if row else 0


def update_water_today(user_id: int, glasses: int):
    """Update today's water intake."""
    conn = get_db()
    conn.execute(
        """INSERT INTO water_logs (user_id, glasses, log_date)
           VALUES (?, ?, date('now'))
           ON CONFLICT(user_id, log_date) DO UPDATE SET glasses = ?""",
        (user_id, glasses, glasses)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Exercise Tracking
# ---------------------------------------------------------------------------
def save_exercise_entry(user_id: int, exercise_name: str, duration: int,
                        cal_burned: int, category: str = "general") -> int:
    """Save an exercise log entry."""
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO exercise_logs
           (user_id, exercise_name, duration_min, cal_burned, category)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, exercise_name, duration, cal_burned, category)
    )
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()
    return entry_id


def get_exercise_log_today(user_id: int) -> List[Dict]:
    """Get today's exercise log."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM exercise_logs WHERE user_id = ? AND logged_at = date('now')
           ORDER BY created_at ASC""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_exercise_stats(user_id: int) -> Dict:
    """Get exercise stats for the user."""
    conn = get_db()
    today = conn.execute(
        """SELECT COALESCE(SUM(cal_burned), 0) as cal,
                  COALESCE(SUM(duration_min), 0) as mins,
                  COUNT(*) as exercises
           FROM exercise_logs WHERE user_id = ? AND logged_at = date('now')""",
        (user_id,)
    ).fetchone()
    weekly = conn.execute(
        """SELECT COALESCE(SUM(cal_burned), 0) as cal,
                  COALESCE(SUM(duration_min), 0) as mins
           FROM exercise_logs WHERE user_id = ?
           AND logged_at >= date('now', '-6 days')""",
        (user_id,)
    ).fetchone()
    conn.close()
    return {
        "today_cal": today["cal"],
        "today_mins": today["mins"],
        "today_exercises": today["exercises"],
        "weekly_cal": weekly["cal"],
        "weekly_mins": weekly["mins"],
    }


def delete_exercise_entry(entry_id: int, user_id: int):
    """Delete a specific exercise entry."""
    conn = get_db()
    conn.execute(
        "DELETE FROM exercise_logs WHERE id = ? AND user_id = ?",
        (entry_id, user_id)
    )
    conn.commit()
    conn.close()
