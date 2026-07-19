# ═══════════════════════════════════════════════════════════════
#  BOT HỢP NHẤT: SHOP LIÊN QUÂN & TÀI XỈU GIẢI TRÍ (ASYNC)
#  Cài thư viện: pip install aiogram==3.13.1 sqlalchemy==2.0.36 aiosqlite==0.20.0 aiofiles==24.1.0 aiohttp
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = "8374524579:AAE2pvVgQqOFnEN2hnhhfRUyopi1B8Dhxcc"  #[span_5](start_span)[span_5](end_span)
ADMIN_IDS = [7936179657]  # ID Telegram Admin[span_6](start_span)[span_6](end_span)

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
from aiohttp import web  #[span_7](start_span)[span_7](end_span)
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

# ── Cấu hình Shop & Tài Xỉu ───────────────────────────────────────────────────
ACCOUNT_PRICE = 200  # VNĐ mỗi acc[span_8](start_span)[span_8](end_span)
MIN_ORDER_QTY = 50  # Số lượng tối thiểu[span_9](start_span)[span_9](end_span)
CHECKER_LINK = "t.me/tretrauchecker_bot?start=_tgr_8UulJtkyZjE1"  #[span_10](start_span)[span_10](end_span)
XU_DIEMDANH = 50  # Số xu nhận được khi điểm danh[span_11](start_span)[span_11](end_span)
THUONG_REF_XU = 5000  # Thưởng mời bạn bè chơi bot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  #[span_12](start_span)[span_12](end_span)
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")  #[span_13](start_span)[span_13](end_span)
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")  #[span_14](start_span)[span_14](end_span)
LOGS_DIR = os.path.join(BASE_DIR, "logs")  #[span_15](start_span)[span_15](end_span)
QR_IMAGE_PATH = os.path.join(UPLOADS_DIR, "qr_current.jpg")  #[span_16](start_span)[span_16](end_span)
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'database.sqlite')}"  #[span_17](start_span)[span_17](end_span)

MENU_BUTTONS = {
    "🏠 Trang Chủ", "🛒 Mua Acc", "💳 Nạp Tiền", "👤 Tài Khoản", "📦 Đơn Hàng", "☎ Hỗ Trợ",
    "🎲 Chơi Tài Xỉu", "🎁 Điểm Danh", "🔗 Giới Thiệu", "🏆 Top Đại Gia", "🎁 Nhập Mã",
    "📊 Dashboard", "📥 Import TXT", "📦 Xem Kho", "📊 Thống Kê", "💰 Cộng Tiền", "💸 Trừ Tiền",
    "🪙 Cộng Xu", "🪙 Trừ Xu", "📷 Đổi QR", "📥 Bill Chờ", "📢 Broadcast", "🚫 Ban User", 
    "✅ Unban User", "🗑 Xóa Account", "📤 Export Chưa Bán", "📤 Export Đã Bán", "🔙 Menu Chính",
    "🎫 Tạo Code", "🎫 Danh Sách Code"
}  #[span_18](start_span)[span_18](end_span)

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOGS_DIR, exist_ok=True)  #[span_19](start_span)[span_19](end_span)
os.makedirs(UPLOADS_DIR, exist_ok=True)  #[span_20](start_span)[span_20](end_span)
os.makedirs(EXPORTS_DIR, exist_ok=True)  #[span_21](start_span)[span_21](end_span)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOGS_DIR, "bot.log"), encoding="utf-8"),
    ],
)  #[span_22](start_span)[span_22](end_span)
logger = logging.getLogger(__name__)  #[span_23](start_span)[span_23](end_span)

# ── Database ──────────────────────────────────────────────────────────────────
engine = create_async_engine(DATABASE_URL, echo=False)  #[span_24](start_span)[span_24](end_span)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  #[span_25](start_span)[span_25](end_span)

class Base(DeclarativeBase):  #[span_26](start_span)[span_26](end_span)
    pass

class AccountStatus(str, enum.Enum):  #[span_27](start_span)[span_27](end_span)
    available = "available"
    sold = "sold"

class OrderStatus(str, enum.Enum):  #[span_28](start_span)[span_28](end_span)
    completed = "completed"
    cancelled = "cancelled"

class DepositStatus(str, enum.Enum):  #[span_29](start_span)[span_29](end_span)
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

# ── Models ────────────────────────────────────────────────────────────────────
class User(Base):  #[span_30](start_span)[span_30](end_span)
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  #[span_31](start_span)[span_31](end_span)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)  #[span_32](start_span)[span_32](end_span)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)  #[span_33](start_span)[span_33](end_span)
    fullname: Mapped[str] = mapped_column(String(255), nullable=False, default="")  #[span_34](start_span)[span_34](end_span)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Ví VNĐ mua acc[span_35](start_span)[span_35](end_span)
    xu: Mapped[int] = mapped_column(Integer, nullable=False, default=100)  # Ví Xu tài xỉu[span_36](start_span)[span_36](end_span)
    last_diemdanh: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # Chống spam điểm danh
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # ID người mời
    total_ref: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Tổng số người đã mời
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  #[span_37](start_span)[span_37](end_span)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  #[span_38](start_span)[span_38](end_span)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())  #[span_39](start_span)[span_39](end_span)
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")  #[span_40](start_span)[span_40](end_span)
    deposits: Mapped[list["Deposit"]] = relationship("Deposit", back_populates="user")  #[span_41](start_span)[span_41](end_span)

class Account(Base):  #[span_42](start_span)[span_42](end_span)
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  #[span_43](start_span)[span_43](end_span)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)  #[span_44](start_span)[span_44](end_span)
    password: Mapped[str] = mapped_column(String(255), nullable=False)  #[span_45](start_span)[span_45](end_span)
    status: Mapped[AccountStatus] = mapped_column(Enum(AccountStatus), nullable=False, default=AccountStatus.available)  #[span_46](start_span)[span_46](end_span)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)  #[span_47](start_span)[span_47](end_span)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())  #[span_48](start_span)[span_48](end_span)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  #[span_49](start_span)[span_49](end_span)
    order: Mapped["Order|None"] = relationship("Order", back_populates="accounts")  #[span_50](start_span)[span_50](end_span)

class Order(Base):  #[span_51](start_span)[span_51](end_span)
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  #[span_52](start_span)[span_52](end_span)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)  #[span_53](start_span)[span_53](end_span)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  #[span_54](start_span)[span_54](end_span)
    price: Mapped[int] = mapped_column(Integer, nullable=False)  #[span_55](start_span)[span_55](end_span)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False, default=OrderStatus.completed)  #[span_56](start_span)[span_56](end_span)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  #[span_57](start_span)[span_57](end_span)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())  #[span_58](start_span)[span_58](end_span)
    user: Mapped["User"] = relationship("User", back_populates="orders")  #[span_59](start_span)[span_59](end_span)
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="order")  #[span_60](start_span)[span_60](end_span)

class Deposit(Base):  #[span_61](start_span)[span_61](end_span)
    __tablename__ = "deposits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  #[span_62](start_span)[span_62](end_span)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)  #[span_63](start_span)[span_63](end_span)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  #[span_64](start_span)[span_64](end_span)
    bill_image: Mapped[str | None] = mapped_column(String(512), nullable=True)  #[span_65](start_span)[span_65](end_span)
    status: Mapped[DepositStatus] = mapped_column(Enum(DepositStatus), nullable=False, default=DepositStatus.pending)  #[span_66](start_span)[span_66](end_span)
    admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  #[span_67](start_span)[span_67](end_span)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())  #[span_68](start_span)[span_68](end_span)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  #[span_69](start_span)[span_69](end_span)
    user: Mapped["User"] = relationship("User", back_populates="deposits")  #[span_70](start_span)[span_70](end_span)

class Giftcode(Base):
    __tablename__ = "giftcodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    xu: Mapped[int] = mapped_column(Integer, nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_by: Mapped[str | None] = mapped_column(Text, nullable=True, default="") # Chuỗi ID người dùng dạng cách nhau dấu phẩy

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")  #[span_71](start_span)[span_71](end_span)

# ── Services ──────────────────────────────────────────────────────────────────
async def get_or_create_user(session, telegram_id, username, fullname, is_admin=False):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))  #[span_72](start_span)[span_72](end_span)
    user = result.scalar_one_or_none()  #[span_73](start_span)[span_73](end_span)
    if user is None:
        user = User(telegram_id=telegram_id, username=username, fullname=fullname, is_admin=is_admin)  #[span_74](start_span)[span_74](end_span)
        session.add(user)  #[span_75](start_span)[span_75](end_span)
        await session.commit()  #[span_76](start_span)[span_76](end_span)
        await session.refresh(user)  #[span_77](start_span)[span_77](end_span)
    else:
        changed = False
        if user.username != username: user.username = username; changed = True  #[span_78](start_span)[span_78](end_span)
        if user.fullname != fullname: user.fullname = fullname; changed = True  #[span_79](start_span)[span_79](end_span)
        if changed:
            await session.commit()  #[span_80](start_span)[span_80](end_span)
            await session.refresh(user)  #[span_81](start_span)[span_81](end_span)
    return user

