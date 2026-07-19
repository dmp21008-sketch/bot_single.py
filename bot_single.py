# ═══════════════════════════════════════════════════════════════
#  BOT HỢP NHẤT HOÀN CHỈNH: SHOP LIÊN QUÂN & TÀI XỈU REALTIME (ASYNC)
#  Cài thư viện: pip install aiogram==3.13.1 sqlalchemy==2.0.36 aiosqlite==0.20.0 aiofiles==24.1.0 aiohttp
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = "8374524579:AAF6CpmmHi0RKYtQ5dJ0bIw9e_wBonjF1nY"  
ADMIN_IDS = [7936179657]  # ID Telegram Admin

import asyncio
import enum
import functools
import logging
import os
import sys
import uuid
import random
from datetime import datetime, timedelta

import aiofiles
from aiohttp import web  
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    KeyboardButton,
    Message,
    InlineKeyboardButton,
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

# ── Cấu hình Shop & Tài Xỉu ───────────────────────────────────────────────────
ACCOUNT_PRICE = 300  # VNĐ mỗi acc
MIN_ORDER_QTY = 50  # Số lượng tối thiểu
CHECKER_LINK = "t.me/tretrauchecker_bot?start=_tgr_8UulJtkyZjE1"  
XU_DIEMDANH = 500  # Số xu nhận được khi điểm danh
THUONG_REF_XU = 5000  # Thưởng mời bạn bè chơi bot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")  
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")  
LOGS_DIR = os.path.join(BASE_DIR, "logs")  
QR_IMAGE_PATH = os.path.join(UPLOADS_DIR, "qr_current.jpg")  
DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_LF6COm8Ruikq@ep-sweet-moon-auyjhn8e-pooler.c-10.us-east-1.aws.neon.tech/neondb?ssl=require"

MENU_BUTTONS = {
    "🏠 Trang Chủ", "🛒 Mua Acc", "💳 Nạp Tiền", "👤 Tài Khoản", "📦 Đơn Hàng", "☎ Hỗ Trợ",
    "🎲 Chơi Tài Xỉu", "🎁 Điểm Danh", "🔗 Giới Thiệu", "🏆 Top Đại Gia", "🎁 Nhập Mã", "🪙 Đổi Tiền",
    "📊 Dashboard", "📥 Import TXT", "📦 Xem Kho", "📊 Thống Kê", "💰 Cộng Tiền", "💸 Trừ Tiền",
    "🪙 Cộng Xu", "🪙 Trừ Xu", "📷 Đổi QR", "📥 Bill Chờ", "📢 Broadcast", "🚫 Ban User", 
    "✅ Unban User", "🗑 Xóa Account", "📤 Export Chưa Bán", "📤 Export Đã Bán", "🔙 Menu Chính",
    "🎫 Tạo Code", "🎫 Danh Sách Code"
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

# ── Models ────────────────────────────────────────────────────────────────────
class User(Base):  
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)  
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)  
    fullname: Mapped[str] = mapped_column(String(255), nullable=False, default="")  
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  
    xu: Mapped[int] = mapped_column(Integer, nullable=False, default=100)  
    last_diemdanh: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  
    total_ref: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())  
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")  
    deposits: Mapped[list["Deposit"]] = relationship("Deposit", back_populates="user")  

class Account(Base):  
    # Đổi sang v3 để Neon tự sinh bảng mới đồng nhất cấu trúc dữ liệu gọn nhẹ
    __tablename__ = "accounts_v3"
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

class Giftcode(Base):
    __tablename__ = "giftcodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    xu: Mapped[int] = mapped_column(Integer, nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_by: Mapped[str | None] = mapped_column(Text, nullable=True, default="") 

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")  

# ── Services ──────────────────────────────────────────────────────────────────
async def get_or_create_user(session, telegram_id, username, fullname, is_admin=False):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))  
    user = result.scalar_one_or_none()  
    if user is None:
        user = User(telegram_id=telegram_id, username=username, fullname=fullname, is_admin=is_admin)  
        session.add(user)  
        await session.commit()  
        await session.refresh(user)  
    else:
        changed = False
        if user.username != username: user.username = username; changed = True  
        if user.fullname != fullname: user.fullname = fullname; changed = True  
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

async def adjust_xu_by_telegram_id(session, telegram_id, amount):
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None: return None
    user.xu += amount
    if user.xu < 0: user.xu = 0
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
    r = await session.execute(select(User)); return list(r.scalars().all())  

async def get_available_count(session):
    r = await session.execute(select(func.count()).where(Account.status == AccountStatus.available)); return r.scalar_one()  

async def get_sold_count(session):
    r = await session.execute(select(func.count()).where(Account.status == AccountStatus.sold)); return r.scalar_one()  

async def get_total_count(session):
    r = await session.execute(select(func.count()).select_from(Account)); return r.scalar_one()  

async def pick_random_accounts(session, quantity):
    r = await session.execute(select(Account).where(Account.status == AccountStatus.available).with_for_update().limit(quantity))
    return list(r.scalars().all())

async def mark_accounts_sold(session, accounts, order_id):
    now = datetime.utcnow()  
    for acc in accounts:
        acc.status = AccountStatus.sold  
        acc.order_id = order_id  
        acc.sold_at = now  
    await session.commit()  

# ── Hàm Import Đã Đồng Bộ Hóa Cấu Trúc Nhẹ Nhàng Xanh Chín ─────────────────────
async def import_accounts(session, lines):
    stats = {"total": 0, "imported": 0, "duplicates": 0, "invalid": 0}
    
    r_all = await session.execute(select(Account.username))
    existing_unames = set(r_all.scalars().all())
    
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
            
        uname = parts[0].strip()
        pwd = parts[1].strip()
        
        if not uname or not pwd:
            stats["invalid"] += 1
            continue
            
        if uname in existing_unames:
            stats["duplicates"] += 1
            continue
            
        session.add(
            Account(username=uname, password=pwd, status=AccountStatus.available)
        )
        existing_unames.add(uname)
        stats["imported"] += 1

    await session.commit()
    return stats

async def get_unsold_accounts(session):
    r = await session.execute(select(Account).where(Account.status == AccountStatus.available)); return list(r.scalars().all())  

async def get_sold_accounts(session):
    r = await session.execute(select(Account).where(Account.status == AccountStatus.sold)); return list(r.scalars().all())  

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
    b.row(KeyboardButton(text="🎲 Chơi Tài Xỉu"), KeyboardButton(text="🎁 Điểm Danh"))
    b.row(KeyboardButton(text="🔗 Giới Thiệu"), KeyboardButton(text="🏆 Top Đại Gia"))
    b.row(KeyboardButton(text="🪙 Đổi Tiền"), KeyboardButton(text="🎁 Nhập Mã"))
    b.row(KeyboardButton(text="📦 Đơn Hàng"), KeyboardButton(text="☎ Hỗ Trợ"))  
    return b.as_markup(resize_keyboard=True)  

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

def tai_xiu_inline_kb():
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🔴 Tài  (11–18)", callback_data="tx:tai"),  
        InlineKeyboardButton(text="🔵 Xỉu  (3–10)",  callback_data="tx:xiu"),  
    )
    return b.as_markup()

