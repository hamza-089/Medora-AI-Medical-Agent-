"""
auth.py - sign-in system for Medora AI.

Features
- Email + password accounts (scrypt-hashed, per-user salt), stored in SQLite
- Optional email verification and password reset by 6-digit code (SMTP)
- Brute-force lockout, password change, account deletion
- Per-user chat history (so each person only ever sees their own chats)

Needs Streamlit:  uv add streamlit
"""

from __future__ import annotations

import hashlib
import hmac
import html as htmllib
import json
import os
import re
import secrets
import smtplib
import sqlite3
import time
import uuid
from email.message import EmailMessage
from pathlib import Path

import streamlit as st

DB_PATH = os.getenv("MEDORA_USERS_DB", str(Path(__file__).with_name("medora_users.db")))
MAX_FAILS = 5          # wrong passwords before a temporary lock
LOCK_SECONDS = 300     # lock length
CODE_TTL = 600         # verification / reset code lifetime (seconds)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
              id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT,
              pw_hash TEXT, provider TEXT NOT NULL DEFAULT 'email',
              verified INTEGER NOT NULL DEFAULT 1,
              fails INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0,
              created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS codes(
              email TEXT NOT NULL, purpose TEXT NOT NULL, code_hash TEXT NOT NULL,
              expires REAL NOT NULL, tries INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(email, purpose));
            CREATE TABLE IF NOT EXISTS chats(
              id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT,
              created REAL, data TEXT);
            CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id);
            """
        )


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def password_problem(password: str) -> str | None:
    if len(password) < 8:
        return "Use at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Include at least one letter and one number."
    return None


def _norm(email: str) -> str:
    return (email or "").strip().lower()


def _user_dict(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"],
            "name": row["name"] or row["email"].split("@")[0],
            "provider": row["provider"]}


# ---------------------------------------------------------------------------
# One-time codes (email verification + password reset)
# ---------------------------------------------------------------------------
def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def _send_email(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "no-reply@medora.local"))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
        s.starttls()
        if os.getenv("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        s.send_message(msg)


def issue_code(email: str, purpose: str) -> None:
    """Create a 6-digit code. Emailed when SMTP is set up; otherwise printed to the server terminal."""
    code = f"{secrets.randbelow(10**6):06d}"
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO codes(email,purpose,code_hash,expires,tries) VALUES(?,?,?,?,0)",
            (email, purpose, hashlib.sha256(f"{email}:{code}".encode()).hexdigest(),
             time.time() + CODE_TTL),
        )
    label = "verify your email" if purpose == "verify" else "reset your password"
    if smtp_configured():
        _send_email(email, "Your Medora AI code",
                    f"Use this code to {label}: {code}\nIt expires in {CODE_TTL // 60} minutes.\n"
                    "If you did not ask for it, ignore this email.")
    else:
        print(f"[Medora auth] DEV MODE - code for {email} ({purpose}): {code}", flush=True)


def check_code(email: str, purpose: str, code: str) -> bool:
    with _db() as con:
        row = con.execute("SELECT * FROM codes WHERE email=? AND purpose=?", (email, purpose)).fetchone()
        if not row or row["expires"] < time.time() or row["tries"] >= 5:
            con.execute("DELETE FROM codes WHERE email=? AND purpose=?", (email, purpose))
            return False
        ok = hmac.compare_digest(
            row["code_hash"], hashlib.sha256(f"{email}:{code.strip()}".encode()).hexdigest())
        if ok:
            con.execute("DELETE FROM codes WHERE email=? AND purpose=?", (email, purpose))
        else:
            con.execute("UPDATE codes SET tries=tries+1 WHERE email=? AND purpose=?", (email, purpose))
        return ok


# ---------------------------------------------------------------------------
# Account actions
# ---------------------------------------------------------------------------
def register(name: str, email: str, password: str) -> tuple[bool, str]:
    email = _norm(email)
    if not name.strip():
        return False, "Please enter your name."
    if not EMAIL_RE.match(email):
        return False, "Enter a valid email address."
    if (problem := password_problem(password)):
        return False, problem
    needs_verify = smtp_configured()
    try:
        with _db() as con:
            con.execute(
                "INSERT INTO users(id,email,name,pw_hash,provider,verified,created) VALUES(?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, email, name.strip(), hash_password(password), "email",
                 0 if needs_verify else 1, time.time()),
            )
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists. Try signing in."
    if needs_verify:
        issue_code(email, "verify")
        return True, "verify"
    return True, "created"


def verify_email(email: str, code: str) -> bool:
    email = _norm(email)
    if check_code(email, "verify", code):
        with _db() as con:
            con.execute("UPDATE users SET verified=1 WHERE email=?", (email,))
        return True
    return False


def login(email: str, password: str) -> tuple[dict | None, str]:
    email = _norm(email)
    generic = "Incorrect email or password."
    with _db() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            hash_password(password)  # keep timing similar
            return None, generic
        if row["locked_until"] > time.time():
            mins = int((row["locked_until"] - time.time()) // 60) + 1
            return None, f"Too many attempts. Try again in about {mins} minute(s)."
        if not verify_password(password, row["pw_hash"]):
            fails = row["fails"] + 1
            locked = time.time() + LOCK_SECONDS if fails >= MAX_FAILS else 0
            con.execute("UPDATE users SET fails=?, locked_until=? WHERE id=?",
                        (0 if locked else fails, locked, row["id"]))
            return None, generic
        if not row["verified"]:
            return None, "unverified"
        con.execute("UPDATE users SET fails=0, locked_until=0 WHERE id=?", (row["id"],))
        return _user_dict(row), "ok"


def reset_password(email: str, code: str, new_password: str) -> tuple[bool, str]:
    email = _norm(email)
    if (problem := password_problem(new_password)):
        return False, problem
    if not check_code(email, "reset", code):
        return False, "That code is wrong or has expired."
    with _db() as con:
        con.execute("UPDATE users SET pw_hash=?, fails=0, locked_until=0, verified=1 WHERE email=?",
                    (hash_password(new_password), email))
    return True, "Password updated. You can sign in now."


def change_password(user_id: str, old: str, new: str) -> tuple[bool, str]:
    if (problem := password_problem(new)):
        return False, problem
    with _db() as con:
        row = con.execute("SELECT pw_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if row and row["pw_hash"] and not verify_password(old, row["pw_hash"]):
            return False, "Current password is incorrect."
        con.execute("UPDATE users SET pw_hash=? WHERE id=?", (hash_password(new), user_id))
    return True, "Password changed."


def delete_account(user_id: str) -> None:
    with _db() as con:
        con.execute("DELETE FROM chats WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM users WHERE id=?", (user_id,))


# ---------------------------------------------------------------------------
# Per-user chat storage
# ---------------------------------------------------------------------------
def save_chat(user_id: str, chat: dict) -> None:
    data = {
        "messages": [{**m, "audio": None} for m in chat["messages"]],
        "vs_id": chat["vs_id"], "files": chat["files"], "summary": chat["summary"],
        "processed": sorted(chat["processed"]),
    }
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO chats(id,user_id,title,created,data) VALUES(?,?,?,?,?)",
            (chat["id"], user_id, chat["title"], chat["created"], json.dumps(data)))


def load_chats(user_id: str) -> dict:
    chats = {}
    with _db() as con:
        for r in con.execute("SELECT * FROM chats WHERE user_id=?", (user_id,)):
            d = json.loads(r["data"])
            chats[r["id"]] = {
                "id": r["id"], "title": r["title"], "created": r["created"],
                "messages": d["messages"], "vs_id": d["vs_id"], "files": d["files"],
                "summary": d["summary"], "processed": set(d["processed"]), "uploader_n": 0,
            }
    return chats


def delete_chat_row(user_id: str, chat_id: str) -> None:
    with _db() as con:
        con.execute("DELETE FROM chats WHERE id=? AND user_id=?", (chat_id, user_id))


# ---------------------------------------------------------------------------
# Session handling
# ---------------------------------------------------------------------------
def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def sign_out() -> None:
    st.session_state.clear()
    st.rerun()


def _start(user: dict) -> None:
    st.session_state.auth_user = user
    st.rerun()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def _esc(t: str) -> str:
    return htmllib.escape(t)


def _brand_panel() -> None:
    st.markdown(
        """
        <div class="auth-brand">
          <div class="auth-logo"><span>M</span>Medora</div>
          <div>
            <div class="auth-headline">Health information,<br>explained with care.</div>
            <p>Ask about medical terms, understand a de-identified report, and keep every
            conversation private to your account.</p>
          </div>
          <small>Educational information only. Medora does not diagnose conditions or replace
          a qualified healthcare professional.</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _sign_in_tab() -> None:
    if st.session_state.get("pending_verify"):
        _verify_form(st.session_state.pending_verify)
        return

    with st.form("signin_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="Your password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        user, msg = login(email, password)
        if user:
            _start(user)
        elif msg == "unverified":
            issue_code(_norm(email), "verify")
            st.session_state.pending_verify = _norm(email)
            st.rerun()
        else:
            st.error(msg)


def _verify_form(email: str) -> None:
    st.info(f"We sent a 6-digit code to {email}. "
            + ("" if smtp_configured() else "(Dev mode: the code is printed in the server terminal.)"))
    with st.form("verify_form"):
        code = st.text_input("Verification code", max_chars=6)
        ok = st.form_submit_button("Verify email", type="primary", use_container_width=True)
    if ok:
        if verify_email(email, code):
            st.session_state.pop("pending_verify", None)
            st.success("Email verified. Please sign in.")
        else:
            st.error("That code is wrong or has expired.")
    if st.button("Cancel", key="verify_cancel"):
        st.session_state.pop("pending_verify", None)
        st.rerun()


def _sign_up_tab() -> None:
    with st.form("signup_form"):
        name = st.text_input("Full name")
        email = st.text_input("Email", placeholder="you@example.com", key="su_email")
        password = st.text_input("Password", type="password", key="su_pw",
                                 help="At least 8 characters, with a letter and a number.")
        confirm = st.text_input("Confirm password", type="password", key="su_pw2")
        agree = st.checkbox("I understand Medora provides educational information, not medical advice.")
        submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
    if submitted:
        if password != confirm:
            st.error("Passwords do not match.")
        elif not agree:
            st.error("Please accept the notice to continue.")
        else:
            ok, msg = register(name, email, password)
            if not ok:
                st.error(msg)
            elif msg == "verify":
                st.session_state.pending_verify = _norm(email)
                st.rerun()
            else:
                user, _ = login(email, password)
                if user:
                    _start(user)


def _reset_tab() -> None:
    step = st.session_state.get("reset_email")
    if not step:
        with st.form("reset_request"):
            email = st.text_input("Account email", key="rs_email")
            go = st.form_submit_button("Send reset code", use_container_width=True)
        if go:
            email = _norm(email)
            if EMAIL_RE.match(email):
                with _db() as con:
                    exists = con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
                if exists:
                    issue_code(email, "reset")
                st.session_state.reset_email = email  # same message either way (no account probing)
                st.rerun()
            else:
                st.error("Enter a valid email address.")
        return
    st.info(f"If an account exists for {step}, a code was sent. "
            + ("" if smtp_configured() else "(Dev mode: see the server terminal.)"))
    with st.form("reset_confirm"):
        code = st.text_input("6-digit code", max_chars=6)
        new_pw = st.text_input("New password", type="password", key="rs_pw")
        go = st.form_submit_button("Set new password", type="primary", use_container_width=True)
    if go:
        ok, msg = reset_password(step, code, new_pw)
        if ok:
            st.session_state.pop("reset_email", None)
            st.success(msg)
        else:
            st.error(msg)
    if st.button("Start over", key="reset_cancel"):
        st.session_state.pop("reset_email", None)
        st.rerun()


def render_login() -> None:
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        _brand_panel()
    with right:
        st.markdown('<div class="auth-title">Welcome</div>'
                    '<div class="auth-sub">Sign in to continue your conversations.</div>',
                    unsafe_allow_html=True)
        t1, t2, t3 = st.tabs(["Sign in", "Create account", "Forgot password"])
        with t1:
            _sign_in_tab()
        with t2:
            _sign_up_tab()
        with t3:
            _reset_tab()


def require_login() -> dict:
    """Call near the top of app.py. Returns the signed-in user, or shows the login page and stops."""
    init_db()
    user = current_user()
    if user:
        return user
    render_login()
    st.stop()


def render_account_settings(user: dict) -> None:
    """Change password + delete account (use inside a sidebar expander)."""
    st.caption(f"Signed in with {user['provider'].title()} · {user['email']}")
    if user["provider"] == "email":
        with st.form("chpw"):
            old = st.text_input("Current password", type="password")
            new = st.text_input("New password", type="password")
            if st.form_submit_button("Change password"):
                ok, msg = change_password(user["id"], old, new)
                (st.success if ok else st.error)(msg)
    sure = st.checkbox("Permanently delete my account and chats", key="del_acct_ok")
    if st.button("Delete account", disabled=not sure, key="del_acct"):
        delete_account(user["id"])
        sign_out()