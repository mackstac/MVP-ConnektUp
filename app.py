"""
SmarNet - Production MVP (v3.4)
----------------------------------------
Optimized for GitHub Codespaces & Streamlit Cloud

Features included:
1. International Country Codes: Compact dropdown selector with flags.
2. Self-Scan Prevention: Blocks users from saving their own profile name.
3. Resume Image Uploader: Encodes profile resume images directly into the QR payload.
4. Session-Isolated Profiles: Multi-user safe session sandboxing.
5. Pyzbar QR Scanner Engine: Decodes highly dense QR images instantly.
6. Strict Format Validation: Real-time validation for emails, links, and digits.
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

# Supported international country dialing configurations
COUNTRY_CODES = [
    ("+1", "🇺🇸/🇨🇦 +1"),
    ("+44", "🇬🇧 +44"),
    ("+91", "🇮🇳 +91"),
    ("+61", "🇦🇺 +61"),
    ("+49", "🇩🇪 +49"),
    ("+33", "🇫🇷 +33"),
    ("+81", "🇯🇵 +81"),
    ("+86", "🇨🇳 +86"),
    ("+55", "🇧🇷 +55"),
    ("+34", "🇪🇸 +34"),
    ("+39", "🇮🇹 +39"),
]

# ---------------------------------------------------------------------------
# Data Validation Helpers
# ---------------------------------------------------------------------------
def is_valid_email(email_str):
    if not email_str: 
        return True  # Allow empty if field isn't mandatory
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
# Database Layer
# ---------------------------------------------------------------------------
def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Initializes the structural tables for global real-time synchronization."""
    conn = get_conn()
    c = conn.cursor()
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


def get_known_events():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT event FROM contacts WHERE event IS NOT NULL AND event != ''")
    rows = c.fetchall()
    conn.close()
    return sorted([r[0] for r in rows])


# ---------------------------------------------------------------------------
# Core QR Utilities
# ---------------------------------------------------------------------------
def decode_qr_from_image(image: Image.Image):
    try:
        decoded_objects = decode(image)
        if decoded_objects:
            return decoded_objects[0].data.decode("utf-8")
    except Exception as e:
        print(f"Scanner engine error: {e}")
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
    """Transforms raw data into a clean digital business card."""
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

        if data.get("pitch"):
            st.info(f"💡 **Elevator Pitch:**\n{data['pitch']}")
        if data.get("bio"):
            st.markdown(f"📝 **Bio:** *{data['bio']}*")

        if data.get("resume_b64"):
            with st.expander("📄 View Attached Resume Image", expanded=False):
                try:
                    resume_bytes = base64.b64decode(data["resume_b64"])
                    st.image(resume_bytes, use_container_width=True)
                except Exception:
                    st.error("Could not render the attached resume file.")


# ---------------------------------------------------------------------------
# Session Sandbox Initialization
# ---------------------------------------------------------------------------
init_db()

if "profile" not in st.session_state:
    st.session_state["profile"] = {}
if "resume_b64" not in st.session_state:
    st.session_state["resume_b64"] = ""
if "modes" not in st.session_state:
    st.session_state["modes"] = DEFAULT_MODES.copy()
if "visibility" not in st.session_state:
    st.session_state["visibility"] = DEFAULT_VISIBILITY.copy()
if "current_event" not in st.session_state:
    st.session_state["current_event"] = ""

st.set_page_config(page_title="SmarNet Contact Manager", page_icon="📱", layout="wide")
st.title("SmarNet")
st.caption("Build a dynamic profile, scan contacts with event context, and explore your network.")

tab_profile, tab_scan, tab_contacts, tab_analytics = st.tabs(
    ["My Profile", "Scan & Save", "My Contacts", "Analytics"]
)

