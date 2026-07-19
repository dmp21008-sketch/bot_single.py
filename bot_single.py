# ═══════════════════════════════════════════════════════════════
#  BOT LIÊN QUÂN + TÀI XỈU HIỆU ỨNG ĐỘNG - BẢN FULL MERGE TELEBOT
#  Cài thư viện trên Replit: pip install pyTelegramBotAPI flask
# ═══════════════════════════════════════════════════════════════

import os
import time
import sqlite3
import threading
import random
import uuid
import datetime
from telebot import types
import telebot
from flask import Flask

# =======================================================
# ⚙️ CẤU HÌNH HỆ THỐNG
# =======================================================
BOT_TOKEN = os.environ.get("8374524579:AAE2pvVgQqOFnEN2hnhhfRUyopi1B8Dhxcc")
ADMIN_ID = 7936179657  # ID Telegram của Admin chủ shop

ACCOUNT_PRICE = 200      # Giá VNĐ/Điểm cho 1 acc lẻ
VIP_WEEK_PRICE = 50000   # Giá mua gói VIP Tuần
VIP_MONTH_PRICE = 100000 # Giá mua gói VIP Tháng
VIP_DAILY_LIMIT = 100    # Giới hạn nhận acc free mỗi ngày của VIP
LOW_STOCK_ALERT = 10     # Ngưỡng cảnh báo hết acc gửi cho Admin

CHECKER_LINK = "https://t.me/tretrauchecker_bot?start=_tgr_8UulJtkyZjE1"
DB_FILE = "database.db"
QR_IMAGE_PATH = "uploads/qr_current.jpg"
# =======================================================

bot = telebot.TeleBot(BOT_TOKEN)
os.makedirs("uploads", exist_ok=True)
os.makedirs("exports", exist_ok=True)

# Bộ nhớ tạm cấu hình Admin giống suộc cũ
CONFIG = {
    "xu_diemdanh": 500, # Đã nâng lên 500 điểm theo ý bạn ở các phiên trước
    "force_result": None
}

# Trạng thái FSM ngầm cho user (nhập số tiền nạp, nhập mã, nhập file...)
user_state = {}

