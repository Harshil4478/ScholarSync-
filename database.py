
import sqlite3
from datetime import datetime

DB_NAME = "relief_routes.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergency_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            people_affected INTEGER NOT NULL,
            severity TEXT NOT NULL,
            supplies_needed TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            status TEXT DEFAULT 'Pending',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def add_emergency_request(
    location,
    description,
    people_affected,
    severity,
    supplies_needed,
    latitude=None,
    longitude=None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO emergency_requests (
            location,
            description,
            people_affected,
            severity,
            supplies_needed,
            latitude,
            longitude,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
    """, (
        location,
        description,
        people_affected,
        severity,
        ", ".join(supplies_needed),
        latitude,
        longitude,
        datetime.now().isoformat(timespec="seconds")
    ))

    conn.commit()
    request_id = cursor.lastrowid
    conn.close()

    return request_id


def get_emergency_requests():
    conn = get_connection()

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM emergency_requests
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
            END,
            created_at DESC
    """)

    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return records


def update_request_status(request_id, new_status):
    allowed_statuses = [
        "Pending",
        "In Progress",
        "Resolved"
    ]

    if new_status not in allowed_statuses:
        raise ValueError("Invalid request status")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE emergency_requests
        SET status = ?
        WHERE id = ?
    """, (new_status, request_id))

    conn.commit()
    conn.close()


def get_request_count():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM emergency_requests
        WHERE status != 'Resolved'
    """)

    count = cursor.fetchone()[0]
    conn.close()

    return count


initialize_database()
