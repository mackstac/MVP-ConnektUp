"""
Networking Contact Scanner - MVP (v2.1)
----------------------------------------
New in this version:
- Duplicate Prevention: Automatically checks if a contact name is already 
  saved under the current event before writing to the database.
- Dynamic profile + per-mode visibility + live QR preview.
- Event context tracking & smart contact grouping.
- Visual business card layouts instead of raw JSON text.

Run with:
    streamlit run app.py
"""

import json
import sqlite3
from datetime import datetime
from io import BytesIO

import cv2
import numpy as np
import pandas as pd
import qrcode
import streamlit as st
from PIL import Image

DB_PATH = "contacts.db"

DEFAULT_FIELDS = ["name", "title", "company", "email", "phone", "linkedin", "website", "pitch", "bio"]
DEFAULT_MODES = ["Investor", "Startup", "Supplier", "Other"]
DEFAULT_VISIBILITY = {
    "Investor": ["name", "title", "company", "email", "linkedin"],
    "Startup": ["name", "title", "company", "email", "website", "pitch"],
    "Supplier": ["name", "title", "company", "email", "phone"],
    "Other": ["name", "company", "email"],
}

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

    # Seed default settings if they don't exist yet
    defaults = {
        "profile": {},
        "modes": DEFAULT_MODES,
        "visibility": DEFAULT_VISIBILITY,
        "current_event": "",
        "known_events": [],
    }
    for key, value in defaults.items():
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        if c.fetchone() is None:
            c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, json.dumps(value)))
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return default
    return json.loads(row[0])


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


