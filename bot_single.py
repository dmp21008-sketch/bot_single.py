# ═══════════════════════════════════════════════════════════════
#  BOT LIÊN QUÂN - ĐÃ FIX LỖI TIMEOUT RENDER WEB SERVICE
#  Cài thư viện: pip install aiogram==3.13.1 sqlalchemy==2.0.36 aiosqlite==0.20.0 aiofiles==24.1.0 aiohttp
#  Chạy: python bot_single.py
# ═══════════════════════════════════════════════════════════════

# ── SỬA 2 DÒNG NÀY TRƯỚC KHI CHẠY ──────────────────────────────
BOT_TOKEN = "NHAP_BOT_TOKEN_CUA_BAN_VAO_DAY"
ADMIN_IDS = [7936179657]  # Telegram ID của admin
# ────────────────────────────────────────────────────────────────

import asyncio
import enum
import functools
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable

import aiofiles
from aiohttp import web  # Thêm thư viện mở cổng Web cho Render
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

# ── Cấu hình ──────────────────────────────────────────────────────────────────

ACCOUNT_PRICE = 200  # VNĐ mỗi acc
MIN_ORDER_QTY = 50  # Số lượng tối thiểu
CHECKER_LINK = "https://t.me/tretrauchecker_bot?start=ref_7936179657"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
QR_IMAGE_PATH = os.path.join(UPLOADS_DIR, "qr_current.jpg")
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'database.sqlite')}"

MENU_BUTTONS = {
    "🏠 Trang Chủ",
    "🛒 Mua Acc",
    "💳 Nạp Tiền",
    "👤 Tài Khoản",
    "📦 Đơn Hàng",
    "☎ Hỗ Trợ",
    "📊 Dashboard",
    "📥 Import TXT",
    "📦 Xem Kho",
    "📊 Thống Kê",
    "💰 Cộng Tiền",
    "💸 Trừ Tiền",
    "📷 Đổi QR",
    "📥 Bill Chờ",
    "📢 Broadcast",
    "🚫 Ban User",
    "✅ Unban User",
    "🗑 Xóa Account",
    "📤 Export Chưa Bán",
    "📤 Export Đã Bán",
    "🔙 Menu Chính",
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
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


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
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fullname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")
    deposits: Mapped[list["Deposit"]] = relationship("Deposit", back_populates="user")


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus), nullable=False, default=AccountStatus.available
    )
    order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("orders.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order: Mapped["Order|None"] = relationship("Order", back_populates="accounts")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.completed
    )
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    user: Mapped["User"] = relationship("User", back_populates="orders")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="order")


class Deposit(Base):
    __tablename__ = "deposits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    bill_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[DepositStatus] = mapped_column(
        Enum(DepositStatus), nullable=False, default=DepositStatus.pending
    )
    admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user: Mapped["User"] = relationship("User", back_populates="deposits")