async def get_user_by_telegram_id(session, telegram_id):
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))  #[span_82](start_span)[span_82](end_span)
    return r.scalar_one_or_none()  #[span_83](start_span)[span_83](end_span)

async def get_user_by_id(session, user_id):
    r = await session.execute(select(User).where(User.id == user_id))  #[span_84](start_span)[span_84](end_span)
    return r.scalar_one_or_none()  #[span_85](start_span)[span_85](end_span)

async def add_balance(session, user_id, amount):
    user = await get_user_by_id(session, user_id)  #[span_86](start_span)[span_86](end_span)
    if user is None: return None
    user.balance += amount  #[span_87](start_span)[span_87](end_span)
    await session.commit()  #[span_88](start_span)[span_88](end_span)
    await session.refresh(user)  #[span_89](start_span)[span_89](end_span)
    return user

async def adjust_balance_by_telegram_id(session, telegram_id, amount):
    user = await get_user_by_telegram_id(session, telegram_id)  #[span_90](start_span)[span_90](end_span)
    if user is None: return None
    user.balance += amount  #[span_91](start_span)[span_91](end_span)
    if user.balance < 0: user.balance = 0  #[span_92](start_span)[span_92](end_span)
    await session.commit()  #[span_93](start_span)[span_93](end_span)
    await session.refresh(user)  #[span_94](start_span)[span_94](end_span)
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
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))  #[span_95](start_span)[span_95](end_span)
    user = r.scalar_one_or_none()  #[span_96](start_span)[span_96](end_span)
    if user is None: return False
    user.is_banned = True  #[span_97](start_span)[span_97](end_span)
    await session.commit()  #[span_98](start_span)[span_98](end_span)
    return True

async def unban_user(session, telegram_id):
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))  #[span_99](start_span)[span_99](end_span)
    user = r.scalar_one_or_none()  #[span_100](start_span)[span_100](end_span)
    if user is None: return False
    user.is_banned = False  #[span_101](start_span)[span_101](end_span)
    await session.commit()  #[span_102](start_span)[span_102](end_span)
    return True

async def get_all_users(session):
    r = await session.execute(select(User)); return list(r.scalars().all())  #[span_103](start_span)[span_103](end_span)

async def get_available_count(session):
    r = await session.execute(select(func.count()).where(Account.status == AccountStatus.available)); return r.scalar_one()  #[span_104](start_span)[span_104](end_span)

async def get_sold_count(session):
    r = await session.execute(select(func.count()).where(Account.status == AccountStatus.sold)); return r.scalar_one()  #[span_105](start_span)[span_105](end_span)

async def get_total_count(session):
    r = await session.execute(select(func.count()).select_from(Account)); return r.scalar_one()  #[span_106](start_span)[span_106](end_span)

async def pick_random_accounts(session, quantity):
    r = await session.execute(select(Account).where(Account.status == AccountStatus.available).with_for_update().limit(quantity))
    return list(r.scalars().all())

async def mark_accounts_sold(session, accounts, order_id):
    now = datetime.utcnow()  #[span_107](start_span)[span_107](end_span)
    for acc in accounts:
        acc.status = AccountStatus.sold  #[span_108](start_span)[span_108](end_span)
        acc.order_id = order_id  #[span_109](start_span)[span_109](end_span)
        acc.sold_at = now  #[span_110](start_span)[span_110](end_span)
    await session.commit()  #[span_111](start_span)[span_111](end_span)

async def import_accounts(session, lines):
    stats = {"total": 0, "imported": 0, "duplicates": 0, "invalid": 0}  #[span_112](start_span)[span_112](end_span)
    
    # Tối ưu hóa: Lấy set username hiện tại tránh vòng lặp SELECT nghẽn
    r_all = await session.execute(select(Account.username))
    existing_unames = set(r_all.scalars().all())

    for raw in lines:
        line = raw.strip()  #[span_113](start_span)[span_113](end_span)
        if not line: continue  #[span_114](start_span)[span_114](end_span)
        stats["total"] += 1  #[span_115](start_span)[span_115](end_span)
        if "|" in line: parts = line.split("|", 1)  #[span_116](start_span)[span_116](end_span)
        elif ":" in line: parts = line.split(":", 1)  #[span_117](start_span)[span_117](end_span)
        else: stats["invalid"] += 1; continue  #[span_118](start_span)[span_118](end_span)
        uname, pwd = parts[0].strip(), parts[1].strip()  #[span_119](start_span)[span_119](end_span)
        if not uname or not pwd: stats["invalid"] += 1; continue  #[span_120](start_span)[span_120](end_span)
        if uname in existing_unames: stats["duplicates"] += 1; continue  #[span_121](start_span)[span_121](end_span)
        session.add(Account(username=uname, password=pwd, status=AccountStatus.available))  #[span_122](start_span)[span_122](end_span)
        existing_unames.add(uname)
        stats["imported"] += 1  #[span_123](start_span)[span_123](end_span)
    await session.commit()  #[span_124](start_span)[span_124](end_span)
    return stats

async def get_unsold_accounts(session):
    r = await session.execute(select(Account).where(Account.status == AccountStatus.available)); return list(r.scalars().all())  #[span_125](start_span)[span_125](end_span)

async def get_sold_accounts(session):
    r = await session.execute(select(Account).where(Account.status == AccountStatus.sold)); return list(r.scalars().all())  #[span_126](start_span)[span_126](end_span)

async def delete_account_by_username(session, username):
    r = await session.execute(select(Account).where(Account.username == username))  #[span_127](start_span)[span_127](end_span)
    acc = r.scalar_one_or_none()  #[span_128](start_span)[span_128](end_span)
    if acc is None: return False
    await session.delete(acc)  #[span_129](start_span)[span_129](end_span)
    await session.commit()  #[span_130](start_span)[span_130](end_span)
    return True

async def create_order(session, user_id, quantity, price, file_name):
    order = Order(user_id=user_id, quantity=quantity, price=price, status=OrderStatus.completed, file_name=file_name)  #[span_131](start_span)[span_131](end_span)
    session.add(order)  #[span_132](start_span)[span_132](end_span)
    await session.flush()  #[span_133](start_span)[span_133](end_span)
    return order

async def get_user_orders(session, user_id, limit=20):
    r = await session.execute(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit))  #[span_134](start_span)[span_134](end_span)
    return list(r.scalars().all())  #[span_135](start_span)[span_135](end_span)

async def get_all_orders(session, limit=50):
    r = await session.execute(select(Order).order_by(Order.created_at.desc()).limit(limit))  #[span_136](start_span)[span_136](end_span)
    return list(r.scalars().all())  #[span_137](start_span)[span_137](end_span)

async def create_deposit(session, user_id, amount, bill_image=None):
    dep = Deposit(user_id=user_id, amount=amount, bill_image=bill_image, status=DepositStatus.pending)  #[span_138](start_span)[span_138](end_span)
    session.add(dep)  #[span_139](start_span)[span_139](end_span)
    await session.commit()  #[span_140](start_span)[span_140](end_span)
    await session.refresh(dep)  #[span_141](start_span)[span_141](end_span)
    return dep

async def get_deposit_by_id(session, deposit_id):
    r = await session.execute(select(Deposit).options(selectinload(Deposit.user)).where(Deposit.id == deposit_id))  #[span_142](start_span)[span_142](end_span)
    return r.scalar_one_or_none()  #[span_143](start_span)[span_143](end_span)

async def approve_deposit(session, deposit_id, admin_tg_id):
    dep = await get_deposit_by_id(session, deposit_id)  #[span_144](start_span)[span_144](end_span)
    if dep is None or dep.status != DepositStatus.pending: return None  #[span_145](start_span)[span_145](end_span)
    dep.status = DepositStatus.approved  #[span_146](start_span)[span_146](end_span)
    dep.admin_id = admin_tg_id  #[span_147](start_span)[span_147](end_span)
    dep.approved_at = datetime.utcnow()  #[span_148](start_span)[span_148](end_span)
    await session.commit()  #[span_149](start_span)[span_149](end_span)
    await session.refresh(dep)  #[span_150](start_span)[span_150](end_span)
    return dep

async def reject_deposit(session, deposit_id, admin_tg_id):
    dep = await get_deposit_by_id(session, deposit_id)  #[span_151](start_span)[span_151](end_span)
    if dep is None or dep.status != DepositStatus.pending: return None  #[span_152](start_span)[span_152](end_span)
    dep.status = DepositStatus.rejected  #[span_153](start_span)[span_153](end_span)
    dep.admin_id = admin_tg_id  #[span_154](start_span)[span_154](end_span)
    dep.approved_at = datetime.utcnow()  #[span_155](start_span)[span_155](end_span)
    await session.commit()  #[span_156](start_span)[span_156](end_span)
    await session.refresh(dep)  #[span_157](start_span)[span_157](end_span)
    return dep

async def get_pending_deposits(session):
    r = await session.execute(select(Deposit).options(selectinload(Deposit.user)).where(Deposit.status == DepositStatus.pending).order_by(Deposit.created_at.asc()))  #[span_158](start_span)[span_158](end_span)
    return list(r.scalars().all())  #[span_159](start_span)[span_159](end_span)

