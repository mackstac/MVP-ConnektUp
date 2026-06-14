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
        "resume": "https://www.teslarati.com/wp-content/uploads/2016/04/elon-musk-one-page-resume.jpg",
        "pitch": "Making life multiplanetary and accelerating the transition to sustainable energy.", 
        "shared_as": "Investor"
    }, "Investor", "Investor", "Tech Founders Summit", 1),

    ("Sam Altman", {
        "name": "Sam Altman", 
        "company": "OpenAI", 
        "title": "CEO",
        "email": "sam@openai.com", 
        "website": "openai.com",
        "resume": "https://upload.wikimedia.org/wikipedia/commons/e/ec/Sam_Altman_at_TechCrunch_Disrupt_San_Francisco_2013_%28cropped%29.jpg",
        "pitch": "Ensuring that artificial general intelligence benefits all of humanity.", 
        "shared_as": "Startup"
    }, "Startup", "Startup", "Tech Founders Summit", 1),
]


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
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


def set_setting(key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value)),
    )
    conn.commit()
    conn.close()


def seed():
    init_db()

    set_setting("profile", SAMPLE_PROFILE)
    set_setting("modes", DEFAULT_MODES)
    set_setting("visibility", DEFAULT_VISIBILITY)
    set_setting("current_event", "Tech Founders Summit")
    # Added "Tech Founders Summit" to known events array below
    set_setting("known_events", ["Demo Day 2026", "Founder Meetup - March", "Tech Founders Summit"])

    conn = get_conn()
    c = conn.cursor()

    for name, data, saved_mode, shared_mode, event, days_ago in SAMPLE_CONTACTS:
        ts = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")
        c.execute(
            "INSERT INTO contacts (name, data, saved_mode, shared_mode, event, saved_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, json.dumps(data), saved_mode, shared_mode, event, ts),
        )
        c.execute(
            "INSERT INTO scan_log (shared_mode, event, scanned_at) VALUES (?, ?, ?)",
            (shared_mode, event, ts),
        )

    conn.commit()
    conn.close()
    print(f"Seeded {len(SAMPLE_CONTACTS)} sample contacts and scan log entries into {DB_PATH}.")


if __name__ == "__main__":
    seed()