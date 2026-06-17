"""
Seed demo data (Option B Fixed Version for Single-User Schema)
---------------------------------------------------------------
Populates contacts.db with a sample profile, mode/visibility settings, and
a handful of realistic contacts + scan log entries across multiple events -
so the app has something to show (especially the My Contacts and Analytics
tabs) before your demo, instead of starting from a blank slate.

Run this BEFORE starting the app or trigger via the Admin Panel:
    python seed_demo_data.py
    streamlit run app.py

Re-running this script adds another copy of the sample contacts - delete
contacts.db first if you want a clean reset.
"""

import sys
import json
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "contacts.db"

DEFAULT_MODES = ["Investor", "Startup", "Supplier", "Other"]
DEFAULT_VISIBILITY = {
    "Investor": ["name", "title", "company", "email", "linkedin"],
    "Startup": ["name", "title", "company", "email", "website", "pitch"],
    "Supplier": ["name", "title", "company", "email", "phone"],
    "Other": ["name", "company", "email"],
}

SAMPLE_PROFILE = {
    "name": "Alex Rivera",
    "title": "Founder & CEO",
    "company": "Acme Labs",
    "email": "alex@acmelabs.io",
    "phone": "+1-555-0100",
    "linkedin": "linkedin.com/in/alexrivera",
    "website": "acmelabs.io",
    "pitch": "AI-powered logistics platform for last-mile delivery",
    "bio": "Building the future of urban delivery.",
}

SAMPLE_CONTACTS = [
    (
        "Sarah Jenkins",
        {
            "name": "Sarah Jenkins",
            "title": "Partner",
            "company": "Vanguard Ventures",
            "email": "sarah@vanguard.vc",
            "linkedin": "linkedin.com/in/sarahj-vc",
            "shared_as": "Investor",
        },
        "Investor",
        "Investor",
        "TechCrunch Disrupt 2024",
        5,
    ),
    (
        "Michael Chen",
        {
            "name": "Michael Chen",
            "title": "CTO & Co-Founder",
            "company": "ByteSize AI",
            "email": "mike@bytesize.ai",
            "website": "bytesize.ai",
            "pitch": "No-code platform for deploying edge machine learning models locally on IoT hardware.",
            "shared_as": "Startup",
        },
        "Startup",
        "Startup",
        "TechCrunch Disrupt 2024",
                4,
    ),
    (
        "Elena Rostova",
        {
            "name": "Elena Rostova",
            "title": "Director of Growth",
            "company": "CloudScale Solutions",
            "email": "elena@cloudscale.com",
            "phone": "+1-555-0144",
            "shared_as": "Supplier",
        },
        "Supplier",
        "Supplier",
        "SaaS North 2024",
        2,
    ),
    (
        "David Kim",
        {
            "name": "David Kim",
            "title": "Principal",
            "company": "Apex Capital",
            "email": "d.kim@apexcap.com",
            "linkedin": "linkedin.com/in/davidkim-apex",
            "shared_as": "Investor",
        },
        "Investor",
        "Investor",
        "SaaS North 2024",
        1,
    ),
    (
        "Jessica Taylor",
        {
            "name": "Jessica Taylor",
            "title": "Product Designer",
            "company": "Freelance",
            "email": "jess@jtaylordesign.co",
            "shared_as": "Other",
        },
        "Other",
        "Other",
        "Local Tech Meetup",
        0,
    ),
]


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Fixed Schema: Removed multi-user 'username' constraints to safely map to your v5.3 app build
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            data TEXT,
            saved_mode TEXT,
            shared_mode TEXT,
            event TEXT,
            saved_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shared_mode TEXT,
            event TEXT,
            scanned_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def seed():
    init_db()

    conn = get_conn()
    c = conn.cursor()

    for name, data, saved_mode, shared_mode, event, days_ago in SAMPLE_CONTACTS:
        ts = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")

        # Removed 'username' completely from INSERT queries
        c.execute(
            """
            INSERT INTO contacts (name, data, saved_mode, shared_mode, event, saved_at) 
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, json.dumps(data), saved_mode, shared_mode, event, ts),
        )

        c.execute(
            """
            INSERT INTO scan_log (shared_mode, event, scanned_at) 
            VALUES (?, ?, ?)
            """,
            (shared_mode, event, ts),
        )

    conn.commit()
    conn.close()
    print(f"Successfully seeded {len(SAMPLE_CONTACTS)} contacts and log analytics metrics directly into {DB_PATH}.")


if __name__ == "__main__":
    # Option B bypass: Ignores extra sys.argv flags passed during execution and runs cleanly
    seed()