# ═══════════════════════════════════════════════════════════════
#  BOT LIÊN QUÂN SUPER VERSION: VIP, ĐIỂM DANH, REF, MINI-GAME & WEB PORT
#  Cài thư viện: pip install aiogram==3.13.1 sqlalchemy==2.0.36 aiosqlite==0.20.0 aiofiles==24.1.0 aiohttp
# ═══════════════════════════════════════════════════════════════

# ── SỬA 2 DÒNG NÀY TRƯỚC KHI CHẠY ──────────────────────────────
BOT_TOKEN = "8374524579:AAE2pvVgQqOFnEN2hnhhfRUyopi1B8Dhxcc"
ADMIN_IDS = [7936179657]  # Telegram ID của admin
# ────────────────────────────────────────────────────────────────

import asyncio
import enum
import functools
import logging
import os
import sys
import uuid
import random
import datetime as dt_mod
from datetime import datetime, date
from typing import Any, Awaitable, Callable

import aiofiles
from aiohttp import web
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    TelegramObject,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
)

# ── Cấu hình hệ thống ──────────────────────────────────────────────────────────

ACCOUNT_PRICE = 200  # VNĐ mỗi acc
VIP_WEEK_PRICE = 50000  # VNĐ gói tuần
VIP_MONTH_PRICE = 100000  # VNĐ gói tháng
VIP_DAILY_LIMIT = 100  # Số acc free tối đa mỗi ngày của VIP
LOW_STOCK_ALERT = 10  # Ngưỡng cảnh báo hết acc gửi cho Admin

CHECKER_LINK = "https://t.me/tretrauchecker_bot?start=ref_7936179657"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
QR_IMAGE_PATH = os.path.join(UPLOADS_DIR, "qr_current.jpg")
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'database.sqlite')}"

MENU_BUTTONS = {
    "🏠 Trang Chủ", "🛒 Mua Acc", "💳 Nạp Tiền", "👤 Tài Khoản", 
    "📦 Đơn Hàng", "☎ Hỗ Trợ", "🎁 Free & VIP", "🎮 Mini Game", "📊 Dashboard", 
    "📥 Import TXT", "📦 Xem Kho", "📊 Thống Kê", "💰 Cộng Tiền", 
    "💸 Trừ Tiền", "📷 Đổi QR", "📥 Bill Chờ", "📢 Broadcast", 
    "🚫 Ban User", "✅ Unban User", "🗑 Xóa Account", "📤 Export Chưa Bán", 
    "📤 Export Đã Bán", "🔙 Menu Chính", "❌ Hủy"
}

# ── Logging ───────────────────────────────────────────────────────────────────

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOGS_DIR, "bot.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Database ──────────────────────────────────────────────────────────────────

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# ── Models ────────────────────────────────────────────────────────────────────

class AccountStatus(str, enum.Enum):
    available = "available"
    sold = "sold"

class OrderStatus(str, enum.Enum):
    completed = "completed"
    cancelled = "cancelled"

class DepositStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fullname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Hệ thống Điểm (Points) & VIP
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vip_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_checkin_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    vip_claimed_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_vip_claim_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")
    deposits: Mapped[list["Deposit"]] = relationship("Deposit", back_populates="user")

    @property
    def is_vip(self) -> bool:
        if self.vip_until and self.vip_until > datetime.utcnow():
            return True
        return False

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(Enum(AccountStatus), nullable=False, default=AccountStatus.available)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order: Mapped["Order|None"] = relationship("Order", back_populates="accounts")

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False, default=OrderStatus.completed)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user: Mapped["User"] = relationship("User", back_populates="orders")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="order")

class Deposit(Base):
    __tablename__ = "deposits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    bill_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[DepositStatus] = mapped_column(Enum(DepositStatus), nullable=False, default=DepositStatus.pending)
    admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user: Mapped["User"] = relationship("User", back_populates="deposits")

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")

# ── Services ──────────────────────────────────────────────────────────────────

async def get_or_create_user(session, telegram_id, username, fullname, is_admin=False, referrer_id=None, bot: Bot = None):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            fullname=fullname,
            is_admin=is_admin,
            referred_by=referrer_id if referrer_id and referrer_id != telegram_id else None
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        # Thưởng 5,000 điểm cho người giới thiệu (Ref)
        if user.referred_by:
            ref_result = await session.execute(select(User).where(User.telegram_id == user.referred_by))
            referrer = ref_result.scalar_one_or_none()
            if referrer:
                referrer.points += 5000
                await session.commit()
                if bot:
                    try:
                        await bot.send_message(
                            user.referred_by,
                            f"🔔 <b>Thông báo giới thiệu!</b>\n\n"
                            f"Thành viên <b>{fullname}</b> vừa tham gia qua link của bạn.\n"
                            f"🎉 Bạn nhận được thưởng: +<b>5,000 điểm</b> vào ví!",
                            parse_mode="HTML"
                        )
                    except Exception: pass
    else:
        changed = False
        if user.username != username:
            user.username = username
            changed = True
        if user.fullname != fullname:
            user.fullname = fullname
            changed = True
        if changed:
            await session.commit()
            await session.refresh(user)
    return user

async def get_user_by_telegram_id(session, telegram_id):
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return r.scalar_one_or_none()

async def get_user_by_id(session, user_id):
    r = await session.execute(select(User).where(User.id == user_id))
    return r.scalar_one_or_none()

async def add_balance(session, user_id, amount):
    user = await get_user_by_id(session, user_id)
    if user is None: return None
    user.balance += amount
    await session.commit()
    await session.refresh(user)
    return user

async def adjust_balance_by_telegram_id(session, telegram_id, amount):
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None: return None
    user.balance += amount
    if user.balance < 0: user.balance = 0
    await session.commit()
    await session.refresh(user)
    return user

async def ban_user(session, telegram_id):
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = r.scalar_one_or_none()
    if user is None: return False
    user.is_banned = True
    await session.commit()
    return True

