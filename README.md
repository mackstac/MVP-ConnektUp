# Networking Contact Scanner - MVP (v2)

A single-user prototype for the "build a dynamic profile -> share via QR ->
scan and save with event context -> filter and analyze your contacts" flow.

## What's new in this version

1. **Dynamic profile visibility**
   - Fill in your profile once (name, title, company, email, phone,
     LinkedIn, website, pitch, bio).
   - Define your own "modes" (Investor, Startup, Supplier, or anything
     else) and choose - per mode - which fields are visible.
   - A live QR preview shows exactly what will be shared for the selected
     mode, and updates instantly as you edit fields or toggle visibility.

2. **Event context**
   - Set the "current event" you're at (e.g. "TechCrunch Disrupt 2026").
   - This is remembered between sessions as a smart default, and every
     contact you save gets tagged with it automatically.

3. **Smart listing**
   - Your saved contacts are grouped by **event**, then by **mode**, so
     "everyone I met at X as an investor" is a couple of clicks away.
   - Filter dropdowns let you narrow down by event and/or mode; the event
     filter defaults to your current event.

4. **Analytics**
   - Total contacts saved, total scans, and number of events tracked.
   - Charts: contacts by mode, contacts by event, saves over time, and the
     modes other people shared with you when you scanned their codes.

## Setup (one-time)

You'll need Python 3.9+ installed. Then, in a terminal, from this folder:

```bash
pip install -r requirements.txt
```

## Running the app

```bash
streamlit run app.py
```

This opens a browser tab with four sections:

### My Profile
- Enter your details and click **Save profile**.
- Add one or more modes (e.g. Investor, Startup, Supplier) and, for each,
  tick which fields are visible.
- Scroll down to the **live QR preview** - this is the code you'd display
  or print for that mode. Download it as a PNG.

### Scan & Save
- Set the **current event** (type a new one, or pick a previous one from
  the dropdown - it remembers your last event as the default).
- Scan a QR code via camera or by uploading an image (use
  `generate_qr.py` to create sample codes for testing, see below).
- The mode the other person shared as is pre-selected; adjust it if you
  want to file the contact under a different mode in *your* list, then
  click **Save contact**.

### My Contacts
- Filter by event and/or mode.
- Contacts are grouped by event, then by mode, for quick scanning of "who
  did I meet, and in what context."

### Analytics
- See counts and trends: contacts by mode/event, saves over time, and
  what modes people have been sharing with you.

## Generating test QR codes

`generate_qr.py` is a standalone helper that creates a few sample QR codes
(simulating *other people's* shared profiles) so you have something to
scan while testing:

```bash
python generate_qr.py
```

This creates `investor_mode_qr.png`, `startup_mode_qr.png`, and
`supplier_mode_qr.png` - display these on another screen or print them out,
then scan them in the **Scan & Save** tab.

## Data storage

Everything is stored locally in `contacts.db` (SQLite) - your profile and
mode/visibility settings, your saved contacts, and a log of every QR scan
(used for the analytics tab). Delete this file to reset the app to a blank
state.

## What's still a stand-in for the bigger vision

- This is single-user and local - your "My Profile" tab represents *your*
  side, and "Scan & Save" represents you receiving *someone else's* QR
  code. In a real product, each user would have their own account/profile
  hosted centrally, and "Analytics" for a user would include how many
  *other* people scanned *their* codes (which needs a server/backend).
- The QR payload is plain JSON for simplicity. A production version might
  encode a link to a hosted profile page instead, so the visible fields
  can be updated even after the QR code has been printed/shared.