class Setting(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


# ── Services ──────────────────────────────────────────────────────────────────


async def get_or_create_user(session, telegram_id, username, fullname, is_admin=False):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            fullname=fullname,
            is_admin=is_admin,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
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
    if user is None:
        return None
    user.balance += amount
    await session.commit()
    await session.refresh(user)
    return user


async def adjust_balance_by_telegram_id(session, telegram_id, amount):
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        return None
    user.balance += amount
    if user.balance < 0:
        user.balance = 0
    await session.commit()
    await session.refresh(user)
    return user


async def ban_user(session, telegram_id):
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = r.scalar_one_or_none()
    if user is None:
        return False
    user.is_banned = True
    await session.commit()
    return True


async def unban_user(session, telegram_id):
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = r.scalar_one_or_none()
    if user is None:
        return False
    user.is_banned = False
    await session.commit()
    return True


async def get_all_users(session):
    r = await session.execute(select(User))
    return list(r.scalars().all())


async def get_available_count(session):
    r = await session.execute(
        select(func.count()).where(Account.status == AccountStatus.available)
    )
    return r.scalar_one()


async def get_sold_count(session):
    r = await session.execute(
        select(func.count()).where(Account.status == AccountStatus.sold)
    )
    return r.scalar_one()


async def get_total_count(session):
    r = await session.execute(select(func.count()).select_from(Account))
    return r.scalar_one()


async def pick_random_accounts(session, quantity):
    r = await session.execute(
        select(Account)
        .where(Account.status == AccountStatus.available)
        .order_by(func.random())
        .limit(quantity)
    )
    return list(r.scalars().all())


async def mark_accounts_sold(session, accounts, order_id):
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
        if not line:
            continue
        stats["total"] += 1
        if "|" in line:
            parts = line.split("|", 1)
        elif ":" in line:
            parts = line.split(":", 1)
        else:
            stats["invalid"] += 1
            continue
        uname, pwd = parts[0].strip(), parts[1].strip()
        if not uname or not pwd:
            stats["invalid"] += 1
            continue
        ex = await session.execute(select(Account).where(Account.username == uname))
        if ex.scalar_one_or_none() is not None:
            stats["duplicates"] += 1
            continue
        session.add(
            Account(username=uname, password=pwd, status=AccountStatus.available)
        )
        stats["imported"] += 1
    await session.commit()
    return stats


async def get_unsold_accounts(session):
    r = await session.execute(
        select(Account).where(Account.status == AccountStatus.available)
    )
    return list(r.scalars().all())


async def get_sold_accounts(session):
    r = await session.execute(
        select(Account).where(Account.status == AccountStatus.sold)
    )
    return list(r.scalars().all())


async def delete_account_by_username(session, username):
    r = await session.execute(select(Account).where(Account.username == username))
    acc = r.scalar_one_or_none()
    if acc is None:
        return False
    await session.delete(acc)
    await session.commit()
    return True


async def create_order(session, user_id, quantity, price, file_name):
    order = Order(
        user_id=user_id,
        quantity=quantity,
        price=price,
        status=OrderStatus.completed,
        file_name=file_name,
    )
    session.add(order)
    await session.flush()
    return order


async def get_user_orders(session, user_id, limit=20):
    r = await session.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    return list(r.scalars().all())


async def get_all_orders(session, limit=50):
    r = await session.execute(
        select(Order).order_by(Order.created_at.desc()).limit(limit)
    )
    return list(r.scalars().all())


async def create_deposit(session, user_id, amount, bill_image=None):
    dep = Deposit(
        user_id=user_id,
        amount=amount,
        bill_image=bill_image,
        status=DepositStatus.pending,
    )
    session.add(dep)
    await session.commit()
    await session.refresh(dep)
    return dep


async def get_deposit_by_id(session, deposit_id):
    r = await session.execute(
        select(Deposit)
        .options(selectinload(Deposit.user))
        .where(Deposit.id == deposit_id)
    )
    return r.scalar_one_or_none()


async def approve_deposit(session, deposit_id, admin_tg_id):
    dep = await get_deposit_by_id(session, deposit_id)
    if dep is None or dep.status != DepositStatus.pending:
        return None
    dep.status = DepositStatus.approved
    dep.admin_id = admin_tg_id
    dep.approved_at = datetime.utcnow()
    await session.commit()
    await session.refresh(dep)
    return dep


async def reject_deposit(session, deposit_id, admin_tg_id):
    dep = await get_deposit_by_id(session, deposit_id)
    if dep is None or dep.status != DepositStatus.pending:
        return None
    dep.status = DepositStatus.rejected
    dep.admin_id = admin_tg_id
    dep.approved_at = datetime.utcnow()
    await session.commit()
    await session.refresh(dep)
    return dep


async def get_pending_deposits(session):
    r = await session.execute(
        select(Deposit)
        .options(selectinload(Deposit.user))
        .where(Deposit.status == DepositStatus.pending)
        .order_by(Deposit.created_at.asc())
    )
    return list(r.scalars().all())


# ── File utils ────────────────────────────────────────────────────────────────


async def save_export_file(lines, prefix):
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fp = os.path.join(EXPORTS_DIR, f"{prefix}_{ts}.txt")
    async with aiofiles.open(fp, "w", encoding="utf-8") as f:
        await f.write("\n".join(lines))
    return fp


async def save_order_file(accounts_data, order_id):
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"order_{order_id}_{ts}.txt"
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
    b.row(KeyboardButton(text="📦 Đơn Hàng"), KeyboardButton(text="☎ Hỗ Trợ"))
    return b.as_markup(resize_keyboard=True)


def cancel_kb():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="❌ Hủy"))
    return b.as_markup(resize_keyboard=True)


def deposit_approval_kb(deposit_id):
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✅ DUYỆT", callback_data=f"approve_deposit:{deposit_id}"
        ),
        InlineKeyboardButton(
            text="❌ TỪ CHỐI", callback_data=f"reject_deposit:{deposit_id}"
        ),
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
    b.row(
        KeyboardButton(text="📤 Export Chưa Bán"),
        KeyboardButton(text="📤 Export Đã Bán"),
    )
    b.row(KeyboardButton(text="🔙 Menu Chính"))
    return b.as_markup(resize_keyboard=True)


