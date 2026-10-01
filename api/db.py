"""FoodieGo's database: real SQLite, created fresh in memory for every run so demos are repeatable."""
from __future__ import annotations

import contextvars
import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Optional

SCHEMA = """
CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  restaurant TEXT NOT NULL,
  items TEXT NOT NULL,           -- JSON list of {name, price}
  total INTEGER NOT NULL,        -- rupees
  status TEXT NOT NULL CHECK (status IN ('preparing', 'out_for_delivery', 'delivered')),
  eta_min INTEGER
);
CREATE TABLE payments (
  order_id TEXT PRIMARY KEY REFERENCES orders(id),
  method TEXT NOT NULL,
  amount INTEGER NOT NULL
);
CREATE TABLE refunds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT NOT NULL REFERENCES orders(id),
  amount INTEGER NOT NULL CHECK (amount > 0),
  reason TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('issued', 'pending_approval'))
);
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event TEXT NOT NULL,
  detail TEXT NOT NULL
);
"""

# (id, user, restaurant, items, status, eta_min, payment method)
ORDERS = [
    ("4519", "u_42", "Biryani Blues", [("Chicken biryani", 309), ("Raita", 40)], "delivered", None, "UPI"),
    ("4521", "u_42", "Pizza Corner", [("Farmhouse pizza", 399), ("Garlic bread", 100)], "out_for_delivery", 5, "UPI"),
    ("4524", "u_42", "Dosa Plaza", [("Masala dosa", 120)], "preparing", 25, "Card"),
    ("4530", "u_7", "Burger Barn", [("Veg burger", 150), ("Fries", 50)], "delivered", None, "Card"),
    ("4533", "u_9", "Wok Express", [("Hakka noodles", 220)], "out_for_delivery", 12, "UPI"),
]

_conn: contextvars.ContextVar[sqlite3.Connection] = contextvars.ContextVar("conn")


@contextmanager
def session():
    """A fresh, seeded database for the duration of one run."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for oid, user, restaurant, items, status, eta, method in ORDERS:
        total = sum(price for _, price in items)
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
            (oid, user, restaurant, json.dumps([{"name": n, "price": p} for n, p in items]), total, status, eta),
        )
        conn.execute("INSERT INTO payments VALUES (?, ?, ?)", (oid, method, total))
    token = _conn.set(conn)
    try:
        yield
    finally:
        _conn.reset(token)
        conn.close()


def one(sql: str, *args: Any) -> Optional[dict]:
    row = _conn.get().execute(sql, args).fetchone()
    return dict(row) if row else None


def run(sql: str, *args: Any) -> int:
    """Execute a write and return the new row id."""
    return _conn.get().execute(sql, args).lastrowid
