"""Stock linked to centres, dispatch log, and emergency edit/delete.

Single source of truth: a centre's available water / food / medical stock is
the SUM of its linked inventory rows (inventory.centre_id) by category.
The old supply columns on relief_centres are migrated once and then ignored.
"""
import sqlite3
from datetime import datetime

from database import DB_NAME
from relief_centres import delete_relief_centre, get_relief_centres

# inventory category -> the key the planner uses
CATEGORY_TO_KEY = {"Water": "water_litres", "Food": "food_packets", "Medical": "medical_kits"}
KEY_TO_CATEGORY = {key: category for category, key in CATEGORY_TO_KEY.items()}
STOCK_DEFAULTS = {  # key -> (resource name, category, unit) for auto-created rows
    "water_litres": ("Drinking Water", "Water", "Litres"),
    "food_packets": ("Food Packets", "Food", "Packets"),
    "medical_kits": ("Medical Kits", "Medical", "Kits"),
}
LOW_STOCK_THRESHOLDS = {"water_litres": 500, "food_packets": 100, "medical_kits": 10}
STOCK_LABELS = {"water_litres": "Water (L)", "food_packets": "Food packets", "medical_kits": "Medical kits"}
DISPATCH_STATUSES = ["Approved", "On the way", "Delivered", "Cancelled"]
SEVERITIES = ["Critical", "High", "Medium", "Low"]