async def unban_user(session, telegram_id):
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = r.scalar_one_or_none()
    if user is None: return False
    user.is_banned = False
    await session.commit()
    return True

async def get_all_users(session):
    r = await session.execute(select(User))
    return list(r.scalars().all())

async def get_available_count(session):
    r = await session.execute(select(func.count()).where(Account.status == AccountStatus.available))
    return r.scalar_one()

async def get_sold_count(session):
    r = await session.execute(select(func.count()).where(Account.status == AccountStatus.sold))
    return r.scalar_one()

async def get_total_count(session):
    r = await session.execute(select(func.count()).select_from(Account))
    return r.scalar_one()

async def check_and_alert_stock(session, bot: Bot):
    available = await get_available_count(session)
    if available <= LOW_STOCK_ALERT:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id, 
                    f"⚠️ <b>CẢNH BÁO KHẨN CẤP: KHO SẮP HẾT ACC!</b>\n\n"
                    f"📦 Số lượng acc khả dụng còn lại: <b>{available}</b>\n"
                    f"📌 Sếp vui lòng nạp thêm file TXT để tránh gián đoạn dịch vụ nhé!",
                    parse_mode="HTML"
                )
            except Exception: pass

async def pick_random_accounts(session, quantity):
    r = await session.execute(select(Account).where(Account.status == AccountStatus.available).order_by(func.random()).limit(quantity))
    return list(r.scalars().all())

async def mark_accounts_sold(session, accounts, order_id=None):
    now = datetime.utcnow()
    for acc in accounts:
        acc.status = AccountStatus.sold
        acc.order_id = order_id
        acc.sold_at = now
    await session.commit()

async def import_accounts(session, lines):
    stats = {"total": 0, "imported": 0, "duplicates": 0, "invalid": 0}
    for raw in lines:
        line = raw.strip()
        if not line: continue
        stats["total"] += 1
        if "|" in line: parts = line.split("|", 1)
        elif ":" in line: parts = line.split(":", 1)
        else: stats["invalid"] += 1; continue
        uname, pwd = parts[0].strip(), parts[1].strip()
        if not uname or not pwd: stats["invalid"] += 1; continue
        ex = await session.execute(select(Account).where(Account.username == uname))
        if ex.scalar_one_or_none() is not None: stats["duplicates"] += 1; continue
        session.add(Account(username=uname, password=pwd, status=AccountStatus.available))
        stats["imported"] += 1
    await session.commit()
    return stats

async def get_unsold_accounts(session):
    r = await session.execute(select(Account).where(Account.status == AccountStatus.available))
    return list(r.scalars().all())

async def get_sold_accounts(session):
    r = await session.execute(select(Account).where(Account.status == AccountStatus.sold))
    return list(r.scalars().all())

async def delete_account_by_username(session, username):
    r = await session.execute(select(Account).where(Account.username == username))
    acc = r.scalar_one_or_none()
    if acc is None: return False
    await session.delete(acc)
    await session.commit()
    return True

async def create_order(session, user_id, quantity, price, file_name):
    order = Order(user_id=user_id, quantity=quantity, price=price, status=OrderStatus.completed, file_name=file_name)
    session.add(order)
    await session.flush()
    return order

async def get_user_orders(session, user_id, limit=20):
    r = await session.execute(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit))
    return list(r.scalars().all())

async def get_all_orders(session, limit=50):
    r = await session.execute(select(Order).order_by(Order.created_at.desc()).limit(limit))
    return list(r.scalars().all())

async def create_deposit(session, user_id, amount, bill_image=None):
    dep = Deposit(user_id=user_id, amount=amount, bill_image=bill_image, status=DepositStatus.pending)
    session.add(dep)
    await session.commit()
    await session.refresh(dep)
    return dep

async def get_deposit_by_id(session, deposit_id):
    r = await session.execute(select(Deposit).options(selectinload(Deposit.user)).where(Deposit.id == deposit_id))
    return r.scalar_one_or_none()

async def approve_deposit(session, deposit_id, admin_tg_id):
    dep = await get_deposit_by_id(session, deposit_id)
    if dep is None or dep.status != DepositStatus.pending: return None
    dep.status = DepositStatus.approved
    dep.admin_id = admin_tg_id
    dep.approved_at = datetime.utcnow()
    await session.commit()
    await session.refresh(dep)
    return dep

async def reject_deposit(session, deposit_id, admin_tg_id):
    dep = await get_deposit_by_id(session, deposit_id)
    if dep is None or dep.status != DepositStatus.pending: return None
    dep.status = DepositStatus.rejected
    dep.admin_id = admin_tg_id
    dep.approved_at = datetime.utcnow()
    await session.commit()
    await session.refresh(dep)
    return dep

async def get_pending_deposits(session):
    r = await session.execute(select(Deposit).options(selectinload(Deposit.user)).where(Deposit.status == DepositStatus.pending).order_by(Deposit.created_at.asc()))
    return list(r.scalars().all())

# ── File utils ────────────────────────────────────────────────────────────────

async def save_export_file(lines, prefix):
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fp = os.path.join(EXPORTS_DIR, f"{prefix}_{ts}.txt")
    async with aiofiles.open(fp, "w", encoding="utf-8") as f:
        await f.write("\n".join(lines))
    return fp

async def save_order_file(accounts_data, prefix_name="order"):
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix_name}_{uuid.uuid4().hex[:6]}_{ts}.txt"
    fp = os.path.join(EXPORTS_DIR, filename)
    async with aiofiles.open(fp, "w", encoding="utf-8") as f:
        await f.write("\n".join(f"{u}|{p}" for u, p in accounts_data))
    return fp, filename

async def save_bill_image(file_bytes, extension="jpg"):
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    fp = os.path.join(UPLOADS_DIR, f"bill_{uuid.uuid4().hex}.{extension}")
    async with aiofiles.open(fp, "wb") as f:
        await f.write(file_bytes)
    return fp