# ── File utils ────────────────────────────────────────────────────────────────
async def save_export_file(lines, prefix):
    os.makedirs(EXPORTS_DIR, exist_ok=True)  #[span_160](start_span)[span_160](end_span)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")  #[span_161](start_span)[span_161](end_span)
    fp = os.path.join(EXPORTS_DIR, f"{prefix}_{ts}.txt")  #[span_162](start_span)[span_162](end_span)
    async with aiofiles.open(fp, "w", encoding="utf-8") as f:  #[span_163](start_span)[span_163](end_span)
        await f.write("\n".join(lines))  #[span_164](start_span)[span_164](end_span)
    return fp  #[span_165](start_span)[span_165](end_span)

async def save_order_file(accounts_data, order_id):
    os.makedirs(EXPORTS_DIR, exist_ok=True)  #[span_166](start_span)[span_166](end_span)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")  #[span_167](start_span)[span_167](end_span)
    filename = f"order_{order_id}_{ts}.txt"  #[span_168](start_span)[span_168](end_span)
    fp = os.path.join(EXPORTS_DIR, filename)  #[span_169](start_span)[span_169](end_span)
    async with aiofiles.open(fp, "w", encoding="utf-8") as f:  #[span_170](start_span)[span_170](end_span)
        await f.write("\n".join(f"{u}|{p}" for u, p in accounts_data))  #[span_171](start_span)[span_171](end_span)
    return fp, filename  #[span_172](start_span)[span_172](end_span)

async def save_bill_image(file_bytes, extension="jpg"):
    os.makedirs(UPLOADS_DIR, exist_ok=True)  #[span_173](start_span)[span_173](end_span)
    fp = os.path.join(UPLOADS_DIR, f"bill_{uuid.uuid4().hex}.{extension}")  #[span_174](start_span)[span_174](end_span)
    async with aiofiles.open(fp, "wb") as f:  #[span_175](start_span)[span_175](end_span)
        await f.write(file_bytes)  #[span_176](start_span)[span_176](end_span)
    return fp  #[span_177](start_span)[span_177](end_span)

async def save_qr_image(file_bytes):
    os.makedirs(UPLOADS_DIR, exist_ok=True)  #[span_178](start_span)[span_178](end_span)
    async with aiofiles.open(QR_IMAGE_PATH, "wb") as f:  #[span_179](start_span)[span_179](end_span)
        await f.write(file_bytes)  #[span_180](start_span)[span_180](end_span)
    return QR_IMAGE_PATH  #[span_181](start_span)[span_181](end_span)

def qr_exists():
    return os.path.isfile(QR_IMAGE_PATH)  #[span_182](start_span)[span_182](end_span)

# ── Keyboards ─────────────────────────────────────────────────────────────────
def main_menu_kb():
    b = ReplyKeyboardBuilder()  #[span_183](start_span)[span_183](end_span)
    b.row(KeyboardButton(text="🏠 Trang Chủ"), KeyboardButton(text="🛒 Mua Acc"))  #[span_184](start_span)[span_184](end_span)
    b.row(KeyboardButton(text="💳 Nạp Tiền"), KeyboardButton(text="👤 Tài Khoản"))  #[span_185](start_span)[span_185](end_span)
    b.row(KeyboardButton(text="🎲 Chơi Tài Xỉu"), KeyboardButton(text="🎁 Điểm Danh"))
    b.row(KeyboardButton(text="🔗 Giới Thiệu"), KeyboardButton(text="🏆 Top Đại Gia"))
    b.row(KeyboardButton(text="🎁 Nhập Mã"), KeyboardButton(text="📦 Đơn Hàng"))
    b.row(KeyboardButton(text="☎ Hỗ Trợ"))  #[span_186](start_span)[span_186](end_span)
    return b.as_markup(resize_keyboard=True)  #[span_187](start_span)[span_187](end_span)

def cancel_kb():
    b = ReplyKeyboardBuilder()  #[span_188](start_span)[span_188](end_span)
    b.row(KeyboardButton(text="❌ Hủy"))  #[span_189](start_span)[span_189](end_span)
    return b.as_markup(resize_keyboard=True)  #[span_190](start_span)[span_190](end_span)

def deposit_approval_kb(deposit_id):
    b = InlineKeyboardBuilder()  #[span_191](start_span)[span_191](end_span)
    b.row(
        InlineKeyboardButton(text="✅ DUYỆT", callback_data=f"approve_deposit:{deposit_id}"),  #[span_192](start_span)[span_192](end_span)
        InlineKeyboardButton(text="❌ TỪ CHỐI", callback_data=f"reject_deposit:{deposit_id}"),  #[span_193](start_span)[span_193](end_span)
    )
    return b.as_markup()  #[span_194](start_span)[span_194](end_span)

def tai_xiu_inline_kb():
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🔴 Tài  (11–18)", callback_data="tx:tai"),  #[span_195](start_span)[span_195](end_span)
        InlineKeyboardButton(text="🔵 Xỉu  (3–10)",  callback_data="tx:xiu"),  #[span_196](start_span)[span_196](end_span)
    )
    return b.as_markup()

def admin_menu_kb():
    b = ReplyKeyboardBuilder()  #[span_197](start_span)[span_197](end_span)
    b.row(KeyboardButton(text="📊 Dashboard"), KeyboardButton(text="📥 Import TXT"))  #[span_198](start_span)[span_198](end_span)
    b.row(KeyboardButton(text="📦 Xem Kho"), KeyboardButton(text="📊 Thống Kê"))  #[span_199](start_span)[span_199](end_span)
    b.row(KeyboardButton(text="💰 Cộng Tiền"), KeyboardButton(text="💸 Trừ Tiền"))  #[span_200](start_span)[span_200](end_span)
    b.row(KeyboardButton(text="🪙 Cộng Xu"), KeyboardButton(text="🪙 Trừ Xu"))
    b.row(KeyboardButton(text="🎫 Tạo Code"), KeyboardButton(text="🎫 Danh Sách Code"))
    b.row(KeyboardButton(text="📷 Đổi QR"), KeyboardButton(text="📥 Bill Chờ"))  #[span_201](start_span)[span_201](end_span)
    b.row(KeyboardButton(text="📢 Broadcast"), KeyboardButton(text="🚫 Ban User"))  #[span_202](start_span)[span_202](end_span)
    b.row(KeyboardButton(text="✅ Unban User"), KeyboardButton(text="🗑 Xóa Account"))  #[span_203](start_span)[span_203](end_span)
    b.row(KeyboardButton(text="📤 Export Chưa Bán"), KeyboardButton(text="📤 Export Đã Bán"))  #[span_204](start_span)[span_204](end_span)
    b.row(KeyboardButton(text="🔙 Menu Chính"))  #[span_205](start_span)[span_205](end_span)
    return b.as_markup(resize_keyboard=True)  #[span_206](start_span)[span_206](end_span)

# ── Middleware ────────────────────────────────────────────────────────────────
class AuthMiddleware(BaseMiddleware):  #[span_207](start_span)[span_207](end_span)
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")  #[span_208](start_span)[span_208](end_span)
        if user is None: return await handler(event, data)  #[span_209](start_span)[span_209](end_span)
        is_admin = user.id in ADMIN_IDS  #[span_210](start_span)[span_210](end_span)
        fullname = (user.full_name or "").strip() or user.username or str(user.id)  #[span_211](start_span)[span_211](end_span)
        async with AsyncSessionLocal() as session:  #[span_212](start_span)[span_212](end_span)
            db_user = await get_or_create_user(session, user.id, user.username, fullname, is_admin)  #[span_213](start_span)[span_213](end_span)
            if db_user.is_admin != is_admin:
                db_user.is_admin = is_admin
                await session.commit()  #[span_214](start_span)[span_214](end_span)
            data["db_user"] = db_user  #[span_215](start_span)[span_215](end_span)
            data["db_session"] = session  #[span_216](start_span)[span_216](end_span)
            data["is_admin"] = is_admin  #[span_217](start_span)[span_217](end_span)
            if db_user.is_banned and not is_admin:  #[span_218](start_span)[span_218](end_span)
                if isinstance(event, Message): await event.answer("🚫 Bạn đã bị cấm sử dụng bot.")  #[span_219](start_span)[span_219](end_span)
                return
            return await handler(event, data)  #[span_220](start_span)[span_220](end_span)

# ── States ────────────────────────────────────────────────────────────────────
class ShopState(StatesGroup):  #[span_221](start_span)[span_221](end_span)
    waiting_quantity = State()  #[span_222](start_span)[span_222](end_span)

class DepositState(StatesGroup):  #[span_223](start_span)[span_223](end_span)
    waiting_amount = State()  #[span_224](start_span)[span_224](end_span)
    waiting_bill = State()  #[span_225](start_span)[span_225](end_span)

class TaixiuState(StatesGroup):
    waiting_bet = State()

class CodeState(StatesGroup):
    waiting_code_input = State()

