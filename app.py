"""
Connexa - Production MVP (v6.0)
----------------------------------------
Features included:
1. Multi-User Authentication: Streamlit-Authenticator framework layer.
2. Isolated Database Schema: Rows are bound strictly to user sessions.
3. Local vs Global Purge: Clear individual user rows or wipe structural assets.
4. Auto-Isolated Demo Injection: Passes active user tags to seed utilities.
5. International Country Codes: Compact dropdown selector.
6. Self-Scan Prevention: Blocks users from saving their own profile name.
7. Multi-Format Resume Uploader: Supports PDF, PNG, and JPG.
8. Pyzbar QR Scanner Engine: Decodes dense QR images instantly.
9. Responsive Typography: HTML/CSS clamp structures tailored for Dark Mode.
10. Clean UI Defaults: Left sidebar panel collapsed by default on launch.
"""

import base64
import json
import re
import sqlite3
from datetime import datetime
from io import BytesIO

import pandas as pd
import qrcode
import streamlit as st
import streamlit_authenticator as stauth
from PIL import Image
from pyzbar.pyzbar import decode

DB_PATH = "contacts.db"

DEFAULT_FIELDS = ["name", "title", "company", "email", "phone", "linkedin", "website", "pitch", "bio"]
DEFAULT_MODES = ["Investor", "Startup", "Supplier", "Other"]
DEFAULT_VISIBILITY = {
    "Investor": ["name", "title", "company", "email", "linkedin"],
    "Startup": ["name", "title", "company", "email", "website", "pitch"],
    "Supplier": ["name", "title", "company", "email", "phone"],
    "Other": ["name", "company", "email"],
}

COUNTRY_CODES = [
    ("+1", "US/CA +1"),
    ("+44", "UK +44"),
    ("+91", "IN +91"),
    ("+61", "AU +61"),
    ("+49", "DE +49"),
    ("+33", "FR +33"),
    ("+81", "JP +81"),
    ("+86", "CN +86"),
    ("+55", "BR +55"),
    ("+34", "ES +34"),
    ("+39", "IT +39"),
]

# ---------------------------------------------------------------------------
# Data Validation Helpers
# ---------------------------------------------------------------------------
def is_valid_email(email_str):
    if not email_str: 
        return True  
    return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email_str.strip()))

def is_valid_link(link_str):
    if not link_str: 
        return True
    return link_str.strip().startswith(("http://", "https://"))

def is_valid_linkedin(li_str):
    if not li_str: 
        return True
    return "linkedin.com/" in li_str and li_str.strip().startswith(("http://", "https://"))

# ---------------------------------------------------------------------------
# Database Layer (User-Isolated Schema Architecture)
# ---------------------------------------------------------------------------
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


