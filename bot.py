import os
import re
import threading
import telebot
import vk_api
from flask import Flask

# === НАСТРОЙКИ ТОКЕНОВ ===
TELEGRAM_TOKEN = "8311376717:AAEftfCMxf_GdMIf8h7gcFBV0RAvraMuSQw"
VK_TOKEN = "bd024558bd024558bd02455812be41a353bbd02bd024558d7adb85384607e6310595f8c"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# === СЕРВЕР ДЛЯ RENDER ===
@app.route("/")
def home():
    return "Сервер работает, бот активен!"

# === ФИЛЬТРЫ РЕГИОНОВ И МУСОРА ===

# Разрешенные регионы (Москва, Подмосковье, Лобня, Троицк, Лыткарино и т.д.)
MOSCOW_MO_PATTERNS = [
    r'\bмосква\b', r'\bмоскве\b', r'\bмоскву\b', r'\bмск\b',
    r'\bлобня\b', r'\bлобне\b', r'\bлобню\b',
    r'\bтроицк\b', r'\bтроицке\b',
    r'\bлыткарино\b',
    r'\bхимки\b', r'\bхимках\b',
    r'\bмытищи\b', r'\bмытищах\b',
    r'\bкоролев\b', r'\bкоролёв\b', r'\bкоролеве\b', r'\bкоролёве\b',
    r'\bподольск\b', r'\bподольске\b',
    r'\bкрасногорск\b', r'\bкрасногорске\b',
    r'\bлюберцы\b', r'\bлюберцах\b',
    r'\bбалашиха\b', r'\bбалашихе\b',
    r'\bдолгопрудный\b', r'\bдолгопрудном\b',
    r'\bодинцово\b',
    r'\bщёлково\b', r'\bщелково\b',
    r'\bраменское\b',
    r'\bэлектросталь\b',
    r'\bжуковский\b',
    r'\bпушкино\b',
    r'\bзеленоград\b', r'\bзеленограде\b',
    r'\bподмосковье\b', r'\bподмосковья\b'
]

# Строго запрещенные другие города (чтобы не пролетали Самара, Нижний Новгород и т.д.)
EXCLUDE_CITIES_PATTERNS = [
    r'\bнижний новгород\b', r'\bсамара\b', r'\bсимферополь\b', r'\bчебоксары\b',
    r'\bказань\b', r'\bекатеринбург\b', r'\bновосибирск\b', r'\bкраснодар\b',
    r'\bсочи\b', r'\bростов\b', r'\bуфа\b', r'\bпермь\b', r'\bчелябинск\b',
    r'\bомск\b', r'\bвладивосток\b', r'\bхабаровск\b', r'\bворонеж\b'
]

# Обязательные ключевые слова баттлов
BATTLE_PATTERNS = [
    r'\bбатл\b', r'\bбаттл\b', r'\bбатлы\b', r'\bбаттлы\b', 
    r'\bbattle\b', r'\battles\b'
]

# Мусор (караоке, вокал, реклама тренеров, наборы, розыгрыши)
JUNK_PATTERNS = [
    r'караоке', r'вокал', r'пение', r'рэп', r'rap battle', r'mc battle',
    r'открыт набор', r'набор в группу', r'занятия в студии',
    r'аренда зала', r'аренда студии', r'розыгрыш', r'наш тренер',
    r'дискотека', r'кавер', r'k-pop', r'к-поп', r'cover dance',
    r'продам', r'куплю', r'вакансия', r'работа', r'фотограф', r'визажист'
]

def is_valid_battle_post(text):
    text_lower = text.lower()

    # 1. Должно быть слово "баттл" / "батл"
    if not any(re.search(p, text_lower) for p in BATTLE_PATTERNS):
        return False

    # 2. Строго должна упоминаться Москва или МО
    if not any(re.search(p, text_lower) for p in MOSCOW_MO_PATTERNS):
        return False

    # 3. Не должно быть других городов из черного списка
    if any(re.search(p, text_lower) for p in EXCLUDE_CITIES_PATTERNS):
        return False

    # 4. Отсекаем мусор (караоке, наборы, тренеров и т.д.)
    if any(re.search(p, text_lower) for p in JUNK_PATTERNS):
        return False

    return True

# === ЛОГИКА БОТА ===
@bot.message_handler(commands=['start'])
def start_message(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🔍 Найти баттлы"))
    bot.send_message(
        message.chat.id, 
        "Привет! Я бот для поиска танцевальных баттлов строго по Москве и МО. Нажми кнопку ниже.", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "🔍 Найти баттлы")
def search_battles(message):
    bot.send_message(message.chat.id, "Ищу актуальные танцевальные баттлы в Москве и МО...")
    
    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        
        # Запросы с явным указанием Москвы и МО в поисковой выдаче ВК
        queries = [
            "москва танцевальный баттл OR москва баттл",
            "мск баттл OR химки баттл OR лобня баттл",
            "all styles battle москва OR hip hop battle москва"
        ]
        
        raw_items = []
        for q in queries:
            res = vk.newsfeed.search(q=q, count=150)
            raw_items.extend(res.get('items', []))
            
        found_battles = []
        seen_links = set()
        
        for item in raw_items:
            text = item.get('text', '')
            if not text:
                continue
                
            owner_id = item.get('owner_id')
            post_id = item.get('id')
            link = f"https://vk.com/wall{owner_id}_{post_id}"
            
            if link in seen_links:
                continue
                
            if is_valid_battle_post(text):
                seen_links.add(link)
                preview = text[:250].replace('\n', ' ') + "..."
                found_battles.append(f"🔥 {preview}\n\n🔗 Ссылка: {link}")
        
        if found_battles:
            for battle in found_battles[:10]:
                bot.send_message(message.chat.id, battle)
        else:
            bot.send_message(message.chat.id, "Пока что новых баттлов по Москве и МО не нашлось. Попробуйте позже!")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при сканировании: {e}")

# === ЗАПУСК В ОБЛАКЕ RENDER ===
def run_telegram_bot():
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling(none_stop=True)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