def admin_menu_kb():
    b = ReplyKeyboardBuilder()  
    b.row(KeyboardButton(text="📊 Dashboard"), KeyboardButton(text="📥 Import TXT"))  
    b.row(KeyboardButton(text="📦 Xem Kho"), KeyboardButton(text="📊 Thống Kê"))  
    b.row(KeyboardButton(text="💰 Cộng Tiền"), KeyboardButton(text="💸 Trừ Tiền"))  
    b.row(KeyboardButton(text="🪙 Cộng Xu"), KeyboardButton(text="🪙 Trừ Xu"))
    b.row(KeyboardButton(text="🎫 Tạo Code"), KeyboardButton(text="🎫 Danh Sách Code"))
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
        async with AsyncSessionLocal() as session:  
            db_user = await get_or_create_user(session, user.id, user.username, fullname, is_admin)  
            if db_user.is_admin != is_admin:
                db_user.is_admin = is_admin
                await session.commit()  
            data["db_user"] = db_user  
            data["db_session"] = session  
            data["is_admin"] = is_admin  
            if db_user.is_banned and not is_admin:  
                if isinstance(event, Message): await event.answer("🚫 Bạn đã bị cấm sử dụng bot.")  
                return
            return await handler(event, data)  

# ── States ────────────────────────────────────────────────────────────────────
class ShopState(StatesGroup):  
    waiting_quantity = State()  

class DepositState(StatesGroup):  
    waiting_amount = State()  
    waiting_bill = State()  

class TaixiuState(StatesGroup):
    waiting_bet = State()
    waiting_exchange_xu = State()

class CodeState(StatesGroup):
    waiting_code_input = State()

class AdminStates(StatesGroup):  
    waiting_qr = State()  
    waiting_import_file = State()  
    waiting_add_balance_id = State()  
    waiting_add_balance_amount = State()  
    waiting_subtract_balance_id = State()  
    waiting_subtract_balance_amount = State()  
    waiting_add_xu_id = State()
    waiting_add_xu_amount = State()
    waiting_subtract_xu_id = State()
    waiting_subtract_xu_amount = State()
    waiting_create_code_name = State()
    waiting_create_code_xu = State()
    waiting_create_code_uses = State()
    waiting_ban_id = State()  
    waiting_unban_id = State()  
    waiting_delete_username = State()  
    waiting_broadcast_text = State()  

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
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, db_user: User, db_session, bot: Bot):
    await state.clear()  
    
    is_new = (datetime.utcnow() - db_user.created_at).total_seconds() < 15
    ref_args = command.args
    
    if is_new and ref_args and ref_args.isdigit():
        ref_id = int(ref_args)
        if ref_id != db_user.telegram_id and db_user.referred_by is None:
            r_ref = await db_session.execute(select(User).where(User.telegram_id == ref_id))
            referrer = r_ref.scalar_one_or_none()
            if referrer:
                referrer.xu += THUONG_REF_XU
                referrer.total_ref += 1
                db_user.referred_by = ref_id
                await db_session.commit()
                try:
                    await bot.send_message(
                        ref_id,
                        f"🎉 <b>+{THUONG_REF_XU:,} XU GIỚI THIỆU!</b>\n"
                        f"👤 Thành viên mới: <b>{db_user.fullname}</b> vừa tham gia qua link của bạn.\n"
                        f"💰 Số dư xu: <b>{referrer.xu:,} xu</b>",
                        parse_mode="HTML"
                    )
                except Exception: pass

    name = db_user.fullname or message.from_user.full_name or "bạn"  
    available = await get_available_count(db_session)  
    await message.answer(
        f"👋 Chào mừng <b>{name}</b> đến với Shop Liên Quân & Giải Trí!\n\n"  
        f"🛒 Mua acc tự động, giá rẻ\n"  
        f"💰 Số dư tiền: <b>{db_user.balance:,} VNĐ</b>\n"  
        f"🎲 Ví giải trí: <b>{db_user.xu:,} xu</b>\n"
        f"📦 Kho còn: <b>{available:,} acc</b>\n\n"  
        f"⚡ Cú pháp cược nhanh Tài Xỉu (Tung đồng thời): <code>/tx [t/x] [xu]</code>\n"
        f"_(Ví dụ đặt Tài 50 xu: /tx t 50)_",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),  
    )

@router.message(lambda m: m.text == "🏠 Trang Chủ")
async def home(message: Message, state: FSMContext, db_user: User, db_session):
    await state.clear()  
    available = await get_available_count(db_session)  
    name = db_user.fullname or message.from_user.full_name or "bạn"  
    await message.answer(
        f"🏠 <b>Trang Chủ</b>\n\n"  
        f"👋 Xin chào <b>{name}</b>!\n"  
        f"💰 Số dư tiền: <b>{db_user.balance:,} VNĐ</b>\n"  
        f"🎲 Ví giải trí: <b>{db_user.xu:,} xu</b>\n"
        f"📦 Kho còn: <b>{available:,} acc</b>",  
        parse_mode="HTML",
        reply_markup=main_menu_kb(),  
    )

@router.message(lambda m: m.text == "☎ Hỗ Trợ")
async def support(message: Message, state: FSMContext):
    await state.clear()  
    await message.answer(
        "☎ <b>Hỗ Trợ Khách Hàng</b>\n\n"  
        "Nếu gặp lỗi hoặc cần giải đáp, liên hệ Admin:\n"
        "👤 Admin: @lananh9719\n\n"  
        "⏰ Hoạt động: 8:00 - 22:00 hàng ngày.",  
        parse_mode="HTML",
    )

# ── Shop Liên Quân ────────────────────────────────────────────────────────────
@router.message(lambda m: m.text == "🛒 Mua Acc")
async def buy_acc_start(message: Message, state: FSMContext, db_session):
    await state.clear()  
    available = await get_available_count(db_session)  
    await message.answer(
        f"🛒 <b>Mua Acc Liên Quân</b>\n\n"  
        f"💵 Giá bán: <b>{ACCOUNT_PRICE:,} VNĐ / acc</b>\n"  
        f"📦 Kho còn: <b>{available:,} acc</b>\n"  
        f"⚠️ Yêu cầu mua tối thiểu: <b>{MIN_ORDER_QTY} acc</b>\n\n"  
        "Vui lòng nhập số lượng acc muốn mua:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),  
    )
    await state.set_state(ShopState.waiting_quantity)  

@router.message(ShopState.waiting_quantity, F.text == "❌ Hủy")
async def buy_cancel(message: Message, state: FSMContext):
    await state.clear()  
    await message.answer("❌ Đã hủy giao dịch.", reply_markup=main_menu_kb())  