# ---------------------------------------------------------------------------
# Tab 1: My Profile (Enhanced Country Code Parsing, Sizes & Form Validation)
# ---------------------------------------------------------------------------
with tab_profile:
    st.subheader("1. Your profile fields")
    st.write("Fill in your info—this configuration is sandboxed safely to your device's browser window.")

    profile = st.session_state["profile"]
    modes = st.session_state["modes"]
    visibility = st.session_state["visibility"]

    cols = st.columns(2)
    new_profile = {}
    
    # Track syntax validation anomalies before committing to database schemas
    validation_errors = []
    
    for i, field in enumerate(DEFAULT_FIELDS):
        col = cols[i % 2]
        
        # CASE 1: Compact Custom Country Code Layout & Phone Rules
        if field == "phone":
            saved_phone = profile.get("phone", "")
            current_code_idx = 0
            raw_phone_num = saved_phone
            
            # Intelligently split existing numbers back out into dropdown and digits fields
            for idx, (code, label) in enumerate(COUNTRY_CODES):
                if saved_phone.startswith(code):
                    current_code_idx = idx
                    raw_phone_num = saved_phone[len(code):].strip()
                    break
            
            with col:
                st.markdown("<label style='font-size:14px; font-weight:500;'>Phone Number (Digits only)</label>", unsafe_allow_html=True)
                p_col1, p_col2 = st.columns([1, 4])  # Adjusted to [1, 4] layout to drastically shrink dropdown selector
                
                chosen_label = p_col1.selectbox(
                    "Code", [c[1] for c in COUNTRY_CODES], index=current_code_idx, 
                    key="profile_phone_code", label_visibility="collapsed"
                )
                # Lookup the raw dialing code character array matching our visual string selection
                actual_code = COUNTRY_CODES[[c[1] for c in COUNTRY_CODES].index(chosen_label)][0]
                entered_num = p_col2.text_input(
                    "Digits", value=raw_phone_num, placeholder="5550199",
                    key="profile_phone_digits", label_visibility="collapsed"
                )
                
                # Enforce digits constraint checking
                clean_num = entered_num.strip()
                if clean_num:
                    if not clean_num.isdigit():
                        st.error("⚠️ Phone field must contain digits only (no spaces, dashes, or letters).")
                        validation_errors.append("Phone tracking string contains letters or spaces.")
                    new_profile["phone"] = f"{actual_code} {clean_num}"
                else:
                    new_profile["phone"] = ""

        # CASE 2: Email Format Check
        elif field == "email":
            val = col.text_input("Email Address", value=profile.get("email", ""), key="profile_email")
            if val and not is_valid_email(val):
                col.error("⚠️ Invalid email layout format (e.g., name@domain.com)")
                validation_errors.append("Invalid Email")
            new_profile["email"] = val.strip()

        # CASE 3: LinkedIn Profile Check
        elif field == "linkedin":
            val = col.text_input("LinkedIn Profile URL", value=profile.get("linkedin", ""), key="profile_linkedin", placeholder="https://linkedin.com/in/username")
            if val and not is_valid_linkedin(val):
                col.error("⚠️ LinkedIn field must be a valid link containing 'linkedin.com/'")
                validation_errors.append("Invalid LinkedIn link")
            new_profile["linkedin"] = val.strip()

        # CASE 4: External Website URL Check
        elif field == "website":
            val = col.text_input("Website URL", value=profile.get("website", ""), key="profile_website", placeholder="https://example.com")
            if val and not is_valid_link(val):
                col.error("⚠️ Website field must be a valid link starting with http:// or https://")
                validation_errors.append("Invalid Website link")
            new_profile["website"] = val.strip()

        # CASE 5: Generic inputs fallback (Name, Title, Company, Bio, Pitch)
        else:
            new_profile[field] = col.text_input(
                field.capitalize(), value=profile.get(field, ""), key=f"profile_{field}"
            )

    st.markdown("##### 📁 Attach Resume Image")
    resume_file = st.file_uploader("Upload an image of your resume (PNG, JPG)", type=["png", "jpg", "jpeg"])
    
    if resume_file is not None:
        img = Image.open(resume_file)
        img.thumbnail((400, 500))  
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=60)
        b64_string = base64.b64encode(buffered.getvalue()).decode()
        st.session_state["resume_b64"] = b64_string
        st.success("Resume image attached and ready for QR generation!")
    elif st.button("Clear current resume attachment"):
        st.session_state["resume_b64"] = ""
        st.rerun()

    # Block session serialization mechanics if inputs fail layout verification
    if st.button("Save profile settings"):
        if validation_errors:
            st.error("❌ Cannot save profile configuration. Please correct the formatting errors highlighted above.")
        else:
            st.session_state["profile"] = new_profile
            st.success("Profile saved locally to your active session.")
            st.rerun()

    st.divider()
    st.subheader("2. Modes and field visibility")
    
    with st.expander("Add a custom session mode"):
        new_mode_name = st.text_input("Mode name", key="new_mode_name")
        if st.button("Add mode"):
            if new_mode_name and new_mode_name not in modes:
                st.session_state["modes"].append(new_mode_name)
                st.session_state["visibility"][new_mode_name] = ["name", "email"]
                st.success(f"Added custom mode '{new_mode_name}'.")
                st.rerun()

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

    resume_checked = st.checkbox("Include Resume Image in this mode", value=("resume_b64" in visible_fields))
    if resume_checked:
        new_visible.append("resume_b64")

    if st.button("Save visibility configuration"):
        st.session_state["visibility"][selected_mode] = new_visible
        st.success(f"Visibility for '{selected_mode}' updated.")
        st.rerun()

    st.divider()
    st.subheader("3. Live QR preview")

    qr_mode = st.selectbox("Generate QR code representation", modes, key="qr_mode_select")
    preview_visible = visibility.get(qr_mode, [])
    
    payload = {f: new_profile.get(f, "") for f in preview_visible if f in new_profile and new_profile.get(f)}
    if "resume_b64" in preview_visible and st.session_state["resume_b64"]:
        payload["resume_b64"] = st.session_state["resume_b64"]
        
    payload["shared_as"] = qr_mode

    preview_col, qr_col = st.columns([2, 1])
    with preview_col:
        st.write("Your generated live QR content:")
        display_payload = {k: (v[:30] + "..." if k == "resume_b64" else v) for k, v in payload.items()}
        st.json(display_payload)
    with qr_col:
        img_bytes = make_qr_image_bytes(payload)
        st.image(img_bytes, caption=f"{qr_mode} mode QR code", width=220)
        st.download_button(
            "Download QR Card",
            img_bytes,
            file_name=f"{qr_mode.lower().replace(' ', '_')}_mode_qr.png",
            mime="image/png",
        )