async def save_qr_image(file_bytes):
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    async with aiofiles.open(QR_IMAGE_PATH, "wb") as f:
        await f.write(file_bytes)
    return QR_IMAGE_PATH

def qr_exists():
    return os.path.isfile(QR_IMAGE_PATH)

# ── Keyboards ─────────────────────────────────────────────────────────────────

def main_menu_kb():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🏠 Trang Chủ"), KeyboardButton(text="🛒 Mua Acc"))
    b.row(KeyboardButton(text="💳 Nạp Tiền"), KeyboardButton(text="👤 Tài Khoản"))
    b.row(KeyboardButton(text="📦 Đơn Hàng"), KeyboardButton(text="🎁 Free & VIP"))
    b.row(KeyboardButton(text="🎮 Mini Game"), KeyboardButton(text="☎ Hỗ Trợ"))
    return b.as_markup(resize_keyboard=True)

def free_vip_menu_kb():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📅 Điểm Danh Nhận Điểm"), KeyboardButton(text="🔗 Link Giới Thiệu"))
    b.row(KeyboardButton(text="👑 Nhận Acc VIP (100/ngày)"), KeyboardButton(text="🔄 Đổi Điểm Ra Tiền"))
    b.row(KeyboardButton(text="⚡ Mua Gói VIP"), KeyboardButton(text="🔙 Menu Chính"))
    return b.as_markup(resize_keyboard=True)

def minigame_menu_kb():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🎰 Vòng Quay May Mắn (200 điểm)"), KeyboardButton(text="🎲 Tài Xỉu Xúc Xắc"))
    b.row(KeyboardButton(text="🔙 Menu Chính"))
    return b.as_markup(resize_keyboard=True)

def taixiu_inline_kb():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔺 TÀI (4-6 nút)", callback_data="tx_bet:tai"),
          InlineKeyboardButton(text="🔻 XỈU (1-3 nút)", callback_data="tx_bet:xiu"))
    return b.as_markup()

def buy_vip_inline_kb():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="👑 VIP Tuần (50,000đ)", callback_data="buy_vip:week"))
    b.row(InlineKeyboardButton(text="👑 VIP Tháng (100,000đ)", callback_data="buy_vip:month"))
    return b.as_markup()

def cancel_kb():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="❌ Hủy"))
    return b.as_markup(resize_keyboard=True)

def deposit_approval_kb(deposit_id):
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ DUYỆT", callback_data=f"approve_deposit:{deposit_id}"),
        InlineKeyboardButton(text="❌ TỪ CHỐI", callback_data=f"reject_deposit:{deposit_id}"),
    )
    return b.as_markup()

def admin_menu_kb():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📊 Dashboard"), KeyboardButton(text="📥 Import TXT"))
    b.row(KeyboardButton(text="📦 Xem Kho"), KeyboardButton(text="📊 Thống Kê"))
    b.row(KeyboardButton(text="💰 Cộng Tiền"), KeyboardButton(text="💸 Trừ Tiền"))
    b.row(KeyboardButton(text="📷 Đổi QR"), KeyboardButton(text="📥 Bill Chờ"))
    b.row(KeyboardButton(text="📢 Broadcast"), KeyboardButton(text="🚫 Ban User"))
    b.row(KeyboardButton(text="✅ Unban User"), KeyboardButton(text="🗑 Xóa Account"))
    b.row(KeyboardButton(text="📤 Export Chưa Bán"), KeyboardButton(text="📤 Export Đã Bán"))
    b.row(KeyboardButton(text="🔙 Menu Chính"))
    return b.as_markup(resize_keyboard=True)

# ── Middleware ────────────────────────────────────────────────────────────────

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None: return await handler(event, data)
        is_admin = user.id in ADMIN_IDS
        fullname = (user.full_name or "").strip() or user.username or str(user.id)
        
        referrer_id = None
        if isinstance(event, Message) and event.text and event.text.startswith("/start ref_"):
            try: referrer_id = int(event.text.split("ref_")[1])
            except Exception: pass

        bot = data.get("bot")
        async with AsyncSessionLocal() as session:
            db_user = await get_or_create_user(
                session, user.id, user.username, fullname, is_admin, referrer_id, bot
            )
            if db_user.is_admin != is_admin:
                db_user.is_admin = is_admin
                await session.commit()
            data["db_user"] = db_user
            data["db_session"] = session
            data["is_admin"] = is_admin
            if db_user.is_banned and not is_admin:
                if isinstance(event, Message):
                    await event.answer("🚫 Bạn đã bị cấm sử dụng bot.")
                return
            return await handler(event, data)

# ── States ────────────────────────────────────────────────────────────────────

class ShopState(StatesGroup):
    waiting_quantity = State()
    waiting_vip_claim_qty = State()
    waiting_exchange_points = State()
    waiting_tx_points = State()

class DepositState(StatesGroup):
    waiting_amount = State()
    waiting_bill = State()

class AdminStates(StatesGroup):
    waiting_qr = State()
    waiting_import_file = State()
    waiting_add_balance_id = State()
    waiting_add_balance_amount = State()
    waiting_subtract_balance_id = State()
    waiting_subtract_balance_amount = State()
    waiting_ban_id = State()
    waiting_unban_id = State()
    waiting_delete_username = State()
    waiting_broadcast_text = State()

# ── Helpers ───────────────────────────────────────────────────────────────────

def admin_only(func):
    @functools.wraps(func)
    async def wrapper(message: Message, is_admin: bool, *args, **kwargs):
        if not is_admin:
            await message.answer("❌ Bạn không có quyền truy cập.")
            return
        return await func(message, is_admin=is_admin, *args, **kwargs)
    return wrapper

# ── Router ────────────────────────────────────────────────────────────────────

router = Router()

