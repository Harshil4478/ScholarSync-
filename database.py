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

# ---------- RESOURCE INVENTORY ----------

def initialize_inventory():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity >= 0),
            unit TEXT NOT NULL,
            location TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Link stock to a relief centre (NULL = central warehouse / not linked).
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(inventory)")}
    if "centre_id" not in columns:
        cursor.execute("ALTER TABLE inventory ADD COLUMN centre_id INTEGER")

    conn.commit()
    conn.close()


def add_inventory_item(name, category, quantity, unit, location, centre_id=None):
    if not name.strip() or not location.strip():
        raise ValueError("Resource name and location are required")

    if quantity < 0:
        raise ValueError("Quantity cannot be negative")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO inventory (
            resource_name,
            category,
            quantity,
            unit,
            location,
            updated_at,
            centre_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name.strip(),
        category,
        quantity,
        unit,
        location.strip(),
        datetime.now().isoformat(timespec="seconds"),
        centre_id
    ))

    conn.commit()
    conn.close()


def get_inventory():
    conn = get_connection()
    conn.row_factory = sqlite3.Row

    records = conn.execute("""
        SELECT * FROM inventory
        ORDER BY updated_at DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in records]


def update_inventory_quantity(item_id, new_quantity):
    if new_quantity < 0:
        raise ValueError("Quantity cannot be negative")

    conn = get_connection()

    conn.execute("""
        UPDATE inventory
        SET quantity = ?, updated_at = ?
        WHERE id = ?
    """, (
        new_quantity,
        datetime.now().isoformat(timespec="seconds"),
        item_id
    ))

    conn.commit()
    conn.close()


initialize_database()
initialize_inventory()