class AdminStates(StatesGroup):  #[span_226](start_span)[span_226](end_span)
    waiting_qr = State()  #[span_227](start_span)[span_227](end_span)
    waiting_import_file = State()  #[span_228](start_span)[span_228](end_span)
    waiting_add_balance_id = State()  #[span_229](start_span)[span_229](end_span)
    waiting_add_balance_amount = State()  #[span_230](start_span)[span_230](end_span)
    waiting_subtract_balance_id = State()  #[span_231](start_span)[span_231](end_span)
    waiting_subtract_balance_amount = State()  #[span_232](start_span)[span_232](end_span)
    waiting_add_xu_id = State()
    waiting_add_xu_amount = State()
    waiting_subtract_xu_id = State()
    waiting_subtract_xu_amount = State()
    waiting_create_code_name = State()
    waiting_create_code_xu = State()
    waiting_create_code_uses = State()
    waiting_ban_id = State()  #[span_233](start_span)[span_233](end_span)
    waiting_unban_id = State()  #[span_234](start_span)[span_234](end_span)
    waiting_delete_username = State()  #[span_235](start_span)[span_235](end_span)
    waiting_broadcast_text = State()  #[span_236](start_span)[span_236](end_span)

def admin_only(func):  #[span_237](start_span)[span_237](end_span)
    @functools.wraps(func)
    async def wrapper(message: Message, is_admin: bool, *args, **kwargs):
        if not is_admin:
            await message.answer("❌ Bạn không có quyền truy cập.")  #[span_238](start_span)[span_238](end_span)
            return
        return await func(message, is_admin=is_admin, *args, **kwargs)
    return wrapper  #[span_239](start_span)[span_239](end_span)

# ── Router ────────────────────────────────────────────────────────────────────
router = Router()  #[span_240](start_span)[span_240](end_span)

# ── /start & home ─────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, db_user: User, db_session, bot: Bot):
    await state.clear()  #[span_241](start_span)[span_241](end_span)
    
    # Xử lý hệ thống giới thiệu (Chỉ tài khoản mới tinh tạo dưới 15 giây)
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

    name = db_user.fullname or message.from_user.full_name or "bạn"  #[span_242](start_span)[span_242](end_span)
    available = await get_available_count(db_session)  #[span_243](start_span)[span_243](end_span)
    await message.answer(
        f"👋 Chào mừng <b>{name}</b> đến với Shop Liên Quân & Giải Trí!\n\n"  #[span_244](start_span)[span_244](end_span)
        f"🛒 Mua acc tự động, giá rẻ\n"  #[span_245](start_span)[span_245](end_span)
        f"💰 Số dư tiền: <b>{db_user.balance:,} VNĐ</b>\n"  #[span_246](start_span)[span_246](end_span)
        f"🎲 Ví giải trí: <b>{db_user.xu:,} xu</b>\n"
        f"📦 Kho còn: <b>{available:,} acc</b>\n\n"  #[span_247](start_span)[span_247](end_span)
        f"⚡ Cú pháp cược nhanh Tài Xỉu: <code>/tx [t/x] [xu]</code>\n"
        f"_(Ví dụ đặt Tài 50 xu: /tx t 50)_",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),  #[span_248](start_span)[span_248](end_span)
    )

@router.message(lambda m: m.text == "🏠 Trang Chủ")
async def home(message: Message, state: FSMContext, db_user: User, db_session):
    await state.clear()  #[span_249](start_span)[span_249](end_span)
    available = await get_available_count(db_session)  #[span_250](start_span)[span_250](end_span)
    name = db_user.fullname or message.from_user.full_name or "bạn"  #[span_251](start_span)[span_251](end_span)
    await message.answer(
        f"🏠 <b>Trang Chủ</b>\n\n"  #[span_252](start_span)[span_252](end_span)
        f"👋 Xin chào <b>{name}</b>!\n"  #[span_253](start_span)[span_253](end_span)
        f"💰 Số dư tiền: <b>{db_user.balance:,} VNĐ</b>\n"  #[span_254](start_span)[span_254](end_span)
        f"🎲 Ví giải trí: <b>{db_user.xu:,} xu</b>\n"
        f"📦 Kho còn: <b>{available:,} acc</b>",  #[span_255](start_span)[span_255](end_span)
        parse_mode="HTML",
        reply_markup=main_menu_kb(),  #[span_256](start_span)[span_256](end_span)
    )

@router.message(lambda m: m.text == "☎ Hỗ Trợ")
async def support(message: Message, state: FSMContext):
    await state.clear()  #[span_257](start_span)[span_257](end_span)
    await message.answer(
        "☎ <b>Hỗ Trợ Khách Hàng</b>\n\n"  #[span_258](start_span)[span_258](end_span)
        "Nếu gặp lỗi hoặc cần giải đáp, liên hệ Admin:\n"
        "👤 Admin: @lananh9719\n\n"  #[span_259](start_span)[span_259](end_span)
        "⏰ Hoạt động: 8:00 - 22:00 hàng ngày.",  #[span_260](start_span)[span_260](end_span)
        parse_mode="HTML",
    )

# ── Shop Liên Quân ────────────────────────────────────────────────────────────
@router.message(lambda m: m.text == "🛒 Mua Acc")
async def buy_acc_start(message: Message, state: FSMContext, db_session):
    await state.clear()  #[span_261](start_span)[span_261](end_span)
    available = await get_available_count(db_session)  #[span_262](start_span)[span_262](end_span)
    await message.answer(
        f"🛒 <b>Mua Acc Liên Quân</b>\n\n"  #[span_263](start_span)[span_263](end_span)
        f"💵 Giá bán: <b>{ACCOUNT_PRICE:,} VNĐ / acc</b>\n"  #[span_264](start_span)[span_264](end_span)
        f"📦 Kho còn: <b>{available:,} acc</b>\n"  #[span_265](start_span)[span_265](end_span)
        f"⚠️ Yêu cầu mua tối thiểu: <b>{MIN_ORDER_QTY} acc</b>\n\n"  #[span_266](start_span)[span_266](end_span)
        "Vui lòng nhập số lượng acc muốn mua:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),  #[span_267](start_span)[span_267](end_span)
    )
    await state.set_state(ShopState.waiting_quantity)  #[span_268](start_span)[span_268](end_span)

@router.message(ShopState.waiting_quantity, F.text == "❌ Hủy")
async def buy_cancel(message: Message, state: FSMContext):
    await state.clear()  #[span_269](start_span)[span_269](end_span)
    await message.answer("❌ Đã hủy giao dịch.", reply_markup=main_menu_kb())  #[span_270](start_span)[span_270](end_span)

@router.message(ShopState.waiting_quantity, ~F.text.in_(MENU_BUTTONS))
async def buy_acc_quantity(message: Message, state: FSMContext, db_user: User, db_session):
    text = message.text or ""
    if not text.isdigit():
        await message.answer("⚠️ Vui lòng nhập số nguyên hợp lệ.")  #[span_271](start_span)[span_271](end_span)
        return
    quantity = int(text)
    if quantity < MIN_ORDER_QTY:
        await message.answer(f"⚠️ Số lượng tối thiểu là <b>{MIN_ORDER_QTY} acc</b>.", parse_mode="HTML")  #[span_272](start_span)[span_272](end_span)
        return
    total_price = quantity * ACCOUNT_PRICE
    
    # Dùng Cơ chế Khóa Dòng .with_for_update() Chống Bug Trùng Đơn
    r_u = await db_session.execute(select(User).where(User.id == db_user.id).with_for_update())
    fresh_user = r_u.scalar_one_or_none()
    
    if fresh_user.balance < total_price:
        shortage = total_price - fresh_user.balance
        await message.answer(
            f"❌ <b>Số dư VNĐ không đủ!</b>\n\n"  #[span_273](start_span)[span_273](end_span)
            f"💰 Hiện có: <b>{fresh_user.balance:,} VNĐ</b>\n"  #[span_274](start_span)[span_274](end_span)
            f"💵 Cần thanh toán: <b>{total_price:,} VNĐ</b>\n"  #[span_275](start_span)[span_275](end_span)
            f"⚠️ Thiếu: <b>{shortage:,} VNĐ</b>\n\nVui lòng nạp thêm tiền.",  #[span_276](start_span)[span_276](end_span)
            parse_mode="HTML", reply_markup=main_menu_kb()  #[span_277](start_span)[span_277](end_span)
        )
        await state.clear()  #[span_278](start_span)[span_278](end_span)
        return
        
    available = await get_available_count(db_session)  #[span_279](start_span)[span_279](end_span)
    if available < quantity:
        await message.answer(f"❌ Kho không đủ hàng!\n📦 Kho hiện còn: <b>{available:,} acc</b>", parse_mode="HTML", reply_markup=main_menu_kb())  #[span_280](start_span)[span_280](end_span)
        await state.clear()  #[span_281](start_span)[span_281](end_span)
        return

    accounts = await pick_random_accounts(db_session, quantity)
    if len(accounts) < quantity:
        await message.answer("❌ Có lỗi xảy ra khi lấy tài khoản. Thử lại sau.", reply_markup=main_menu_kb())  #[span_282](start_span)[span_282](end_span)
        await state.clear()  #[span_283](start_span)[span_283](end_span)
        return

    order = await create_order(db_session, fresh_user.id, quantity, total_price, "")  #[span_284](start_span)[span_284](end_span)
    fresh_user.balance -= total_price
    await mark_accounts_sold(db_session, accounts, order.id)  #[span_285](start_span)[span_285](end_span)

    account_data = [(a.username, a.password) for a in accounts]
    filepath, filename = await save_order_file(account_data, order.id)  #[span_286](start_span)[span_286](end_span)
    order.file_name = filename  #[span_287](start_span)[span_287](end_span)
    await db_session.commit()  #[span_288](start_span)[span_288](end_span)
    await state.clear()  #[span_289](start_span)[span_289](end_span)

    await message.answer(
        f"✅ <b>Mua hàng thành công!</b>\n\n"  #[span_290](start_span)[span_290](end_span)
        f"📦 Số lượng: <b>{quantity} acc</b>\n"  #[span_291](start_span)[span_291](end_span)
        f"💵 Tổng tiền: <b>{total_price:,} VNĐ</b>\n"  #[span_292](start_span)[span_292](end_span)
        f"🧾 Mã đơn: <b>#{order.id}</b>\n\nĐang gửi file...",  #[span_293](start_span)[span_293](end_span)
        parse_mode="HTML", reply_markup=main_menu_kb()  #[span_294](start_span)[span_294](end_span)
    )
    await message.answer_document(FSInputFile(filepath, filename=filename), caption=f"📄 Đơn hàng #{order.id} — {quantity} acc")  #[span_295](start_span)[span_295](end_span)
    await message.answer(f"📌 Link check acc free:\n{CHECKER_LINK}")  #[span_296](start_span)[span_296](end_span)