@router.message(ShopState.waiting_quantity, ~F.text.in_(MENU_BUTTONS))
async def buy_acc_quantity(message: Message, state: FSMContext, db_user: User, db_session):
    text = message.text or ""
    if not text.isdigit():
        await message.answer("⚠️ Vui lòng nhập số nguyên hợp lệ.")  
        return
    quantity = int(text)
    if quantity < MIN_ORDER_QTY:
        await message.answer(f"⚠️ Số lượng tối thiểu là <b>{MIN_ORDER_QTY} acc</b>.", parse_mode="HTML")  
        return
    total_price = quantity * ACCOUNT_PRICE
    
    r_u = await db_session.execute(select(User).where(User.id == db_user.id).with_for_update())
    fresh_user = r_u.scalar_one_or_none()
    
    if fresh_user.balance < total_price:
        shortage = total_price - fresh_user.balance
        await message.answer(
            f"❌ <b>Số dư VNĐ không đủ!</b>\n\n"  
            f"💰 Hiện có: <b>{fresh_user.balance:,} VNĐ</b>\n"  
            f"💵 Cần thanh toán: <b>{total_price:,} VNĐ</b>\n"  
            f"⚠️ Thiếu: <b>{shortage:,} VNĐ</b>\n\nVui lòng nạp thêm tiền.",  
            parse_mode="HTML", reply_markup=main_menu_kb()  
        )
        await state.clear()  
        return
        
    available = await get_available_count(db_session)  
    if available < quantity:
        await message.answer(f"❌ Kho không đủ hàng!\n📦 Kho hiện còn: <b>{available:,} acc</b>", parse_mode="HTML", reply_markup=main_menu_kb())  
        await state.clear()  
        return

    accounts = await pick_random_accounts(db_session, quantity)
    if len(accounts) < quantity:
        await message.answer("❌ Có lỗi xảy ra khi lấy tài khoản. Thử lại sau.", reply_markup=main_menu_kb())  
        await state.clear()  
        return

    order = await create_order(db_session, fresh_user.id, quantity, total_price, "")  
    fresh_user.balance -= total_price
    await mark_accounts_sold(db_session, accounts, order.id)  

    account_data = [(a.username, a.password) for a in accounts]
    filepath, filename = await save_order_file(account_data, order.id)  
    order.file_name = filename  
    await db_session.commit()  
    await state.clear()  

    await message.answer(
        f"✅ <b>Mua hàng thành công!</b>\n\n"  
        f"📦 Số lượng: <b>{quantity} acc</b>\n"  
        f"💵 Tổng tiền: <b>{total_price:,} VNĐ</b>\n"  
        f"🧾 Mã đơn: <b>#{order.id}</b>\n\nĐang gửi file...",  
        parse_mode="HTML", reply_markup=main_menu_kb()  
    )
    await message.answer_document(FSInputFile(filepath, filename=filename), caption=f"📄 Đơn hàng #{order.id} — {quantity} acc")  
    await message.answer(f"📌 Link check acc free:\n{CHECKER_LINK}")  

# ── Tài khoản & Đơn hàng ─────────────────────────────────────────────────────
@router.message(lambda m: m.text == "👤 Tài Khoản")
async def my_account(message: Message, state: FSMContext, db_user: User, db_session):
    await state.clear()  
    joined = db_user.created_at.strftime("%d/%m/%Y") if db_user.created_at else "N/A"  
    orders = await get_user_orders(db_session, db_user.id, limit=9999)  
    uname = f"@{db_user.username}" if db_user.username else "Không có"  
    await message.answer(
        f"👤 <b>Thông Tin Tài Khoản</b>\n\n"  
        f"🆔 ID Telegram: <code>{db_user.telegram_id}</code>\n"  
        f"👤 Username: {uname}\n"  
        f"📛 Tên: {db_user.fullname}\n\n"  
        f"💰 Số dư VNĐ: <b>{db_user.balance:,} VNĐ</b>\n"  
        f"🎲 Số dư Xu: <b>{db_user.xu:,} xu</b>\n"  
        f"👥 Đã giới thiệu: <b>{db_user.total_ref} người</b>\n"  
        f"📦 Đơn đã mua: <b>{len(orders)}</b>\n"  
        f"📅 Tham gia ngày: {joined}",  
        parse_mode="HTML",
    )

@router.message(lambda m: m.text == "📦 Đơn Hàng")
async def my_orders(message: Message, state: FSMContext, db_user: User, db_session):
    await state.clear()  
    orders = await get_user_orders(db_session, db_user.id, limit=20)  
    if not orders:
        await message.answer("📦 Bạn chưa mua đơn hàng nào.")  
        return
    lines = ["📦 <b>20 Đơn Hàng Gần Nhất</b>\n"]  
    for i, o in enumerate(orders, 1):
        created = o.created_at.strftime("%d/%m/%Y %H:%M") if o.created_at else "N/A"  
        lines.append(f"{i}. Đơn #{o.id} — {o.quantity} acc — {o.price:,} VNĐ — {created}")  
    await message.answer("\n".join(lines), parse_mode="HTML")  

# ── Nạp tiền VNĐ ──────────────────────────────────────────────────────────────
@router.message(lambda m: m.text == "💳 Nạp Tiền")
async def deposit_start(message: Message, state: FSMContext):
    await state.clear()  
    if not qr_exists():
        await message.answer("⚠️ Hệ thống nạp tiền đang bảo trì (Thiếu QR). Vui lòng liên hệ Admin.")  
        return
    await message.answer_photo(
        FSInputFile(QR_IMAGE_PATH),  
        caption="💳 <b>Nạp Tiền Qua QR</b>\n\nQuét mã QR để chuyển khoản tiền thật.\n\nNhập số tiền muốn nạp (VNĐ):",
        parse_mode="HTML", reply_markup=cancel_kb()  
    )
    await state.set_state(DepositState.waiting_amount)  

@router.message(DepositState.waiting_amount, F.text == "❌ Hủy")
async def deposit_cancel_amount(message: Message, state: FSMContext):
    await state.clear()  
    await message.answer("❌ Đã hủy nạp tiền.", reply_markup=main_menu_kb())  

@router.message(DepositState.waiting_amount, ~F.text.in_(MENU_BUTTONS))
async def deposit_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", "").replace(".", "").strip()  
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ.")  
        return
    amount = int(text)
    await state.update_data(amount=amount)  
    await message.answer(f"💵 Số tiền nạp: <b>{amount:,} VNĐ</b>\n\n📷 Vui lòng gửi ảnh chụp màn hình bill chuyển khoản:", parse_mode="HTML", reply_markup=cancel_kb())  
    await state.set_state(DepositState.waiting_bill)  

@router.message(DepositState.waiting_bill, F.text == "❌ Hủy")
async def deposit_cancel_bill(message: Message, state: FSMContext):
    await state.clear()  
    await message.answer("❌ Đã hủy nạp tiền.", reply_markup=main_menu_kb())  

@router.message(DepositState.waiting_bill, F.photo)
async def deposit_bill_photo(message: Message, state: FSMContext, bot: Bot, db_user: User, db_session):
    data = await state.get_data()  
    amount = data.get("amount", 0)  
    await state.clear()  
    photo = message.photo[-1]  
    file = await bot.get_file(photo.file_id)  
    file_bytes = await bot.download_file(file.file_path)  
    bill_path = await save_bill_image(file_bytes.read(), "jpg")  
    
    deposit = await create_deposit(db_session, db_user.id, amount, bill_path)  
    uname = f"@{db_user.username}" if db_user.username else "Không có"  
    now_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S")  
    caption = (
        f"💳 <b>YÊU CẦU NẠP TIỀN</b>\n\n"  
        f"🆔 ID Telegram: <code>{db_user.telegram_id}</code>\n"  
        f"👤 Username: {uname}\n"  
        f"📛 Tên: {db_user.fullname}\n"  
        f"💵 Số tiền: <b>{amount:,} VNĐ</b>\n"  
        f"🕐 Thời gian: {now_str}\n"  
        f"🧾 Mã Bill nạp: #{deposit.id}"  
    )
    kb = deposit_approval_kb(deposit.id)  
    for admin_id in ADMIN_IDS:
        try:
            await message.forward(admin_id)  
            await bot.send_message(admin_id, caption, parse_mode="HTML", reply_markup=kb)  
        except Exception: pass
    await message.answer("✅ <b>Đã gửi bill cho Admin!</b>\n\n Vui lòng đợi trong giây lát hệ thống đang duyệt.", parse_mode="HTML", reply_markup=main_menu_kb())  

