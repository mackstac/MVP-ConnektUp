"""
QR Code Generator - MVP helper
--------------------------------
Generates test QR codes that encode a person's profile info as JSON.
Each "mode" (Investor, Startup, Supplier...) can have a different
set of fields - this is what the scanner app (app.py) will read.

Run with:
    python generate_qr.py

This will create a few sample PNG files you can scan with app.py
to test the flow before connecting it to a real profile builder.
"""

import json

import qrcode


def generate_profile_qr(profile_data: dict, filename: str):
    """Encode a profile dict as JSON inside a QR code image."""
    payload = json.dumps(profile_data)

    qr = qrcode.QRCode(
        version=None,  # auto-size based on data length
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
    print(f"Saved {filename}  ({len(payload)} bytes encoded)")


if __name__ == "__main__":
    # Example: the same person shares different info depending on
    # which "mode" they were in when they generated the code.

    investor_view = {
        "name": "Jane Doe",
        "shared_as": "Investor",
        "company": "Acme Ventures",
        "title": "Partner",
        "email": "jane@acmeventures.com",
        "linkedin": "linkedin.com/in/janedoe",
    }

    startup_view = {
        "name": "Jane Doe",
        "shared_as": "Startup Founder",
        "company": "Acme Labs",
        "title": "Founder & CEO",
        "email": "jane@acmelabs.io",
        "pitch": "AI-powered logistics platform for last-mile delivery",
        "website": "acmelabs.io",
    }

    supplier_view = {
        "name": "Jane Doe",
        "shared_as": "Supplier Contact",
        "company": "Acme Components",
        "title": "Procurement Lead",
        "email": "procurement@acmecomponents.com",
        "phone": "+1-555-0100",
    }

    generate_profile_qr(investor_view, "investor_mode_qr.png")
    generate_profile_qr(startup_view, "startup_mode_qr.png")
    generate_profile_qr(supplier_view, "supplier_mode_qr.png")