# ---------------------------------------------------------------------------
# Tab 2: Scan & Save
# ---------------------------------------------------------------------------
with tab_scan:
    st.subheader("1. Event context")

    known_events = get_known_events()
    current_event = st.session_state["current_event"]

    event_options = ["(new event)"] + known_events
    default_index = event_options.index(current_event) if current_event in event_options else 0
    chosen_event_option = st.selectbox("Current event context", event_options, index=default_index)

    if chosen_event_option == "(new event)":
        event = st.text_input("Event name", value=current_event if current_event not in known_events else "")
    else:
        event = chosen_event_option

    st.divider()
    st.subheader("2. Capture the QR code")

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
            st.success("QR Matrix unpacked successfully.")
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
            st.warning("Could not resolve tracking markers. Ensure alignment is clean and legible.")

    if decoded_data:
        st.subheader("3. Save to global list")

        default_name = decoded_data.get("name", "")
        name = st.text_input("Assign Contact Name", value=default_name)
        modes = st.session_state["modes"]

        st.write("Save under category:")
        default_mode_index = modes.index(shared_mode) if shared_mode in modes else 0
        saved_mode = st.radio(
            "Mode Selector", modes, horizontal=True, label_visibility="collapsed",
            index=default_mode_index, key="save_mode",
        )

        my_saved_name = st.session_state["profile"].get("name", "").strip()
        is_self_scan = bool(my_saved_name and name.strip().lower() == my_saved_name.lower())

        if is_self_scan:
            st.error("⚠️ Self-scan restriction active. You cannot save yourself as an external network contact.")
            st.button("Save contact data", type="primary", disabled=True)
        else:
            if st.button("Save contact data", type="primary"):
                if not name:
                    st.error("Name field required.")
                elif not event:
                    st.error("Event context field required.")
                elif contact_exists(name, event):
                    st.warning(f"⚠️ '{name}' is already recorded under the '{event}' group index.")
                else:
                    save_contact(name, decoded_data, saved_mode, shared_mode, event)
                    st.session_state["current_event"] = event
                    st.success(f"Saved '{name}' globally under '{saved_mode}' card layout.")
                    st.rerun()