# ════════════════════════════════════════════════════════
# 💾 DATABASE SQLITE - KHỞI TẠO VÀ QUẢN LÝ VĨNH VIỄN
# ════════════════════════════════════════════════════════
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        # Bảng người dùng
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                fullname TEXT,
                xu INTEGER DEFAULT 100,
                vip_until TEXT,
                last_checkin_date TEXT,
                vip_claimed_today INTEGER DEFAULT 0,
                last_vip_claim_date TEXT,
                referred_by INTEGER
            )
        ''')
        # Bảng kho acc liên quân
        conn.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                status TEXT DEFAULT 'available',
                sold_at TEXT
            )
        ''')
        # Bảng giftcode
        conn.execute('''
            CREATE TABLE IF NOT EXISTS codes (
                code TEXT PRIMARY KEY,
                xu INTEGER,
                luot INTEGER,
                da_dung TEXT DEFAULT ''
            )
        ''')
        # Bảng đơn hàng mua acc
        conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                quantity INTEGER,
                price INTEGER,
                file_name TEXT,
                created_at TEXT
            )
        ''')
        # Bảng bill chờ nạp tiền
        conn.execute('''
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending'
            )
        ''')
        conn.commit()

init_db()

def get_user(telegram_id, username="User", fullname=""):
    with get_db_connection() as conn:
        user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
        if not user:
            conn.execute(
                'INSERT INTO users (telegram_id, username, fullname) VALUES (?, ?, ?)',
                (telegram_id, username or f"User_{telegram_id}", fullname or f"User_{telegram_id}")
            )
            conn.commit()
            user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
        return dict(user)

def update_user_xu(telegram_id, amount):
    with get_db_connection() as conn:
        conn.execute('UPDATE users SET xu = xu + ? WHERE telegram_id = ?', (amount, telegram_id))
        conn.commit()

# ════════════════════════════════════════════════════════
# ⌨️ HỆ THỐNG GIAO DIỆN BÀN PHÍM (KEYBOARD)
# ════════════════════════════════════════════════════════
def menu_chinh(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🏠 Trang Chủ"), types.KeyboardButton("🛒 Mua Acc"))
    markup.row(types.KeyboardButton("💳 Nạp Tiền"), types.KeyboardButton("👤 Tài Khoản"))
    markup.row(types.KeyboardButton("📦 Đơn Hàng"), types.KeyboardButton("🎁 Free & VIP"))
    markup.row(types.KeyboardButton("☎ Hỗ Trợ"))
    if user_id == ADMIN_ID:
        markup.row(types.KeyboardButton("⚙️ Menu Admin Panel"))
    return markup

def menu_free_vip():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📅 Điểm Danh Nhận Điểm"), types.KeyboardButton("🔗 Link Giới Thiệu"))
    markup.row(types.KeyboardButton("👑 Nhận Acc VIP Free"), types.KeyboardButton("⚡ Mua Gói VIP"))
    markup.row(types.KeyboardButton("🔙 Menu Chính"))
    return markup

def menu_admin_panel():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📊 Dashboard"), types.KeyboardButton("📥 Import TXT"))
    markup.row(types.KeyboardButton("📦 Xem Kho"), types.KeyboardButton("📷 Đổi QR"))
    markup.row(types.KeyboardButton("📢 Broadcast"), types.KeyboardButton("🔙 Menu Chính"))
    return markup

def inline_menu_vip():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("👑 VIP Tuần (50kđ)", callback_data="buy_vip_week"),
        types.InlineKeyboardButton("👑 VIP Tháng (100kđ)", callback_data="buy_vip_month")
    )
    return markup

def inline_duyet_bill(deposit_id):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ DUYỆT", callback_data=f"approve_{deposit_id}"),
        types.InlineKeyboardButton("❌ TỪ CHỐI", callback_data=f"reject_{deposit_id}")
    )
    return markup

# ════════════════════════════════════════════════════════
# ⚡ XỬ LÝ LỆNH /start & MENU CHÍNH
# ════════════════════════════════════════════════════════
@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    fullname = message.from_user.full_name
    
    # Xử lý mời Ref qua link giới thiệu
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_by = int(args[1].split("_")[1])
            with get_db_connection() as conn:
                ex_user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (user_id,)).fetchone()
                if not ex_user and ref_by != user_id:
                    # Thưởng ref_by 5000 điểm
                    conn.execute('UPDATE users SET xu = xu + 5000 WHERE telegram_id = ?', (ref_by,))
                    bot.send_message(ref_by, f"🔔 Người chơi <b>{fullname}</b> vừa tham gia qua link giới thiệu của bạn! Bạn nhận được: +<b>5,000 điểm</b>.", parse_mode="HTML")
                    get_user(user_id, username, fullname)
                    conn.execute('UPDATE users SET referred_by = ? WHERE telegram_id = ?', (ref_by, user_id))
                    conn.commit()
        except Exception:
            pass

    user = get_user(user_id, username, fullname)
    text = (
        f"👋 Chào mừng <b>{user['fullname']}</b> đến với Shop Liên Quân - Tài Xỉu Động!\n\n"
        f"💰 Số dư ví: <b>{user['xu']:,} điểm</b>\n"
        f"👑 Cấp bậc: <b>{'👑 Thành viên VIP' if kiem_tra_vip(user_id) else 'Thành viên Thường'}</b>\n\n"
        f"🎮 <b>HƯỚNG DẪN CHƠI TÀI XỈU SIÊU TỐC:</b>\n"
        f"👉 Gõ lệnh: <code>/tx t [số điểm]</code> (Đặt Tài)\n"
        f"👉 Gõ lệnh: <code>/tx x [số điểm]</code> (Đặt Xỉu)\n"
        f"👉 Gõ lệnh: <code>/tang [ID_Nhận] [số điểm]</code> (Tặng điểm cho bạn bè)\n"
        f"<i>Luật: 3-10 nút = Xỉu | 11-18 nút = Tài. Lắc hiệu ứng chuyển động Telegram thật 100%!</i>"
    )
    if user_id == ADMIN_ID:
        text += "\n\n👑 <b>LỆNH ADMIN ẨN:</b>\n<code>/gaikq [tai/xiu/huy]</code> - Ép kết quả phiên sau\n<code>/taoma [MÃ] [xu] [lượt]</code> - Tạo code\n<code>/xoama [MÃ]</code> - Xóa code\n<code>/congbong [ID] [số xu]</code> - Bơm điểm\n<code>/setvip [ID] [số ngày]</code> - Set VIP nhanh"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=menu_chinh(user_id))

def kiem_tra_vip(user_id):
    with get_db_connection() as conn:
        user = conn.execute('SELECT vip_until FROM users WHERE telegram_id = ?', (user_id,)).fetchone()
        if user and user['vip_until']:
            until = datetime.datetime.strptime(user['vip_until'], "%Y-%m-%d %H:%M:%S")
            if until > datetime.datetime.now():
                return True
    return False

# Xử lý các nút bấm text menu chính
@bot.message_handler(func=lambda m: m.text in [
    "🏠 Trang Chủ", "🔙 Menu Chính", "🛒 Mua Acc", "💳 Nạp Tiền", 
    "👤 Tài Khoản", "📦 Đơn Hàng", "🎁 Free & VIP", "☎ Hỗ Trợ", "⚙️ Menu Admin Panel"
])
def handling_text_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.username)
    
    if message.text in ["🏠 Trang Chủ", "🔙 Menu Chính"]:
        user_state.pop(user_id, None)
        cmd_start(message)
    elif message.text == "☎ Hỗ Trợ":
        bot.send_message(message.chat.id, "☎ <b>HỆ THỐNG TRỢ GIÚP CHỦ SHOP</b>\n\n👤 Admin: @lananh9719\n⏰ Thời gian hỗ trợ duyệt nạp: 8:00 - 24:00", parse_mode="HTML")
    elif message.text == "⚙️ Menu Admin Panel" and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "🔐 Đã mở bảng điều khiển Admin Panel của sếp!", reply_markup=menu_admin_panel())
        
    elif message.text == "👤 Tài Khoản":
        is_vip = "👑 VIP" if kiem_tra_vip(user_id) else "Thường"
        text = (
            f"👤 <b>HỒ SƠ TÀI KHOẢN CỦA BẠN</b>\n\n"
            f"🪪 ID Telegram: <code>{user_id}</code>\n"
            f"🏅 Cấp bậc: <b>{is_vip}</b>\n"
            f"💰 Số dư ví điểm: <b>{user['xu']:,} Xu/Điểm</b>\n"
            f"💡 Mẹo lấy ID: Gõ lệnh <code>/myid</code> gửi lên nhóm/bot."
        )
        bot.send_message(message.chat.id, text, parse_mode="HTML")
        
    elif message.text == "🎁 Free & VIP":
        bot.send_message(message.chat.id, "🎁 Chào mừng tới Khu Vực Cày Điểm & Ưu Đãi VIP. Hãy chọn tính năng bên dưới:", reply_markup=menu_free_vip())
        
    elif message.text == "💳 Nạp Tiền":
        if not os.path.exists(QR_IMAGE_PATH):
            bot.send_message(message.chat.id, "⚠️ Chủ shop chưa cấu hình mã ảnh QR nạp tiền.")
            return
        user_state[user_id] = "nap_tien_cho_gia"
        with open(QR_IMAGE_PATH, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption="💳 Bạn vui lòng quét mã QR chuyển khoản ở trên.\n\n👉 Nhập số tiền bạn muốn nạp (Ví dụ: 50000):")

    elif message.text == "🛒 Mua Acc":
        with get_db_connection() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM accounts WHERE status='available'").fetchone()[0]
        bot.send_message(message.chat.id, f"🛒 <b>MUA ACCOUNT LIÊN QUÂN LẺ</b>\n\n💵 Giá bán: <b>{ACCOUNT_PRICE:,} điểm/1 acc</b>\n📦 Kho hàng còn: <b>{cnt} account khả dụng</b>\n\n👉 Vui lòng nhập số lượng acc bạn muốn mua:")
        user_state[user_id] = "mua_acc_cho_qty"

    elif message.text == "📦 Đơn Hàng":
        with get_db_connection() as conn:
            orders = conn.execute('SELECT * FROM orders WHERE telegram_id = ? ORDER BY id DESC LIMIT 10', (user_id,)).fetchall()
        if not orders:
            bot.send_message(message.chat.id, "📦 Bạn chưa thực hiện đơn hàng mua acc nào trên hệ thống.")
            return
        txt = "📋 <b>LỊCH SỬ MUA ACC (10 ĐƠN GẦN NHẤT):</b>\n\n"
        for o in orders:
            txt += f"• Đơn #{o['id']} | Số lượng: {o['quantity']} acc | Giá: {o['price']:,}đ\n"
        bot.send_message(message.chat.id, txt, parse_mode="HTML")

# ════════════════════════════════════════════════════════
# 🎲 TRÒ CHƠI TÀI XỈU LỆNH NHANH CHUYỂN ĐỘNG ĐỘNG GIỮ NGUYÊN KHÔNG MỨC MAX
# ════════════════════════════════════════════════════════
@bot.message_handler(commands=['tx'])
def lenh_tx_nhanh(message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.username)
    args = message.text.split()
    
    if len(args) < 3:
        bot.reply_to(message, "⚠️ <b>Cú pháp đặt cược sai!</b>\n👉 Gõ nhanh: <code>/tx t 500</code> (Đặt Tài)\n👉 Gõ nhanh: <code>/tx x 1000</code> (Đặt Xỉu)", parse_mode="HTML")
        return
        
    cua_chon = args[1].lower()
    if cua_chon not in ["t", "tai", "tài", "x", "xiu", "xỉu"]:
        bot.reply_to(message, "⚠️ Cửa cược không hợp lệ! Hãy dùng <b>t</b> hoặc <b>x</b>.", parse_mode="HTML")
        return
        
    cua_dat = "Tài" if cua_chon in ["t", "tai", "tài"] else "Xỉu"
    
    try:
        cuoc = int(args[2])
    except ValueError:
        bot.reply_to(message, "⚠️ Số điểm cược nhập vào bắt buộc phải là số nguyên!")
        return
        
    if cuoc <= 0:
        bot.reply_to(message, "⚠️ Số tiền đặt cược phải lớn hơn 0 xu!")
        return
        
    if cuoc > user["xu"]:
        bot.reply_to(message, f"😢 Tài khoản không đủ điểm. Ví bạn còn: <b>{user['xu']:,} điểm</b>.", parse_mode="HTML")
        return

    # Trừ cược ngay khi gõ lệnh để chống cheat bug
    update_user_xu(user_id, -cuoc)
    
    bot.send_message(message.chat.id, f"🎲 Bạn đặt cược thành công <b>{cuoc:,} điểm</b> vào cửa <b>{cua_dat.upper()}</b>.\n⏳ Máy chủ đang đổ xúc xắc chuyển động...", parse_mode="HTML")
    
    # 3 Xúc xắc xoay động của Telegram
    dice1 = bot.send_dice(message.chat.id, emoji="🎲")
    dice2 = bot.send_dice(message.chat.id, emoji="🎲")
    dice3 = bot.send_dice(message.chat.id, emoji="🎲")
    
    d1, d2, d3 = dice1.dice.value, dice2.dice.value, dice3.dice.value
    tong = d1 + d2 + d3
    
    # Hệ thống gài kết quả Admin
    if CONFIG["force_result"] is not None:
        ket_qua = CONFIG["force_result"]
        CONFIG["force_result"] = None
    else:
        ket_qua = "Xỉu" if tong <= 10 else "Tài"
        
    thang = (cua_dat == ket_qua)
    time.sleep(2.5) # Chờ xúc xắc quay xong mượt mà
    
    if thang:
        update_user_xu(user_id, cuoc * 2)
        status = f"🎉 <b>CHIẾN THẮNG!</b>\n🪙 Cộng thưởng: +<b>{cuoc * 2:,} điểm</b>"
    else:
        status = f"💥 <b>THẤT BẠI!</b>\n😢 Trừ điểm cược: -<b>{cuoc:,} điểm</b>"
        
    fresh_user = get_user(user_id)
    bot.send_message(
        message.chat.id,
        f"📊 <b>KẾT QUẢ PHIÊN LẮC</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎲 Kết quả: {d1} + {d2} + {d3} = <b>{tong} nút</b>\n"
        f"👉 Cửa thắng: <b>{ket_qua.upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{status}\n"
        f"💳 Ví hiện tại: <b>{fresh_user['xu']:,} điểm</b>",
        parse_mode="HTML",
        reply_markup=menu_chinh(user_id)
    )

# ════════════════════════════════════════════════════════
# 💸 LỆNH TẶNG ĐIỂM GIỮA NGƯỜI CHƠI
# ════════════════════════════════════════════════════════
@bot.message_handler(commands=['tang', 'chuyen'])
def cmd_tang_diem(message):
    user_id = message.from_user.id
    user_gui = get_user(user_id, message.from_user.username)
    args = message.text.split()
    
    if len(args) < 3:
        bot.reply_to(message, "⚠️ Cú pháp: <code>/tang [ID_Người_Nhận] [Số_điểm]</code>", parse_mode="HTML")
        return
    try:
        target_id = int(args[1])
        so_diem = int(args[2])
    except ValueError:
        bot.reply_to(message, "⚠️ ID người nhận và Số điểm bắt buộc phải là chữ số.")
        return
        
    if target_id == user_id:
        bot.reply_to(message, "⚠️ Bạn không thể tự chuyển điểm cho chính mình.")
        return
    if so_diem <= 0:
        bot.reply_to(message, "⚠️ Số điểm chuyển tặng phải lớn hơn 0.")
        return
    if so_diem > user_gui["xu"]:
        bot.reply_to(message, f"❌ Số dư điểm không đủ. Bạn chỉ còn: <b>{user_gui['xu']:,} điểm</b>.", parse_mode="HTML")
        return

    with get_db_connection() as conn:
        user_nhan = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (target_id,)).fetchone()
        if not user_nhan:
            bot.reply_to(message, "❌ Người nhận chưa từng kích hoạt bot này. Hãy bảo họ gõ lệnh <code>/start</code> trước nhé.", parse_mode="HTML")
            return
            
        conn.execute('UPDATE users SET xu = xu - ? WHERE telegram_id = ?', (so_diem, user_id))
        conn.execute('UPDATE users SET xu = xu + ? WHERE telegram_id = ?', (so_diem, target_id))
        conn.commit()

    bot.send_message(message.chat.id, f"✅ Đã chuyển tặng thành công <b>{so_diem:,} điểm</b> cho ID <code>{target_id}</code>.", parse_mode="HTML")
    try:
        bot.send_message(target_id, f"🎁 Bạn vừa nhận được +<b>{so_diem:,} điểm</b> quà tặng từ tài khoản ID <code>{user_id}</code>!", parse_mode="HTML")
    except Exception:
        pass

# ════════════════════════════════════════════════════════
# 🎁 KHU VỰC ĐIỂM DANH, LINK REF, NHẬN ACC VIP TỰ ĐỘNG
# ════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: m.text in [
    "📅 Điểm Danh Nhận Điểm", "🔗 Link Giới Thiệu", "👑 Nhận Acc VIP Free", "⚡ Mua Gói VIP"
])
def handling_free_vip_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.username)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    if message.text == "📅 Điểm Danh Nhận Điểm":
        if user["last_checkin_date"] == today_str:
            bot.reply_to(message, "⚠️ Hôm nay bạn đã thực hiện điểm danh rồi, quay lại vào ngày mai nhé!")
            return
        with get_db_connection() as conn:
            conn.execute('UPDATE users SET xu = xu + ?, last_checkin_date = ? WHERE telegram_id = ?', (CONFIG["xu_diemdanh"], today_str, user_id))
            conn.commit()
        bot.send_message(message.chat.id, f"🎉 Điểm danh thành công! Bạn nhận được: +<b>{CONFIG['xu_diemdanh']} điểm</b>.", parse_mode="HTML")
        
    elif message.text == "🔗 Link Giới Thiệu":
        bot_info = bot.get_me()
        url = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        bot.send_message(message.chat.id, f"🔗 <b>LINK GIỚI THIỆU ĐỘC QUYỀN CỦA BẠN:</b>\n<code>{url}</code>\n\n🎁 Thưởng ngay +<b>5,000 điểm</b> vào ví chính khi có người mới tham gia qua link của bạn!", parse_mode="HTML")
        
    elif message.text == "⚡ Mua Gói VIP":
        bot.send_message(message.chat.id, f"👑 <b>MUA VIP TỰ ĐỘNG BẰNG ĐIỂM VÍ</b>\n\n💰 Số dư hiện tại: {user['xu']:,} điểm\n👉 Gói Tuần: 50,000đ | Gói Tháng: 100,000đ.\nChọn gói muốn mua dưới đây:", parse_mode="HTML", reply_markup=inline_menu_vip())
        
    elif message.text == "👑 Nhận Acc VIP Free":
        if not kiem_tra_vip(user_id):
            bot.reply_to(message, "❌ Tính năng nhận acc free chỉ dành cho tài khoản đang kích hoạt trạng thái VIP!")
            return
        with get_db_connection() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM accounts WHERE status='available'").fetchone()[0]
            db_user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (user_id,)).fetchone()
            
        claimed = db_user['vip_claimed_today'] if db_user['last_vip_claim_date'] == today_str else 0
        con_lai = VIP_DAILY_LIMIT - claimed
        
        if con_lai <= 0:
            bot.send_message(message.chat.id, "⚠️ Hôm nay bạn đã lấy hết định mức giới hạn 100 acc free rồi!")
            return
        bot.send_message(message.chat.id, f"👑 Bạn đang có quyền lấy thêm tối đa: <b>{con_lai} acc free</b> hôm nay.\n📦 Kho còn: {cnt} acc.\n👉 Vui lòng nhập số lượng muốn lấy:")
        user_state[user_id] = "nhan_vip_free_cho_qty"

# ════════════════════════════════════════════════════════
# 📥 XỬ LÝ LƯU TRỮ VÀ NHẬP DỮ LIỆU INPUT (FSM STATES)
# ════════════════════════════════════════════════════════
@bot.message_handler(content_types=['photo', 'document', 'text'])
def handling_all_inputs(message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    if not state: return

    # Xử lý nhập số lượng mua acc lẻ
    if state == "mua_acc_cho_qty" and message.text and message.text.isdigit():
        qty = int(message.text)
        if qty <= 0: return
        total_cost = qty * ACCOUNT_PRICE
        user = get_user(user_id)
        if user["xu"] < total_cost:
            bot.send_message(message.chat.id, f"❌ Không đủ số dư! Đơn hàng cần {total_cost:,}đ nhưng ví bạn chỉ có {user['xu']:,}đ.", reply_markup=menu_chinh(user_id))
            user_state.pop(user_id, None)
            return
            
        with get_db_connection() as conn:
            accs = conn.execute("SELECT * FROM accounts WHERE status='available' ORDER BY RANDOM() LIMIT ?", (qty,)).fetchall()
            if len(accs) < qty:
                bot.send_message(message.chat.id, f"❌ Kho hàng không đủ acc! Hiện chỉ còn {len(accs)} acc khả dụng.")
                user_state.pop(user_id, None)
                return
            
            # Xuất file text
            fn = f"exports/order_{uuid.uuid4().hex[:6]}.txt"
            with open(fn, 'w', encoding='utf-8') as f:
                for a in accs:
                    f.write(f"{a['username']}|{a['password']}\n")
                    conn.execute("UPDATE accounts SET status='sold', sold_at=? WHERE id=?", (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a['id']))
            
            conn.execute("UPDATE users SET xu = xu - ? WHERE telegram_id = ?", (total_cost, user_id))
            conn.execute("INSERT INTO orders (telegram_id, quantity, price, file_name, created_at) VALUES (?, ?, ?, ?, ?)",
                         (user_id, qty, total_cost, fn, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            
            # Kiểm tra ngưỡng cảnh báo kho hết hàng
            cnt = conn.execute("SELECT COUNT(*) FROM accounts WHERE status='available'").fetchone()[0]
            if cnt <= LOW_STOCK_ALERT:
                try: bot.send_message(ADMIN_ID, f"⚠️ <b>CẢNH BÁO:</b> Kho sắp hết acc lẻ! Còn lại: {cnt} acc.")
                except Exception: pass
                
        user_state.pop(user_id, None)
        bot.send_message(message.chat.id, f"✅ Thanh toán đơn hàng mua {qty} acc thành công!", reply_markup=menu_chinh(user_id))
        with open(fn, 'rb') as document:
            bot.send_document(message.chat.id, document, caption=f"📌 Kiểm tra acc miễn phí tại:\n\n{CHECKER_LINK}")

    # Xử lý nhận acc free cho VIP
    elif state == "nhan_vip_free_cho_qty" and message.text and message.text.isdigit():
        qty = int(message.text)
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            db_user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (user_id,)).fetchone()
            claimed = db_user['vip_claimed_today'] if db_user['last_vip_claim_date'] == today_str else 0
            con_lai = VIP_DAILY_LIMIT - claimed
            if qty > con_lai:
                bot.reply_to(message, f"⚠️ Bạn nhập vượt giới hạn. Hôm nay bạn chỉ được lấy thêm {con_lai} acc.")
                return
                
            accs = conn.execute("SELECT * FROM accounts WHERE status='available' ORDER BY RANDOM() LIMIT ?", (qty,)).fetchall()
            if len(accs) < qty:
                bot.reply_to(message, f"❌ Kho hàng không đủ acc! Hiện chỉ còn {len(accs)} acc.")
                return
                
            fn = f"exports/vip_free_{uuid.uuid4().hex[:6]}.txt"
            with open(fn, 'w', encoding='utf-8') as f:
                for a in accs:
                    f.write(f"{a['username']}|{a['password']}\n")
                    conn.execute("UPDATE accounts SET status='sold', sold_at=? WHERE id=?", (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a['id']))
            
            conn.execute("UPDATE users SET vip_claimed_today = ?, last_vip_claim_date = ? WHERE telegram_id = ?", (claimed + qty, today_str, user_id))
            conn.commit()
            
        user_state.pop(user_id, None)
        bot.send_message(message.chat.id, f"🎉 Đã xuất {qty} acc free dành cho VIP!", reply_markup=menu_free_vip())
        with open(fn, 'rb') as document:
            bot.send_document(message.chat.id, document, caption=f"📌 Kiểm tra acc miễn phí tại:\n\n{CHECKER_LINK}")

    # Xử lý Nhập Bill tiền nạp
    elif state == "nap_tien_cho_gia" and message.text and message.text.isdigit():
        amount = int(message.text)
        user_state[user_id] = f"nap_bill_cho_anh_{amount}"
        bot.send_message(message.chat.id, f"💵 Ghi nhận số tiền: <b>{amount:,} VNĐ</b>\n\n👉 Vui lòng gửi tấm ảnh chụp màn hình Bill giao dịch thành công tại đây:")
        
    elif str(state).startswith("nap_bill_cho_anh_") and message.content_type == 'photo':
        amount = int(str(state).split("_")[-1])
        user_state.pop(user_id, None)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO deposits (telegram_id, amount) VALUES (?, ?)", (user_id, amount))
            dep_id = cursor.lastrowid
            conn.commit()
            
        bot.send_message(message.chat.id, "✅ Đã gửi hóa đơn lên hệ thống! Vui lòng chờ Admin duyệt điểm.", reply_markup=menu_chinh(user_id))
        
        # Bắn bill về Admin
        try:
            bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
            bot.send_message(ADMIN_ID, f"💳 <b>YÊU CẦU NẠP TIỀN #{dep_id}</b>\n\n👤 User: <code>{user_id}</code>\n💵 Số tiền: <b>{amount:,} VNĐ</b>\n👉 Hãy bấm nút duyệt nạp bên dưới:", parse_mode="HTML", reply_markup=inline_duyet_bill(dep_id))
        except Exception: pass

    # ADMIN: Nhập ảnh đổi QR ngân hàng
    elif state == "adm_cho_anh_qr" and message.content_type == 'photo' and user_id == ADMIN_ID:
        user_state.pop(user_id, None)
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(QR_IMAGE_PATH, 'wb') as new_file:
            new_file.write(downloaded_file)
        bot.send_message(message.chat.id, "✅ Đã cập nhật ảnh mã QR nạp tiền mới của hệ thống!", reply_markup=menu_admin_panel())

    # ADMIN: Gửi file TXT để import acc vào kho
    elif state == "adm_cho_file_txt" and message.content_type == 'document' and user_id == ADMIN_ID:
        user_state.pop(user_id, None)
        if not message.document.file_name.endswith(".txt"):
            bot.send_message(message.chat.id, "❌ Lỗi: Bắt buộc phải là file đuôi định dạng .txt")
            return
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path).decode("utf-8", errors="ignore")
        
        success = 0
        dup = 0
        with get_db_connection() as conn:
            for line in downloaded_file.splitlines():
                line = line.strip()
                if not line: continue
                if "|" in line: parts = line.split("|", 1)
                elif ":" in line: parts = line.split(":", 1)
                else: continue
                
                u, p = parts[0].strip(), parts[1].strip()
                try:
                    conn.execute("INSERT INTO accounts (username, password) VALUES (?, ?)", (u, p))
                    success += 1
                except sqlite3.IntegrityError:
                    dup += 1
            conn.commit()
        bot.send_message(message.chat.id, f"📥 <b>KẾT QUẢ ĐỌC FILE ACC:</b>\n✅ Thành công: {success} acc\n🔁 Bị trùng: {dup} acc", parse_mode="HTML", reply_markup=menu_admin_panel())

    # ADMIN: Nhập tin nhắn để Broadcast thông báo hàng loạt
    elif state == "adm_cho_broadcast" and message.text and user_id == ADMIN_ID:
        user_state.pop(user_id, None)
        with get_db_connection() as conn:
            users = conn.execute("SELECT telegram_id FROM users").fetchall()
        sent = 0
        for u in users:
            try:
                bot.send_message(u['telegram_id'], f"📢 <b>THÔNG BÁO TỪ HỆ THỐNG:</b>\n\n{message.text}", parse_mode="HTML")
                sent += 1
                time.sleep(0.05)
            except Exception: pass
        bot.send_message(message.chat.id, f"✅ Đã truyền tải thông báo thành công tới {sent}/{len(users)} người dùng.", reply_markup=menu_admin_panel())

# ════════════════════════════════════════════════════════
# 👑 XỬ LÝ LỆNH TRỰC TIẾP CỦA CHỦ SHOP (ADMIN)
# ════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: m.text in ["📊 Dashboard", "📥 Import TXT", "📦 Xem Kho", "📷 Đổi QR", "📢 Broadcast"] and m.from_user.id == ADMIN_ID)
def handling_admin_buttons(message):
    user_id = message.from_user.id
    if message.text == "📊 Dashboard":
        with get_db_connection() as conn:
            total_u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_acc = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            avail_acc = conn.execute("SELECT COUNT(*) FROM accounts WHERE status='available'").fetchone()[0]
            revenue = conn.execute("SELECT SUM(price) FROM orders").fetchone()[0] or 0
        bot.send_message(message.chat.id, f"📊 <b>DASHBOARD QUẢN LÝ TỔNG QUAN</b>\n\n👥 Tổng người dùng: {total_u}\n📦 Tổng số acc: {total_acc}\n✅ Acc chưa bán: {avail_acc}\n💰 Doanh thu shop: {revenue:,} điểm", parse_mode="HTML")
        
    elif message.text == "📥 Import TXT":
        user_state[user_id] = "adm_cho_file_txt"
        bot.send_message(message.chat.id, "📥 Sếp vui lòng gửi file đính kèm định dạng <code>.txt</code> chứa list acc (Tài khoản|Mật khẩu) lên đây:", parse_mode="HTML")
        
    elif message.text == "📦 Xem Kho":
        with get_db_connection() as conn:
            avail = conn.execute("SELECT COUNT(*) FROM accounts WHERE status='available'").fetchone()[0]
            sold = conn.execute("SELECT COUNT(*) FROM accounts WHERE status='sold'").fetchone()[0]
        bot.send_message(message.chat.id, f"📦 <b>XEM KHO HÀNG</b>\n\n✅ Chưa bán: <b>{avail} acc</b>\n💸 Đã bán ra: <b>{sold} acc</b>", parse_mode="HTML")
        
    elif message.text == "📷 Đổi QR":
        user_state[user_id] = "adm_cho_anh_qr"
        bot.send_message(message.chat.id, "📷 Sếp gửi hình ảnh mã quét QR ngân hàng mới lên đây:")
        
    elif message.text == "📢 Broadcast":
        user_state[user_id] = "adm_cho_broadcast"
        bot.send_message(message.chat.id, "📢 Nhập nội dung thông báo sếp muốn gửi đi tới toàn bộ thành viên:")

# Lệnh ẩn gài kết quả Tài Xỉu
@bot.message_handler(commands=['gaikq'])
def cmd_gai_kq(message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2: return
    opt = args[1].lower()
    if opt in ["tai", "tài"]:
        CONFIG["force_result"] = "Tài"
        bot.reply_to(message, "🔮 Thiết lập: Gài phiên tiếp theo chắc chắn ra TÀI!")
    elif opt in ["xiu", "xỉu"]:
        CONFIG["force_result"] = "Xỉu"
        bot.reply_to(message, "🔮 Thiết lập: Gài phiên tiếp theo chắc chắn ra XỈU!")
    elif opt == "huy":
        CONFIG["force_result"] = None
        bot.reply_to(message, "🎲 Đã xóa bỏ lệnh gài kết quả.")

# Lệnh ẩn tạo Giftcode phát cho user
@bot.message_handler(commands=['taoma'])
def cmd_tao_ma_code(message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 4:
        bot.reply_to(message, "⚠️ Cú pháp: <code>/taoma [TENM_MA] [số xu] [lượt]</code>", parse_mode="HTML")
        return
    ma = args[1].upper()
    try:
        xu = int(args[2])
        luot = int(args[3])
    except ValueError: return
    
    with get_db_connection() as conn:
        try:
            conn.execute("INSERT INTO codes (code, xu, luot) VALUES (?, ?, ?)", (ma, xu, luot))
            conn.commit()
            bot.reply_to(message, f"✅ Đã tạo thành công mã Code: <b>{ma}</b>\n🎁 Trị giá: {xu:,} xu | Số lượt nhập: {luot} lượt", parse_mode="HTML")
        except sqlite3.IntegrityError:
            bot.reply_to(message, "❌ Mã này đã tồn tại rồi sếp!")

# Lệnh ẩn nạp điểm/xu trực tiếp
@bot.message_handler(commands=['congbong'])
def cmd_cong_bong_xu(message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3: return
    try:
        tg_id = int(args[1])
        amount = int(args[2])
        update_user_xu(tg_id, amount)
        bot.reply_to(message, f"👑 Đã cộng trực tiếp +<b>{amount:,} điểm</b> cho tài khoản ID <code>{tg_id}</code>.", parse_mode="HTML")
        try: bot.send_message(tg_id, f"🎁 Tài khoản của bạn được Admin cộng thưởng trực tiếp: +<b>{amount:,} xu/điểm</b>!", parse_mode="HTML")
        except Exception: pass
    except Exception: pass

# Lệnh ẩn set hạn sử dụng VIP nhanh
@bot.message_handler(commands=['setvip'])
def cmd_set_vip_day(message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3: return
    try:
        tg_id = int(args[1])
        days = int(args[2])
        exp = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with get_db_connection() as conn:
            conn.execute("UPDATE users SET vip_until = ? WHERE telegram_id = ?", (exp, tg_id))
            conn.commit()
        bot.reply_to(message, f"👑 Đã kích hoạt VIP thành công cho ID <code>{tg_id}</code> thời hạn <b>{days} ngày</b>.", parse_mode="HTML")
    except Exception: pass

@bot.message_handler(commands=['myid'])
def cmd_show_my_id(message):
    bot.reply_to(message, f"🪪 ID Telegram của bạn là: <code>{message.from_user.id}</code>", parse_mode="HTML")

# ════════════════════════════════════════════════════════
# 🎛 XỬ LÝ SỰ KIỆN CALLBACK QUERY (INLINE KEYBOARDS)
# ════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda call: True)
def handling_callback_queries(call):
    user_id = call.from_user.id
    
    # Mua VIP tự động bằng tiền ví điểm
    if call.data.startswith("buy_vip_"):
        gói = call.data.split("_")[-1]
        cost = VIP_WEEK_PRICE if gói == "week" else VIP_MONTH_PRICE
        days = 7 if gói == "week" else 30
        
        user = get_user(user_id)
        if user["xu"] < cost:
            bot.answer_callback_query(call.id, "❌ Số dư điểm ví không đủ để kích hoạt gói VIP này!", show_alert=True)
            return
            
        exp = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with get_db_connection() as conn:
            conn.execute("UPDATE users SET xu = xu - ?, vip_until = ? WHERE telegram_id = ?", (cost, exp, user_id))
            conn.commit()
            
        bot.edit_message_text(f"🎉 Bạn đã mua thành công gói thành viên VIP! Thời hạn sử dụng đến ngày: <b>{exp}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    # Duyệt duyệt nạp bill tiền của Admin
    elif call.data.startswith("approve_") or call.data.startswith("reject_"):
        if user_id != ADMIN_ID: return
        act, dep_id = call.data.split("_")
        
        with get_db_connection() as conn:
            dep = conn.execute("SELECT * FROM deposits WHERE id=?", (dep_id,)).fetchone()
            if dep and dep['status'] == 'pending':
                if act == "approve":
                    conn.execute("UPDATE deposits SET status='approved' WHERE id=?", (dep_id,))
                    conn.execute("UPDATE users SET xu = xu + ? WHERE telegram_id = ?", (dep['amount'], dep['telegram_id']))
                    conn.commit()
                    bot.edit_message_text(f"✅ Đã DUYỆT nạp thành công hóa đơn #{dep_id}.", call.message.chat.id, call.message.message_id)
                    try: bot.send_message(dep['telegram_id'], f"✅ Giao dịch nạp tiền thành công! Bạn được cộng +<b>{dep['amount']:,} điểm</b> vào tài khoản.", parse_mode="HTML")
                    except Exception: pass
                else:
                    conn.execute("UPDATE deposits SET status='rejected' WHERE id=?", (dep_id,))
                    conn.commit()
                    bot.edit_message_text(f"❌ Đã TỪ CHỐI nạp hóa đơn #{dep_id}.", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

# ════════════════════════════════════════════════════════
# 🌐 WEB SERVER MỒI CHỐNG KHÓA / SLEEP TRÊN RENDER
# ════════════════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Lien Quan & Tai Xiu Dynamic is running perfectly!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Kích hoạt mở luồng chạy Web Server mồi độc lập
threading.Thread(target=run_web_server, daemon=True).start()

# 🚀 KHỞI ĐỘNG HỆ THỐNG ĐỌC ENGINE POLLING
print("🤖 Hệ thống Bot Tổng hợp (Telebot + SQLite + Web Server) đã sẵn sàng chạy!")
bot.infinity_polling()