@router.message(DepositState.waiting_bill, ~F.text.in_(MENU_BUTTONS))
async def deposit_bill_invalid(message: Message):
    await message.answer("⚠️ Vui lòng gửi hình ảnh hóa đơn giao dịch.")  

@router.callback_query(F.data.startswith("approve_deposit:"))
async def cb_approve_deposit(callback: CallbackQuery, bot: Bot, is_admin: bool, db_session):
    if not is_admin: await callback.answer("❌ Bạn không có quyền.", show_alert=True); return  
    deposit_id = int(callback.data.split(":")[1])  
    deposit = await approve_deposit(db_session, deposit_id, callback.from_user.id)  
    if deposit is None: await callback.answer("⚠️ Bill không tồn tại hoặc đã xử lý trước đó.", show_alert=True); return  
    user_after = await add_balance(db_session, deposit.user_id, deposit.amount)  
    user_tg_id = deposit.user.telegram_id if deposit.user else None  
    await callback.message.edit_reply_markup(reply_markup=None)  
    await callback.message.reply(f"✅ Đã duyệt nạp tiền thành công <b>{deposit.amount:,} VNĐ</b> cho đơn #{deposit_id}", parse_mode="HTML")  
    if user_tg_id:
        try: await bot.send_message(user_tg_id, f"✅ <b>Nạp tiền thành công!</b>\n\n💵 Cộng: <b>{deposit.amount:,} VNĐ</b>\n💰 Số dư ví VNĐ: <b>{user_after.balance:,} VNĐ</b>", parse_mode="HTML")  
        except Exception: pass
    await callback.answer("✅ Hoàn tất!")  

@router.callback_query(F.data.startswith("reject_deposit:"))
async def cb_reject_deposit(callback: CallbackQuery, bot: Bot, is_admin: bool, db_session):
    if not is_admin: await callback.answer("❌ Bạn không có quyền.", show_alert=True); return  
    deposit_id = int(callback.data.split(":")[1])  
    deposit = await reject_deposit(db_session, deposit_id, callback.from_user.id)  
    if deposit is None: await callback.answer("⚠️ Bill không tồn tại hoặc đã xử lý.", show_alert=True); return  
    user_tg_id = deposit.user.telegram_id if deposit.user else None  
    await callback.message.edit_reply_markup(reply_markup=None)  
    await callback.message.reply(f"❌ Đã từ chối đơn nạp #{deposit_id}", parse_mode="HTML")  
    if user_tg_id:
        try: await bot.send_message(user_tg_id, f"❌ <b>Đơn nạp tiền bị từ chối!</b>\n\n💵 Số tiền: <b>{deposit.amount:,} VNĐ</b>\nVui lòng kiểm tra lại hình ảnh hóa đơn.", parse_mode="HTML")  
        except Exception: pass
    await callback.answer("❌ Đã từ chối!")  

