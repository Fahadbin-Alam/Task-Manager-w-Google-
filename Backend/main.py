# Author: Fahadbin Alam (fma52), 4/19/26
# Mod by Codex, 4/19/26
# From One World Relief donation backend integration, 4/19/26
from fastapi import FastAPI, Request, HTTPException, Depends, Header, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sqlite3
import bcrypt
import json
import csv
import io
import hmac
import hashlib
import requests
from jose import JWTError, jwt

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# ===== PATHS =====
BASE_DIR = Path(__file__).resolve().parent
if load_dotenv:
    load_dotenv(BASE_DIR.parent / ".env")

# ===== CONFIG =====
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production").strip()
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "app.db"))).resolve()
OWR_DIR = BASE_DIR.parent / "one-world-relief"

# ===== ONE WORLD RELIEF CONFIG =====
OWR_STRIPE_SECRET_KEY = os.getenv("OWR_STRIPE_SECRET_KEY", "").strip()
OWR_STRIPE_WEBHOOK_SECRET = os.getenv("OWR_STRIPE_WEBHOOK_SECRET", "").strip()
OWR_PAYPAL_CLIENT_ID = os.getenv("OWR_PAYPAL_CLIENT_ID", "").strip()
OWR_PAYPAL_CLIENT_SECRET = os.getenv("OWR_PAYPAL_CLIENT_SECRET", "").strip()
OWR_PAYPAL_BASE_URL = os.getenv("OWR_PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com").strip()
OWR_SUCCESS_URL = os.getenv("OWR_SUCCESS_URL", "http://localhost:8000/charity/thank-you").strip()
OWR_CANCEL_URL = os.getenv("OWR_CANCEL_URL", "http://localhost:8000/charity/cancelled").strip()
OWR_ADMIN_API_KEY = os.getenv("OWR_ADMIN_API_KEY", "").strip()