# ── Tài khoản & Đơn hàng ─────────────────────────────────────────────────────
@router.message(lambda m: m.text == "👤 Tài Khoản")
async def my_account(message: Message, state: FSMContext, db_user: User, db_session):
    await state.clear()  #[span_297](start_span)[span_297](end_span)
    joined = db_user.created_at.strftime("%d/%m/%Y") if db_user.created_at else "N/A"  #[span_298](start_span)[span_298](end_span)
    orders = await get_user_orders(db_session, db_user.id, limit=9999)  #[span_299](start_span)[span_299](end_span)
    uname = f"@{db_user.username}" if db_user.username else "Không có"  #[span_300](start_span)[span_300](end_span)
    await message.answer(
        f"👤 <b>Thông Tin Tài Khoản</b>\n\n"  #[span_301](start_span)[span_301](end_span)
        f"🆔 ID Telegram: <code>{db_user.telegram_id}</code>\n"  #[span_302](start_span)[span_302](end_span)
        f"👤 Username: {uname}\n"  #[span_303](start_span)[span_303](end_span)
        f"📛 Tên: {db_user.fullname}\n\n"  #[span_304](start_span)[span_304](end_span)
        f"💰 Số dư VNĐ: <b>{db_user.balance:,} VNĐ</b>\n"  #[span_305](start_span)[span_305](end_span)
        f"🎲 Số dư Xu: <b>{db_user.xu:,} xu</b>\n"
        f"👥 Đã giới thiệu: <b>{db_user.total_ref} người</b>\n"
        f"📦 Đơn đã mua: <b>{len(orders)}</b>\n"  #[span_306](start_span)[span_306](end_span)
        f"📅 Tham gia ngày: {joined}",  #[span_307](start_span)[span_307](end_span)
        parse_mode="HTML",
    )

@router.message(lambda m: m.text == "📦 Đơn Hàng")
async def my_orders(message: Message, state: FSMContext, db_user: User, db_session):
    await state.clear()  #[span_308](start_span)[span_308](end_span)
    orders = await get_user_orders(db_session, db_user.id, limit=20)  #[span_309](start_span)[span_309](end_span)
    if not orders:
        await message.answer("📦 Bạn chưa mua đơn hàng nào.")  #[span_310](start_span)[span_310](end_span)
        return
    lines = ["📦 <b>20 Đơn Hàng Gần Nhất</b>\n"]  #[span_311](start_span)[span_311](end_span)
    for i, o in enumerate(orders, 1):
        created = o.created_at.strftime("%d/%m/%Y %H:%M") if o.created_at else "N/A"  #[span_312](start_span)[span_312](end_span)
        lines.append(f"{i}. Đơn #{o.id} — {o.quantity} acc — {o.price:,} VNĐ — {created}")  #[span_313](start_span)[span_313](end_span)
    await message.answer("\n".join(lines), parse_mode="HTML")  #[span_314](start_span)[span_314](end_span)

# ── Nạp tiền VNĐ ──────────────────────────────────────────────────────────────
@router.message(lambda m: m.text == "💳 Nạp Tiền")
async def deposit_start(message: Message, state: FSMContext):
    await state.clear()  #[span_315](start_span)[span_315](end_span)
    if not qr_exists():
        await message.answer("⚠️ Hệ thống nạp tiền đang bảo trì (Thiếu QR). Vui lòng liên hệ Admin.")  #[span_316](start_span)[span_316](end_span)
        return
    await message.answer_photo(
        FSInputFile(QR_IMAGE_PATH),  #[span_317](start_span)[span_317](end_span)
        caption="💳 <b>Nạp Tiền Qua QR</b>\n\nQuét mã QR để chuyển khoản tiền thật.\n\nNhập số tiền muốn nạp (VNĐ):",
        parse_mode="HTML", reply_markup=cancel_kb()  #[span_318](start_span)[span_318](end_span)
    )
    await state.set_state(DepositState.waiting_amount)  #[span_319](start_span)[span_319](end_span)

@router.message(DepositState.waiting_amount, F.text == "❌ Hủy")
async def deposit_cancel_amount(message: Message, state: FSMContext):
    await state.clear()  #[span_320](start_span)[span_320](end_span)
    await message.answer("❌ Đã hủy nạp tiền.", reply_markup=main_menu_kb())  #[span_321](start_span)[span_321](end_span)

@router.message(DepositState.waiting_amount, ~F.text.in_(MENU_BUTTONS))
async def deposit_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", "").replace(".", "").strip()  #[span_322](start_span)[span_322](end_span)
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ.")  #[span_323](start_span)[span_323](end_span)
        return
    amount = int(text)
    await state.update_data(amount=amount)  #[span_324](start_span)[span_324](end_span)
    await message.answer(f"💵 Số tiền nạp: <b>{amount:,} VNĐ</b>\n\n📷 Vui lòng gửi ảnh chụp màn hình bill chuyển khoản:", parse_mode="HTML", reply_markup=cancel_kb())  #[span_325](start_span)[span_325](end_span)
    await state.set_state(DepositState.waiting_bill)  #[span_326](start_span)[span_326](end_span)

@router.message(DepositState.waiting_bill, F.text == "❌ Hủy")
async def deposit_cancel_bill(message: Message, state: FSMContext):
    await state.clear()  #[span_327](start_span)[span_327](end_span)
    await message.answer("❌ Đã hủy nạp tiền.", reply_markup=main_menu_kb())  #[span_328](start_span)[span_328](end_span)

@router.message(DepositState.waiting_bill, F.photo)
async def deposit_bill_photo(message: Message, state: FSMContext, bot: Bot, db_user: User, db_session):
    data = await state.get_data()  #[span_329](start_span)[span_329](end_span)
    amount = data.get("amount", 0)  #[span_330](start_span)[span_330](end_span)
    await state.clear()  #[span_331](start_span)[span_331](end_span)
    photo = message.photo[-1]  #[span_332](start_span)[span_332](end_span)
    file = await bot.get_file(photo.file_id)  #[span_333](start_span)[span_333](end_span)
    file_bytes = await bot.download_file(file.file_path)  #[span_334](start_span)[span_334](end_span)
    bill_path = await save_bill_image(file_bytes.read(), "jpg")  #[span_335](start_span)[span_335](end_span)
    
    deposit = await create_deposit(db_session, db_user.id, amount, bill_path)  #[span_336](start_span)[span_336](end_span)
    uname = f"@{db_user.username}" if db_user.username else "Không có"  #[span_337](start_span)[span_337](end_span)
    now_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S")  #[span_338](start_span)[span_338](end_span)
    caption = (
        f"💳 <b>YÊU CẦU NẠP TIỀN</b>\n\n"  #[span_339](start_span)[span_339](end_span)
        f"🆔 ID Telegram: <code>{db_user.telegram_id}</code>\n"  #[span_340](start_span)[span_340](end_span)
        f"👤 Username: {uname}\n"  #[span_341](start_span)[span_341](end_span)
        f"📛 Tên: {db_user.fullname}\n"  #[span_342](start_span)[span_342](end_span)
        f"💵 Số tiền: <b>{amount:,} VNĐ</b>\n"  #[span_343](start_span)[span_343](end_span)
        f"🕐 Thời gian: {now_str}\n"  #[span_344](start_span)[span_344](end_span)
        f"🧾 Mã Bill nạp: #{deposit.id}"  #[span_345](start_span)[span_345](end_span)
    )
    kb = deposit_approval_kb(deposit.id)  #[span_346](start_span)[span_346](end_span)
    for admin_id in ADMIN_IDS:
        try:
            await message.forward(admin_id)  #[span_347](start_span)[span_347](end_span)
            await bot.send_message(admin_id, caption, parse_mode="HTML", reply_markup=kb)  #[span_348](start_span)[span_348](end_span)
        except Exception: pass
    await message.answer("✅ <b>Đã gửi bill cho Admin!</b>\n\n Vui lòng đợi trong giây lát hệ thống đang duyệt.", parse_mode="HTML", reply_markup=main_menu_kb())  #[span_349](start_span)[span_349](end_span)