def save_contact(name, data, saved_mode, shared_mode, event):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO contacts (name, data, saved_mode, shared_mode, event, saved_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, json.dumps(data), saved_mode, shared_mode, event, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def contact_exists(name, event):
    """Safety check: Returns True if this contact name already exists for this specific event."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM contacts WHERE LOWER(name) = LOWER(?) AND LOWER(event) = LOWER(?)", (name, event))
    row = c.fetchone()
    conn.close()
    return row is not None


def get_contacts():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, name, data, saved_mode, shared_mode, event, saved_at "
        "FROM contacts ORDER BY saved_at DESC"
    )
    rows = c.fetchall()
    conn.close()
    return rows


def delete_contact(contact_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()


def log_scan(shared_mode, event):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO scan_log (shared_mode, event, scanned_at) VALUES (?, ?, ?)",
        (shared_mode, event, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def get_scan_log():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT shared_mode, event, scanned_at FROM scan_log ORDER BY scanned_at")
    rows = c.fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# QR helpers
# ---------------------------------------------------------------------------
def decode_qr_from_image(image: Image.Image):
    img_array = np.array(image.convert("RGB"))
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img_array)
    return data or None


def make_qr_image_bytes(payload: dict) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(payload))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# App UI Styling Helpers
# ---------------------------------------------------------------------------
def render_business_card(data):
    """Transforms a raw data dictionary into a beautifully styled digital card."""
    if not data:
        return
    
    if "raw_text" in data:
        st.warning("⚠️ Scanned unstructured QR code text:")
        st.code(data["raw_text"])
        return

    with st.container(border=True):
        name = data.get("name", "Unknown Contact")
        shared_as = data.get("shared_as", "Contact")
        
        st.markdown(f"### 👤 {name}")
        st.caption(f"🏷️ Shared Profile Mode: **{shared_as}**")
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            title = data.get("title", "")
            company = data.get("company", "")
            if title or company:
                st.markdown(f"💼 **Role:** {title} at {company}" if title and company else f"💼 **Org:** {title}{company}")
            if data.get("email"):
                st.markdown(f"📧 **Email:** [{data['email']}](mailto:{data['email']})")
            if data.get("phone"):
                st.markdown(f"📞 **Phone:** `{data['phone']}`")
        
        with col2:
            if data.get("linkedin"):
                lk = str(data["linkedin"])
                url = lk if lk.startswith(("http://", "https://")) else f"https://{lk}"
                st.markdown(f"🔗 **LinkedIn:** [View Profile]({url})")
            if data.get("website"):
                web = str(data["website"])
                url = web if web.startswith(("http://", "https://")) else f"https://{web}"
                st.markdown(f"🌐 **Website:** [Visit Site]({url})")

            if data.get("resume"):
                res = str(data["resume"])
                url = res if res.startswith(("http://", "https://")) else f"https://{res}"
                st.markdown(f"📄 **Resume:** [View Resume Image]({url})")

        if data.get("pitch"):
            st.info(f"💡 **Elevator Pitch:**\n{data['pitch']}")
        if data.get("bio"):
            st.markdown(f"📝 **Bio:** *{data['bio']}*")


# ---------------------------------------------------------------------------
# App Execution Start
# ---------------------------------------------------------------------------
init_db()

st.set_page_config(page_title="Networking Contact Scanner", page_icon="📱", layout="wide")
st.title("SmarNet")
st.caption(
    "Build a dynamic profile, scan contacts with event context, "
    "and explore your network with smart filters and analytics."
)

tab_profile, tab_scan, tab_contacts, tab_analytics = st.tabs(
    ["My Profile", "Scan & Save", "My Contacts", "Analytics"]
)

# ---------------------------------------------------------------------------
# Tab 1: My Profile
# ---------------------------------------------------------------------------
with tab_profile:
    st.subheader("1. Your profile fields")
    st.write("Fill in whatever you're comfortable sharing - you'll control what's visible per mode below.")

    profile = get_setting("profile", {})
    modes = get_setting("modes", DEFAULT_MODES)
    visibility = get_setting("visibility", DEFAULT_VISIBILITY)

    cols = st.columns(2)
    new_profile = {}
    for i, field in enumerate(DEFAULT_FIELDS):
        col = cols[i % 2]
        new_profile[field] = col.text_input(
            field.capitalize(), value=profile.get(field, ""), key=f"profile_{field}"
        )

    if st.button("Save profile"):
        set_setting("profile", new_profile)
        profile = new_profile
        st.success("Profile saved.")

    st.divider()
    st.subheader("2. Modes and field visibility")
    st.write("Add modes for the different ways you network, then choose which fields each mode shares.")

    with st.expander("Add a new mode"):
        new_mode_name = st.text_input("Mode name", key="new_mode_name")
        if st.button("Add mode"):
            if new_mode_name and new_mode_name not in modes:
                modes.append(new_mode_name)
                visibility[new_mode_name] = ["name", "email"]
                set_setting("modes", modes)
                set_setting("visibility", visibility)
                st.success(f"Added mode '{new_mode_name}'.")
                st.rerun()
            elif new_mode_name in modes:
                st.warning("That mode already exists.")

    selected_mode = st.selectbox("Configure visibility for mode", modes, key="vis_mode_select")

    visible_fields = visibility.get(selected_mode, [])
    new_visible = []
    vis_cols = st.columns(3)
    for i, field in enumerate(DEFAULT_FIELDS):
        col = vis_cols[i % 3]
        checked = col.checkbox(
            field.capitalize(), value=(field in visible_fields), key=f"vis_{selected_mode}_{field}"
        )
        if checked:
            new_visible.append(field)

    if st.button("Save visibility for this mode"):
        visibility[selected_mode] = new_visible
        set_setting("visibility", visibility)
        st.success(f"Visibility for '{selected_mode}' updated.")
        visible_fields = new_visible

    st.divider()
    st.subheader("3. Live QR preview")
    st.write("This updates live as you edit your profile and visibility settings above.")

    qr_mode = st.selectbox("Preview and generate QR for mode", modes, key="qr_mode_select")
    preview_visible = visibility.get(qr_mode, [])
    payload = {f: new_profile.get(f, "") for f in preview_visible if new_profile.get(f)}
    payload["shared_as"] = qr_mode

    preview_col, qr_col = st.columns([2, 1])
    with preview_col:
        st.write("This QR code will share:")
        st.json(payload)
    with qr_col:
        img_bytes = make_qr_image_bytes(payload)
        st.image(img_bytes, caption=f"{qr_mode} mode QR code", width=220)
        st.download_button(
            "Download QR code",
            img_bytes,
            file_name=f"{qr_mode.lower().replace(' ', '_')}_mode_qr.png",
            mime="image/png",
        )

# ---------------------------------------------------------------------------
# Tab 2: Scan & Save -> Anti-Duplicate Logic Added Here
# ---------------------------------------------------------------------------
with tab_scan:
    st.subheader("1. Event context")

    known_events = get_setting("known_events", [])
    current_event = get_setting("current_event", "")

    event_options = ["(new event)"] + known_events
    default_index = event_options.index(current_event) if current_event in event_options else 0
    chosen_event_option = st.selectbox("Current event", event_options, index=default_index)

    if chosen_event_option == "(new event)":
        event = st.text_input(
            "Event name", value=current_event if current_event not in known_events else ""
        )
    else:
        event = chosen_event_option

    st.caption(
        "Every contact you save is tagged with this event, so you can later "
        "filter 'everyone I met at X'. The last event you used is remembered as the default."
    )

    st.divider()
    st.subheader("2. Capture the QR code")

    source = st.radio("Image source", ["Camera", "Upload image"], horizontal=True)

    image = None
    if source == "Camera":
        img_file = st.camera_input("Point your camera at the QR code")
        if img_file is not None:
            image = Image.open(img_file)
    else:
        img_file = st.file_uploader("Upload a QR code image", type=["png", "jpg", "jpeg"])
        if img_file is not None:
            image = Image.open(img_file)

    decoded_data = None
    shared_mode = "Unknown"
    if image is not None:
        raw = decode_qr_from_image(image)
        if raw:
            st.success("QR code detected.")
            try:
                decoded_data = json.loads(raw)
            except json.JSONDecodeError:
                decoded_data = {"raw_text": raw}
            shared_mode = decoded_data.get("shared_as", "Unknown")

            if event and st.session_state.get("last_scanned_raw") != raw:
                log_scan(shared_mode, event)
                st.session_state["last_scanned_raw"] = raw

            with st.expander("View scanned data preview", expanded=True):
                render_business_card(decoded_data)
        else:
            st.warning("No QR code found in this image. Try again with a clearer shot.")

    if decoded_data:
        st.subheader("3. Save this contact")

        default_name = decoded_data.get("name", "")
        name = st.text_input("Contact name", value=default_name)

        modes = get_setting("modes", DEFAULT_MODES)
        st.write("Save under which mode?")
        default_mode_index = modes.index(shared_mode) if shared_mode in modes else 0
        saved_mode = st.radio(
            "Mode", modes, horizontal=True, label_visibility="collapsed",
            index=default_mode_index, key="save_mode",
        )

        if st.button("Save contact", type="primary"):
            if not name:
                st.error("Please enter a name before saving.")
            elif not event:
                st.error("Please set an event name above before saving.")
            # NEW SCRIPT CHECK: Stops duplicates from getting created!
            elif contact_exists(name, event):
                st.warning(f"⚠️ '{name}' is already in your contacts under the '{event}' event context.")
            else:
                save_contact(name, decoded_data, saved_mode, shared_mode, event)
                if event not in known_events:
                    known_events.append(event)
                    set_setting("known_events", known_events)
                set_setting("current_event", event)
                st.success(f"Saved '{name}' under '{saved_mode}' mode, tagged to '{event}'.")

# ---------------------------------------------------------------------------
# Tab 3: My Contacts
# ---------------------------------------------------------------------------
with tab_contacts:
    st.subheader("Your contacts")

    contacts = get_contacts()
    if not contacts:
        st.info("No contacts saved yet. Go scan a QR code in the 'Scan & Save' tab.")
    else:
        df = pd.DataFrame(
            contacts,
            columns=["id", "name", "data", "saved_mode", "shared_mode", "event", "saved_at"],
        )

        col1, col2 = st.columns(2)
        with col1:
            events = ["All"] + sorted(df["event"].unique().tolist())
            current_event = get_setting("current_event", "")
            default_event_index = events.index(current_event) if current_event in events else 0
            event_filter = st.selectbox("Event", events, index=default_event_index)
        with col2:
            mode_options = ["All"] + sorted(df["saved_mode"].unique().tolist())
            mode_filter = st.selectbox("Mode", mode_options)

        filtered = df.copy()
        if event_filter != "All":
            filtered = filtered[filtered["event"] == event_filter]
        if mode_filter != "All":
            filtered = filtered[filtered["saved_mode"] == mode_filter]

        st.write(f"Showing {len(filtered)} of {len(df)} contact(s).")

        for ev in filtered["event"].unique():
            ev_df = filtered[filtered["event"] == ev]
            st.markdown(f"## 📍 {ev} &nbsp; ({len(ev_df)})")

            for mode in sorted(ev_df["saved_mode"].unique()):
                mode_df = ev_df[ev_df["saved_mode"] == mode]
                st.markdown(f"#### 🏷️ Filed as: *{mode}*")

                for _, row in mode_df.iterrows():
                    data = json.loads(row["data"])
                    
                    c1, c2 = st.columns([6, 1])
                    with c1:
                        render_business_card(data)
                    with c2:
                        st.caption(f"📅 Saved At:\n`{row['saved_at'][:10]}`")
                        if st.button("Delete Contact", key=f"del_{row['id']}", type="secondary"):
                            delete_contact(row["id"])
                            st.rerun()
            st.divider()

# ---------------------------------------------------------------------------
# Tab 4: Analytics
# ---------------------------------------------------------------------------
with tab_analytics:
    st.subheader("Network analytics")

    contacts = get_contacts()
    scans = get_scan_log()

    if not contacts and not scans:
        st.info("No data yet - scan and save some contacts to see analytics here.")
    else:
        df = pd.DataFrame(
            contacts,
            columns=["id", "name", "data", "saved_mode", "shared_mode", "event", "saved_at"],
        )
        scan_df = pd.DataFrame(scans, columns=["shared_mode", "event", "scanned_at"])

        m1, m2, m3 = st.columns(3)
        m1.metric("Saved contacts", len(df))
        m2.metric("Total scans", len(scan_df))
        m3.metric("Events tracked", df["event"].nunique() if not df.empty else 0)

        if not df.empty:
            st.markdown("**Contacts by mode (how you filed them)**")
            st.bar_chart(df["saved_mode"].value_counts())

            st.markdown("**Contacts by event**")
            st.bar_chart(df["event"].value_counts())

            st.markdown("**Saves over time**")
            df["date"] = pd.to_datetime(df["saved_at"]).dt.date
            st.bar_chart(df.groupby("date").size())

        if not scan_df.empty:
            st.markdown("**Modes people shared with you (from scanned QR codes)**")
            st.bar_chart(scan_df["shared_mode"].value_counts())