# ===== PASSWORD HASHING (Needed before DB init) =====
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# ===== DATABASE SETUP =====
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        plain_password TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS user_favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        item_type TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        UNIQUE (user_id, item_id, item_type)
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS user_planner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        course_name TEXT NOT NULL,
        days TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        location TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        UNIQUE (user_id, course_id)
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS charity_donors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS charity_donations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id INTEGER NOT NULL,
        amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
        currency TEXT NOT NULL DEFAULT 'USD',
        payment_method TEXT NOT NULL,
        provider TEXT NOT NULL,
        provider_payment_id TEXT,
        provider_order_id TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        campaign TEXT,
        note TEXT,
        metadata_json TEXT,
        receipt_number TEXT UNIQUE,
        tax_year INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        paid_at TIMESTAMP,
        FOREIGN KEY (donor_id) REFERENCES charity_donors (id) ON DELETE CASCADE
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS charity_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donation_id INTEGER UNIQUE NOT NULL,
        receipt_number TEXT UNIQUE NOT NULL,
        donor_name TEXT NOT NULL,
        donor_email TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        receipt_text TEXT NOT NULL,
        email_status TEXT NOT NULL DEFAULT 'queued',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (donation_id) REFERENCES charity_donations (id) ON DELETE CASCADE
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS charity_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donation_id INTEGER,
        event_type TEXT NOT NULL,
        event_payload TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (donation_id) REFERENCES charity_donations (id) ON DELETE SET NULL
    )""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_charity_donations_paid_at ON charity_donations(paid_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_charity_donations_status ON charity_donations(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_charity_donations_tax_year ON charity_donations(tax_year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_charity_donors_email ON charity_donors(email)")

    # Create demo account if it doesn't exist
    cursor.execute("SELECT id FROM users WHERE email = ?", ("demo@example.com",))
    if cursor.fetchone() is None:
        demo_password = "demo123"
        demo_hash = hash_password(demo_password)
        cursor.execute("INSERT INTO users (email, password_hash, plain_password) VALUES (?, ?, ?)",
                      ("demo@example.com", demo_hash, demo_password))
        demo_id = cursor.lastrowid
        sample_notifications = [
            (demo_id, "Welcome to Succeed!", "Your Drexel student guide is ready. Explore tools like the Course Planner and Events."),
            (demo_id, "Event Reminder", "Anime Club Meetup is coming up at Creese Student Center."),
            (demo_id, "Course Planner Tip", "Add your courses to the planner to visualize your weekly schedule."),
            (demo_id, "Assignment Due Soon", "Web Development Lab #3 is due this Friday at 11:59 PM."),
        ]
        cursor.executemany(
            "INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
            sample_notifications
        )
    
    conn.commit()
    conn.close()

init_db()

# ===== APP SETUP =====
app = FastAPI(title="Drexel Student Success API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ===== PYDANTIC MODELS =====
class Club(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

class Event(BaseModel):
    id: int
    club_id: int
    title: str
    start_time: datetime
    end_time: datetime
    location: str
    description: Optional[str] = None

class ClassItem(BaseModel):
    id: int
    name: str
    days: List[str]          # ["M","W","F"]
    start_time: str          # "11:00 AM"
    end_time: str            # "11:50 AM"
    location: str

class Favorite(BaseModel):
    item_id: int
    item_type: str  # "club" or "event"

class PlannerCourse(BaseModel):
    id: int
    name: str
    days: List[str]
    start_time: str
    end_time: str
    location: str

# ===== AUTH MODELS =====
class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    email: str


# ===== CHARITY DONATION MODELS =====
class DonationCheckoutRequest(BaseModel):
    donor_name: str = Field(min_length=2, max_length=120)
    donor_email: EmailStr
    amount_usd: float = Field(gt=0)
    payment_method: str = Field(
        description="Supported values: paypal, credit_card, card, stripe"
    )
    campaign: Optional[str] = Field(default="General Fund", max_length=120)
    note: Optional[str] = Field(default=None, max_length=500)
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class DonationCheckoutResponse(BaseModel):
    donation_id: int
    provider: str
    status: str
    redirect_url: Optional[str] = None
    message: str


class DonationMarkPaidRequest(BaseModel):
    provider_payment_id: str = Field(min_length=1, max_length=200)
    paid_at: Optional[datetime] = None


class DonationListItem(BaseModel):
    id: int
    donor_name: str
    donor_email: str
    amount_usd: float
    currency: str
    payment_method: str
    provider: str
    status: str
    receipt_number: Optional[str] = None
    provider_payment_id: Optional[str] = None
    tax_year: Optional[int] = None
    created_at: str
    paid_at: Optional[str] = None

# ===== JWT FUNCTIONS =====
def create_access_token(user_id: int, email: str, expires_delta: Optional[timedelta] = None):
    if expires_delta is None:
        expires_delta = timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expires_delta
    to_encode = {"user_id": user_id, "email": email, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    return verify_token(token)

# ===== DATABASE ACCESS =====
def get_db():
    return sqlite3.connect(DB_PATH)

def get_user_by_email(email: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return row

def create_user(email: str, password_hash: str, plain_password: str = None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (email, password_hash, plain_password) VALUES (?, ?, ?)", 
                      (email, password_hash, plain_password))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

def get_user_favorites(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, item_type FROM user_favorites WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"item_id": row[0], "item_type": row[1]} for row in rows]

def add_user_favorite(user_id: int, item_id: int, item_type: str):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO user_favorites (user_id, item_id, item_type) VALUES (?, ?, ?)", (user_id, item_id, item_type))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def remove_user_favorite(user_id: int, item_id: int, item_type: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_favorites WHERE user_id = ? AND item_id = ? AND item_type = ?", (user_id, item_id, item_type))
    conn.commit()
    conn.close()

def get_user_planner(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT course_id, course_name, days, start_time, end_time, location FROM user_planner WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({"id": row[0], "name": row[1], "days": json.loads(row[2]), "start_time": row[3], "end_time": row[4], "location": row[5]})
    return result

def add_user_planner_course(user_id: int, course_id: int, course_name: str, days: List[str], start_time: str, end_time: str, location: str):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO user_planner (user_id, course_id, course_name, days, start_time, end_time, location) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (user_id, course_id, course_name, json.dumps(days), start_time, end_time, location))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def remove_user_planner_course(user_id: int, course_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_planner WHERE user_id = ? AND course_id = ?", (user_id, course_id))
    conn.commit()
    conn.close()

def get_user_notifications(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, message, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "message": r[2], "is_read": bool(r[3]), "created_at": r[4]} for r in rows]

def mark_notification_read(user_id: int, notif_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, user_id))
    conn.commit()
    conn.close()

def mark_all_notifications_read(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ===== CHARITY HELPERS =====
def require_charity_admin(x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")):
    # If no admin key is configured, endpoints remain open for local development.
    if OWR_ADMIN_API_KEY and x_admin_key != OWR_ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Admin-Key")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def normalize_payment_method(raw_method: str) -> str:
    method = raw_method.strip().lower()
    if method in {"credit_card", "card", "stripe"}:
        return method
    if method == "paypal":
        return method
    raise HTTPException(
        status_code=400,
        detail="payment_method must be one of: paypal, credit_card, card, stripe",
    )


def payment_provider_from_method(method: str) -> str:
    if method == "paypal":
        return "paypal"
    return "stripe"


def usd_to_cents(amount_usd: float) -> int:
    cents = int(round(amount_usd * 100))
    if cents <= 0:
        raise HTTPException(status_code=400, detail="Donation amount must be greater than zero")
    return cents


def cents_to_usd(amount_cents: int) -> float:
    return round(amount_cents / 100.0, 2)


def json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, default=str)


def get_or_create_charity_donor(full_name: str, email: str) -> int:
    normalized_email = email.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name FROM charity_donors WHERE email = ?", (normalized_email,))
    row = cursor.fetchone()
    if row:
        donor_id = row[0]
        if row[1] != full_name.strip():
            cursor.execute(
                "UPDATE charity_donors SET full_name = ? WHERE id = ?",
                (full_name.strip(), donor_id),
            )
            conn.commit()
        conn.close()
        return donor_id

    cursor.execute(
        "INSERT INTO charity_donors (full_name, email) VALUES (?, ?)",
        (full_name.strip(), normalized_email),
    )
    conn.commit()
    donor_id = cursor.lastrowid
    conn.close()
    return donor_id


def add_charity_audit_log(donation_id: Optional[int], event_type: str, payload: Optional[Dict[str, Any]] = None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO charity_audit_logs (donation_id, event_type, event_payload) VALUES (?, ?, ?)",
        (donation_id, event_type, json_dump(payload or {})),
    )
    conn.commit()
    conn.close()


def create_pending_charity_donation(
    donor_id: int,
    amount_cents: int,
    payment_method: str,
    provider: str,
    campaign: Optional[str],
    note: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO charity_donations (
            donor_id, amount_cents, currency, payment_method, provider, status, campaign, note, metadata_json
        ) VALUES (?, ?, 'USD', ?, ?, 'pending', ?, ?, ?)
        """,
        (
            donor_id,
            amount_cents,
            payment_method,
            provider,
            campaign,
            note,
            json_dump(metadata or {}),
        ),
    )
    conn.commit()
    donation_id = cursor.lastrowid
    conn.close()
    add_charity_audit_log(
        donation_id,
        "donation_pending_created",
        {"amount_cents": amount_cents, "payment_method": payment_method, "provider": provider},
    )
    return donation_id


def set_charity_donation_provider_order(donation_id: int, provider_order_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE charity_donations SET provider_order_id = ? WHERE id = ?",
        (provider_order_id, donation_id),
    )
    conn.commit()
    conn.close()


def get_charity_donation(donation_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            d.id, d.amount_cents, d.currency, d.payment_method, d.provider, d.provider_payment_id,
            d.provider_order_id, d.status, d.campaign, d.note, d.receipt_number, d.tax_year,
            d.created_at, d.paid_at, dd.full_name AS donor_name, dd.email AS donor_email
        FROM charity_donations d
        JOIN charity_donors dd ON dd.id = d.donor_id
        WHERE d.id = ?
        """,
        (donation_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_charity_donation_by_provider_order(provider_order_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            d.id, d.amount_cents, d.currency, d.payment_method, d.provider, d.provider_payment_id,
            d.provider_order_id, d.status, d.campaign, d.note, d.receipt_number, d.tax_year,
            d.created_at, d.paid_at, dd.full_name AS donor_name, dd.email AS donor_email
        FROM charity_donations d
        JOIN charity_donors dd ON dd.id = d.donor_id
        WHERE d.provider_order_id = ?
        ORDER BY d.id DESC
        LIMIT 1
        """,
        (provider_order_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def make_receipt_number(donation_id: int, paid_at: datetime) -> str:
    return f"OWR-{paid_at.year}-{donation_id:06d}"


def make_receipt_text(donation: Dict[str, Any]) -> str:
    paid_at = donation.get("paid_at") or utc_now_iso()
    lines = [
        f"Receipt Number: {donation.get('receipt_number')}",
        f"Date Paid (UTC): {paid_at}",
        f"Donor Name: {donation.get('donor_name')}",
        f"Donor Email: {donation.get('donor_email')}",
        f"Amount: ${cents_to_usd(donation.get('amount_cents', 0)):.2f} {donation.get('currency', 'USD')}",
        f"Payment Method: {donation.get('payment_method')}",
        f"Payment Provider: {donation.get('provider')}",
        f"Provider Transaction ID: {donation.get('provider_payment_id') or '(pending)'}",
        f"Campaign: {donation.get('campaign') or 'General Fund'}",
        f"Tax Year: {donation.get('tax_year') or ''}",
        "",
        "Thank you for supporting One World Relief.",
    ]
    return "\n".join(lines)


def upsert_charity_receipt(donation: Dict[str, Any]):
    receipt_text = make_receipt_text(donation)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO charity_receipts (
            donation_id, receipt_number, donor_name, donor_email, amount_cents, currency, receipt_text, email_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued')
        ON CONFLICT(donation_id) DO UPDATE SET
            receipt_number = excluded.receipt_number,
            donor_name = excluded.donor_name,
            donor_email = excluded.donor_email,
            amount_cents = excluded.amount_cents,
            currency = excluded.currency,
            receipt_text = excluded.receipt_text
        """,
        (
            donation["id"],
            donation["receipt_number"],
            donation["donor_name"],
            donation["donor_email"],
            donation["amount_cents"],
            donation["currency"],
            receipt_text,
        ),
    )
    conn.commit()
    conn.close()


def set_charity_donation_status(
    donation_id: int,
    status: str,
    provider_payment_id: Optional[str] = None,
    paid_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    donation = get_charity_donation(donation_id)
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if status == "paid":
        finalized_paid_at = paid_at or utc_now()
        paid_str = finalized_paid_at.replace(microsecond=0).isoformat()
        tax_year = finalized_paid_at.year
        receipt_number = donation.get("receipt_number") or make_receipt_number(donation_id, finalized_paid_at)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE charity_donations
            SET status = 'paid',
                provider_payment_id = COALESCE(?, provider_payment_id),
                paid_at = COALESCE(?, paid_at),
                tax_year = COALESCE(tax_year, ?),
                receipt_number = COALESCE(receipt_number, ?)
            WHERE id = ?
            """,
            (provider_payment_id, paid_str, tax_year, receipt_number, donation_id),
        )
        conn.commit()
        conn.close()
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE charity_donations SET status = ?, provider_payment_id = COALESCE(?, provider_payment_id) WHERE id = ?",
            (status, provider_payment_id, donation_id),
        )
        conn.commit()
        conn.close()

    updated = get_charity_donation(donation_id)
    if updated and updated.get("status") == "paid":
        upsert_charity_receipt(updated)

    add_charity_audit_log(
        donation_id,
        f"donation_{status}",
        {
            "provider_payment_id": provider_payment_id,
            "paid_at": paid_at.isoformat() if paid_at else None,
        },
    )
    return updated or donation


def get_paypal_access_token() -> str:
    if not OWR_PAYPAL_CLIENT_ID or not OWR_PAYPAL_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="PayPal is not configured. Set OWR_PAYPAL_CLIENT_ID and OWR_PAYPAL_CLIENT_SECRET.",
        )

    response = requests.post(
        f"{OWR_PAYPAL_BASE_URL}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(OWR_PAYPAL_CLIENT_ID, OWR_PAYPAL_CLIENT_SECRET),
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        timeout=20,
    )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"PayPal auth failed: {response.text}")

    return response.json()["access_token"]


def create_paypal_order(
    donation_id: int,
    amount_cents: int,
    donor_name: str,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    access_token = get_paypal_access_token()
    amount_usd = f"{cents_to_usd(amount_cents):.2f}"

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": f"owr-donation-{donation_id}",
                "custom_id": str(donation_id),
                "description": f"One World Relief Donation from {donor_name}",
                "amount": {"currency_code": "USD", "value": amount_usd},
            }
        ],
        "application_context": {
            "brand_name": "One World Relief",
            "landing_page": "BILLING",
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
            "return_url": f"{success_url}?donation_id={donation_id}",
            "cancel_url": f"{cancel_url}?donation_id={donation_id}",
        },
    }

    response = requests.post(
        f"{OWR_PAYPAL_BASE_URL}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"PayPal order creation failed: {response.text}")

    data = response.json()
    approve_url = None
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            approve_url = link.get("href")
            break

    if not approve_url:
        raise HTTPException(status_code=502, detail="PayPal did not return an approval link")

    return {"order_id": data["id"], "approve_url": approve_url}


def capture_paypal_order(order_id: str) -> Dict[str, Any]:
    access_token = get_paypal_access_token()
    response = requests.post(
        f"{OWR_PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=20,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"PayPal capture failed: {response.text}")
    return response.json()


def create_stripe_checkout_session(
    donation_id: int,
    amount_cents: int,
    donor_email: str,
    donor_name: str,
    campaign: Optional[str],
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    if not OWR_STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Set OWR_STRIPE_SECRET_KEY.",
        )

    data = {
        "mode": "payment",
        "success_url": f"{success_url}?donation_id={donation_id}&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{cancel_url}?donation_id={donation_id}",
        "customer_email": donor_email,
        "client_reference_id": str(donation_id),
        "metadata[donation_id]": str(donation_id),
        "metadata[source]": "one-world-relief",
        "metadata[campaign]": campaign or "General Fund",
        "payment_intent_data[metadata][donation_id]": str(donation_id),
        "payment_intent_data[metadata][source]": "one-world-relief",
        "payment_intent_data[metadata][campaign]": campaign or "General Fund",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][product_data][name]": f"One World Relief - {campaign or 'General Fund'}",
        "line_items[0][price_data][product_data][description]": f"Donation from {donor_name}",
        "line_items[0][price_data][unit_amount]": str(amount_cents),
    }

    response = requests.post(
        "https://api.stripe.com/v1/checkout/sessions",
        data=data,
        headers={"Stripe-Version": "2026-02-25.clover"},
        auth=(OWR_STRIPE_SECRET_KEY, ""),
        timeout=20,
    )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Stripe session creation failed: {response.text}")

    payload = response.json()
    return {"session_id": payload["id"], "checkout_url": payload["url"]}


def verify_stripe_signature(raw_body: bytes, stripe_signature: str) -> bool:
    if not OWR_STRIPE_WEBHOOK_SECRET:
        # Local fallback if webhook secret is not configured.
        return True

    parts = stripe_signature.split(",")
    values = {}
    for part in parts:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        values.setdefault(k, []).append(v)

    ts_values = values.get("t", [])
    sig_values = values.get("v1", [])
    if not ts_values or not sig_values:
        return False

    timestamp = ts_values[0]
    signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}"
    expected_sig = hmac.new(
        OWR_STRIPE_WEBHOOK_SECRET.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return any(hmac.compare_digest(expected_sig, candidate) for candidate in sig_values)


def to_donation_list_item(row: Dict[str, Any]) -> DonationListItem:
    return DonationListItem(
        id=row["id"],
        donor_name=row["donor_name"],
        donor_email=row["donor_email"],
        amount_usd=cents_to_usd(row["amount_cents"]),
        currency=row["currency"],
        payment_method=row["payment_method"],
        provider=row["provider"],
        status=row["status"],
        receipt_number=row["receipt_number"],
        provider_payment_id=row["provider_payment_id"],
        tax_year=row["tax_year"],
        created_at=row["created_at"],
        paid_at=row["paid_at"],
    )

# ===== IN-MEMORY MOCK DATA =====
CLUBS: List[Club] = [
    Club(id=1, name="Drexel Anime Club", description="Meetups, watch parties, manga talk."),
    Club(id=2, name="InfoSec Club", description="Cybersecurity workshops and CTF practice."),
]

EVENTS: List[Event] = [
    Event(
        id=1,
        club_id=1,
        title="Anime Club Meetup",
        start_time=datetime(2026, 2, 5, 18, 0),
        end_time=datetime(2026, 2, 5, 19, 30),
        location="Creese Student Center",
        description="Weekly meetup + watch party."
    ),
    Event(
        id=2,
        club_id=2,
        title="Cybersecurity Workshop",
        start_time=datetime(2026, 2, 6, 17, 0),
        end_time=datetime(2026, 2, 6, 18, 30),
        location="Bossone 302",
        description="Beginner-friendly: passwords, MFA, phishing."
    ),
]

CLASSES: List[ClassItem] = [
    ClassItem(
        id=1,
        name="General Psychology I",
        days=["M","W","F"],
        start_time="11:00 AM",
        end_time="11:50 AM",
        location="Nesbitt 111"
    ),
    ClassItem(
        id=2,
        name="Data Structures",
        days=["T","R"],
        start_time="2:00 PM",
        end_time="3:30 PM",
        location="Bossone 303"
    ),
    ClassItem(
        id=3,
        name="Calculus II",
        days=["M","W","F"],
        start_time="1:00 PM",
        end_time="1:50 PM",
        location="Curtis 113"
    ),
    ClassItem(
        id=4,
        name="Web Development",
        days=["T","R"],
        start_time="10:00 AM",
        end_time="11:30 AM",
        location="Raytheon 204"
    ),
    ClassItem(
        id=5,
        name="Public Speaking",
        days=["M","W"],
        start_time="3:00 PM",
        end_time="4:30 PM",
        location="Myers 101"
    ),
]

FAVORITES: List[Favorite] = []

PLANNER_ITEMS: List[PlannerCourse] = []

# -----------------------------
# Helpers
# -----------------------------
def time_to_minutes(t: str) -> int:
    # "HH:MM AM/PM"
    # safe parse even if hour is 1-digit ("8:00 AM") -> normalize first
    t = t.strip()
    parts = t.split()
    hm = parts[0]
    ampm = parts[1].upper()
    hour_str, minute_str = hm.split(":")
    hour = int(hour_str)
    minute = int(minute_str)

    if ampm == "PM" and hour != 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    return hour * 60 + minute

DAY_ORDER = {"M": 1, "T": 2, "W": 3, "R": 4, "F": 5, "S": 6, "U": 7}

def sort_classes(items: List[ClassItem]) -> List[ClassItem]:
    # sort by first day then start time
    return sorted(
        items,
        key=lambda c: (DAY_ORDER.get(c.days[0], 99), time_to_minutes(c.start_time), c.name)
    )

# -----------------------------
# HTML PAGES (Clean Rendering)
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    try:
        html_path = BASE_DIR.parent / "SUCCEED_Final_Version.html"
        with open(str(html_path), "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>"

@app.get("/login", response_class=HTMLResponse)
def login_page():
    try:
        html_path = BASE_DIR.parent / "login.html"
        with open(str(html_path), "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>"

@app.get("/clubs-view", response_class=HTMLResponse)
def clubs_view(request: Request):
    return templates.TemplateResponse("clubs.html", {"request": request, "clubs": [c.dict() for c in CLUBS]})

@app.get("/clubs/{club_id}/events-view", response_class=HTMLResponse)
def events_view(request: Request, club_id: int):
    if not any(c.id == club_id for c in CLUBS):
        raise HTTPException(status_code=404, detail="Club not found")

    club = next(c for c in CLUBS if c.id == club_id)
    club_events = sorted([e for e in EVENTS if e.club_id == club_id], key=lambda e: e.start_time)

    return templates.TemplateResponse(
        "events.html",
        {"request": request, "club": club, "events": club_events}
    )

@app.get("/schedule", response_class=HTMLResponse)
def schedule_view(request: Request):
    sorted_items = sort_classes(CLASSES)
    return templates.TemplateResponse("schedule.html", {"request": request, "classes": sorted_items})


def read_charity_asset(filename: str) -> str:
    asset_path = OWR_DIR / filename
    if not asset_path.exists():
        raise HTTPException(status_code=404, detail=f"Missing charity asset: {filename}")
    with open(asset_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/charity", response_class=HTMLResponse)
def charity_home():
    return read_charity_asset("index.html")


@app.get("/charity/index.html", response_class=HTMLResponse)
def charity_nested_index_page():
    return read_charity_asset("index.html")


@app.get("/charity/about.html", response_class=HTMLResponse)
def charity_nested_about_page():
    return read_charity_asset("about.html")


@app.get("/charity/projects.html", response_class=HTMLResponse)
def charity_nested_projects_page():
    return read_charity_asset("projects.html")


@app.get("/charity/donate.html", response_class=HTMLResponse)
def charity_nested_donate_page():
    return read_charity_asset("donate.html")


@app.get("/charity/contact.html", response_class=HTMLResponse)
def charity_nested_contact_page():
    return read_charity_asset("contact.html")


@app.get("/charity/one-world-relief.css", response_class=PlainTextResponse)
def charity_nested_css():
    return PlainTextResponse(read_charity_asset("one-world-relief.css"), media_type="text/css")


@app.get("/charity/one-world-relief.js", response_class=PlainTextResponse)
def charity_nested_js():
    return PlainTextResponse(read_charity_asset("one-world-relief.js"), media_type="application/javascript")


@app.get("/charity/project-data.js", response_class=PlainTextResponse)
def charity_nested_project_data():
    return PlainTextResponse(read_charity_asset("project-data.js"), media_type="application/javascript")


@app.get("/about.html", response_class=HTMLResponse)
def charity_about_page():
    return read_charity_asset("about.html")


@app.get("/index.html", response_class=HTMLResponse)
def charity_index_page():
    return read_charity_asset("index.html")


@app.get("/projects.html", response_class=HTMLResponse)
def charity_projects_page():
    return read_charity_asset("projects.html")


@app.get("/donate.html", response_class=HTMLResponse)
def charity_donate_page():
    return read_charity_asset("donate.html")


@app.get("/contact.html", response_class=HTMLResponse)
def charity_contact_page():
    return read_charity_asset("contact.html")


@app.get("/one-world-relief.css", response_class=PlainTextResponse)
def charity_css():
    return PlainTextResponse(read_charity_asset("one-world-relief.css"), media_type="text/css")


@app.get("/one-world-relief.js", response_class=PlainTextResponse)
def charity_js():
    return PlainTextResponse(read_charity_asset("one-world-relief.js"), media_type="application/javascript")


@app.get("/project-data.js", response_class=PlainTextResponse)
def charity_project_data():
    return PlainTextResponse(read_charity_asset("project-data.js"), media_type="application/javascript")


@app.get("/charity/thank-you", response_class=HTMLResponse)
def charity_thank_you():
    return """
    <html><head><title>One World Relief - Thank You</title></head>
    <body style="font-family: sans-serif; max-width: 700px; margin: 40px auto; line-height: 1.5;">
      <h1>Thank you for your donation</h1>
      <p>Your donation was received. We will issue a receipt and keep a tax-friendly log entry automatically.</p>
      <p><a href="/charity">Back to One World Relief</a></p>
    </body></html>
    """


@app.get("/charity/cancelled", response_class=HTMLResponse)
def charity_cancelled():
    return """
    <html><head><title>One World Relief - Donation Cancelled</title></head>
    <body style="font-family: sans-serif; max-width: 700px; margin: 40px auto; line-height: 1.5;">
      <h1>Donation Cancelled</h1>
      <p>No worries. Your donation has not been finalized yet.</p>
      <p><a href="/charity">Return to donation page</a></p>
    </body></html>
    """

# ===== AUTHENTICATION ENDPOINTS =====
@app.post("/auth/register", response_model=Token)
def register(req: RegisterRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed = hash_password(req.password)
    user_id = create_user(req.email, hashed, plain_password=req.password)
    token = create_access_token(user_id, req.email)
    
    return {"access_token": token, "token_type": "bearer", "user_id": user_id, "email": req.email}

@app.post("/auth/login", response_model=Token)
def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_id, email, password_hash = user
    if not verify_password(req.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(user_id, email)
    return {"access_token": token, "token_type": "bearer", "user_id": user_id, "email": email}

# ===== API - PUBLIC ENDPOINTS (No auth required) =====
@app.get("/clubs", response_model=List[Club])
def get_clubs():
    return CLUBS

@app.get("/events", response_model=List[Event])
def get_events():
    return EVENTS

@app.get("/clubs/{club_id}/events", response_model=List[Event])
def get_events_for_club(club_id: int):
    if not any(c.id == club_id for c in CLUBS):
        raise HTTPException(status_code=404, detail="Club not found")
    return [e for e in EVENTS if e.club_id == club_id]

# ===== USER FAVORITES ENDPOINTS =====
@app.get("/favorites")
def get_favorites(user: dict = Depends(get_current_user)):
    return get_user_favorites(user["user_id"])

@app.post("/favorites")
def add_favorite(fav: Favorite, user: dict = Depends(get_current_user)):
    if add_user_favorite(user["user_id"], fav.item_id, fav.item_type):
        return {"message": "Added to favorites"}
    else:
        return {"message": "Already in favorites"}

@app.delete("/favorites/{item_id}/{item_type}")
def remove_favorite(item_id: int, item_type: str, user: dict = Depends(get_current_user)):
    remove_user_favorite(user["user_id"], item_id, item_type)
    return {"message": "Removed from favorites"}

# ===== USER PLANNER ENDPOINTS =====
@app.get("/planner")
def get_planner(user: dict = Depends(get_current_user)):
    return get_user_planner(user["user_id"])

@app.post("/planner")
def add_to_planner(course: PlannerCourse, user: dict = Depends(get_current_user)):
    if add_user_planner_course(user["user_id"], course.id, course.name, course.days, course.start_time, course.end_time, course.location):
        return {"message": "Added to planner"}
    else:
        return {"message": "Course already in planner"}

@app.delete("/planner/{course_id}")
def remove_from_planner(course_id: int, user: dict = Depends(get_current_user)):
    remove_user_planner_course(user["user_id"], course_id)
    return {"message": "Removed from planner"}

@app.get("/courses")
def get_available_courses():
    return CLASSES

# ===== NOTIFICATIONS ENDPOINTS =====
@app.get("/notifications")
def get_notifications(user: dict = Depends(get_current_user)):
    return get_user_notifications(user["user_id"])

@app.post("/notifications/{notif_id}/read")
def read_notification(notif_id: int, user: dict = Depends(get_current_user)):
    mark_notification_read(user["user_id"], notif_id)
    return {"message": "Marked as read"}

@app.post("/notifications/read-all")
def read_all_notifications(user: dict = Depends(get_current_user)):
    mark_all_notifications_read(user["user_id"])
    return {"message": "All notifications marked as read"}


# ===== ONE WORLD RELIEF DONATION ENDPOINTS =====
@app.post("/charity/donations/checkout", response_model=DonationCheckoutResponse)
def create_charity_checkout(req: DonationCheckoutRequest):
    payment_method = normalize_payment_method(req.payment_method)
    provider = payment_provider_from_method(payment_method)
    amount_cents = usd_to_cents(req.amount_usd)

    donor_id = get_or_create_charity_donor(req.donor_name, str(req.donor_email))
    donation_id = create_pending_charity_donation(
        donor_id=donor_id,
        amount_cents=amount_cents,
        payment_method=payment_method,
        provider=provider,
        campaign=req.campaign,
        note=req.note,
        metadata={"request_time": utc_now_iso()},
    )

    success_url = req.success_url or OWR_SUCCESS_URL
    cancel_url = req.cancel_url or OWR_CANCEL_URL

    try:
        if provider == "paypal":
            order = create_paypal_order(
                donation_id=donation_id,
                amount_cents=amount_cents,
                donor_name=req.donor_name,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            set_charity_donation_provider_order(donation_id, order["order_id"])
            add_charity_audit_log(
                donation_id,
                "paypal_order_created",
                {"order_id": order["order_id"], "approve_url": order["approve_url"]},
            )
            return DonationCheckoutResponse(
                donation_id=donation_id,
                provider="paypal",
                status="pending",
                redirect_url=order["approve_url"],
                message="Redirect donor to PayPal approval URL",
            )

        stripe_session = create_stripe_checkout_session(
            donation_id=donation_id,
            amount_cents=amount_cents,
            donor_email=str(req.donor_email),
            donor_name=req.donor_name,
            campaign=req.campaign,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        set_charity_donation_provider_order(donation_id, stripe_session["session_id"])
        add_charity_audit_log(
            donation_id,
            "stripe_checkout_created",
            {"session_id": stripe_session["session_id"]},
        )
        return DonationCheckoutResponse(
            donation_id=donation_id,
            provider="stripe",
            status="pending",
            redirect_url=stripe_session["checkout_url"],
            message="Redirect donor to Stripe Checkout URL",
        )
    except HTTPException:
        set_charity_donation_status(donation_id, "failed")
        raise


@app.post("/charity/donations/{donation_id}/mock-complete")
def mock_complete_charity_donation(
    donation_id: int,
    req: DonationMarkPaidRequest,
    _admin: None = Depends(require_charity_admin),
):
    donation = set_charity_donation_status(
        donation_id,
        "paid",
        provider_payment_id=req.provider_payment_id,
        paid_at=req.paid_at,
    )
    return {
        "message": "Donation marked as paid",
        "donation_id": donation_id,
        "receipt_number": donation.get("receipt_number"),
    }


@app.post("/charity/paypal/capture/{order_id}")
def capture_paypal_donation(order_id: str):
    payload = capture_paypal_order(order_id)
    purchase_units = payload.get("purchase_units", [])
    first_unit = purchase_units[0] if purchase_units else {}
    captures = first_unit.get("payments", {}).get("captures", [])
    first_capture = captures[0] if captures else {}

    donation_id: Optional[int] = None
    custom_id = first_capture.get("custom_id") or first_unit.get("custom_id")
    if custom_id and str(custom_id).isdigit():
        donation_id = int(custom_id)
    else:
        donation = get_charity_donation_by_provider_order(order_id)
        if donation:
            donation_id = donation["id"]

    if not donation_id:
        add_charity_audit_log(None, "paypal_capture_unmatched", {"order_id": order_id, "payload": payload})
        raise HTTPException(status_code=404, detail="Could not map PayPal order to donation")

    capture_id = first_capture.get("id") or order_id
    updated = set_charity_donation_status(donation_id, "paid", provider_payment_id=capture_id)
    add_charity_audit_log(
        donation_id,
        "paypal_capture_completed",
        {"order_id": order_id, "capture_id": capture_id},
    )
    return {
        "message": "PayPal donation captured",
        "donation_id": donation_id,
        "receipt_number": updated.get("receipt_number"),
    }


@app.post("/charity/webhooks/stripe")
async def stripe_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("stripe-signature", "")
    if not verify_stripe_signature(raw_body, signature):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    event = json.loads(raw_body.decode("utf-8"))
    event_type = event.get("type", "")
    event_obj = event.get("data", {}).get("object", {})
    metadata = event_obj.get("metadata", {}) or {}

    donation_id_text = metadata.get("donation_id")
    donation_id = int(donation_id_text) if donation_id_text and str(donation_id_text).isdigit() else None

    if event_type == "checkout.session.completed" and donation_id:
        payment_id = event_obj.get("payment_intent") or event_obj.get("id")
        updated = set_charity_donation_status(donation_id, "paid", provider_payment_id=payment_id)
        return {
            "received": True,
            "donation_id": donation_id,
            "receipt_number": updated.get("receipt_number"),
        }

    if event_type in {"payment_intent.payment_failed", "checkout.session.expired"} and donation_id:
        set_charity_donation_status(donation_id, "failed", provider_payment_id=event_obj.get("id"))
        return {"received": True, "donation_id": donation_id, "status": "failed"}

    add_charity_audit_log(
        donation_id,
        "stripe_event_ignored",
        {"event_type": event_type, "event_id": event.get("id")},
    )
    return {"received": True}


@app.post("/charity/webhooks/paypal")
async def paypal_webhook(request: Request):
    payload = await request.json()
    event_type = payload.get("event_type", "")
    resource = payload.get("resource", {}) or {}

    if event_type != "PAYMENT.CAPTURE.COMPLETED":
        add_charity_audit_log(None, "paypal_event_ignored", {"event_type": event_type})
        return {"received": True}

    donation_id: Optional[int] = None
    custom_id = resource.get("custom_id")
    if custom_id and str(custom_id).isdigit():
        donation_id = int(custom_id)

    order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
    if not donation_id and order_id:
        donation = get_charity_donation_by_provider_order(order_id)
        if donation:
            donation_id = donation["id"]

    if not donation_id:
        add_charity_audit_log(None, "paypal_capture_unmatched", {"payload": payload})
        return {"received": True, "status": "unmatched"}

    provider_payment_id = resource.get("id")
    updated = set_charity_donation_status(donation_id, "paid", provider_payment_id=provider_payment_id)
    add_charity_audit_log(
        donation_id,
        "paypal_webhook_capture_completed",
        {"provider_payment_id": provider_payment_id, "order_id": order_id},
    )
    return {"received": True, "donation_id": donation_id, "receipt_number": updated.get("receipt_number")}


@app.get("/charity/donations", response_model=List[DonationListItem])
def list_charity_donations(
    status: Optional[str] = Query(default=None),
    donor_email: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    _admin: None = Depends(require_charity_admin),
):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            d.id, d.amount_cents, d.currency, d.payment_method, d.provider, d.provider_payment_id,
            d.status, d.receipt_number, d.tax_year, d.created_at, d.paid_at,
            dd.full_name AS donor_name, dd.email AS donor_email
        FROM charity_donations d
        JOIN charity_donors dd ON dd.id = d.donor_id
    """

    where_clauses: List[str] = []
    params: List[Any] = []

    if status:
        where_clauses.append("d.status = ?")
        params.append(status.strip().lower())
    if donor_email:
        where_clauses.append("dd.email = ?")
        params.append(donor_email.strip().lower())
    if date_from:
        where_clauses.append("d.paid_at >= ?")
        params.append(f"{date_from.strip()}T00:00:00")
    if date_to:
        where_clauses.append("d.paid_at <= ?")
        params.append(f"{date_to.strip()}T23:59:59")

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY COALESCE(d.paid_at, d.created_at) DESC, d.id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [to_donation_list_item(dict(row)) for row in rows]


@app.get("/charity/donations/export.csv", response_class=PlainTextResponse)
def export_charity_donations_csv(
    status: Optional[str] = Query(default="paid"),
    donor_email: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    _admin: None = Depends(require_charity_admin),
):
    donations = list_charity_donations(
        status=status,
        donor_email=donor_email,
        date_from=date_from,
        date_to=date_to,
    )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "donation_id",
            "donor_name",
            "donor_email",
            "amount_usd",
            "currency",
            "payment_method",
            "provider",
            "provider_payment_id",
            "status",
            "receipt_number",
            "tax_year",
            "created_at",
            "paid_at",
        ]
    )
    for item in donations:
        writer.writerow(
            [
                item.id,
                item.donor_name,
                item.donor_email,
                f"{item.amount_usd:.2f}",
                item.currency,
                item.payment_method,
                item.provider,
                item.provider_payment_id or "",
                item.status,
                item.receipt_number or "",
                item.tax_year or "",
                item.created_at,
                item.paid_at or "",
            ]
        )

    return PlainTextResponse(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="one-world-relief-donations.csv"'},
    )


@app.get("/charity/receipts/{receipt_number}")
def get_charity_receipt(receipt_number: str, _admin: None = Depends(require_charity_admin)):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            r.receipt_number, r.donor_name, r.donor_email, r.amount_cents, r.currency,
            r.receipt_text, r.email_status, r.created_at,
            d.id AS donation_id, d.payment_method, d.provider, d.provider_payment_id, d.paid_at
        FROM charity_receipts r
        JOIN charity_donations d ON d.id = r.donation_id
        WHERE r.receipt_number = ?
        """,
        (receipt_number,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")

    payload = dict(row)
    payload["amount_usd"] = cents_to_usd(payload["amount_cents"])
    return payload

# ===== DEV ENDPOINTS (For Developers to View Registered Users) =====
@app.get("/dev/users")
def get_all_users_for_dev():
    """Returns all registered users with their email and plain password for development purposes"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, plain_password FROM users ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "email": row[1],
            "password": row[2] if row[2] else "(no plain password stored)"
        })
    
    return result

# ===== RUN SERVER =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