@router.message(DepositState.waiting_bill, ~F.text.in_(MENU_BUTTONS))
async def deposit_bill_invalid(message: Message):
    await message.answer("⚠️ Vui lòng gửi hình ảnh hóa đơn giao dịch.")  #[span_350](start_span)[span_350](end_span)

@router.callback_query(F.data.startswith("approve_deposit:"))
async def cb_approve_deposit(callback: CallbackQuery, bot: Bot, is_admin: bool, db_session):
    if not is_admin: await callback.answer("❌ Bạn không có quyền.", show_alert=True); return  #[span_351](start_span)[span_351](end_span)
    deposit_id = int(callback.data.split(":")[1])  #[span_352](start_span)[span_352](end_span)
    deposit = await approve_deposit(db_session, deposit_id, callback.from_user.id)  #[span_353](start_span)[span_353](end_span)
    if deposit is None: await callback.answer("⚠️ Bill không tồn tại hoặc đã xử lý trước đó.", show_alert=True); return  #[span_354](start_span)[span_354](end_span)
    user_after = await add_balance(db_session, deposit.user_id, deposit.amount)  #[span_355](start_span)[span_355](end_span)
    user_tg_id = deposit.user.telegram_id if deposit.user else None  #[span_356](start_span)[span_356](end_span)
    await callback.message.edit_reply_markup(reply_markup=None)  #[span_357](start_span)[span_357](end_span)
    await callback.message.reply(f"✅ Đã duyệt nạp tiền thành công <b>{deposit.amount:,} VNĐ</b> cho đơn #{deposit_id}", parse_mode="HTML")  #[span_358](start_span)[span_358](end_span)
    if user_tg_id:
        try: await bot.send_message(user_tg_id, f"✅ <b>Nạp tiền thành công!</b>\n\n💵 Cộng: <b>{deposit.amount:,} VNĐ</b>\n💰 Số dư ví VNĐ: <b>{user_after.balance:,} VNĐ</b>", parse_mode="HTML")  #[span_359](start_span)[span_359](end_span)
        except Exception: pass
    await callback.answer("✅ Hoàn tất!")  #[span_360](start_span)[span_360](end_span)

@router.callback_query(F.data.startswith("reject_deposit:"))
async def cb_reject_deposit(callback: CallbackQuery, bot: Bot, is_admin: bool, db_session):
    if not is_admin: await callback.answer("❌ Bạn không có quyền.", show_alert=True); return  #[span_361](start_span)[span_361](end_span)
    deposit_id = int(callback.data.split(":")[1])  #[span_362](start_span)[span_362](end_span)
    deposit = await reject_deposit(db_session, deposit_id, callback.from_user.id)  #[span_363](start_span)[span_363](end_span)
    if deposit is None: await callback.answer("⚠️ Bill không tồn tại hoặc đã xử lý.", show_alert=True); return  #[span_364](start_span)[span_364](end_span)
    user_tg_id = deposit.user.telegram_id if deposit.user else None  #[span_365](start_span)[span_365](end_span)
    await callback.message.edit_reply_markup(reply_markup=None)  #[span_366](start_span)[span_366](end_span)
    await callback.message.reply(f"❌ Đã từ chối đơn nạp #{deposit_id}", parse_mode="HTML")  #[span_367](start_span)[span_367](end_span)
    if user_tg_id:
        try: await bot.send_message(user_tg_id, f"❌ <b>Đơn nạp tiền bị từ chối!</b>\n\n💵 Số tiền: <b>{deposit.amount:,} VNĐ</b>\nVui lòng kiểm tra lại hình ảnh hóa đơn.", parse_mode="HTML")  #[span_368](start_span)[span_368](end_span)
        except Exception: pass
    await callback.answer("❌ Đã hủy!")  #[span_369](start_span)[span_369](end_span)

# ── Mini Game Tài Xỉu (Xanh Chín 100% - Không Gài Kết Quả) ─────────────────────
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
async def tx_process_bet(message: Message, state: FSMContext, db_session, db_user: User):
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Số xu đặt cược phải là số nguyên dương hợp lệ.")
        return
    bet = int(text)
    
    # Khóa dòng chống spam tiền nhanh
    r_u = await db_session.execute(select(User).where(User.id == db_user.id).with_for_update())
    user = r_u.scalar_one_or_none()
    
    if user.xu < bet:
        await message.answer(f"❌ Bạn không đủ xu! Hiện có <b>{user.xu:,} xu</b>.", parse_mode="HTML")
        await state.clear()
        return
        
    data = await state.get_data()
    chosen_side = data.get("chosen_side")
    await state.clear()

    await message.answer("🎲 Đang lắc xúc xắc...")
    await asyncio.sleep(1.5) # Tạo độ trễ cảm giác hồi hộp

    d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
    tong = d1 + d2 + d3
    ket_qua = "tai" if tong >= 11 else "xiu"
    ket_qua_text = "🔴 TÀI" if ket_qua == "tai" else "🔵 XỈU"

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

# ── Lệnh cược nhanh /tx t hoặc x ──────────────────────────────────────────────
@router.message(Command("tx"))
async def cmd_tx_fast(message: Message, db_session, db_user: User):
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

    d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
    tong = d1 + d2 + d3
    ket_qua = "tai" if tong >= 11 else "xiu"
    ket_qua_text = "🔴 TÀI" if ket_qua == "tai" else "🔵 XỈU"

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

# ── Hệ Thống Giftcode Lưu Trữ SQLite ──────────────────────────────────────────
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
        await message.answer("❌ Mã quà tặng không tồn tại hoặc đã bị xóa!", reply_markup=main_menu_kb())
        return
        
    used_ids = [x for x in (code_obj.used_by or "").split(",") if x]
    if str(db_user.telegram_id) in used_ids:
        await message.answer("⚠️ Bạn đã sử dụng mã quà tặng này rồi!", reply_markup=main_menu_kb())
        return
        
    if code_obj.used_count >= code_obj.max_uses:
        await message.answer("😢 Mã quà tặng này đã hết lượt sử dụng mất rồi!", reply_markup=main_menu_kb())
        return

    # Khóa dòng cộng xu cho user
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
    if not is_admin: await message.answer("❌ Bạn không có quyền."); return  #[span_370](start_span)[span_370](end_span)
    await message.answer("🔐 <b>HỆ THỐNG ĐIỀU HÀNH ADMIN</b>", parse_mode="HTML", reply_markup=admin_menu_kb())  #[span_371](start_span)[span_371](end_span)

@router.message(lambda m: m.text == "🔙 Menu Chính")
async def back_to_main(message: Message):
    await message.answer("🏠 Quay về Menu chính", reply_markup=main_menu_kb())  #[span_372](start_span)[span_372](end_span)

@router.message(lambda m: m.text == "📊 Dashboard")
@admin_only
async def admin_dashboard(message: Message, is_admin: bool, db_session):
    t_acc = await get_total_count(db_session)  #[span_373](start_span)[span_373](end_span)
    a_acc = await get_available_count(db_session)  #[span_374](start_span)[span_374](end_span)
    s_acc = await get_sold_count(db_session)  #[span_375](start_span)[span_375](end_span)
    orders = await get_all_orders(db_session, 9999)  #[span_376](start_span)[span_376](end_span)
    users = await get_all_users(db_session)  #[span_377](start_span)[span_377](end_span)
    bills = await get_pending_deposits(db_session)  #[span_378](start_span)[span_378](end_span)
    await message.answer(
        f"📊 <b>DASHBOARD HỆ THỐNG</b>\n\n"  #[span_379](start_span)[span_379](end_span)
        f"👥 Tổng người dùng: <b>{len(users)}</b>\n"  #[span_380](start_span)[span_380](end_span)
        f"📦 Tổng acc trong kho: <b>{t_acc}</b>\n"  #[span_381](start_span)[span_381](end_span)
        f"✅ Acc chưa bán: <b>{a_acc}</b>\n"  #[span_382](start_span)[span_382](end_span)
        f"🔴 Acc đã bán: <b>{s_acc}</b>\n"  #[span_383](start_span)[span_383](end_span)
        f"🧾 Tổng số đơn: <b>{len(orders)}</b>\n"  #[span_384](start_span)[span_384](end_span)
        f"💰 Doanh thu VNĐ: <b>{sum(o.price for o in orders):,} VNĐ</b>\n"  #[span_385](start_span)[span_385](end_span)
        f"⏳ Hoá đơn chờ duyệt: <b>{len(bills)}</b>",  #[span_386](start_span)[span_386](end_span)
        parse_mode="HTML"
    )

@router.message(lambda m: m.text == "📦 Xem Kho")
@admin_only
async def admin_view_stock(message: Message, is_admin: bool, db_session):
    t = await get_total_count(db_session)  #[span_387](start_span)[span_387](end_span)
    a = await get_available_count(db_session)  #[span_388](start_span)[span_388](end_span)
    s = await get_sold_count(db_session)  #[span_389](start_span)[span_389](end_span)
    await message.answer(f"📦 <b>Trạng Thái Kho</b>\n\n📊 Tổng: <b>{t}</b>\n✅ Chưa bán: <b>{a}</b>\n🔴 Đã bán: <b>{s}</b>", parse_mode="HTML")  #[span_390](start_span)[span_390](end_span)

