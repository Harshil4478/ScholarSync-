import sqlite3
from datetime import datetime

DB_NAME = "relief_routes.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_relief_centres():
    """Create the relief-centre table without changing existing tables."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relief_centres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                centre_name TEXT NOT NULL,
                address TEXT NOT NULL,
                contact_person TEXT,
                phone TEXT,
                capacity INTEGER NOT NULL CHECK (capacity > 0),
                water_litres INTEGER NOT NULL DEFAULT 0 CHECK (water_litres >= 0),
                food_packets INTEGER NOT NULL DEFAULT 0 CHECK (food_packets >= 0),
                medical_kits INTEGER NOT NULL DEFAULT 0 CHECK (medical_kits >= 0),
                vehicles INTEGER NOT NULL DEFAULT 0 CHECK (vehicles >= 0),
                latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90),
                longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
                created_at TEXT NOT NULL
            )
        """)
        # Safe migration for databases created before the status column existed.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(relief_centres)")}
        if "status" not in columns:
            conn.execute(
                "ALTER TABLE relief_centres ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'"
            )
        conn.commit()
    finally:
        conn.close()


CENTRE_STATUSES = ["Active", "Full", "Closed"]
EDITABLE_FIELDS = {
    "centre_name", "address", "contact_person", "phone", "capacity",
    "water_litres", "food_packets", "medical_kits", "vehicles", "status",
    "latitude", "longitude",
}


def add_relief_centre(*, centre_name, address, contact_person="", phone="",
                      capacity, water_litres=0, food_packets=0, medical_kits=0,
                      vehicles=0, latitude, longitude):
    if not centre_name.strip() or not address.strip():
        raise ValueError("Centre name and address are required.")
    if int(capacity) <= 0:
        raise ValueError("Capacity must be greater than zero.")
    quantities = [water_litres, food_packets, medical_kits, vehicles]
    if any(int(value) < 0 for value in quantities):
        raise ValueError("Supply quantities cannot be negative.")
    latitude = float(latitude)
    longitude = float(longitude)
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO relief_centres (
                centre_name, address, contact_person, phone, capacity,
                water_litres, food_packets, medical_kits, vehicles,
                latitude, longitude, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            centre_name.strip(), address.strip(), contact_person.strip(), phone.strip(),
            int(capacity), int(water_litres), int(food_packets), int(medical_kits),
            int(vehicles), latitude, longitude,
            datetime.now().isoformat(timespec="seconds")
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def delete_relief_centre(centre_id):
    """Delete one relief centre by its database ID."""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM relief_centres WHERE id = ?", (int(centre_id),))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_relief_centre(centre_id, **fields):
    """Update selected fields of one centre. Returns True if a row changed."""
    fields = {k: v for k, v in fields.items() if k in EDITABLE_FIELDS}
    if not fields:
        return False
    if "status" in fields and fields["status"] not in CENTRE_STATUSES:
        raise ValueError(f"Status must be one of {CENTRE_STATUSES}.")
    if "capacity" in fields and int(fields["capacity"]) <= 0:
        raise ValueError("Capacity must be greater than zero.")
    for key in ("water_litres", "food_packets", "medical_kits", "vehicles"):
        if key in fields and int(fields[key]) < 0:
            raise ValueError("Supply quantities cannot be negative.")
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn = get_connection()
    try:
        cursor = conn.execute(
            f"UPDATE relief_centres SET {assignments} WHERE id = ?",
            (*fields.values(), int(centre_id)),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def deduct_supplies(centre_id, *, water_litres=0, food_packets=0, medical_kits=0):
    """Remove dispatched supplies from a centre (never below zero)."""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            UPDATE relief_centres SET
                water_litres = MAX(water_litres - ?, 0),
                food_packets = MAX(food_packets - ?, 0),
                medical_kits = MAX(medical_kits - ?, 0)
            WHERE id = ?
        """, (int(water_litres), int(food_packets), int(medical_kits), int(centre_id)))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_relief_centres():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM relief_centres ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


initialize_relief_centres()