# ── Lệnh Lập VIP Nhanh Cho Admin ───────────────────────────────────────────────

@router.message(Command("setvip"))
async def cmd_set_vip(message: Message, is_admin: bool):
    if not is_admin:
        await message.answer("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("⚠️ Cú pháp: <code>/setvip [Telegram_ID] [Số_ngày]</code>", parse_mode="HTML")
        return
    try:
        target_tg_id, days = int(args[1]), int(args[2])
    except ValueError:
        await message.answer("⚠️ Telegram ID và Số ngày phải là chữ số.")
        return

    async with AsyncSessionLocal() as s:
        user = await get_user_by_telegram_id(s, target_tg_id)
        if not user:
            await message.answer("❌ Không tìm thấy người dùng này.")
            return
        now = datetime.utcnow()
        user.vip_until = (user.vip_until if user.vip_until and user.vip_until > now else now) + dt_mod.timedelta(days=days)
        time_str = user.vip_until.strftime("%d/%m/%Y %H:%M")
        await s.commit()
    await message.answer(f"👑 Đã cấp VIP cho <b>{user.fullname}</b> thêm <b>{days} ngày</b>.\n⏰ Hạn: <b>{time_str}</b>", parse_mode="HTML")

# ── /start & Trang Chủ ─────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    name = db_user.fullname or message.from_user.full_name or "bạn"
    async with AsyncSessionLocal() as s: available = await get_available_count(s)
    vip_status = "👑 VIP" if db_user.is_vip else "Thường"
    await message.answer(
        f"👋 Chào mừng <b>{name}</b> đến với Shop Liên Quân!\n\n"
        f"🛒 Mua acc chất lượng, giá rẻ\n"
        f"🏅 Cấp bậc: <b>{vip_status}</b>\n"
        f"💰 Số dư: <b>{db_user.balance:,} VNĐ</b>\n"
        f"🪙 Ví điểm: <b>{db_user.points:,} Điểm</b>\n"
        f"📦 Kho còn: <b>{available:,} acc</b>\n\n"
        "Chọn chức năng bên dưới:",
        parse_mode="HTML", reply_markup=main_menu_kb(),
    )

@router.message(lambda m: m.text in ("🏠 Trang Chủ", "🔙 Menu Chính"))
async def home(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    async with AsyncSessionLocal() as s: available = await get_available_count(s)
    name = db_user.fullname or message.from_user.full_name or "bạn"
    vip_status = "👑 VIP" if db_user.is_vip else "Thường"
    await message.answer(
        f"🏠 <b>Trang Chủ Shop</b>\n\n"
        f"👋 Xin chào <b>{name}</b>!\n"
        f"🏅 Cấp bậc: <b>{vip_status}</b>\n"
        f"💰 Số dư: <b>{db_user.balance:,} VNĐ</b>\n"
        f"🪙 Ví điểm: <b>{db_user.points:,} Điểm</b>\n"
        f"📦 Kho còn: <b>{available:,} acc</b>\n\n"
        "Chọn chức năng bên dưới:",
        parse_mode="HTML", reply_markup=main_menu_kb(),
    )

@router.message(lambda m: m.text == "☎ Hỗ Trợ")
async def support(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("☎ <b>Hỗ Trợ</b>\n\n👤 Admin: @lananh9719\n⏰ Thời gian hỗ trợ: 8:00 - 22:00", parse_mode="HTML")

# ── Shop (Mua Acc) ────────────────────────────────────────────────────────────

@router.message(lambda m: m.text == "🛒 Mua Acc")
async def buy_acc_start(message: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as s: available = await get_available_count(s)
    await message.answer(
        f"🛒 <b>Mua Acc Liên Quân</b>\n\n💵 Giá: <b>{ACCOUNT_PRICE:,} VNĐ / 1 acc</b>\n📦 Kho còn: <b>{available:,} acc</b>\n\nNhập số lượng acc bạn muốn mua:",
        parse_mode="HTML", reply_markup=cancel_kb(),
    )
    await state.set_state(ShopState.waiting_quantity)

@router.message(ShopState.waiting_quantity, F.text == "❌ Hủy")
async def buy_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy lệnh mua.", reply_markup=main_menu_kb())

@router.message(ShopState.waiting_quantity, ~F.text.in_(MENU_BUTTONS))
async def buy_acc_quantity(message: Message, state: FSMContext, db_user: User, bot: Bot):
    text = message.text or ""
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Vui lòng nhập số nguyên hợp lệ lớn hơn 0.")
        return
    quantity = int(text)
    total_price = quantity * ACCOUNT_PRICE
    
    async with AsyncSessionLocal() as s:
        fresh_user = await get_user_by_id(s, db_user.id)
        if fresh_user.balance < total_price:
            await message.answer(f"❌ Số dư không đủ! Thiếu {(total_price - fresh_user.balance):,} VNĐ.", reply_markup=main_menu_kb())
            await state.clear()
            return
        available = await get_available_count(s)
        if available < quantity:
            await message.answer(f"❌ Kho không đủ hàng! Chỉ còn {available} acc.", reply_markup=main_menu_kb())
            await state.clear()
            return
        
        accounts = await pick_random_accounts(s, quantity)
        order = await create_order(s, fresh_user.id, quantity, total_price, "")
        fresh_user.balance -= total_price
        await mark_accounts_sold(s, accounts, order.id)
        account_data = [(a.username, a.password) for a in accounts]
        filepath, filename = await save_order_file(account_data, "order")
        order.file_name = filename
        await s.commit()
        await check_and_alert_stock(s, bot)
        
    await state.clear()
    await message.answer(f"✅ <b>Mua thành công {quantity} acc!</b> đơn #{order.id}", parse_mode="HTML", reply_markup=main_menu_kb())
    await message.answer_document(FSInputFile(filepath, filename=filename))

# ── Khu vực Free & VIP (Điểm danh, Ref, Đổi điểm) ────────────────────────────────

@router.message(lambda m: m.text == "🎁 Free & VIP")
async def free_vip_menu(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    today = date.today()
    checkin_status = "Đã nhận hôm nay" if db_user.last_checkin_date == today else "Chưa nhận (+500 điểm)"
    vip_claim_status = f"Đã lấy {db_user.vip_claimed_today if db_user.last_vip_claim_date == today else 0}/{VIP_DAILY_LIMIT} acc" if db_user.is_vip else "Hết hạn VIP"

    await message.answer(
        f"🎁 <b>KHU VỰC FREE & VIP</b>\n\n"
        f"🪙 Điểm hiện có: <b>{db_user.points:,} Điểm</b>\n"
        f"📅 Điểm danh hôm nay: <i>{checkin_status}</i>\n"
        f"👑 Nhận acc VIP: <i>{vip_claim_status}</i>\n\n"
        f"📌 <b>Tỷ lệ đổi: 100 điểm = 10 VNĐ</b>",
        parse_mode="HTML", reply_markup=free_vip_menu_kb()
    )

@router.message(lambda m: m.text == "📅 Điểm Danh Nhận Điểm")
async def daily_checkin(message: Message, db_user: User):
    today = date.today()
    if db_user.last_checkin_date == today:
        await message.answer("⚠️ Hôm nay bạn đã điểm danh rồi!")
        return
    async with AsyncSessionLocal() as s:
        fresh_user = await get_user_by_id(s, db_user.id)
        fresh_user.points += 500
        fresh_user.last_checkin_date = today
        await s.commit()
    await message.answer("🎉 Điểm danh thành công! Bạn nhận được +<b>500 điểm</b>.", parse_mode="HTML")

@router.message(lambda m: m.text == "🔗 Link Giới Thiệu")
async def referral_link(message: Message, bot: Bot, db_user: User):
    bot_info = await bot.get_me()
    ref_url = f"https://t.me/{bot_info.username}?start=ref_{db_user.telegram_id}"
    await message.answer(f"🔗 <b>LINK REF CỦA BẠN:</b>\n<code>{ref_url}</code>\n\n🎁 Nhận ngay +<b>5,000 điểm</b> khi có bạn mới dùng bot!", parse_mode="HTML")

@router.message(lambda m: m.text == "🔄 Đổi Điểm Ra Tiền")
async def exchange_points_start(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    await message.answer(f"🪙 Bạn đang có: <b>{db_user.points:,} Điểm</b>\n📌 Tỷ lệ đổi: 100 điểm = 10đ\n\nNhập số điểm muốn đổi (Phải chia hết cho 100):", parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(ShopState.waiting_exchange_points)

@router.message(ShopState.waiting_exchange_points, F.text == "❌ Hủy")
async def exchange_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy đổi điểm.", reply_markup=free_vip_menu_kb())

@router.message(ShopState.waiting_exchange_points, ~F.text.in_(MENU_BUTTONS))
async def exchange_points_execute(message: Message, state: FSMContext, db_user: User):
    text = message.text or ""
    if not text.isdigit() or int(text) < 100 or int(text) % 100 != 0:
        await message.answer("⚠️ Số điểm phải là số nguyên lớn hơn 100 và chia hết cho 100.")
        return
    pts = int(text)
    
    async with AsyncSessionLocal() as s:
        fresh_user = await get_user_by_id(s, db_user.id)
        if fresh_user.points < pts:
            await message.answer("❌ Bạn không đủ số điểm này để đổi.")
            return
        money = (pts // 100) * 10
        fresh_user.points -= pts
        fresh_user.balance += money
        await s.commit()
    await state.clear()
    await message.answer(f"🎉 <b>Đổi điểm thành công!</b>\n🔥 Trừ: -<b>{pts:,} điểm</b>\n💰 Cộng: +<b>{money:,} VNĐ</b> vào ví chính!", parse_mode="HTML", reply_markup=free_vip_menu_kb())

@router.message(lambda m: m.text == "👑 Nhận Acc VIP (100/ngày)")
async def vip_claim_start(message: Message, state: FSMContext, db_user: User):
    if not db_user.is_vip:
        await message.answer("❌ Tính năng này chỉ dành cho thành viên VIP!")
        return
    today = date.today()
    claimed = db_user.vip_claimed_today if db_user.last_vip_claim_date == today else 0
    left = VIP_DAILY_LIMIT - claimed
    if left <= 0:
        await message.answer("⚠️ Hôm nay bạn đã nhận hết giới hạn 100 acc VIP rồi.")
        return
    await message.answer(f"👑 Bạn còn có thể lấy: <b>{left} acc VIP free</b> hôm nay.\nNhập số lượng muốn lấy:", parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(ShopState.waiting_vip_claim_qty)

@router.message(ShopState.waiting_vip_claim_qty, F.text == "❌ Hủy")
async def vip_claim_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy.", reply_markup=free_vip_menu_kb())

@router.message(ShopState.waiting_vip_claim_qty, ~F.text.in_(MENU_BUTTONS))
async def vip_claim_execute(message: Message, state: FSMContext, db_user: User, bot: Bot):
    text = message.text or ""
    if not text.isdigit() or int(text) <= 0: return
    qty = int(text)
    today = date.today()
    
    async with AsyncSessionLocal() as s:
        fresh_user = await get_user_by_id(s, db_user.id)
        claimed = fresh_user.vip_claimed_today if fresh_user.last_vip_claim_date == today else 0
        if qty > (VIP_DAILY_LIMIT - claimed):
            await message.answer("⚠️ Số lượng vượt mức giới hạn còn lại trong ngày.")
            return
        available = await get_available_count(s)
        if available < qty:
            await message.answer("❌ Kho không đủ hàng.")
            return
        accounts = await pick_random_accounts(s, qty)
        if fresh_user.last_vip_claim_date == today: fresh_user.vip_claimed_today += qty
        else:
            fresh_user.last_vip_claim_date = today
            fresh_user.vip_claimed_today = qty
        await mark_accounts_sold(s, accounts, None)
        account_data = [(a.username, a.password) for a in accounts]
        filepath, filename = await save_order_file(account_data, "vip_free")
        await s.commit()
        await check_and_alert_stock(s, bot)
        
    await state.clear()
    await message.answer(f"🎉 VIP nhận thành công {qty} acc free!", reply_markup=free_vip_menu_kb())
    await message.answer_document(FSInputFile(filepath, filename=filename))

@router.message(lambda m: m.text == "⚡ Mua Gói VIP")
async def buy_vip_menu(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    await message.answer(f"👑 <b>MUA VIP TỰ ĐỘNG</b>\n\n💰 Số dư của bạn: <b>{db_user.balance:,} VNĐ</b>\nChọn gói VIP:", parse_mode="HTML", reply_markup=buy_vip_inline_kb())

@router.callback_query(F.data.startswith("buy_vip:"))
async def cb_buy_vip(callback: CallbackQuery, db_user: User):
    vtype = callback.data.split(":")[1]
    price = VIP_WEEK_PRICE if vtype == "week" else VIP_MONTH_PRICE
    days = 7 if vtype == "week" else 30
    async with AsyncSessionLocal() as s:
        fresh_user = await get_user_by_id(s, db_user.id)
        if fresh_user.balance < price:
            await callback.answer(f"❌ Số dư không đủ {price:,}đ!", show_alert=True)
            return
        fresh_user.balance -= price
        now = datetime.utcnow()
        fresh_user.vip_until = (fresh_user.vip_until if fresh_user.vip_until and fresh_user.vip_until > now else now) + dt_mod.timedelta(days=days)
        time_str = fresh_user.vip_until.strftime("%d/%m/%Y %H:%M")
        await s.commit()
    await callback.message.answer(f"🎉 Kích hoạt VIP thành công! Hạn dùng đến: <b>{time_str}</b>", parse_mode="HTML")
    await callback.answer()

# ── Khu vực chơi Mini-game ─────────────────────────────────────────────────────

@router.message(lambda m: m.text == "🎮 Mini Game")
async def minigame_menu(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    await message.answer(f"🎮 <b>SÂN CHƠI GIẢI TRÍ</b>\n\n🪙 Ví điểm hiện có: <b>{db_user.points:,} Điểm</b>\nChọn trò chơi bạn muốn tham gia phía dưới:", parse_mode="HTML", reply_markup=minigame_menu_kb())

@router.message(lambda m: m.text == "🎰 Vòng Quay May Mắn (200 điểm)")
async def lucky_wheel_play(message: Message, db_user: User):
    if db_user.points < 200:
        await message.answer("❌ Bạn không đủ 200 điểm để quay thưởng.")
        return
    async with AsyncSessionLocal() as s:
        fresh_user = await get_user_by_id(s, db_user.id)
        fresh_user.points -= 200
        await s.commit()
        
    msg = await message.answer("⏳ [ ─── ] Đang khởi động vòng quay...")
    await asyncio.sleep(0.4)
    await msg.edit_text("🎰 [ ▓░░░ ] Đang xoay bánh xe...")
    await asyncio.sleep(0.4)
    await msg.edit_text("🎰 [ ▓▓▓░ ] Vòng quay đang giảm tốc...")
    await asyncio.sleep(0.4)
    
    rnd = random.random()
    if rnd < 0.60: # 60% Thua
        await msg.edit_text("💥 <b>Kết quả:</b> Ô [ Chúc bạn may mắn lần sau! ]\n😢 Rất tiếc, bạn đã mất 200 điểm rồi.", parse_mode="HTML")
    elif rnd < 0.85: # 25% Huề vốn
        async with AsyncSessionLocal() as s:
            fresh_user = await get_user_by_id(s, db_user.id); fresh_user.points += 200; await s.commit()
        await msg.edit_text("🎰 <b>Kết quả:</b> Ô [ Hoàn Điểm ]\n🪙 Bạn được trả lại đúng 200 điểm huề vốn nhé!", parse_mode="HTML")
    elif rnd < 0.98: # 13% Trúng điểm lớn
        async with AsyncSessionLocal() as s:
            fresh_user = await get_user_by_id(s, db_user.id); fresh_user.points += 600; await s.commit()
        await msg.edit_text("🎉 <b>Kết quả:</b> Ô [ +600 Điểm ]\n🔥 Quá đỉnh! Bạn nhận được lời lãi to +600 điểm vào ví!", parse_mode="HTML")
    else: # 2% Trúng VIP Tuần cực hiếm
        async with AsyncSessionLocal() as s:
            fresh_user = await get_user_by_id(s, db_user.id)
            now = datetime.utcnow()
            fresh_user.vip_until = (fresh_user.vip_until if fresh_user.vip_until and fresh_user.vip_until > now else now) + dt_mod.timedelta(days=7)
            await s.commit()
        await msg.edit_text("👑 <b>KẾT QUẢ SIÊU VIP:</b> Ô [ Gói VIP 7 Ngày ]\n🔥 💥 Ôi thần linh ơi! Bạn đã trúng giải đặc biệt nhận 7 ngày VIP miễn phí!", parse_mode="HTML")

@router.message(lambda m: m.text == "🎲 Tài Xỉu Xúc Xắc")
async def taixiu_start(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    await message.answer(f"🎲 <b>TÀI XỈU XÚC XẮC</b>\n\n🪙 Điểm của bạn: <b>{db_user.points:,} Điểm</b>\n\nNhập số điểm muốn đặt cược (Tối đa 1,000đ):", parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(ShopState.waiting_tx_points)

@router.message(ShopState.waiting_tx_points, F.text == "❌ Hủy")
async def tx_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy cược.", reply_markup=minigame_menu_kb())

@router.message(ShopState.waiting_tx_points, ~F.text.in_(MENU_BUTTONS))
async def tx_amount_set(message: Message, state: FSMContext, db_user: User):
    text = message.text or ""
    if not text.isdigit() or int(text) <= 0 or int(text) > 1000:
        await message.answer("⚠️ Điểm cược phải là số nguyên từ 1 đến 1,000.")
        return
    bet = int(text)
    if db_user.points < bet:
        await message.answer("❌ Bạn không có đủ số điểm này trong ví để cược.")
        return
    await state.update_data(bet_amount=bet)
    await message.answer(f"📊 Đặt cược: <b>{bet:,} Điểm</b>\n\nChọn của cược của bạn:", parse_mode="HTML", reply_markup=taixiu_inline_kb())

@router.callback_query(F.data.startswith("tx_bet:"))
async def cb_taixiu_play(callback: CallbackQuery, state: FSMContext, db_user: User, bot: Bot):
    data = await state.get_data()
    bet = data.get("bet_amount", 0)
    if bet <= 0: return
    await state.clear()
    
    choice = callback.data.split(":")[1]
    
    async with AsyncSessionLocal() as s:
        fresh_user = await get_user_by_id(s, db_user.id)
        if fresh_user.points < bet:
            await callback.answer("❌ Lỗi tài khoản không đủ điểm!", show_alert=True)
            return
        fresh_user.points -= bet
        await s.commit()

    await callback.message.answer(f"🎲 Bạn cược <b>{bet} điểm</b> vào ô [ <b>{choice.upper()}</b> ]. Hệ thống đang lắc...", parse_mode="HTML")
    await callback.message.delete()
    
    # Gửi emoji xúc xắc động Telegram
    dice_msg = await bot.send_dice(callback.message.chat.id, emoji="🎲")
    dice_value = dice_msg.dice.value
    await asyncio.sleep(2.2) # Chờ 2 giây cho xúc xắc ngừng quay thật trên màn hình điện thoại
    
    result = "tai" if dice_value in [4, 5, 6] else "xiu"
    win = (choice == result)
    
    if win:
        async with AsyncSessionLocal() as s:
            fresh_user = await get_user_by_id(s, db_user.id); fresh_user.points += (bet * 2); await s.commit()
        await bot.send_message(callback.message.chat.id, f"🎉 <b>CHIẾN THẮNG!</b>\n\n🎲 Xúc xắc ra: <b>{dice_value} nút</b> -> <b>{result.upper()}</b>\n🪙 Chúc mừng bạn đoán đúng và nhận được +<b>{bet*2:,} điểm</b>!", parse_mode="HTML")
    else:
        await bot.send_message(callback.message.chat.id, f"💥 <b>THẤT BẠI!</b>\n\n🎲 Xúc xắc ra: <b>{dice_value} nút</b> -> <b>{result.upper()}</b>\n😢 Sai rồi! Bạn đã bị mất -<b>{bet:,} điểm</b> cược.", parse_mode="HTML")
    await callback.answer()

# ── Tài khoản & Đơn hàng ─────────────────────────────────────────────────────

@router.message(lambda m: m.text == "👤 Tài Khoản")
async def my_account(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    joined = db_user.created_at.strftime("%d/%m/%Y") if db_user.created_at else "N/A"
    async with AsyncSessionLocal() as s: orders = await get_user_orders(s, db_user.id, limit=9999)
    vip_status = "👑 VIP (" + db_user.vip_until.strftime("%d/%m/%Y") + ")" if db_user.is_vip else "Thường"
    await message.answer(
        f"👤 <b>THÔNG TIN CỦA BẠN</b>\n\n🆔 Telegram ID: <code>{db_user.telegram_id}</code>\n🥇 Cấp bậc: <b>{vip_status}</b>\n🪙 Ví điểm tích lũy: <b>{db_user.points:,} Điểm</b>\n💰 Số dư: <b>{db_user.balance:,} VNĐ</b>\n📦 Tổng đơn mua: <b>{len(orders)}</b>\n📅 Tham gia: {joined}",
        parse_mode="HTML",
    )

@router.message(lambda m: m.text == "📦 Đơn Hàng")
async def my_orders(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    async with AsyncSessionLocal() as s: orders = await get_user_orders(s, db_user.id, limit=20)
    if not orders:
        await message.answer("📦 Bạn chưa mua đơn hàng nào.")
        return
    lines = ["📦 <b>20 Đơn Hàng Mua Gần Nhất</b>\n"]
    for i, o in enumerate(orders, 1):
        lines.append(f"{i}. Đơn #{o.id} — {o.quantity} acc — {o.price:,} VNĐ")
    await message.answer("\n".join(lines), parse_mode="HTML")

# ── Nạp tiền ─────────────────────────────────────────────────────────────────

@router.message(lambda m: m.text == "💳 Nạp Tiền")
async def deposit_start(message: Message, state: FSMContext):
    await state.clear()
    if not qr_exists():
        await message.answer("⚠️ Admin chưa cấu hình mã QR.")
        return
    await message.answer_photo(FSInputFile(QR_IMAGE_PATH), caption="💳 Chuyển khoản quét mã QR phía trên.\n\nNhập số tiền muốn nạp (VNĐ):", parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(DepositState.waiting_amount)

@router.message(DepositState.waiting_amount, F.text == "❌ Hủy")
async def deposit_cancel_amount(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy nạp tiền.", reply_markup=main_menu_kb())

@router.message(DepositState.waiting_amount, ~F.text.in_(MENU_BUTTONS))
async def deposit_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", "").replace(".", "").strip()
    if not text.isdigit() or int(text) <= 0: return
    await state.update_data(amount=int(text))
    await message.answer(f"💵 Số tiền nạp: <b>{int(text):,} VNĐ</b>\n\n📷 Vui lòng gửi ảnh chụp màn hình Bill chuyển khoản thành công:", parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(DepositState.waiting_bill)

@router.message(DepositState.waiting_bill, F.photo)
async def deposit_bill_photo(message: Message, state: FSMContext, bot: Bot, db_user: User):
    data = await state.get_data(); amount = data.get("amount", 0); await state.clear()
    photo = message.photo[-1]; file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    bill_path = await save_bill_image(file_bytes.read(), "jpg")
    
    async with AsyncSessionLocal() as s:
        deposit = await create_deposit(s, db_user.id, amount, bill_path)
        caption = f"💳 <b>YÊU CẦU NẠP TIỀN #{deposit.id}</b>\n\n🆔 ID: <code>{db_user.telegram_id}</code>\n👤 Tên: {db_user.fullname}\n💵 Số tiền: <b>{amount:,} VNĐ</b>"
        for admin_id in ADMIN_IDS:
            try:
                await message.forward(admin_id)
                await bot.send_message(admin_id, caption, parse_mode="HTML", reply_markup=deposit_approval_kb(deposit.id))
            except Exception: pass
    await message.answer("✅ Đã gửi bill nạp tiền! Vui lòng chờ admin duyệt.", reply_markup=main_menu_kb())

@router.callback_query(F.data.startswith("approve_deposit:"))
async def cb_approve_deposit(callback: CallbackQuery, bot: Bot, is_admin: bool):
    if not is_admin: return
    deposit_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as s:
        deposit = await approve_deposit(s, deposit_id, callback.from_user.id)
        if not deposit: return
        user_after = await add_balance(s, deposit.user_id, deposit.amount)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ Đã duyệt nạp thành công đơn #{deposit_id}")
    if deposit.user:
        try: await bot.send_message(deposit.user.telegram_id, f"✅ <b>Nạp tiền thành công!</b>\n\n💵 Số tiền: +<b>{deposit.amount:,} VNĐ</b>\n💰 Số dư: <b>{user_after.balance:,} VNĐ</b>", parse_mode="HTML")
        except Exception: pass

@router.callback_query(F.data.startswith("reject_deposit:"))
async def cb_reject_deposit(callback: CallbackQuery, bot: Bot, is_admin: bool):
    if not is_admin: return
    deposit_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as s:
        deposit = await reject_deposit(s, deposit_id, callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"❌ Đã từ chối đơn nạp #{deposit_id}")

# ── Admin Panel (Giữ nguyên các chức năng cốt lõi) ─────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, is_admin: bool):
    if not is_admin: return
    await message.answer("🔐 <b>ADMIN PANEL CONTROL</b>", parse_mode="HTML", reply_markup=admin_menu_kb())

@router.message(lambda m: m.text == "📊 Dashboard")
@admin_only
async def admin_dashboard(message: Message, is_admin: bool):
    async with AsyncSessionLocal() as s:
        total_acc = await get_total_count(s); available_acc = await get_available_count(s)
        orders = await get_all_orders(s, 9999); users = await get_all_users(s)
    await message.answer(f"📊 <b>DASHBOARD</b>\n\n👥 Tổng user: {len(users)}\n👑 Tổng VIP: {sum(1 for u in users if u.is_vip)}\n📦 Tổng acc: {total_acc}\n✅ Còn: {available_acc}\n💰 Doanh thu: {sum(o.price for o in orders):,}đ", parse_mode="HTML")

@router.message(lambda m: m.text == "📥 Import TXT")
@admin_only
async def admin_import_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("📥 Gửi file .TXT chứa danh sách acc (định dạng: user|pass):", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_import_file)

@router.message(AdminStates.waiting_import_file, F.document)
async def admin_import_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc or not doc.file_name.endswith(".txt"): return
    await state.clear()
    file = await bot.get_file(doc.file_id); raw = await bot.download_file(file.file_path)
    content = raw.read().decode("utf-8", errors="ignore")
    async with AsyncSessionLocal() as s: stats = await import_accounts(s, content.splitlines())
    await message.answer(f"📥 <b>Import hoàn tất:</b>\n✅ Thành công: {stats['imported']}\n🔁 Trùng: {stats['duplicates']}", parse_mode="HTML")

@router.message(lambda m: m.text == "📷 Đổi QR")
@admin_only
async def admin_change_qr_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("📷 Gửi ảnh mã QR nạp tiền mới:")
    await state.set_state(AdminStates.waiting_qr)

@router.message(AdminStates.waiting_qr, F.photo)
async def admin_receive_qr(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]; file = await bot.get_file(photo.file_id)
    raw = await bot.download_file(file.file_path); await save_qr_image(raw.read())
    await state.clear(); await message.answer("✅ Đã cập nhật ảnh QR mới thành công!")

@router.message(lambda m: m.text == "📦 Xem Kho")
@admin_only
async def admin_view_stock(message: Message, is_admin: bool):
    async with AsyncSessionLocal() as s:
        total = await get_total_count(s); available = await get_available_count(s)
    await message.answer(f"📦 <b>XEM KHO ACC</b>\n\n📊 Tổng cộng: {total}\n✅ Khả dụng: {available}", parse_mode="HTML")

# ── Hàm chạy Web Server mồi cho Render ──────────────────────────────────────────

async def handle_web(request): return web.Response(text="Bot Liên Quân Siêu Cấp đang hoạt động!")
async def start_web_server():
    app = web.Application(); app.router.add_get("/", handle_web)
    runner = web.AppRunner(app); await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logger.info(f"✅ Web Server mồi chống lỗi timeout đang mở tại cổng: {port}")

# ── Main Bootstrap ────────────────────────────────────────────────────────────

async def main():
    if not BOT_TOKEN or BOT_TOKEN == "NHAP_BOT_TOKEN_CUA_BAN_VAO_DAY": sys.exit(1)
    await init_db()
    await start_web_server()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.include_router(router)
    logger.info("Bot is polling...")
    try: await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally: await bot.session.close()

if __name__ == "__main__": asyncio.run(main())