# ── Mini Game Tài Xỉu (Xanh Chín 100% - Tung Đồng Thời Realtime) ───────────────
@router.message(lambda m: m.text == "🎲 Chơi Tài Xỉu")
async def tx_start_menu(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    await message.answer(
        f"🎲 <b>MINI GAME TÀI XỈU</b> 🎲\n\n"
        f"💳 Ví xu hiện tại: <b>{db_user.xu:,} xu</b>\n\n"
        f"Luật chơi: Tổng 3 xúc xắc từ 3-10 là Xỉu, từ 11-18 là Tài.\n"
        f"Hãy chọn cửa cược dưới đây:",
        parse_mode="HTML", reply_markup=tai_xiu_inline_kb()
    )

@router.callback_query(F.data.startswith("tx:"))
async def tx_choose_side(callback: CallbackQuery, state: FSMContext):
    side = callback.data.split(":")[1]
    side_name = "🔴 TÀI" if side == "tai" else "🔵 XỈU"
    await state.update_data(chosen_side=side)
    await state.set_state(TaixiuState.waiting_bet)
    await callback.message.edit_text(
        f"🗳 Bạn đặt cửa: <b>{side_name}</b>\n\n💬 Nhập số Xu muốn đặt cược vào chat:",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TaixiuState.waiting_bet)
async def tx_process_bet(message: Message, state: FSMContext, db_session, db_user: User, bot: Bot):
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Số xu đặt cược phải là số nguyên dương hợp lệ.")
        return
    bet = int(text)
    
    r_u = await db_session.execute(select(User).where(User.id == db_user.id).with_for_update())
    user = r_u.scalar_one_or_none()
    
    if user.xu < bet:
        await message.answer(f"❌ Bạn không đủ xu! Hiện có <b>{user.xu:,} xu</b>.", parse_mode="HTML")
        await state.clear()
        return
        
    data = await state.get_data()
    chosen_side = data.get("chosen_side")
    await state.clear()

    await message.answer("🎲 Đang lắc xúc xắc đồng thời...")

    dice_results = await asyncio.gather(
        bot.send_dice(chat_id=message.chat.id, emoji="🎲"),
        bot.send_dice(chat_id=message.chat.id, emoji="🎲"),
        bot.send_dice(chat_id=message.chat.id, emoji="🎲")
    )

    d1 = dice_results[0].dice.value
    d2 = dice_results[1].dice.value
    d3 = dice_results[2].dice.value
    
    tong = d1 + d2 + d3
    ket_qua = "tai" if tong >= 11 else "xiu"
    ket_qua_text = "🔴 TÀI" if ket_qua == "tai" else "🔵 XỈU"

    await asyncio.sleep(3.5)

    if chosen_side == ket_qua:
        user.xu += bet
        status = f"🎉 <b>THẮNG PHIÊN!</b> Bạn được cộng <code>+{bet:,}</code> xu."
    else:
        user.xu -= bet
        status = f"💸 <b>THUA PHIÊN!</b> Bạn bị trừ <code>-{bet:,}</code> xu."
        
    await db_session.commit()

    await message.answer(
        f"📊 <b>KẾT QUẢ PHIÊN CƯỢC</b>\n"
        f"──────────────────\n"
        f"🎲 Xúc xắc: {d1} + {d2} + {d3} = <b>{tong}</b>\n"
        f"👉 Kết quả: <b>{ket_qua_text}</b>\n"
        f"──────────────────\n"
        f"{status}\n"
        f"💳 Số dư ví xu mới: <b>{user.xu:,} xu</b>",
        parse_mode="HTML", reply_markup=main_menu_kb()
    )

# ── Lệnh cược nhanh /tx t hoặc x (Tung Đồng Thời) ─────────────────────────────
@router.message(Command("tx"))
async def cmd_tx_fast(message: Message, db_session, db_user: User, bot: Bot):
    args = message.text.split()
    if len(args) < 3:
        await message.answer("⚠️ Cú pháp nhanh: <code>/tx [t/x] [xu]</code>\n<i>(Ví dụ: /tx t 100)</i>", parse_mode="HTML")
        return
    side_arg = args[1].lower()
    if side_arg not in ["t", "x"]:
        await message.answer("⚠️ Sai cửa đặt! Chỉ dùng <code>t</code> (Tài) hoặc <code>x</code> (Xỉu).", parse_mode="HTML")
        return
    cua_dat = "tai" if side_arg == "t" else "xiu"
    cua_text = "🔴 TÀI" if cua_dat == "tai" else "🔵 XỈU"
    
    if not args[2].isdigit():
        await message.answer("⚠️ Số tiền đặt cược phải là số nguyên dương.")
        return
    bet = int(args[2])
    
    r_u = await db_session.execute(select(User).where(User.id == db_user.id).with_for_update())
    user = r_u.scalar_one_or_none()
    
    if user.xu < bet:
        await message.answer(f"❌ Bạn không đủ xu! Ví hiện còn: <b>{user.xu:,} xu</b>.", parse_mode="HTML")
        return

    await message.answer("🎲 Đang lắc lệnh nhanh...")

    dice_results = await asyncio.gather(
        bot.send_dice(chat_id=message.chat.id, emoji="🎲"),
        bot.send_dice(chat_id=message.chat.id, emoji="🎲"),
        bot.send_dice(chat_id=message.chat.id, emoji="🎲")
    )

    d1 = dice_results[0].dice.value
    d2 = dice_results[1].dice.value
    d3 = dice_results[2].dice.value
    
    tong = d1 + d2 + d3
    ket_qua = "tai" if tong >= 11 else "xiu"
    ket_qua_text = "🔴 TÀI" if ket_qua == "tai" else "🔵 XỈU"

    await asyncio.sleep(3.5)  

    if cua_dat == ket_qua:
        user.xu += bet
        status = f"🎉 <b>THẮNG LỆNH!</b> Cộng <code>+{bet:,}</code> xu."
    else:
        user.xu -= bet
        status = f"💸 <b>THUA LỆNH!</b> Trừ <code>-{bet:,}</code> xu."
        
    await db_session.commit()
    await message.answer(
        f"📊 <b>LẮC NHANH: Cửa {cua_text} · Cược {bet:,} xu</b>\n"
        f"🎲 Xúc xắc: {d1} + {d2} + {d3} = <b>{tong}</b> -> <b>{ket_qua_text}</b>\n"
        f"──────────────────\n"
        f"{status}\n"
        f"💳 Ví xu: <b>{user.xu:,} xu</b>",
        parse_mode="HTML"
    )

# ── Điểm Danh Chống Spam 24H ──────────────────────────────────────────────────
@router.message(lambda m: m.text == "🎁 Điểm Danh")
async def cmd_diemdanh(message: Message, db_session, db_user: User):
    now = datetime.utcnow()
    if db_user.last_diemdanh and (now - db_user.last_diemdanh) < timedelta(days=1):
        rem = timedelta(days=1) - (now - db_user.last_diemdanh)
        h, r = divmod(rem.seconds, 3600)
        m, _ = divmod(r, 60)
        await message.answer(f"⚠️ Bạn đã nhận quà điểm danh rồi! Hãy quay lại sau <b>{h} giờ {m} phút</b>.", parse_mode="HTML")
        return
        
    db_user.xu += XU_DIEMDANH
    db_user.last_diemdanh = now
    await db_session.commit()
    await message.answer(f"🎉 <b>Điểm danh thành công!</b>\n🎁 Quà tặng: <code>+{XU_DIEMDANH} xu</code>\n💰 Số dư ví xu: <b>{db_user.xu:,} xu</b>", parse_mode="HTML")

# ── Tính Năng Đổi Xu Thành Tiền VNĐ (100 Xu = 10 VNĐ) ──────────────────────────
@router.message(lambda m: m.text == "🪙 Đổi Tiền")
async def exchange_xu_start(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    await message.answer(
        f"🪙 <b>ĐỔI XU SANG TIỀN VNĐ</b> 🪙\n\n"
        f"⚡ Tỷ lệ quy đổi: <b>100 Xu = 10 VNĐ</b>\n"
        f"💳 Ví xu hiện tại: <b>{db_user.xu:,} xu</b>\n"
        f"💰 Ví tiền VNĐ của bạn: <b>{db_user.balance:,} VNĐ</b>\n\n"
        f"💬 Vui lòng nhập số <b>Xu</b> bạn muốn quy đổi sang VNĐ (Phải là bội số của 100):",
        parse_mode="HTML", reply_markup=cancel_kb()
    )
    await state.set_state(TaixiuState.waiting_exchange_xu)

@router.message(TaixiuState.waiting_exchange_xu, F.text == "❌ Hủy")
async def exchange_xu_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy quy đổi xu.", reply_markup=main_menu_kb())

@router.message(TaixiuState.waiting_exchange_xu, ~F.text.in_(MENU_BUTTONS))
async def exchange_xu_process(message: Message, state: FSMContext, db_session, db_user: User):
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Số xu đổi phải là số nguyên dương hợp lệ.")
        return
    xu_val = int(text)
    if xu_val % 100 != 0:
        await message.answer("⚠️ Số xu muốn đổi phải là bội số của 100 (VD: 100, 200, 500...).")
        return

    r_u = await db_session.execute(select(User).where(User.id == db_user.id).with_for_update())
    user = r_u.scalar_one_or_none()

    if user.xu < xu_val:
        await message.answer(f"❌ Bạn không đủ xu! Ví hiện còn: <b>{user.xu:,} xu</b>.", parse_mode="HTML")
        await state.clear()
        return

    vnd_received = int(xu_val / 10)
    user.xu -= xu_val
    user.balance += vnd_received
    await db_session.commit()
    await state.clear()

    await message.answer(
        f"✅ <b>QUY ĐỔI THÀNH CÔNG!</b>\n\n"
        f"🪙 Đã trừ: <code>-{xu_val:,} xu</code>\n"
        f"💵 Đã cộng: <code>+{vnd_received:,} VNĐ</code>\n"
        f"──────────────────\n"
        f"💰 Số dư ví VNĐ mới: <b>{user.balance:,} VNĐ</b>\n"
        f"💳 Số dư ví Xu mới: <b>{user.xu:,} xu</b>",
        parse_mode="HTML", reply_markup=main_menu_kb()
    )

# ── Hệ Thống Giới Thiệu (Referral System) ─────────────────────────────────────
@router.message(lambda m: m.text == "🔗 Giới Thiệu")
async def cmd_referral(message: Message, db_user: User, bot: Bot):
    bot_me = await bot.get_me()
    link = f"https://t.me/{bot_me.username}?start={db_user.telegram_id}"
    await message.answer(
        f"🔗 <b>HỆ THỐNG MỜI BẠN BÈ NHẬN XU</b> 🔗\n\n"
        f"Copy đường link độc quyền dưới đây gửi cho bạn bè chơi cùng bot. "
        f"Khi họ nhấn Bắt đầu (/start), tài khoản của bạn nhận thưởng ngay vĩnh viễn!\n\n"
        f"🎁 Phần thưởng: <b>+{THUONG_REF_XU:,} xu</b> / 1 người mời thành công.\n\n"
        f"📊 Thống kê cá nhân:\n"
        f"👥 Số người đã mời thành công: <b>{db_user.total_ref} người</b>\n\n"
        f"🎯 Đường link giới thiệu của bạn:\n"
        f"<code>{link}</code>\n\n"
        f"<i>(Chạm vào link trên để tự sao chép nhanh)</i>",
        parse_mode="HTML"
    )

# ── Top Đại Gia ───────────────────────────────────────────────────────────────
@router.message(lambda m: m.text == "🏆 Top Đại Gia")
async def cmd_top_rich(message: Message, db_session):
    r = await db_session.execute(select(User).order_by(User.xu.desc()).limit(10))
    top_list = r.scalars().all()
    if not top_list:
        await message.answer("Chưa có dữ liệu đại gia.")
        return
    text = "🏆 <b>BẢNG XẾP HẠNG ĐẠI GIA XU</b> 🏆\n──────────────\n"
    for i, u in enumerate(top_list, 1):
        text += f"{i}. <b>{u.fullname}</b> — {u.xu:,} xu\n"
    await message.answer(text, parse_mode="HTML")

# ── Hệ Thống Giftcode Lưu Trữ ─────────────────────────────────────────────────
@router.message(lambda m: m.text == "🎁 Nhập Mã")
async def giftcode_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🎁 Vui lòng nhập mã quà tặng (Giftcode) của bạn:", reply_markup=cancel_kb())
    await state.set_state(CodeState.waiting_code_input)

@router.message(CodeState.waiting_code_input, F.text == "❌ Hủy")
async def giftcode_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Đã hủy nhập mã.", reply_markup=main_menu_kb())

@router.message(CodeState.waiting_code_input, ~F.text.in_(MENU_BUTTONS))
async def giftcode_redeem(message: Message, state: FSMContext, db_session, db_user: User):
    code_text = (message.text or "").strip().upper()
    await state.clear()
    
    r_c = await db_session.execute(select(Giftcode).where(Giftcode.code == code_text).with_for_update())
    code_obj = r_c.scalar_one_or_none()
    
    if not code_obj:
        await message.answer("❌ Mã quà tặng không tồn tại hoặc đã hết hạn!", reply_markup=main_menu_kb())
        return
        
    used_ids = [x for x in (code_obj.used_by or "").split(",") if x]
    if str(db_user.telegram_id) in used_ids:
        await message.answer("⚠️ Bạn đã sử dụng mã quà tặng này rồi!", reply_markup=main_menu_kb())
        return
        
    if code_obj.used_count >= code_obj.max_uses:
        await message.answer("😢 Mã quà tặng này đã hết lượt sử dụng!", reply_markup=main_menu_kb())
        return

    r_u = await db_session.execute(select(User).where(User.id == db_user.id).with_for_update())
    user = r_u.scalar_one_or_none()
    
    user.xu += code_obj.xu
    code_obj.used_count += 1
    used_ids.append(str(user.telegram_id))
    code_obj.used_by = ",".join(used_ids)
    
    await db_session.commit()
    await message.answer(f"✅ <b>Nhập mã thành công!</b>\n🎁 Bạn được cộng: <code>+{code_obj.xu:,} xu</code>\n💰 Số dư xu hiện tại: <b>{user.xu:,} xu</b>", parse_mode="HTML", reply_markup=main_menu_kb())

# ── Admin Panel ───────────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: Message, is_admin: bool):
    if not is_admin: await message.answer("❌ Bạn không có quyền."); return  
    await message.answer("🔐 <b>HỆ THỐNG ĐIỀU HÀNH ADMIN</b>", parse_mode="HTML", reply_markup=admin_menu_kb())  

@router.message(lambda m: m.text == "🔙 Menu Chính")
async def back_to_main(message: Message):
    await message.answer("🏠 Quay về Menu chính", reply_markup=main_menu_kb())  

@router.message(lambda m: m.text == "📊 Dashboard")
@admin_only
async def admin_dashboard(message: Message, is_admin: bool, db_session):
    t_acc = await get_total_count(db_session)  
    a_acc = await get_available_count(db_session)  
    s_acc = await get_sold_count(db_session)  
    orders = await get_all_orders(db_session, 9999)  
    users = await get_all_users(db_session)  
    bills = await get_pending_deposits(db_session)  
    await message.answer(
        f"📊 <b>DASHBOARD HỆ THỐNG</b>\n\n"  
        f"👥 Tổng người dùng: <b>{len(users)}</b>\n"  
        f"📦 Tổng acc trong kho: <b>{t_acc}</b>\n"  
        f"✅ Acc chưa bán: <b>{a_acc}</b>\n"  
        f"🔴 Acc đã bán: <b>{s_acc}</b>\n"  
        f"🧾 Tổng số đơn: <b>{len(orders)}</b>\n"  
        f"💰 Doanh thu VNĐ: <b>{sum(o.price for o in orders):,} VNĐ</b>\n"  
        f"⏳ Hoá đơn chờ duyệt: <b>{len(bills)}</b>",  
        parse_mode="HTML"
    )

@router.message(lambda m: m.text == "📦 Xem Kho")
@admin_only
async def admin_view_stock(message: Message, is_admin: bool, db_session):
    t = await get_total_count(db_session)  
    a = await get_available_count(db_session)  
    s = await get_sold_count(db_session)  
    await message.answer(f"📦 <b>Trạng Thái Kho</b>\n\n📊 Tổng: <b>{t}</b>\n✅ Chưa bán: <b>{a}</b>\n🔴 Đã bán: <b>{s}</b>", parse_mode="HTML")  

@router.message(lambda m: m.text == "📊 Thống Kê")
@admin_only
async def admin_stats(message: Message, is_admin: bool, db_session):
    orders = await get_all_orders(db_session, 9999)  
    users = await get_all_users(db_session)  
    t = await get_total_count(db_session)  
    a = await get_available_count(db_session)  
    s = await get_sold_count(db_session)  
    await message.answer(
        f"📊 <b>Thống Kê Vận Hành</b>\n\n👥 Tổng User: <b>{len(users)}</b>\n📦 Tổng Acc: <b>{t}</b>\n✅ Còn: <b>{a}</b>\n🔴 Đã bán: <b>{s}</b>\n🧾 Tổng đơn: <b>{len(orders)}</b>\n💰 Tổng doanh thu: <b>{sum(o.price for o in orders):,} VNĐ</b>",  
        parse_mode="HTML"
    )

@router.message(lambda m: m.text == "📥 Import TXT")
@admin_only
async def admin_import_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("📥 Vui lòng gửi file `.TXT` chứa tài khoản.\n\nĐịnh dạng mỗi dòng: <code>username|password</code>", parse_mode="HTML")  

@router.message(AdminStates.waiting_import_file, F.document)
async def admin_import_file(message: Message, state: FSMContext, bot: Bot, db_session):
    doc = message.document  
    if not doc or not doc.file_name or not doc.file_name.endswith(".txt"):
        await message.answer("⚠️ File gửi lên phải có định dạng đuôi `.txt`!")  
        return
    await state.clear()  
    file = await bot.get_file(doc.file_id)  
    raw = await bot.download_file(file.file_path)  
    content = raw.read().decode("utf-8", errors="ignore")  
    stats = await import_accounts(db_session, content.splitlines())  
    await message.answer(f"📥 <b>KẾT QUẢ IMPORT KHO ACC</b>\n\n📄 Tổng dòng: <b>{stats['total']}</b>\n✅ Đã thêm thành công: <b>{stats['imported']}</b>\n🔁 Bị trùng: <b>{stats['duplicates']}</b>\n❌ Lỗi định dạng: <b>{stats['invalid']}</b>", parse_mode="HTML")  

@router.message(lambda m: m.text == "💰 Cộng Tiền")
@admin_only
async def admin_add_bal_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("💰 Nhập Telegram ID người nhận tiền VNĐ:")  
    await state.set_state(AdminStates.waiting_add_balance_id)  

@router.message(AdminStates.waiting_add_balance_id)
async def admin_add_bal_id(message: Message, state: FSMContext):
    t = (message.text or "").strip()  
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ Telegram ID phải là số."); return  
    await state.update_data(target_id=int(t))  
    await message.answer("💵 Nhập số tiền VNĐ cần cộng thêm:")  
    await state.set_state(AdminStates.waiting_add_balance_amount)  

@router.message(AdminStates.waiting_add_balance_amount)
async def admin_add_bal_amount(message: Message, state: FSMContext, db_session):
    t = (message.text or "").replace(",", "").strip()  
    if not t.isdigit() or int(t) <= 0: await message.answer("⚠️ Số tiền không hợp lệ."); return  
    amt = int(t); data = await state.get_data(); tid = data["target_id"]; await state.clear()  
    user = await adjust_balance_by_telegram_id(db_session, tid, amt)  
    if user is None: await message.answer(f"❌ Không tìm thấy User ID {tid} trong hệ thống."); return  
    await message.answer(f"✅ Đã cộng <b>{amt:,} VNĐ</b> cho <b>{user.fullname}</b>\n💰 Số dư VNĐ mới: <b>{user.balance:,} VNĐ</b>", parse_mode="HTML")  

@router.message(lambda m: m.text == "💸 Trừ Tiền")
@admin_only
async def admin_sub_bal_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("💸 Nhập Telegram ID người cần trừ tiền VNĐ:")  
    await state.set_state(AdminStates.waiting_subtract_balance_id)  

@router.message(AdminStates.waiting_subtract_balance_id)
async def admin_sub_bal_id(message: Message, state: FSMContext):
    t = (message.text or "").strip()  
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ Telegram ID không hợp lệ."); return  
    await state.update_data(target_id=int(t))  
    await message.answer("💵 Nhập số tiền VNĐ cần trừ bớt:")  
    await state.set_state(AdminStates.waiting_subtract_balance_amount)  

@router.message(AdminStates.waiting_subtract_balance_amount)
async def admin_sub_bal_amount(message: Message, state: FSMContext, db_session):
    t = (message.text or "").replace(",", "").strip()  
    if not t.isdigit() or int(t) <= 0: await message.answer("⚠️ Số tiền không hợp lệ."); return  
    amt = int(t); data = await state.get_data(); tid = data["target_id"]; await state.clear()  
    user = await adjust_balance_by_telegram_id(db_session, tid, -amt)  
    if user is None: await message.answer(f"❌ Không tìm thấy User ID {tid}"); return  
    await message.answer(f"✅ Đã trừ <b>{amt:,} VNĐ</b> khỏi <b>{user.fullname}</b>\n💰 Số dư VNĐ mới: <b>{user.balance:,} VNĐ</b>", parse_mode="HTML")  

@router.message(lambda m: m.text == "🪙 Cộng Xu")
@admin_only
async def admin_add_xu_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("🪙 Nhập Telegram ID người cần cộng Xu:")
    await state.set_state(AdminStates.waiting_add_xu_id)

@router.message(AdminStates.waiting_add_xu_id)
async def admin_add_xu_id(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ ID phải là số."); return
    await state.update_data(target_id=int(t))
    await message.answer("🪙 Nhập số lượng Xu muốn cộng:")
    await state.set_state(AdminStates.waiting_add_xu_amount)

@router.message(AdminStates.waiting_add_xu_amount)
async def admin_add_xu_amount(message: Message, state: FSMContext, db_session):
    t = (message.text or "").replace(",", "").strip()
    if not t.isdigit() or int(t) <= 0: await message.answer("⚠️ Số xu không hợp lệ."); return
    amt = int(t); data = await state.get_data(); tid = data["target_id"]; await state.clear()
    user = await adjust_xu_by_telegram_id(db_session, tid, amt)
    if user is None: await message.answer(f"❌ Không tìm thấy User ID {tid}"); return
    await message.answer(f"✅ Đã cộng <b>+{amt:,} xu</b> cho <b>{user.fullname}</b>\n🪙 Số dư xu mới: <b>{user.xu:,} xu</b>", parse_mode="HTML")

@router.message(lambda m: m.text == "🪙 Trừ Xu")
@admin_only
async def admin_sub_xu_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("🪙 Nhập Telegram ID người cần trừ bớt Xu:")
    await state.set_state(AdminStates.waiting_subtract_xu_id)

@router.message(AdminStates.waiting_subtract_xu_id)
async def admin_sub_xu_id(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ ID phải là số."); return
    await state.update_data(target_id=int(t))
    await message.answer("🪙 Nhập số lượng Xu muốn trừ bớt:")
    await state.set_state(AdminStates.waiting_subtract_xu_amount)

@router.message(AdminStates.waiting_subtract_xu_amount)
async def admin_sub_xu_amount(message: Message, state: FSMContext, db_session):
    t = (message.text or "").replace(",", "").strip()
    if not t.isdigit() or int(t) <= 0: await message.answer("⚠️ Số xu không hợp lệ."); return
    amt = int(t); data = await state.get_data(); tid = data["target_id"]; await state.clear()
    user = await adjust_xu_by_telegram_id(db_session, tid, -amt)
    if user is None: await message.answer(f"❌ Không tìm thấy User ID {tid}"); return
    await message.answer(f"✅ Đã trừ <b>-{amt:,} xu</b> từ <b>{user.fullname}</b>\n🪙 Số dư xu mới: <b>{user.xu:,} xu</b>", parse_mode="HTML")

# Quản lý Giftcode Hệ Thống của Admin
@router.message(lambda m: m.text == "🎫 Tạo Code")
@admin_only
async def admin_create_code_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("🎫 Nhập tên Giftcode muốn tạo (Ví dụ: QUATANG100):")
    await state.set_state(AdminStates.waiting_create_code_name)

@router.message(AdminStates.waiting_create_code_name)
async def admin_code_name(message: Message, state: FSMContext):
    name = (message.text or "").strip().upper()
    await state.update_data(code_name=name)
    await message.answer("🪙 Nhập số lượng Xu thưởng của mã này:")
    await state.set_state(AdminStates.waiting_create_code_xu)

@router.message(AdminStates.waiting_create_code_xu)
async def admin_code_xu(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t.isdigit(): await message.answer("⚠️ Vui lòng nhập số."); return
    await state.update_data(code_xu=int(t))
    await message.answer("🔢 Nhập số lượt giới hạn sử dụng tối đa của mã:")
    await state.set_state(AdminStates.waiting_create_code_uses)

@router.message(AdminStates.waiting_create_code_uses)
async def admin_code_uses(message: Message, state: FSMContext, db_session):
    t = (message.text or "").strip()
    if not t.isdigit(): await message.answer("⚠️ Vui lòng nhập số."); return
    uses = int(t); data = await state.get_data(); name = data["code_name"]; xu_val = data["code_xu"]; await state.clear()
    
    ex = await db_session.execute(select(Giftcode).where(Giftcode.code == name))
    if ex.scalar_one_or_none(): await message.answer("❌ Mã Code này đã tồn tại!"); return
    
    db_session.add(Giftcode(code=name, xu=xu_val, max_uses=uses))
    await db_session.commit()
    await message.answer(f"✅ Đã tạo Giftcode thành công!\n🎫 Mã: <b>{name}</b>\n🎁 Phần thưởng: {xu_val:,} xu\n🔢 Giới hạn: {uses} lượt", parse_mode="HTML")

@router.message(lambda m: m.text == "🎫 Danh Sách Code")
@admin_only
async def admin_list_codes(message: Message, is_admin: bool, db_session):
    r = await db_session.execute(select(Giftcode))
    lst = r.scalars().all()
    if not lst: await message.answer("📭 Hệ thống chưa có mã quà tặng nào."); return
    txt = "📋 <b>DANH SÁCH GIFTCODE HỆ THỐNG</b>\n──────────────\n"
    for c in lst:
        txt += f"• <code>{c.code}</code> — Thưởng {c.xu:,} xu — Còn lại: ({c.max_uses - c.used_count}/{c.max_uses}) lượt\n"
    await message.answer(txt, parse_mode="HTML")

@router.message(lambda m: m.text == "📷 Đổi QR")
@admin_only
async def admin_change_qr_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("📷 Vui lòng gửi ảnh mã QR nạp tiền mới lên đây:")  
    await state.set_state(AdminStates.waiting_qr)  

@router.message(AdminStates.waiting_qr, F.photo)
async def admin_receive_qr(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]; file = await bot.get_file(photo.file_id); raw = await bot.download_file(file.file_path)  
    await save_qr_image(raw.read())  
    await state.clear()  
    await message.answer("✅ Ảnh QR nạp tiền đã cập nhật thành công!")  

@router.message(lambda m: m.text == "📥 Bill Chờ")
@admin_only
async def admin_pending_bills(message: Message, is_admin: bool, db_session):
    deposits = await get_pending_deposits(db_session)  
    if not deposits: await message.answer("✅ Không có yêu cầu nạp tiền nào đang xếp hàng."); return  
    lines = [f"📥 <b>Yêu Cầu Chờ Duyệt ({len(deposits)})</b>\n"]  
    for d in deposits:
        uname = f"@{d.user.username}" if d.user and d.user.username else "N/A"  
        name = d.user.fullname if d.user else "N/A"  
        created = d.created_at.strftime("%d/%m/%Y %H:%M") if d.created_at else "N/A"  
        lines.append(f"🧾 ID #{d.id} — {name} ({uname})\n   💵 {d.amount:,} VNĐ — {created}")  
    await message.answer("\n".join(lines), parse_mode="HTML")  

@router.message(lambda m: m.text == "📢 Broadcast")
@admin_only
async def admin_broadcast_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("📢 Nhập nội dung tin nhắn bạn muốn gửi cho toàn bộ người chơi:")  
    await state.set_state(AdminStates.waiting_broadcast_text)  

@router.message(AdminStates.waiting_broadcast_text)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot, db_session):
    text = message.text or ""; await state.clear()  
    if not text: await message.answer("⚠️ Nội dung trống."); return  
    users = await get_all_users(db_session)  
    sent = failed = 0  
    for u in users:
        if u.is_banned: continue  
        try: await bot.send_message(u.telegram_id, text, parse_mode="HTML"); sent += 1  
        except Exception: failed += 1  
    await message.answer(f"📢 <b>Gửi Broadcast Hoàn Tất</b>\n\n✅ Thành công: <b>{sent}</b>\n❌ Thất bại: <b>{failed}</b>", parse_mode="HTML")  

@router.message(lambda m: m.text == "🚫 Ban User")
@admin_only
async def admin_ban_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("🚫 Nhập Telegram ID người cần cấm sử dụng bot:")  
    await state.set_state(AdminStates.waiting_ban_id)  

@router.message(AdminStates.waiting_ban_id)
async def admin_ban_execute(message: Message, state: FSMContext, db_session):
    t = (message.text or "").strip(); await state.clear()  
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ ID sai định dạng."); return  
    ok = await ban_user(db_session, int(t))  
    await message.answer(f"✅ Đã ban ID <code>{t}</code>." if ok else f"❌ Không thấy ID <code>{t}</code>", parse_mode="HTML")  

@router.message(lambda m: m.text == "✅ Unban User")
@admin_only
async def admin_unban_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("✅ Nhập Telegram ID cần mở khóa ban:")  
    await state.set_state(AdminStates.waiting_unban_id)  

@router.message(AdminStates.waiting_unban_id)
async def admin_unban_execute(message: Message, state: FSMContext, db_session):
    t = (message.text or "").strip(); await state.clear()  
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ ID sai."); return  
    ok = await unban_user(db_session, int(t))  
    await message.answer(f"✅ Đã gỡ ban ID <code>{t}</code>." if ok else f"❌ Không thấy ID <code>{t}</code>", parse_mode="HTML")  

@router.message(lambda m: m.text == "🗑 Xóa Account")
@admin_only
async def admin_delete_acc_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("🗑 Nhập tên tài khoản game (username) cần xoá khỏi kho:")  
    await state.set_state(AdminStates.waiting_delete_username)  

@router.message(AdminStates.waiting_delete_username)
async def admin_delete_acc_execute(message: Message, state: FSMContext, db_session):
    uname = (message.text or "").strip(); await state.clear()  
    ok = await delete_account_by_username(db_session, uname)  
    await message.answer(f"✅ Đã xóa acc <code>{uname}</code> khỏi hệ thống." if ok else f"❌ Không thấy acc có tên <code>{uname}</code>", parse_mode="HTML")  

@router.message(lambda m: m.text == "📤 Export Chưa Bán")
@admin_only
async def admin_export_unsold(message: Message, is_admin: bool, db_session):
    accounts = await get_unsold_accounts(db_session)  
    if not accounts: await message.answer(" Kho trống rỗng."); return  
    lines = [f"{a.username}|{a.password}" for a in accounts]  
    fp = await save_export_file(lines, "unsold")  
    await message.answer_document(FSInputFile(fp), caption=f"📤 Acc Chưa Bán\n📊 Số lượng: <b>{len(lines)}</b> acc", parse_mode="HTML")  

@router.message(lambda m: m.text == "📤 Export Đã Bán")
@admin_only
async def admin_export_sold(message: Message, is_admin: bool, db_session):
    accounts = await get_sold_accounts(db_session)  
    if not accounts: await message.answer(" Chưa bán được đơn nào."); return  
    lines = [f"{a.username}|{a.password}" for a in accounts]  
    fp = await save_export_file(lines, "sold")  
    await message.answer_document(FSInputFile(fp), caption=f"📤 Acc Đã Bán\n📊 Số lượng: <b>{len(lines)}</b> acc", parse_mode="HTML")  

# ── Web Server Mồi Chống Sleep Trên Render ────────────────────────────────────
async def handle_web(request):
    return web.Response(text="Bot đang vận hành xanh chín ổn định 24/7!")  

async def start_web_server():
    app = web.Application()  
    app.router.add_get("/", handle_web)  
    runner = web.AppRunner(app)  
    await runner.setup()  
    port = int(os.environ.get("PORT", 8080))  
    site = web.TCPSite(runner, "0.0.0.0", port)  
    await site.start()  
    logger.info(f"✅ Web Server Keep-Alive đang kích hoạt tại Port: {port}")

# ── Tiến Trình Khởi Chạy ──────────────────────────────────────────────────────
async def main():
    await init_db()  
    await start_web_server()  

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))  
    dp = Dispatcher(storage=MemoryStorage())  
    dp.message.middleware(AuthMiddleware())  
    dp.callback_query.middleware(AuthMiddleware())  
    dp.include_router(router)  

    logger.info("🤖 Bot Hợp Nhất Đã Sẵn Sàng Trực Tuyến!")
    try: await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())  
    finally: await bot.session.close()  

if __name__ == "__main__":
    asyncio.run(main())  