def _conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------ setup
def initialize_logistics():
    conn = _conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dispatches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emergency_id INTEGER NOT NULL,
                centre_id INTEGER NOT NULL,
                centre_name TEXT NOT NULL,
                water_litres INTEGER NOT NULL DEFAULT 0,
                food_packets INTEGER NOT NULL DEFAULT 0,
                medical_kits INTEGER NOT NULL DEFAULT 0,
                distance_km REAL,
                duration_min REAL,
                status TEXT NOT NULL DEFAULT 'Approved',
                note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        _migrate_legacy_stock(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate_legacy_stock(conn):
    """One-time: turn old per-centre supply columns into linked inventory rows."""
    for centre in conn.execute("SELECT * FROM relief_centres").fetchall():
        linked = conn.execute(
            "SELECT COUNT(*) FROM inventory WHERE centre_id = ?", (centre["id"],)
        ).fetchone()[0]
        if linked:
            continue
        for key in STOCK_DEFAULTS:
            quantity = int(centre[key] or 0)
            if quantity > 0:
                _add_stock(conn, centre["id"], centre["centre_name"], key, quantity)


# ------------------------------------------------------------------ stock
def _add_stock(conn, centre_id, centre_name, key, quantity):
    category = KEY_TO_CATEGORY[key]
    row = conn.execute(
        "SELECT id FROM inventory WHERE centre_id = ? AND category = ? ORDER BY quantity DESC LIMIT 1",
        (centre_id, category),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE inventory SET quantity = quantity + ?, updated_at = ? WHERE id = ?",
            (quantity, _now(), row["id"]),
        )
    else:
        name, category, unit = STOCK_DEFAULTS[key]
        conn.execute(
            """INSERT INTO inventory (resource_name, category, quantity, unit, location, updated_at, centre_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, category, quantity, unit, centre_name, _now(), centre_id),
        )


def _deduct_stock(conn, centre_id, key, wanted):
    """Remove up to `wanted` from the centre's rows; return what was really removed."""
    remaining = int(wanted)
    rows = conn.execute(
        "SELECT id, quantity FROM inventory WHERE centre_id = ? AND category = ? AND quantity > 0 "
        "ORDER BY quantity DESC",
        (centre_id, KEY_TO_CATEGORY[key]),
    ).fetchall()
    for row in rows:
        if remaining <= 0:
            break
        take = min(remaining, row["quantity"])
        conn.execute(
            "UPDATE inventory SET quantity = quantity - ?, updated_at = ? WHERE id = ?",
            (take, _now(), row["id"]),
        )
        remaining -= take
    return int(wanted) - remaining


def set_initial_stock(centre_id, *, water_litres=0, food_packets=0, medical_kits=0):
    """Create linked inventory rows for a newly registered centre."""
    conn = _conn()
    try:
        centre = conn.execute("SELECT centre_name FROM relief_centres WHERE id = ?", (int(centre_id),)).fetchone()
        if not centre:
            raise ValueError("Relief centre not found.")
        for key, quantity in (("water_litres", water_litres), ("food_packets", food_packets),
                              ("medical_kits", medical_kits)):
            if int(quantity) > 0:
                _add_stock(conn, int(centre_id), centre["centre_name"], key, int(quantity))
        conn.commit()
    finally:
        conn.close()


def get_centres_with_stock():
    """Relief centres with water/food/medical totals computed from linked inventory."""
    centres = get_relief_centres()
    conn = _conn()
    try:
        totals = {
            (row["centre_id"], row["category"]): row["total"]
            for row in conn.execute(
                "SELECT centre_id, category, SUM(quantity) AS total FROM inventory "
                "WHERE centre_id IS NOT NULL GROUP BY centre_id, category"
            )
        }
    finally:
        conn.close()
    for centre in centres:
        for category, key in CATEGORY_TO_KEY.items():
            centre[key] = int(totals.get((centre["id"], category), 0))
    return centres


def delete_centre_and_stock(centre_id):
    """Delete a centre and its linked inventory rows (dispatch history is kept)."""
    conn = _conn()
    try:
        conn.execute("DELETE FROM inventory WHERE centre_id = ?", (int(centre_id),))
        conn.commit()
    finally:
        conn.close()
    return delete_relief_centre(centre_id)


def low_stock_alerts(centres):
    """List of (centre name, supply label, quantity, threshold) for Active centres."""
    alerts = []
    for centre in centres:
        if centre.get("status", "Active") != "Active":
            continue
        for key, threshold in LOW_STOCK_THRESHOLDS.items():
            if int(centre.get(key) or 0) < threshold:
                alerts.append((centre["centre_name"], STOCK_LABELS[key], int(centre.get(key) or 0), threshold))
    return alerts


# ------------------------------------------------------------------ dispatches
def create_dispatch(emergency_id, centre_id, plan, distance_km=None, duration_min=None, note=""):
    """Approve a dispatch: deduct stock, log it, mark the emergency In Progress (one transaction)."""
    conn = _conn()
    try:
        centre = conn.execute("SELECT centre_name, status FROM relief_centres WHERE id = ?", (int(centre_id),)).fetchone()
        if not centre:
            raise ValueError("That relief centre no longer exists.")
        if centre["status"] != "Active":
            raise ValueError(f"Centre is {centre['status']} and cannot dispatch.")
        sent = {key: _deduct_stock(conn, int(centre_id), key, qty) for key, qty in plan.items()
                if key in KEY_TO_CATEGORY and int(qty) > 0}
        if not any(sent.values()):
            raise ValueError("Nothing could be dispatched: the centre has no matching stock.")
        cursor = conn.execute(
            """INSERT INTO dispatches (emergency_id, centre_id, centre_name, water_litres, food_packets,
                   medical_kits, distance_km, duration_min, status, note, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Approved', ?, ?, ?)""",
            (int(emergency_id), int(centre_id), centre["centre_name"],
             sent.get("water_litres", 0), sent.get("food_packets", 0), sent.get("medical_kits", 0),
             distance_km, duration_min, note, _now(), _now()),
        )
        conn.execute(
            "UPDATE emergency_requests SET status = 'In Progress' WHERE id = ? AND status = 'Pending'",
            (int(emergency_id),),
        )
        conn.commit()
        return cursor.lastrowid, sent
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_dispatches(emergency_id=None):
    conn = _conn()
    try:
        if emergency_id is None:
            rows = conn.execute("SELECT * FROM dispatches ORDER BY created_at DESC, id DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM dispatches WHERE emergency_id = ? ORDER BY created_at DESC, id DESC",
                (int(emergency_id),),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def dispatched_totals(emergency_id):
    """Supplies already sent (non-cancelled dispatches) for one emergency."""
    totals = {key: 0 for key in STOCK_DEFAULTS}
    for dispatch in get_dispatches(emergency_id):
        if dispatch["status"] == "Cancelled":
            continue
        for key in totals:
            totals[key] += int(dispatch[key] or 0)
    return totals


def update_dispatch_status(dispatch_id, new_status):
    """Change a dispatch's status. Cancelling returns the stock to the centre."""
    if new_status not in DISPATCH_STATUSES:
        raise ValueError("Invalid dispatch status.")
    conn = _conn()
    try:
        dispatch = conn.execute("SELECT * FROM dispatches WHERE id = ?", (int(dispatch_id),)).fetchone()
        if not dispatch:
            raise ValueError("Dispatch not found.")
        old = dispatch["status"]
        if old == new_status:
            return False
        if old == "Cancelled":
            raise ValueError("A cancelled dispatch cannot be reopened. Create a new dispatch instead.")
        if old == "Delivered" and new_status == "Cancelled":
            raise ValueError("A delivered dispatch cannot be cancelled.")
        if new_status == "Cancelled":
            centre = conn.execute("SELECT centre_name FROM relief_centres WHERE id = ?",
                                  (dispatch["centre_id"],)).fetchone()
            if centre:  # centre may have been deleted since
                for key in STOCK_DEFAULTS:
                    if int(dispatch[key] or 0) > 0:
                        _add_stock(conn, dispatch["centre_id"], centre["centre_name"], key, int(dispatch[key]))
        conn.execute("UPDATE dispatches SET status = ?, updated_at = ? WHERE id = ?",
                     (new_status, _now(), int(dispatch_id)))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ------------------------------------------------------------------ emergencies
def update_emergency(emergency_id, **fields):
    """Edit location, description, people_affected, severity or supplies_needed."""
    allowed = {"location", "description", "people_affected", "severity", "supplies_needed"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return False
    if "severity" in fields and fields["severity"] not in SEVERITIES:
        raise ValueError(f"Severity must be one of {SEVERITIES}.")
    if "people_affected" in fields:
        fields["people_affected"] = int(fields["people_affected"])
        if fields["people_affected"] < 1:
            raise ValueError("People affected must be at least 1.")
    if "supplies_needed" in fields and isinstance(fields["supplies_needed"], (list, tuple)):
        fields["supplies_needed"] = ", ".join(fields["supplies_needed"])
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn = _conn()
    try:
        cursor = conn.execute(f"UPDATE emergency_requests SET {assignments} WHERE id = ?",
                              (*fields.values(), int(emergency_id)))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_emergency(emergency_id):
    conn = _conn()
    try:
        cursor = conn.execute("DELETE FROM emergency_requests WHERE id = ?", (int(emergency_id),))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


initialize_logistics()