def save_contact(username, name, data, saved_mode, shared_mode, event):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO contacts (username, name, data, saved_mode, shared_mode, event, saved_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (username, name, json.dumps(data), saved_mode, shared_mode, event, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def contact_exists(username, name, event):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM contacts WHERE LOWER(username) = LOWER(?) AND LOWER(name) = LOWER(?) AND LOWER(event) = LOWER(?)", 
        (username, name, event)
    )
    row = c.fetchone()
    conn.close()
    return row is not None


def get_contacts(username):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, name, data, saved_mode, shared_mode, event, saved_at "
        "FROM contacts WHERE LOWER(username) = LOWER(?) ORDER BY saved_at DESC", 
        (username,)
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


def log_scan(username, shared_mode, event):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO scan_log (username, shared_mode, event, scanned_at) VALUES (?, ?, ?, ?)",
        (username, shared_mode, event, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def get_scan_log(username):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT shared_mode, event, scanned_at FROM scan_log WHERE LOWER(username) = LOWER(?) ORDER BY scanned_at", 
        (username,)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_known_events(username):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT DISTINCT event FROM contacts WHERE LOWER(username) = LOWER(?) AND event IS NOT NULL AND event != ''", 
        (username,)
    )
    rows = c.fetchall()
    conn.close()
    return sorted([r[0] for r in rows])


# ---------------------------------------------------------------------------
# Authentication Utilities
# ---------------------------------------------------------------------------
def load_authenticator_config():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username, name, password_hash, email FROM users")
    rows = c.fetchall()
    conn.close()
    
    config = {"credentials": {"usernames": {}}}
    for username, name, p_hash, email in rows:
        config["credentials"]["usernames"][username] = {
            "name": name,
            "password": p_hash,
            "email": email
        }
    config["cookie"] = {"name": "connexa_cookie", "key": "connexa_signature_key", "expiry_days": 30}
    return config


def register_new_user(username, name, plain_password, email):
    conn = get_conn()
    c = conn.cursor()
    try:
        hashed_password = stauth.Hasher([plain_password]).generate()[0]
        c.execute(
            "INSERT INTO users (username, name, password_hash, email) VALUES (?, ?, ?, ?)", 
            (username.strip().lower(), name, hashed_password, email)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


# ---------------------------------------------------------------------------
# Core QR Utilities
# ---------------------------------------------------------------------------
def decode_qr_from_image(image: Image.Image):
    try:
        decoded_objects = decode(image)
        if decoded_objects:
            return decoded_objects[0].data.decode("utf-8")
    except Exception:
        pass
    return None


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
# App UI Layout Helpers
# ---------------------------------------------------------------------------
def render_business_card(data):
    if not data:
        return
    
    if "raw_text" in data:
        st.warning("Scanned unstructured QR code text:")
        st.code(data["raw_text"])
        return

    with st.container(border=True):
        name = data.get("name", "Unknown Contact")
        shared_as = data.get("shared_as", "Contact")
        
        st.markdown(f"### {name}")
        st.caption(f"Shared Profile Mode: **{shared_as}**")
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            title = data.get("title", "")
            company = data.get("company", "")
            if title or company:
                st.markdown(f"**Role:** {title} at {company}" if title and company else f"**Organization:** {title}{company}")
            if data.get("email"):
                st.markdown(f"**Email:** [{data['email']}](mailto:{data['email']})")
            if data.get("phone"):
                st.markdown(f"**Phone:** `{data['phone']}`")
        
        with col2:
            if data.get("linkedin"):
                lk = str(data["linkedin"])
                url = lk if lk.startswith(("http://", "https://")) else f"https://{lk}"
                st.markdown(f"**LinkedIn:** [View Profile]({url})")
            if data.get("website"):
                web = str(data["website"])
                url = web if web.startswith(("http://", "https://")) else f"https://{web}"
                st.markdown(f"**Website:** [Visit Site]({url})")

        if data.get("pitch"):
            st.info(f"**Elevator Pitch:**\n{data['pitch']}")
        if data.get("bio"):
            st.markdown(f"**Bio:** *{data['bio']}*")


# ---------------------------------------------------------------------------
# Session Sandbox & Security Gateway Initialization
# ---------------------------------------------------------------------------
init_db()

st.set_page_config(
    page_title="Connexa Contact Manager", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

auth_config = load_authenticator_config()
authenticator = stauth.Authenticate(
    auth_config["credentials"],
    auth_config["cookie"]["name"],
    auth_config["cookie"]["key"],
    auth_config["cookie"]["expiry_days"]
)

# ===========================================================================
# STAGE 1: GATEWAY VERIFICATION SECURITY WALL
# ===========================================================================
if not st.session_state.get("authentication_status"):
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 2, 1])
    
    with col_c:
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 25px;">
                <h1 style="font-size: 3rem; font-weight: 800; color: #FFFFFF; letter-spacing: -1px; margin-bottom: 5px;">Connexa</h1>
                <p style="font-size: 1.15rem; color: #E0E0E0; font-weight: 500;">Your personal event networking accelerator.</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        auth_tab, reg_tab = st.tabs(["Sign In to Suite", "Create Private Account"])
        
        with auth_tab:
            authenticator.login('main')
            if st.session_state["authentication_status"] is False:
                st.error("Username/password combination is incorrect.")
                
        with reg_tab:
            with st.form("Registration Form Engine"):
                st.markdown("#### Dynamic Registration Profile Setup")
                reg_user = st.text_input("Choose unique username (lowercase, alphanumeric names only)").strip().lower()
                reg_name = st.text_input("Your Full Display Name (e.g. John Doe)")
                reg_email = st.text_input("Email Address Address")
                reg_pass = st.text_input("Secure Account Password", type="password")
                submit_reg = st.form_submit_button("Register Account Details", use_container_width=True)
                
                if submit_reg:
                    if not reg_user or not reg_pass or not reg_name:
                        st.error("All structural initialization parameter boxes require valid values.")
                    elif not re.match(r"^[a-zA-Z0-9_]+$", reg_user):
                        st.error("User ID names may only use simple letters, numbers, and underscore tracking traits.")
                    else:
                        if register_new_user(reg_user, reg_name, reg_pass, reg_email):
                            st.success("Account committed perfectly! Switch over to the Sign In tab to enter.")
                        else:
                            st.error("That target username signature is already checked out by an active user pool link.")

# ===========================================================================
# STAGE 2: SECURED MAIN SYSTEM WORKSPACE
# ===========================================================================
else:
    current_user = st.session_state["username"]
    display_name = st.session_state["name"]

    bc1, bc2 = st.columns([10, 2])
    with bc1:
        st.title("Connexa Workspace")
        st.caption(f"Secure Node Sandbox: **{display_name}** (`@{current_user}`)")
    with bc2:
        st.markdown("<br>", unsafe_allow_html=True)
        authenticator.logout("Exit System", "main")

    # Establish sandboxed operational memory
    if "profile" not in st.session_state:
        st.session_state["profile"] = {"name": display_name}
    if "resume_file_data" not in st.session_state:
        st.session_state["resume_file_data"] = None
    if "resume_file_name" not in st.session_state:
        st.session_state["resume_file_name"] = ""
    if "resume_file_type" not in st.session_state:
        st.session_state["resume_file_type"] = ""
    if "modes" not in st.session_state:
        st.session_state["modes"] = DEFAULT_MODES.copy()
    if "visibility" not in st.session_state:
        st.session_state["visibility"] = DEFAULT_VISIBILITY.copy()
    if "current_event" not in st.session_state:
        st.session_state["current_event"] = ""

    tab_profile, tab_scan, tab_contacts, tab_analytics = st.tabs(
        ["My Profile", "Scan & Save", "My Contacts", "Analytics"]
    )

    # ---------------------------------------------------------------------------
    # Tab 1: My Profile
    # ---------------------------------------------------------------------------
    with tab_profile:
        st.subheader("1. Profile Configuration")
        profile = st.session_state["profile"]
        modes = st.session_state["modes"]
        visibility = st.session_state["visibility"]

        cols = st.columns(2)
        new_profile = {}
        validation_errors = []
        
        for i, field in enumerate(DEFAULT_FIELDS):
            col = cols[i % 2]
            
            if field == "phone":
                saved_phone = profile.get("phone", "")
                current_code_idx = 0
                raw_phone_num = saved_phone
                
                for idx, (code, label) in enumerate(COUNTRY_CODES):
                    if saved_phone.startswith(code):
                        current_code_idx = idx
                        raw_phone_num = saved_phone[len(code):].strip()
                        break
                
                with col:
                    st.markdown("<label style='font-size:14px; font-weight:500;'>Phone Number (Digits only)</label>", unsafe_allow_html=True)
                    p_col1, p_col2 = st.columns([1, 4])
                    
                    chosen_label = p_col1.selectbox(
                        "Code", [c[1] for c in COUNTRY_CODES], index=current_code_idx, 
                        key="profile_phone_code", label_visibility="collapsed"
                    )
                    actual_code = COUNTRY_CODES[[c[1] for c in COUNTRY_CODES].index(chosen_label)][0]
                    entered_num = p_col2.text_input(
                        "Digits", value=raw_phone_num, placeholder="5550199",
                        key="profile_phone_digits", label_visibility="collapsed"
                    )
                    
                    clean_num = entered_num.strip()
                    if clean_num:
                        if not clean_num.isdigit():
                            st.error("Phone field must contain digits only.")
                            validation_errors.append("Phone tracking string invalid.")
                        new_profile["phone"] = f"{actual_code} {clean_num}"
                    else:
                        new_profile["phone"] = ""

            elif field == "email":
                val = col.text_input("Email Address", value=profile.get("email", ""), key="profile_email")
                if val and not is_valid_email(val):
                    col.error("Invalid email format.")
                    validation_errors.append("Invalid Email")
                new_profile["email"] = val.strip()

            elif field == "linkedin":
                val = col.text_input("LinkedIn Profile URL", value=profile.get("linkedin", ""), key="profile_linkedin")
                if val and not is_valid_linkedin(val):
                    col.error("LinkedIn URL must contain 'linkedin.com/'")
                    validation_errors.append("Invalid LinkedIn link")
                new_profile["linkedin"] = val.strip()

            elif field == "website":
                val = col.text_input("Website URL", value=profile.get("website", ""), key="profile_website")
                if val and not is_valid_link(val):
                    col.error("Website link must start with http:// or https://")
                    validation_errors.append("Invalid Website link")
                new_profile["website"] = val.strip()

            elif field == "name":
                new_profile[field] = col.text_input("Name *", value=profile.get(field, display_name), key=f"profile_{field}")
            elif field == "company":
                with col:
                    is_employed = st.checkbox("Currently affiliated with an organization", value=True, key="profile_employment_status_toggle")
                    if is_employed:
                        new_profile[field] = st.text_input(
                            "Company / Organization *", 
                            value=profile.get(field, "") if profile.get(field) not in ["Seeking New Opportunities", "Freelance Consultant", "Independent", "Student"] else "", 
                            key=f"profile_{field}_input"
                        )
                    else:
                        status_options = ["Seeking New Opportunities", "Freelance Consultant", "Independent", "Student"]
                        saved_status = profile.get(field, "Seeking New Opportunities")
                        default_status_idx = status_options.index(saved_status) if saved_status in status_options else 0
                        new_profile[field] = st.selectbox("Professional Status *", status_options, index=default_status_idx, key=f"profile_{field}_select")
            else:
                new_profile[field] = col.text_input(field.capitalize(), value=profile.get(field, ""), key=f"profile_{field}")

        st.divider()
        st.markdown("##### Attach Resume File")
        resume_file = st.file_uploader("Upload resume (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])
        
        if resume_file is not None:
            st.session_state["resume_file_data"] = resume_file.read()
            st.session_state["resume_file_name"] = resume_file.name
            st.session_state["resume_file_type"] = resume_file.type
            st.success(f"File '{resume_file.name}' attached successfully.")

        if st.session_state["resume_file_data"] and st.button("Clear staged resume attachment"):
            st.session_state["resume_file_data"] = None
            st.session_state["resume_file_name"] = ""
            st.session_state["resume_file_type"] = ""
            st.rerun()

        if st.button("Save Profile Settings"):
            if not new_profile.get("name") or not new_profile["name"].strip():
                st.error("Name is required.")
            elif not new_profile.get("company") or not new_profile["company"].strip():
                st.error("Company / Status field value is required.")
            elif validation_errors:
                st.error("Fix form styling errors before updating.")
            else:
                st.session_state["profile"] = new_profile
                st.success("Profile saved locally to current user partition.")
                st.rerun()

        st.divider()
        st.subheader("2. Modes and Field Visibility")
        
        with st.expander("Add Custom Session Mode"):
            new_mode_name = st.text_input("Mode name")
            if st.button("Add Mode"):
                if new_mode_name and new_mode_name not in modes:
                    st.session_state["modes"].append(new_mode_name)
                    st.session_state["visibility"][new_mode_name] = ["name", "email"]
                    st.success(f"Added custom mode '{new_mode_name}'.")
                    st.rerun()

        selected_mode = st.selectbox("Configure visibility for mode", modes)
        visible_fields = visibility.get(selected_mode, [])
        new_visible = []
        vis_cols = st.columns(3)
        for i, field in enumerate(DEFAULT_FIELDS):
            col = vis_cols[i % 3]
            if col.checkbox(field.capitalize(), value=(field in visible_fields), key=f"vis_{selected_mode}_{field}"):
                new_visible.append(field)

        if st.button("Save Visibility Configuration"):
            st.session_state["visibility"][selected_mode] = new_visible
            st.success(f"Visibility for '{selected_mode}' updated.")
            st.rerun()

        st.divider()
        st.subheader("3. Live QR Preview")
        qr_mode = st.selectbox("Generate QR code representation", modes)
        preview_visible = visibility.get(qr_mode, [])
        
        payload = {f: new_profile.get(f, "") for f in preview_visible if f in new_profile and new_profile.get(f)}
        payload["shared_as"] = qr_mode

        preview_col, qr_col = st.columns([2, 1])
        with preview_col:
            st.markdown("##### Digital Card Preview")
            render_business_card(payload)

        with qr_col:
            img_bytes = make_qr_image_bytes(payload)
            st.image(img_bytes, caption=f"{qr_mode} mode QR", width=220)
            st.download_button("Download QR Card", img_bytes, file_name=f"{qr_mode.lower().replace(' ', '_')}_qr.png", mime="image/png")

    # ---------------------------------------------------------------------------
    # Tab 2: Scan & Save
    # ---------------------------------------------------------------------------
    with tab_scan:
        st.subheader("1. Event Context")
        known_events = get_known_events(current_user)
        current_event = st.session_state["current_event"]

        event_options = ["(new event)"] + known_events
        default_index = event_options.index(current_event) if current_event in event_options else 0
        chosen_event_option = st.selectbox("Current event context", event_options, index=default_index)

        event = st.text_input("Event name", value=current_event if current_event not in known_events else "") if chosen_event_option == "(new event)" else chosen_event_option

        st.divider()
        st.subheader("2. Capture QR Code")
        source = st.radio("Capture Source", ["Camera Scan", "Upload File"], horizontal=True)

        image = None
        if source == "Camera Scan":
            img_file = st.camera_input("Scan partner profile")
            if img_file is not None: 
                image = Image.open(img_file)
        else:
            img_file = st.file_uploader("Drop QR image here", type=["png", "jpg", "jpeg"])
            if img_file is not None: 
                image = Image.open(img_file)

        decoded_data = None
        shared_mode = "Unknown"
        if image is not None:
            raw = decode_qr_from_image(image)
            if raw:
                st.success("QR matrix parsed successfully.")
                try:
                    decoded_data = json.loads(raw)
                except json.JSONDecodeError:
                    decoded_data = {"raw_text": raw}
                shared_mode = decoded_data.get("shared_as", "Unknown")

                if event and st.session_state.get("last_scanned_raw") != raw:
                    log_scan(current_user, shared_mode, event)
                    st.session_state["last_scanned_raw"] = raw
                    st.rerun()

                with st.expander("View scanned data preview", expanded=True):
                    render_business_card(decoded_data)
            else:
                st.warning("Could not resolve tracking markers.")

        if decoded_data:
            st.subheader("3. Save to Directory")
            name = st.text_input("Assign Contact Name", value=decoded_data.get("name", ""))
            
            saved_mode = st.radio("Save under category role:", modes, horizontal=True, index=modes.index(shared_mode) if shared_mode in modes else 0)

            my_saved_name = st.session_state["profile"].get("name", "").strip()
            if my_saved_name and name.strip().lower() == my_saved_name.lower():
                st.error("Self-scan restriction active. Cannot commit local profile registration into your own contact tree.")
                st.button("Save contact data", disabled=True)
            else:
                if st.button("Save contact data", type="primary"):
                    if not name or not event:
                        st.error("Name and Event scope configuration fields are required.")
                    elif contact_exists(current_user, name, event):
                        st.warning(f"Contact '{name}' already exists in this event folder.")
                    else:
                        save_contact(current_user, name, decoded_data, saved_mode, shared_mode, event)
                        st.session_state["current_event"] = event
                        st.success(f"Saved '{name}' into partition storage.")
                        st.rerun()

    # ---------------------------------------------------------------------------
    # Tab 3: My Contacts (Isolated View Layer)
    # ---------------------------------------------------------------------------
    with tab_contacts:
        st.subheader("Directory Management")
        contacts = get_contacts(current_user)
        
        if not contacts:
            st.info("Your contact directory path is currently empty.")
        else:
            df = pd.DataFrame(contacts, columns=["id", "name", "data", "saved_mode", "shared_mode", "event", "saved_at"])

            col1, col2 = st.columns(2)
            with col1:
                events = ["All Records"] + sorted(df["event"].unique().tolist())
                event_filter = st.selectbox("Filter by Event", events)
            with col2:
                mode_options = ["All Records"] + sorted(df["saved_mode"].unique().tolist())
                mode_filter = st.selectbox("Filter by Category", mode_options)

            filtered = df.copy()
            if event_filter != "All Records": 
                filtered = filtered[filtered["event"] == event_filter]
            if mode_filter != "All Records": 
                filtered = filtered[filtered["saved_mode"] == mode_filter]

            for ev in filtered["event"].unique():
                ev_df = filtered[filtered["event"] == ev]
                st.markdown(f"## Location: {ev}")

                for mode in sorted(ev_df["saved_mode"].unique()):
                    mode_df = ev_df[ev_df["saved_mode"] == mode]
                    st.markdown(f"#### Group: *{mode}*")

                    for _, row in mode_df.iterrows():
                        c1, c2 = st.columns([6, 1])
                        with c1:
                            render_business_card(json.loads(row["data"]))
                        with c2:
                            st.caption(f"Added:\n`{row['saved_at'][:10]}`")
                            if st.button("Remove Card", key=f"del_{row['id']}"):
                                delete_contact(row["id"])
                                st.rerun()
                st.divider()

    # ---------------------------------------------------------------------------
    # Tab 4: Analytics
    # ---------------------------------------------------------------------------
    with tab_analytics:
        st.subheader("Interaction Analysis Matrix")
        contacts = get_contacts(current_user)
        scans = get_scan_log(current_user)

        if not contacts and not scans:
            st.info("No interactive telemetry logged for your profile cluster yet.")
        else:
            df = pd.DataFrame(contacts, columns=["id", "name", "data", "saved_mode", "shared_mode", "event", "saved_at"])
            scan_df = pd.DataFrame(scans, columns=["shared_mode", "event", "scanned_at"])

            m1, m2 = st.columns(2)
            m1.metric("Your Total Verified Contacts", len(df))
            m2.metric("Your Interaction Scans Logged", len(scan_df))

            if not df.empty:
                st.markdown("**Distribution Matrix by Category**")
                st.bar_chart(df["saved_mode"].value_counts())

# ---------------------------------------------------------------------------
# Dynamic Sidebar Control Center (Local Purge vs Global Master Controls)
# ---------------------------------------------------------------------------
st.sidebar.markdown("### Control Dashboard Panel")

with st.sidebar.expander("Admin & Account Maintenance", expanded=False):
    # Action 1: User-Isolated Purge (Available to any logged-in user)
    if st.session_state.get("authentication_status"):
        st.markdown("#### User Data Utility")
        if st.button("Purge MY Profile & Contacts Only", use_container_width=True):
            conn = get_conn()
            c = conn.cursor()
            c.execute("DELETE FROM contacts WHERE LOWER(username) = LOWER(?)", (current_user,))
            c.execute("DELETE FROM scan_log WHERE LOWER(username) = LOWER(?)", (current_user,))
            conn.commit()
            conn.close()
            st.success("Your individual user metrics have been wiped safely.")
            st.rerun()
            
    st.divider()
    
    # Action 2: Master Global Developer Overrides
    st.markdown("#### Master Developer Overrides")
    admin_password = st.text_input("Master Admin Password", type="password")
    correct_password = st.secrets.get("ADMIN_PASSWORD", "admin123")
    
    if admin_password == correct_password:
        st.success("Access Authorized")
        
        if st.button("Load Demo Records to MY Profile", use_container_width=True):
            if not st.session_state.get("authentication_status"):
                st.error("Please log into a valid account before applying mock target profiles.")
            else:
                try:
                    import subprocess
                    subprocess.run(["python", "seed_demo_data.py", current_user], check=True)
                    st.success(f"Demo entries loaded onto user node: @{current_user}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Seeding failure: {e}")
                
        st.divider()
        st.markdown("<span style='color:red; font-weight:bold;'>Global Wipe Action</span>", unsafe_allow_html=True)
        if st.button("GLOBAL SYSTEM RESET (Flush All Users)", use_container_width=True, type="primary"):
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("DROP TABLE IF EXISTS users")
                c.execute("DROP TABLE IF EXISTS contacts")
                c.execute("DROP TABLE IF EXISTS scan_log")
                conn.commit()
                conn.close()
                st.cache_resource.clear()
                st.success("Entire system cluster database dropped and initialized.")
                st.rerun()
            except Exception as e:
                st.error(f"Global purge operation failure: {e}")
    elif admin_password:
        st.error("Invalid credentials.")