# ---------------------------------------------------------------------------
# Tab 3: My Contacts
# ---------------------------------------------------------------------------
with tab_contacts:
    st.subheader("Global Synchronized Contacts")

    contacts = get_contacts()
    if not contacts:
        st.info("Global list empty. Scan or upload profiles to start seeding entries.")
    else:
        df = pd.DataFrame(
            contacts,
            columns=["id", "name", "data", "saved_mode", "shared_mode", "event", "saved_at"],
        )

        col1, col2 = st.columns(2)
        with col1:
            events = ["All Records"] + sorted(df["event"].unique().tolist())
            current_event = st.session_state["current_event"]
            default_event_index = events.index(current_event) if current_event in events else 0
            event_filter = st.selectbox("Filter Location Context", events, index=default_event_index)
        with col2:
            mode_options = ["All Records"] + sorted(df["saved_mode"].unique().tolist())
            mode_filter = st.selectbox("Filter Assignment Mode", mode_options)

        filtered = df.copy()
        if event_filter != "All Records":
            filtered = filtered[filtered["event"] == event_filter]
        if mode_filter != "All Records":
            filtered = filtered[filtered["saved_mode"] == mode_filter]

        st.write(f"Displaying {len(filtered)} out of {len(df)} total global records.")

        for ev in filtered["event"].unique():
            ev_df = filtered[filtered["event"] == ev]
            st.markdown(f"## 📍 {ev} &nbsp; ({len(ev_df)})")

            for mode in sorted(ev_df["saved_mode"].unique()):
                mode_df = ev_df[ev_df["saved_mode"] == mode]
                st.markdown(f"#### 🏷️ Group: *{mode}*")

                for _, row in mode_df.iterrows():
                    data = json.loads(row["data"])
                    
                    c1, c2 = st.columns([6, 1])
                    with c1:
                        render_business_card(data)
                    with c2:
                        st.caption(f"📅 Added:\n`{row['saved_at'][:10]}`")
                        if st.button("Remove Card", key=f"del_{row['id']}", type="secondary"):
                            delete_contact(row["id"])
                            st.rerun()
            st.divider()

# ---------------------------------------------------------------------------
# Tab 4: Analytics
# ---------------------------------------------------------------------------
with tab_analytics:
    st.subheader("Global Metric Analysis")

    contacts = get_contacts()
    scans = get_scan_log()

    if not contacts and not scans:
        st.info("Metrics calculation offline until activity events are recorded.")
    else:
        df = pd.DataFrame(
            contacts,
            columns=["id", "name", "data", "saved_mode", "shared_mode", "event", "saved_at"],
        )
        scan_df = pd.DataFrame(scans, columns=["shared_mode", "event", "scanned_at"])

        m1, m2, m3 = st.columns(3)
        m1.metric("Synced Database Records", len(df))
        m2.metric("Total Platform Interactions", len(scan_df))
        m3.metric("Distinct Events Active", df["event"].nunique() if not df.empty else 0)

        if not df.empty:
            st.markdown("**Distribution Matrix by Saved Category**")
            st.bar_chart(df["saved_mode"].value_counts())

            st.markdown("**Distribution Matrix by Event Index**")
            st.bar_chart(df["event"].value_counts())

            st.markdown("**Platform Traction Timeline**")
            df["date"] = pd.to_datetime(df["saved_at"]).dt.date
            st.bar_chart(df.groupby("date").size())