@router.message(lambda m: m.text == "📊 Thống Kê")
@admin_only
async def admin_stats(message: Message, is_admin: bool, db_session):
    orders = await get_all_orders(db_session, 9999)  #[span_391](start_span)[span_391](end_span)
    users = await get_all_users(db_session)  #[span_392](start_span)[span_392](end_span)
    t = await get_total_count(db_session)  #[span_393](start_span)[span_393](end_span)
    a = await get_available_count(db_session)  #[span_394](start_span)[span_394](end_span)
    s = await get_sold_count(db_session)  #[span_395](start_span)[span_395](end_span)
    await message.answer(
        f"📊 <b>Thống Kê Vận Hành</b>\n\n👥 Tổng User: <b>{len(users)}</b>\n📦 Tổng Acc: <b>{t}</b>\n✅ Còn: <b>{a}</b>\n🔴 Đã bán: <b>{s}</b>\n🧾 Tổng đơn: <b>{len(orders)}</b>\n💰 Tổng doanh thu: <b>{sum(o.price for o in orders):,} VNĐ</b>",  #[span_396](start_span)[span_396](end_span)
        parse_mode="HTML"
    )

@router.message(lambda m: m.text == "📥 Import TXT")
@admin_only
async def admin_import_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("📥 Vui lòng gửi file `.TXT` chứa tài khoản.\n\nĐịnh dạng mỗi dòng: <code>username|password</code>", parse_mode="HTML")  #[span_397](start_span)[span_397](end_span)
    await state.set_state(AdminStates.waiting_import_file)  #[span_398](start_span)[span_398](end_span)

@router.message(AdminStates.waiting_import_file, F.document)
async def admin_import_file(message: Message, state: FSMContext, bot: Bot, db_session):
    doc = message.document  #[span_399](start_span)[span_399](end_span)
    if not doc or not doc.file_name or not doc.file_name.endswith(".txt"):
        await message.answer("⚠️ File gửi lên phải có định dạng đuôi `.txt`!")  #[span_400](start_span)[span_400](end_span)
        return
    await state.clear()  #[span_401](start_span)[span_401](end_span)
    file = await bot.get_file(doc.file_id)  #[span_402](start_span)[span_402](end_span)
    raw = await bot.download_file(file.file_path)  #[span_403](start_span)[span_403](end_span)
    content = raw.read().decode("utf-8", errors="ignore")  #[span_404](start_span)[span_404](end_span)
    stats = await import_accounts(db_session, content.splitlines())  #[span_405](start_span)[span_405](end_span)
    await message.answer(f"📥 <b>KẾT QUẢ IMPORT KHO ACC</b>\n\n📄 Tổng dòng: <b>{stats['total']}</b>\n✅ Đã thêm thành công: <b>{stats['imported']}</b>\n🔁 Bị trùng: <b>{stats['duplicates']}</b>\n❌ Lỗi định dạng: <b>{stats['invalid']}</b>", parse_mode="HTML")  #[span_406](start_span)[span_406](end_span)

# Các hàm Admin điều chỉnh dòng tiền (Cộng/Trừ VNĐ, Cộng/Trừ Xu)
@router.message(lambda m: m.text == "💰 Cộng Tiền")
@admin_only
async def admin_add_bal_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("💰 Nhập Telegram ID người nhận tiền VNĐ:")  #[span_407](start_span)[span_407](end_span)
    await state.set_state(AdminStates.waiting_add_balance_id)  #[span_408](start_span)[span_408](end_span)

@router.message(AdminStates.waiting_add_balance_id)
async def admin_add_bal_id(message: Message, state: FSMContext):
    t = (message.text or "").strip()  #[span_409](start_span)[span_409](end_span)
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ Telegram ID phải là số."); return  #[span_410](start_span)[span_410](end_span)
    await state.update_data(target_id=int(t))  #[span_411](start_span)[span_411](end_span)
    await message.answer("💵 Nhập số tiền VNĐ cần cộng thêm:")  #[span_412](start_span)[span_412](end_span)
    await state.set_state(AdminStates.waiting_add_balance_amount)  #[span_413](start_span)[span_413](end_span)

@router.message(AdminStates.waiting_add_balance_amount)
async def admin_add_bal_amount(message: Message, state: FSMContext, db_session):
    t = (message.text or "").replace(",", "").strip()  #[span_414](start_span)[span_414](end_span)
    if not t.isdigit() or int(t) <= 0: await message.answer("⚠️ Số tiền không hợp lệ."); return  #[span_415](start_span)[span_415](end_span)
    amt = int(t); data = await state.get_data(); tid = data["target_id"]; await state.clear()  #[span_416](start_span)[span_416](end_span)
    user = await adjust_balance_by_telegram_id(db_session, tid, amt)  #[span_417](start_span)[span_417](end_span)
    if user is None: await message.answer(f"❌ Không tìm thấy User ID {tid} trong hệ thống."); return  #[span_418](start_span)[span_418](end_span)
    await message.answer(f"✅ Đã cộng <b>{amt:,} VNĐ</b> cho <b>{user.fullname}</b>\n💰 Số dư VNĐ mới: <b>{user.balance:,} VNĐ</b>", parse_mode="HTML")  #[span_419](start_span)[span_419](end_span)

@router.message(lambda m: m.text == "💸 Trừ Tiền")
@admin_only
async def admin_sub_bal_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("💸 Nhập Telegram ID người cần trừ tiền VNĐ:")  #[span_420](start_span)[span_420](end_span)
    await state.set_state(AdminStates.waiting_subtract_balance_id)  #[span_421](start_span)[span_421](end_span)

@router.message(AdminStates.waiting_subtract_balance_id)
async def admin_sub_bal_id(message: Message, state: FSMContext):
    t = (message.text or "").strip()  #[span_422](start_span)[span_422](end_span)
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ Telegram ID không hợp lệ."); return  #[span_423](start_span)[span_423](end_span)
    await state.update_data(target_id=int(t))  #[span_424](start_span)[span_424](end_span)
    await message.answer("💵 Nhập số tiền VNĐ cần trừ bớt:")  #[span_425](start_span)[span_425](end_span)
    await state.set_state(AdminStates.waiting_subtract_balance_amount)  #[span_426](start_span)[span_426](end_span)

@router.message(AdminStates.waiting_subtract_balance_amount)
async def admin_sub_bal_amount(message: Message, state: FSMContext, db_session):
    t = (message.text or "").replace(",", "").strip()  #[span_427](start_span)[span_427](end_span)
    if not t.isdigit() or int(t) <= 0: await message.answer("⚠️ Số tiền không hợp lệ."); return  #[span_428](start_span)[span_428](end_span)
    amt = int(t); data = await state.get_data(); tid = data["target_id"]; await state.clear()  #[span_429](start_span)[span_429](end_span)
    user = await adjust_balance_by_telegram_id(db_session, tid, -amt)  #[span_430](start_span)[span_430](end_span)
    if user is None: await message.answer(f"❌ Không tìm thấy User ID {tid}"); return  #[span_431](start_span)[span_431](end_span)
    await message.answer(f"✅ Đã trừ <b>{amt:,} VNĐ</b> khỏi <b>{user.fullname}</b>\n💰 Số dư VNĐ mới: <b>{user.balance:,} VNĐ</b>", parse_mode="HTML")  #[span_432](start_span)[span_432](end_span)

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
    
    # Check trùng code
    ex = await db_session.execute(select(Giftcode).where(Giftcode.code == name))
    if ex.scalar_one_or_none(): await message.answer("❌ Mã Code này đã tồn tại trong Database!"); return
    
    db_session.add(Giftcode(code=name, xu=xu_val, max_uses=uses))
    await db_session.commit()
    await message.answer(f"✅ Đã tạo Giftcode vĩnh viễn!\n🎫 Mã: <b>{name}</b>\n🎁 Phần thưởng: {xu_val:,} xu\n🔢 Giới hạn: {uses} lượt", parse_mode="HTML")

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
    await message.answer("📷 Vui lòng gửi ảnh mã QR nạp tiền mới lên đây:")  #[span_433](start_span)[span_433](end_span)
    await state.set_state(AdminStates.waiting_qr)  #[span_434](start_span)[span_434](end_span)

@router.message(AdminStates.waiting_qr, F.photo)
async def admin_receive_qr(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]; file = await bot.get_file(photo.file_id); raw = await bot.download_file(file.file_path)  #[span_435](start_span)[span_435](end_span)
    await save_qr_image(raw.read())  #[span_436](start_span)[span_436](end_span)
    await state.clear()  #[span_437](start_span)[span_437](end_span)
    await message.answer("✅ Ảnh QR nạp tiền đã cập nhật thành công!")  #[span_438](start_span)[span_438](end_span)

