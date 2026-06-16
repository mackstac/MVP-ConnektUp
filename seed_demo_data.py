"""
Seed demo data
-----------------
Populates contacts.db with a sample profile, mode/visibility settings, and
a handful of realistic contacts + scan log entries across multiple events -
so the app has something to show (especially the My Contacts and Analytics
tabs) before your demo, instead of starting from a blank slate.

Run this BEFORE starting the app:
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

# (name, data dict, saved_mode, shared_mode, event, days_ago)
SAMPLE_CONTACTS = [
    ("Priya Shah", {"name": "Priya Shah", "company": "Greenfield Capital", "title": "Partner",
                    "email": "priya@greenfieldvc.com", "linkedin": "linkedin.com/in/priyashah",
                    "shared_as": "Investor"}, "Investor", "Investor", "Demo Day 2026", 0),

    ("Marcus Lee", {"name": "Marcus Lee", "company": "Northstar Ventures", "title": "Principal",
                    "email": "marcus@northstar.vc", "linkedin": "linkedin.com/in/marcuslee",
                    "shared_as": "Investor"}, "Investor", "Investor", "Demo Day 2026", 0),

    ("Sofia Chen", {"name": "Sofia Chen", "company": "Loop Robotics", "title": "Co-founder",
                    "email": "sofia@looprobotics.com", "website": "looprobotics.com",
                    "pitch": "Autonomous warehouse robots", "shared_as": "Startup"},
     "Startup", "Startup", "Demo Day 2026", 0),

    ("David Okafor", {"name": "David Okafor", "company": "PackRight Supplies", "title": "Sales Manager",
                      "email": "david@packright.com", "phone": "+1-555-0123",
                      "shared_as": "Supplier"}, "Supplier", "Supplier", "Demo Day 2026", 0),

    ("Lena Brooks", {"name": "Lena Brooks", "company": "TechCrunch", "title": "Reporter",
                     "email": "lena@techcrunch.com", "shared_as": "Other"},
     "Other", "Other", "Demo Day 2026", 0),

    ("Tom Walker", {"name": "Tom Walker", "company": "BlueSky Capital", "title": "Associate",
                    "email": "tom@blueskycapital.com", "linkedin": "linkedin.com/in/tomwalker",
                    "shared_as": "Investor"}, "Investor", "Investor", "Founder Meetup - March", 5),

    ("Nina Patel", {"name": "Nina Patel", "company": "Forge Components", "title": "Account Manager",
                    "email": "nina@forgecomponents.com", "phone": "+1-555-0199",
                    "shared_as": "Supplier"}, "Supplier", "Supplier", "Founder Meetup - March", 5),

    # --- ADDED VIP CONTACTS WITH RESUMES ---
    ("Elon Musk", {
        "name": "Elon Musk", 
        "company": "SpaceX / Tesla / xAI", 
        "title": "Technoking & Chief Engineer",
        "email": "elon@spacex.com", 
        "linkedin": "linkedin.com/in/elon-musk", 
        "website": "spacex.com",
        "resume": "https://postimg.cc/21HYXs74",
        "pitch": "Making life multiplanetary and accelerating the transition to sustainable energy.", 
        "shared_as": "Investor"
    }, "Investor", "Investor", "Tech Founders Summit", 1),

    ("Sam Altman", {
        "name": "Sam Altman", 
        "company": "OpenAI", 
        "title": "CEO",
        "email": "sam@openai.com", 
        "website": "openai.com",
        "resume": "https://postimg.cc/MfwgG5mg",
        "pitch": "Ensuring that artificial general intelligence benefits all of humanity.", 
        "shared_as": "Startup"
    }, "Startup", "Startup", "Tech Founders Summit", 1),
]


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            name TEXT,
            password_hash TEXT,
            email TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
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
            username TEXT,
            shared_mode TEXT,
            event TEXT,
            scanned_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def seed(target_username):
    init_db()

    conn = get_conn()
    c = conn.cursor()

    for name, data, saved_mode, shared_mode, event, days_ago in SAMPLE_CONTACTS:
        ts = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")
        
        # Inserts contacts bound specifically to the authenticated user partition
        c.execute(
            """
            INSERT INTO contacts (username, name, data, saved_mode, shared_mode, event, saved_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (target_username, name, json.dumps(data), saved_mode, shared_mode, event, ts),
        )
        
        # Logs interaction history bound specifically to the authenticated user partition
        c.execute(
            """
            INSERT INTO scan_log (username, shared_mode, event, scanned_at) 
            VALUES (?, ?, ?, ?)
            """,
            (target_username, shared_mode, event, ts),
        )

    conn.commit()
    conn.close()
    print(f"Seeded {len(SAMPLE_CONTACTS)} sample contacts and scan log entries into {DB_PATH} for user @{target_username}.")


if __name__ == "__main__":
    # Check if a specific user context was passed via app.py's developer switch
    if len(sys.argv) > 1:
        user_context_arg = sys.argv[1].strip().lower()
    else:
        user_context_arg = "admin"
        
    seed(user_context_arg)