# ── Middleware ────────────────────────────────────────────────────────────────


class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        is_admin = user.id in ADMIN_IDS
        fullname = (user.full_name or "").strip() or user.username or str(user.id)
        async with AsyncSessionLocal() as session:
            db_user = await get_or_create_user(
                session, user.id, user.username, fullname, is_admin
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

# ── /start & home ─────────────────────────────────────────────────────────────


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db_user: User, is_admin: bool):
    await state.clear()
    name = db_user.fullname or message.from_user.full_name or "bạn"
    async with AsyncSessionLocal() as s:
        available = await get_available_count(s)
    await message.answer(
        f"👋 Chào mừng <b>{name}</b> đến với Shop Liên Quân!\n\n"
        f"🛒 Mua acc chất lượng, giá rẻ\n"
        f"💰 Số dư: <b>{db_user.balance:,} VNĐ</b>\n"
        f"📦 Kho còn: <b>{available:,} acc</b>\n\n"
        "Chọn chức năng bên dưới:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.message(lambda m: m.text == "🏠 Trang Chủ")
async def home(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    async with AsyncSessionLocal() as s:
        available = await get_available_count(s)
    name = db_user.fullname or message.from_user.full_name or "bạn"
    await message.answer(
        f"🏠 <b>Trang Chủ</b>\n\n"
        f"👋 Xin chào <b>{name}</b>!\n"
        f"💰 Số dư: <b>{db_user.balance:,} VNĐ</b>\n"
        f"📦 Kho còn: <b>{available:,} acc</b>\n\n"
        "Chọn chức năng bên dưới:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.message(lambda m: m.text == "☎ Hỗ Trợ")
async def support(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "☎ <b>Hỗ Trợ</b>\n\n"
        "Nếu gặp vấn đề, vui lòng liên hệ:\n"
        "👤 Admin: @lananh9719\n\n"
        "⏰ Thời gian hỗ trợ: 8:00 - 22:00 mỗi ngày",
        parse_mode="HTML",
    )


# ── Shop ──────────────────────────────────────────────────────────────────────


@router.message(lambda m: m.text == "🛒 Mua Acc")
async def buy_acc_start(message: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as s:
        available = await get_available_count(s)
    await message.answer(
        f"🛒 <b>Mua Acc Liên Quân</b>\n\n"
        f"💵 Giá: <b>{ACCOUNT_PRICE:,} VNĐ / 1 acc</b>\n"
        f"📦 Kho còn: <b>{available:,} acc</b>\n"
        f"⚠️ Số lượng tối thiểu: <b>{MIN_ORDER_QTY} acc</b>\n\n"
        "Nhập số lượng acc bạn muốn mua:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await state.set_state(ShopState.waiting_quantity)


@router.message(ShopState.waiting_quantity, F.text == "❌ Hủy")
async def buy_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy.", reply_markup=main_menu_kb())


@router.message(ShopState.waiting_quantity, ~F.text.in_(MENU_BUTTONS))
async def buy_acc_quantity(message: Message, state: FSMContext, db_user: User):
    text = message.text or ""
    if not text.isdigit():
        await message.answer("⚠️ Vui lòng nhập số nguyên hợp lệ.")
        return
    quantity = int(text)
    if quantity < MIN_ORDER_QTY:
        await message.answer(
            f"⚠️ Số lượng tối thiểu là <b>{MIN_ORDER_QTY} acc</b>.", parse_mode="HTML"
        )
        return
    total_price = quantity * ACCOUNT_PRICE
    async with AsyncSessionLocal() as s:
        fresh_user = await get_user_by_id(s, db_user.id)
        if fresh_user is None:
            await message.answer("❌ Không tìm thấy tài khoản.")
            await state.clear()
            return
        if fresh_user.balance < total_price:
            shortage = total_price - fresh_user.balance
            await message.answer(
                f"❌ <b>Số dư không đủ!</b>\n\n"
                f"💰 Số dư hiện tại: <b>{fresh_user.balance:,} VNĐ</b>\n"
                f"💵 Cần thanh toán: <b>{total_price:,} VNĐ</b>\n"
                f"⚠️ Thiếu: <b>{shortage:,} VNĐ</b>\n\nVui lòng nạp thêm tiền.",
                parse_mode="HTML",
                reply_markup=main_menu_kb(),
            )
            await state.clear()
            return
        available = await get_available_count(s)
        if available < quantity:
            await message.answer(
                f"❌ Kho không đủ hàng!\n📦 Kho còn: <b>{available:,} acc</b>",
                parse_mode="HTML",
                reply_markup=main_menu_kb(),
            )
            await state.clear()
            return
        accounts = await pick_random_accounts(s, quantity)
        if len(accounts) < quantity:
            await message.answer(
                "❌ Lỗi khi lấy acc. Vui lòng thử lại.", reply_markup=main_menu_kb()
            )
            await state.clear()
            return
        order = await create_order(s, fresh_user.id, quantity, total_price, "")
        fresh_user.balance -= total_price
        await mark_accounts_sold(s, accounts, order.id)
        account_data = [(a.username, a.password) for a in accounts]
        filepath, filename = await save_order_file(account_data, order.id)
        order.file_name = filename
        await s.commit()
    await state.clear()
    await message.answer(
        f"✅ <b>Đặt hàng thành công!</b>\n\n"
        f"📦 Số lượng: <b>{quantity} acc</b>\n"
        f"💵 Tổng tiền: <b>{total_price:,} VNĐ</b>\n"
        f"🧾 Mã đơn: <b>#{order.id}</b>\n\nĐang gửi file acc...",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await message.answer_document(
        FSInputFile(filepath, filename=filename),
        caption=f"📄 File acc đơn #{order.id} — {quantity} tài khoản",
    )
    await message.answer(f"📌 Kiểm tra acc miễn phí tại:\n\n{CHECKER_LINK}")


# ── Tài khoản & Đơn hàng ─────────────────────────────────────────────────────


@router.message(lambda m: m.text == "👤 Tài Khoản")
async def my_account(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    joined = db_user.created_at.strftime("%d/%m/%Y") if db_user.created_at else "N/A"
    async with AsyncSessionLocal() as s:
        orders = await get_user_orders(s, db_user.id, limit=9999)
    uname = f"@{db_user.username}" if db_user.username else "Không có"
    await message.answer(
        f"👤 <b>Thông Tin Tài Khoản</b>\n\n"
        f"🆔 Telegram ID: <code>{db_user.telegram_id}</code>\n"
        f"👤 Username: {uname}\n"
        f"📛 Tên: {db_user.fullname}\n"
        f"💰 Số dư: <b>{db_user.balance:,} VNĐ</b>\n"
        f"📦 Tổng đơn: <b>{len(orders)}</b>\n"
        f"📅 Ngày tham gia: {joined}",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "📦 Đơn Hàng")
async def my_orders(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    async with AsyncSessionLocal() as s:
        orders = await get_user_orders(s, db_user.id, limit=20)
    if not orders:
        await message.answer("📦 Bạn chưa có đơn hàng nào.")
        return
    lines = ["📦 <b>20 Đơn Hàng Gần Nhất</b>\n"]
    for i, o in enumerate(orders, 1):
        created = o.created_at.strftime("%d/%m/%Y %H:%M") if o.created_at else "N/A"
        lines.append(
            f"{i}. Đơn #{o.id} — {o.quantity} acc — {o.price:,} VNĐ — {created}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── Nạp tiền ─────────────────────────────────────────────────────────────────


@router.message(lambda m: m.text == "💳 Nạp Tiền")
async def deposit_start(message: Message, state: FSMContext):
    await state.clear()
    if not qr_exists():
        await message.answer("⚠️ Admin chưa cấu hình mã QR. Vui lòng liên hệ Admin.")
        return
    await message.answer_photo(
        FSInputFile(QR_IMAGE_PATH),
        caption="💳 <b>Nạp Tiền</b>\n\nQuét mã QR để chuyển khoản.\n\nNhập số tiền muốn nạp (VNĐ):",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await state.set_state(DepositState.waiting_amount)


@router.message(DepositState.waiting_amount, F.text == "❌ Hủy")
async def deposit_cancel_amount(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy.", reply_markup=main_menu_kb())


@router.message(DepositState.waiting_amount, ~F.text.in_(MENU_BUTTONS))
async def deposit_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", "").replace(".", "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ (VD: 50000).")
        return
    amount = int(text)
    await state.update_data(amount=amount)
    await message.answer(
        f"💵 Số tiền nạp: <b>{amount:,} VNĐ</b>\n\n📷 Vui lòng gửi ảnh bill chuyển khoản:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await state.set_state(DepositState.waiting_bill)


@router.message(DepositState.waiting_bill, F.text == "❌ Hủy")
async def deposit_cancel_bill(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy.", reply_markup=main_menu_kb())


@router.message(DepositState.waiting_bill, F.photo)
async def deposit_bill_photo(
    message: Message, state: FSMContext, bot: Bot, db_user: User
):
    data = await state.get_data()
    amount = data.get("amount", 0)
    await state.clear()
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    bill_path = await save_bill_image(file_bytes.read(), "jpg")
    async with AsyncSessionLocal() as s:
        deposit = await create_deposit(s, db_user.id, amount, bill_path)
        uname = f"@{db_user.username}" if db_user.username else "Không có"
        now_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")
        caption = (
            f"💳 <b>YÊU CẦU NẠP TIỀN</b>\n\n"
            f"🆔 Telegram ID: <code>{db_user.telegram_id}</code>\n"
            f"👤 Username: {uname}\n"
            f"📛 Tên: {db_user.fullname}\n"
            f"💵 Số tiền: <b>{amount:,} VNĐ</b>\n"
            f"🕐 Thời gian: {now_str}\n"
            f"🧾 Deposit ID: #{deposit.id}"
        )
        kb = deposit_approval_kb(deposit.id)
        for admin_id in ADMIN_IDS:
            try:
                await message.forward(admin_id)
                await bot.send_message(
                    admin_id, caption, parse_mode="HTML", reply_markup=kb
                )
            except Exception:
                pass
    await message.answer(
        f"✅ <b>Đã gửi yêu cầu nạp tiền!</b>\n\n"
        f"💵 Số tiền: <b>{amount:,} VNĐ</b>\n"
        "⏳ Vui lòng đợi Admin duyệt.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.message(DepositState.waiting_bill, ~F.text.in_(MENU_BUTTONS))
async def deposit_bill_invalid(message: Message):
    await message.answer("⚠️ Vui lòng gửi ảnh bill (ảnh chụp màn hình).")


@router.callback_query(F.data.startswith("approve_deposit:"))
async def cb_approve_deposit(callback: CallbackQuery, bot: Bot, is_admin: bool):
    if not is_admin:
        await callback.answer("❌ Bạn không có quyền.", show_alert=True)
        return
    deposit_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as s:
        deposit = await approve_deposit(s, deposit_id, callback.from_user.id)
        if deposit is None:
            await callback.answer(
                "⚠️ Yêu cầu không tồn tại hoặc đã xử lý.", show_alert=True
            )
            return
        user_after = await add_balance(s, deposit.user_id, deposit.amount)
        user_tg_id = deposit.user.telegram_id if deposit.user else None
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(
        f"✅ Đã duyệt nạp tiền <b>{deposit.amount:,} VNĐ</b> — #{deposit_id}",
        parse_mode="HTML",
    )
    if user_tg_id:
        try:
            await bot.send_message(
                user_tg_id,
                f"✅ <b>Nạp tiền thành công!</b>\n\n"
                f"💵 Số tiền: <b>{deposit.amount:,} VNĐ</b>\n"
                f"💰 Số dư hiện tại: <b>{user_after.balance:,} VNĐ</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await callback.answer("✅ Đã duyệt!")


@router.callback_query(F.data.startswith("reject_deposit:"))
async def cb_reject_deposit(callback: CallbackQuery, bot: Bot, is_admin: bool):
    if not is_admin:
        await callback.answer("❌ Bạn không có quyền.", show_alert=True)
        return
    deposit_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as s:
        deposit = await reject_deposit(s, deposit_id, callback.from_user.id)
        if deposit is None:
            await callback.answer(
                "⚠️ Yêu cầu không tồn tại hoặc đã xử lý.", show_alert=True
            )
            return
        user_tg_id = deposit.user.telegram_id if deposit.user else None
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(
        f"❌ Đã từ chối nạp tiền <b>{deposit.amount:,} VNĐ</b> — #{deposit_id}",
        parse_mode="HTML",
    )
    if user_tg_id:
        try:
            await bot.send_message(
                user_tg_id,
                f"❌ <b>Yêu cầu nạp tiền bị từ chối!</b>\n\n💵 Số tiền: <b>{deposit.amount:,} VNĐ</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await callback.answer("❌ Đã từ chối!")


# ── Admin ─────────────────────────────────────────────────────────────────────


@router.message(Command("admin"))
async def cmd_admin(message: Message, is_admin: bool):
    if not is_admin:
        await message.answer("❌ Bạn không có quyền.")
        return
    await message.answer(
        "🔐 <b>ADMIN PANEL</b>", parse_mode="HTML", reply_markup=admin_menu_kb()
    )


@router.message(lambda m: m.text == "🔙 Menu Chính")
async def back_to_main(message: Message):
    await message.answer("🏠 Menu Chính", reply_markup=main_menu_kb())


@router.message(lambda m: m.text == "📊 Dashboard")
@admin_only
async def admin_dashboard(message: Message, is_admin: bool):
    async with AsyncSessionLocal() as s:
        total_acc = await get_total_count(s)
        available_acc = await get_available_count(s)
        sold_acc = await get_sold_count(s)
        orders = await get_all_orders(s, 9999)
        users = await get_all_users(s)
        deposits = await get_pending_deposits(s)
    await message.answer(
        f"📊 <b>DASHBOARD</b>\n\n"
        f"👥 Tổng user: <b>{len(users)}</b> (banned: {sum(1 for u in users if u.is_banned)})\n"
        f"📦 Tổng acc: <b>{total_acc}</b>\n"
        f"✅ Còn lại: <b>{available_acc}</b>\n"
        f"🔴 Đã bán: <b>{sold_acc}</b>\n"
        f"🧾 Tổng đơn: <b>{len(orders)}</b>\n"
        f"💰 Doanh thu: <b>{sum(o.price for o in orders):,} VNĐ</b>\n"
        f"⏳ Bill chờ duyệt: <b>{len(deposits)}</b>",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "📦 Xem Kho")
@admin_only
async def admin_view_stock(message: Message, is_admin: bool):
    async with AsyncSessionLocal() as s:
        total = await get_total_count(s)
        available = await get_available_count(s)
        sold = await get_sold_count(s)
    await message.answer(
        f"📦 <b>Xem Kho</b>\n\n📊 Tổng: <b>{total}</b>\n✅ Còn: <b>{available}</b>\n🔴 Bán: <b>{sold}</b>",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "📊 Thống Kê")
@admin_only
async def admin_stats(message: Message, is_admin: bool):
    async with AsyncSessionLocal() as s:
        orders = await get_all_orders(s, 9999)
        users = await get_all_users(s)
        total_acc = await get_total_count(s)
        available_acc = await get_available_count(s)
        sold_acc = await get_sold_count(s)
    await message.answer(
        f"📊 <b>Thống Kê</b>\n\n"
        f"👥 Tổng user: <b>{len(users)}</b>\n"
        f"📦 Tổng acc: <b>{total_acc}</b>\n"
        f"✅ Còn lại: <b>{available_acc}</b>\n"
        f"🔴 Đã bán: <b>{sold_acc}</b>\n"
        f"🧾 Tổng đơn: <b>{len(orders)}</b>\n"
        f"💰 Tổng doanh thu: <b>{sum(o.price for o in orders):,} VNĐ</b>",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text in ("📥 Import TXT",))
@admin_only
async def admin_import_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer(
        "📥 Gửi file TXT chứa danh sách acc.\n\nMỗi dòng: <code>username|password</code>",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_import_file)


@router.message(Command("importacc"))
@admin_only
async def cmd_import_acc(message: Message, state: FSMContext, is_admin: bool):
    await message.answer(
        "📥 Gửi file TXT chứa danh sách acc.\n\nMỗi dòng: <code>username|password</code>",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_import_file)


@router.message(AdminStates.waiting_import_file, F.document)
async def admin_import_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc or not doc.file_name or not doc.file_name.endswith(".txt"):
        await message.answer("⚠️ Vui lòng gửi file .TXT.")
        return
    await state.clear()
    file = await bot.get_file(doc.file_id)
    raw = await bot.download_file(file.file_path)
    content = raw.read().decode("utf-8", errors="ignore")
    async with AsyncSessionLocal() as s:
        stats = await import_accounts(s, content.splitlines())
    await message.answer(
        f"📥 <b>Import Hoàn Tất</b>\n\n"
        f"📄 Tổng dòng: <b>{stats['total']}</b>\n"
        f"✅ Import: <b>{stats['imported']}</b>\n"
        f"🔁 Trùng: <b>{stats['duplicates']}</b>\n"
        f"❌ Sai định dạng: <b>{stats['invalid']}</b>",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_import_file)
async def admin_import_invalid(message: Message):
    await message.answer("⚠️ Vui lòng gửi file .TXT.")


@router.message(lambda m: m.text == "💰 Cộng Tiền")
@admin_only
async def admin_add_balance_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("💰 Nhập Telegram ID người dùng cần cộng tiền:")
    await state.set_state(AdminStates.waiting_add_balance_id)


@router.message(AdminStates.waiting_add_balance_id)
async def admin_add_balance_id(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer("⚠️ Telegram ID không hợp lệ.")
        return
    await state.update_data(target_id=int(text))
    await message.answer("💵 Nhập số tiền cần cộng (VNĐ):")
    await state.set_state(AdminStates.waiting_add_balance_amount)


@router.message(AdminStates.waiting_add_balance_amount)
async def admin_add_balance_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Số tiền không hợp lệ.")
        return
    amount = int(text)
    data = await state.get_data()
    target_id = data["target_id"]
    await state.clear()
    async with AsyncSessionLocal() as s:
        user = await adjust_balance_by_telegram_id(s, target_id, amount)
    if user is None:
        await message.answer(f"❌ Không tìm thấy user ID: {target_id}")
        return
    await message.answer(
        f"✅ Đã cộng <b>{amount:,} VNĐ</b> cho <b>{user.fullname}</b>\n💰 Số dư mới: <b>{user.balance:,} VNĐ</b>",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "💸 Trừ Tiền")
@admin_only
async def admin_subtract_balance_start(
    message: Message, state: FSMContext, is_admin: bool
):
    await message.answer("💸 Nhập Telegram ID người dùng cần trừ tiền:")
    await state.set_state(AdminStates.waiting_subtract_balance_id)


@router.message(AdminStates.waiting_subtract_balance_id)
async def admin_subtract_balance_id(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer("⚠️ Telegram ID không hợp lệ.")
        return
    await state.update_data(target_id=int(text))
    await message.answer("💵 Nhập số tiền cần trừ (VNĐ):")
    await state.set_state(AdminStates.waiting_subtract_balance_amount)


@router.message(AdminStates.waiting_subtract_balance_amount)
async def admin_subtract_balance_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Số tiền không hợp lệ.")
        return
    amount = int(text)
    data = await state.get_data()
    target_id = data["target_id"]
    await state.clear()
    async with AsyncSessionLocal() as s:
        user = await adjust_balance_by_telegram_id(s, target_id, -amount)
    if user is None:
        await message.answer(f"❌ Không tìm thấy user ID: {target_id}")
        return
    await message.answer(
        f"✅ Đã trừ <b>{amount:,} VNĐ</b> khỏi <b>{user.fullname}</b>\n💰 Số dư mới: <b>{user.balance:,} VNĐ</b>",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "📷 Đổi QR")
@admin_only
async def admin_change_qr_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("📷 Gửi ảnh QR mới:")
    await state.set_state(AdminStates.waiting_qr)


@router.message(AdminStates.waiting_qr, F.photo)
async def admin_receive_qr(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    raw = await bot.download_file(file.file_path)
    await save_qr_image(raw.read())
    await state.clear()
    await message.answer("✅ Ảnh QR đã được cập nhật!")


@router.message(AdminStates.waiting_qr)
async def admin_qr_invalid(message: Message):
    await message.answer("⚠️ Vui lòng gửi ảnh (photo).")


@router.message(lambda m: m.text == "📥 Bill Chờ")
@admin_only
async def admin_pending_bills(message: Message, is_admin: bool):
    async with AsyncSessionLocal() as s:
        deposits = await get_pending_deposits(s)
    if not deposits:
        await message.answer("✅ Không có yêu cầu nạp tiền nào đang chờ.")
        return
    lines = [f"📥 <b>Bill đang chờ duyệt ({len(deposits)})</b>\n"]
    for d in deposits:
        uname = f"@{d.user.username}" if d.user and d.user.username else "N/A"
        name = d.user.fullname if d.user else "N/A"
        created = d.created_at.strftime("%d/%m/%Y %H:%M") if d.created_at else "N/A"
        lines.append(
            f"🧾 #{d.id} — {name} ({uname})\n   💵 {d.amount:,} VNĐ — {created}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(lambda m: m.text == "📢 Broadcast")
@admin_only
async def admin_broadcast_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("📢 Nhập nội dung tin nhắn broadcast:")
    await state.set_state(AdminStates.waiting_broadcast_text)


@router.message(AdminStates.waiting_broadcast_text)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    text = message.text or ""
    if not text:
        await message.answer("⚠️ Nội dung trống.")
        return
    await state.clear()
    async with AsyncSessionLocal() as s:
        users = await get_all_users(s)
    sent = failed = 0
    for user in users:
        if user.is_banned:
            continue
        try:
            await bot.send_message(user.telegram_id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    await message.answer(
        f"📢 <b>Broadcast hoàn tất</b>\n\n✅ Gửi thành công: <b>{sent}</b>\n❌ Thất bại: <b>{failed}</b>",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "🚫 Ban User")
@admin_only
async def admin_ban_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("🚫 Nhập Telegram ID cần ban:")
    await state.set_state(AdminStates.waiting_ban_id)


@router.message(AdminStates.waiting_ban_id)
async def admin_ban_execute(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer("⚠️ Telegram ID không hợp lệ.")
        return
    await state.clear()
    async with AsyncSessionLocal() as s:
        ok = await ban_user(s, int(text))
    await message.answer(
        f"✅ Đã ban <code>{text}</code>."
        if ok
        else f"❌ Không tìm thấy user <code>{text}</code>.",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "✅ Unban User")
@admin_only
async def admin_unban_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("✅ Nhập Telegram ID cần unban:")
    await state.set_state(AdminStates.waiting_unban_id)


@router.message(AdminStates.waiting_unban_id)
async def admin_unban_execute(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer("⚠️ Telegram ID không hợp lệ.")
        return
    await state.clear()
    async with AsyncSessionLocal() as s:
        ok = await unban_user(s, int(text))
    await message.answer(
        f"✅ Đã unban <code>{text}</code>."
        if ok
        else f"❌ Không tìm thấy user <code>{text}</code>.",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "🗑 Xóa Account")
@admin_only
async def admin_delete_acc_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("🗑 Nhập username acc cần xóa:")
    await state.set_state(AdminStates.waiting_delete_username)


@router.message(AdminStates.waiting_delete_username)
async def admin_delete_acc_execute(message: Message, state: FSMContext):
    username = (message.text or "").strip()
    if not username:
        await message.answer("⚠️ Username không hợp lệ.")
        return
    await state.clear()
    async with AsyncSessionLocal() as s:
        ok = await delete_account_by_username(s, username)
    await message.answer(
        f"✅ Đã xóa <code>{username}</code>."
        if ok
        else f"❌ Không tìm thấy acc <code>{username}</code>.",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "📤 Export Chưa Bán")
@admin_only
async def admin_export_unsold(message: Message, is_admin: bool):
    async with AsyncSessionLocal() as s:
        accounts = await get_unsold_accounts(s)
    if not accounts:
        await message.answer("📦 Kho không có acc nào chưa bán.")
        return
    lines = [f"{a.username}|{a.password}" for a in accounts]
    fp = await save_export_file(lines, "unsold")
    await message.answer_document(
        FSInputFile(fp),
        caption=f"📤 <b>Export Acc Chưa Bán</b>\n📊 Tổng: <b>{len(lines)}</b> acc",
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "📤 Export Đã Bán")
@admin_only
async def admin_export_sold(message: Message, is_admin: bool):
    async with AsyncSessionLocal() as s:
        accounts = await get_sold_accounts(s)
    if not accounts:
        await message.answer("📦 Chưa có acc nào được bán.")
        return
    lines = [f"{a.username}|{a.password}" for a in accounts]
    fp = await save_export_file(lines, "sold")
    await message.answer_document(
        FSInputFile(fp),
        caption=f"📤 <b>Export Acc Đã Bán</b>\n📊 Tổng: <b>{len(lines)}</b> acc",
        parse_mode="HTML",
    )


# ── Hàm chạy Web Server mồi cho Render ──────────────────────────────────────────


async def handle_web(request):
    return web.Response(text="Bot đang chạy mượt mà!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))  # Lấy cổng Render cấp
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"✅ Web Server mồi đang chạy tại port {port}")


# ── Main ──────────────────────────────────────────────────────────────────────


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "NHAP_BOT_TOKEN_CUA_BAN_VAO_DAY":
        print(
            "❌ Chưa nhập BOT_TOKEN! Mở file bot_single.py và sửa dòng BOT_TOKEN ở đầu file."
        )
        sys.exit(1)

    await init_db()

    # Bắt đầu chạy song song Web Server cùng lúc với Bot Telegram
    await start_web_server()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.include_router(router)

    logger.info("✅ Bot đang chạy...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