@router.message(lambda m: m.text == "📥 Bill Chờ")
@admin_only
async def admin_pending_bills(message: Message, is_admin: bool, db_session):
    deposits = await get_pending_deposits(db_session)  #[span_439](start_span)[span_439](end_span)
    if not deposits: await message.answer("✅ Không có yêu cầu nạp tiền nào đang xếp hàng."); return  #[span_440](start_span)[span_440](end_span)
    lines = [f"📥 <b>Yêu Cầu Chờ Duyệt ({len(deposits)})</b>\n"]  #[span_441](start_span)[span_441](end_span)
    for d in deposits:
        uname = f"@{d.user.username}" if d.user and d.user.username else "N/A"  #[span_442](start_span)[span_442](end_span)
        name = d.user.fullname if d.user else "N/A"  #[span_443](start_span)[span_443](end_span)
        created = d.created_at.strftime("%d/%m/%Y %H:%M") if d.created_at else "N/A"  #[span_444](start_span)[span_444](end_span)
        lines.append(f"🧾 ID #{d.id} — {name} ({uname})\n   💵 {d.amount:,} VNĐ — {created}")  #[span_445](start_span)[span_445](end_span)
    await message.answer("\n".join(lines), parse_mode="HTML")  #[span_446](start_span)[span_446](end_span)

@router.message(lambda m: m.text == "📢 Broadcast")
@admin_only
async def admin_broadcast_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("📢 Nhập nội dung tin nhắn bạn muốn gửi cho toàn bộ người chơi:")  #[span_447](start_span)[span_447](end_span)
    await state.set_state(AdminStates.waiting_broadcast_text)  #[span_448](start_span)[span_448](end_span)

@router.message(AdminStates.waiting_broadcast_text)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot, db_session):
    text = message.text or ""; await state.clear()  #[span_449](start_span)[span_449](end_span)
    if not text: await message.answer("⚠️ Nội dung trống."); return  #[span_450](start_span)[span_450](end_span)
    users = await get_all_users(db_session)  #[span_451](start_span)[span_451](end_span)
    sent = failed = 0  #[span_452](start_span)[span_452](end_span)
    for u in users:
        if u.is_banned: continue  #[span_453](start_span)[span_453](end_span)
        try: await bot.send_message(u.telegram_id, text, parse_mode="HTML"); sent += 1  #[span_454](start_span)[span_454](end_span)
        except Exception: failed += 1  #[span_455](start_span)[span_455](end_span)
    await message.answer(f"📢 <b>Gửi Broadcast Hoàn Tất</b>\n\n✅ Thành công: <b>{sent}</b>\n❌ Thất bại: <b>{failed}</b>", parse_mode="HTML")  #[span_456](start_span)[span_456](end_span)

@router.message(lambda m: m.text == "🚫 Ban User")
@admin_only
async def admin_ban_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("🚫 Nhập Telegram ID người cần cấm sử dụng bot:")  #[span_457](start_span)[span_457](end_span)
    await state.set_state(AdminStates.waiting_ban_id)  #[span_458](start_span)[span_458](end_span)

@router.message(AdminStates.waiting_ban_id)
async def admin_ban_execute(message: Message, state: FSMContext, db_session):
    t = (message.text or "").strip(); await state.clear()  #[span_459](start_span)[span_459](end_span)
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ ID sai định dạng."); return  #[span_460](start_span)[span_460](end_span)
    ok = await ban_user(db_session, int(t))  #[span_461](start_span)[span_461](end_span)
    await message.answer(f"✅ Đã ban ID <code>{t}</code>." if ok else f"❌ Không thấy ID <code>{t}</code>", parse_mode="HTML")  #[span_462](start_span)[span_462](end_span)

@router.message(lambda m: m.text == "✅ Unban User")
@admin_only
async def admin_unban_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("✅ Nhập Telegram ID cần mở khóa ban:")  #[span_463](start_span)[span_463](end_span)
    await state.set_state(AdminStates.waiting_unban_id)  #[span_464](start_span)[span_464](end_span)

@router.message(AdminStates.waiting_unban_id)
async def admin_unban_execute(message: Message, state: FSMContext, db_session):
    t = (message.text or "").strip(); await state.clear()  #[span_465](start_span)[span_465](end_span)
    if not t.lstrip("-").isdigit(): await message.answer("⚠️ ID sai."); return  #[span_466](start_span)[span_466](end_span)
    ok = await unban_user(db_session, int(t))  #[span_467](start_span)[span_467](end_span)
    await message.answer(f"✅ Đã gỡ ban ID <code>{t}</code>." if ok else f"❌ Không thấy ID <code>{t}</code>", parse_mode="HTML")  #[span_468](start_span)[span_468](end_span)

@router.message(lambda m: m.text == "🗑 Xóa Account")
@admin_only
async def admin_delete_acc_start(message: Message, state: FSMContext, is_admin: bool):
    await message.answer("🗑 Nhập tên tài khoản game (username) cần xoá khỏi kho:")  #[span_469](start_span)[span_469](end_span)
    await state.set_state(AdminStates.waiting_delete_username)  #[span_470](start_span)[span_470](end_span)

@router.message(AdminStates.waiting_delete_username)
async def admin_delete_acc_execute(message: Message, state: FSMContext, db_session):
    uname = (message.text or "").strip(); await state.clear()  #[span_471](start_span)[span_471](end_span)
    ok = await delete_account_by_username(db_session, uname)  #[span_472](start_span)[span_472](end_span)
    await message.answer(f"✅ Đã xóa acc <code>{uname}</code> khỏi hệ thống." if ok else f"❌ Không thấy acc có tên <code>{uname}</code>", parse_mode="HTML")  #[span_473](start_span)[span_473](end_span)

@router.message(lambda m: m.text == "📤 Export Chưa Bán")
@admin_only
async def admin_export_unsold(message: Message, is_admin: bool, db_session):
    accounts = await get_unsold_accounts(db_session)  #[span_474](start_span)[span_474](end_span)
    if not accounts: await message.answer(" Kho trống rỗng."); return  #[span_475](start_span)[span_475](end_span)
    lines = [f"{a.username}|{a.password}" for a in accounts]  #[span_476](start_span)[span_476](end_span)
    fp = await save_export_file(lines, "unsold")  #[span_477](start_span)[span_477](end_span)
    await message.answer_document(FSInputFile(fp), caption=f"📤 Acc Chưa Bán\n📊 Số lượng: <b>{len(lines)}</b> acc", parse_mode="HTML")  #[span_478](start_span)[span_478](end_span)

@router.message(lambda m: m.text == "📤 Export Đã Bán")
@admin_only
async def admin_export_sold(message: Message, is_admin: bool, db_session):
    accounts = await get_sold_accounts(db_session)  #[span_479](start_span)[span_479](end_span)
    if not accounts: await message.answer(" Chưa bán được đơn nào."); return  #[span_480](start_span)[span_480](end_span)
    lines = [f"{a.username}|{a.password}" for a in accounts]  #[span_481](start_span)[span_481](end_span)
    fp = await save_export_file(lines, "sold")  #[span_482](start_span)[span_482](end_span)
    await message.answer_document(FSInputFile(fp), caption=f"📤 Acc Đã Bán\n📊 Số lượng: <b>{len(lines)}</b> acc", parse_mode="HTML")  #[span_483](start_span)[span_483](end_span)

# ── Web Server Mồi Chống Sleep Trên Render ────────────────────────────────────
async def handle_web(request):
    return web.Response(text="Bot đang vận hành xanh chín ổn định 24/7!")  #[span_484](start_span)[span_484](end_span)

async def start_web_server():
    app = web.Application()  #[span_485](start_span)[span_485](end_span)
    app.router.add_get("/", handle_web)  #[span_486](start_span)[span_486](end_span)
    runner = web.AppRunner(app)  #[span_487](start_span)[span_487](end_span)
    await runner.setup()  #[span_488](start_span)[span_488](end_span)
    port = int(os.environ.get("PORT", 8080))  # Cổng mạng tự động do hệ thống Render cấp[span_489](start_span)[span_489](end_span)
    site = web.TCPSite(runner, "0.0.0.0", port)  #[span_490](start_span)[span_490](end_span)
    await site.start()  #[span_491](start_span)[span_491](end_span)
    logger.info(f"✅ Web Server Keep-Alive đang kích hoạt tại Port: {port}")

# ── Tiến Trình Khởi Chạy ──────────────────────────────────────────────────────
async def main():
    await init_db()  # Khởi tạo bảng dữ liệu SQLite[span_492](start_span)[span_492](end_span)
    await start_web_server()  # Khởi chạy cổng Web Service mồi[span_493](start_span)[span_493](end_span)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))  #[span_494](start_span)[span_494](end_span)
    dp = Dispatcher(storage=MemoryStorage())  #[span_495](start_span)[span_495](end_span)
    dp.message.middleware(AuthMiddleware())  #[span_496](start_span)[span_496](end_span)
    dp.callback_query.middleware(AuthMiddleware())  #[span_497](start_span)[span_497](end_span)
    dp.include_router(router)  #[span_498](start_span)[span_498](end_span)

    logger.info("🤖 Bot Hợp Nhất Đã Sẵn Sàng Trực Tuyến!")
    try: await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())  #[span_499](start_span)[span_499](end_span)
    finally: await bot.session.close()  #[span_500](start_span)[span_500](end_span)

if __name__ == "__main__":
    asyncio.run(main())  #[span_501](start_span)[span_501](end_span)
