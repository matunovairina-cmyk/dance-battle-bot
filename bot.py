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

# === СТРОГИЕ ФИЛЬТРЫ ===

# Разрешенные локации (Москва, МО, Лобня, Троицк, Лыткарино)
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

# Черный список других городов, чтобы исключить регионы
EXCLUDE_CITIES_PATTERNS = [
    r'\бнижний новгород\b', r'\бсамара\b', r'\бсимферополь\b', r'\бчебоксары\b',
    r'\бказань\b', r'\бекатеринбург\b', r'\бновосибирск\b', r'\бкраснодар\b',
    r'\бсочи\b', r'\бростов\b', r'\буфа\b', r'\бпермь\b', r'\бчелябинск\b',
    r'\бомск\b', r'\бвладивосток\b', r'\бхабаровск\b', r'\бворонеж\b',
    r'\бновошахтинск\b'
]

# Обязательные слова (ищем именно баттлы)
BATTLE_PATTERNS = [
    r'\bбатл\b', r'\bбаттл\b', r'\bбатлы\b', r'\bбаттлы\b', 
    r'\bbattle\b', r'\battles\b'
]

# ЖЕСТКИЙ МУСОР (Брейк-данс, расписания, новости, наборы, реклама)
JUNK_PATTERNS = [
    # Брейк-данс (удаляем полностью по вашему требованию)
    r'брейк', r'брейкинг', r'breakdance', r'breaking', r'bboy', r'bgirl',
    # Расписания и общие анонсы
    r'расписание', r'планируйте', r'день рождения', r'итоги', r'поздравляем',
    # Обучение и реклама студий
    r'открыт набор', r'набор в группу', r'занятия в студии', r'наш тренер',
    r'аренда зала', r'аренда студии', r'розыгрыш', r'скидка', r'абонемент',
    # Другие танцевальные стили и направления
    r'дискотека', r'кавер', r'k-pop', r'к-поп', r'cover dance',
    r'рэп', r'вокал', r'пение', r'кавказск', r'тодес',
    # Разное
    r'продам', r'куплю', r'вакансия', r'работа', r'фотограф', r'визажист'
]

def is_valid_battle_post(text):
    text_lower = text.lower()

    # 1. Должно быть слово баттл/батл
    if not any(re.search(p, text_lower) for p in BATTLE_PATTERNS):
        return False

    # 2. Строго Москва или МО (включая Лобню)
    if not any(re.search(p, text_lower) for p in MOSCOW_MO_PATTERNS):
        return False

    # 3. Никаких других городов
    if any(re.search(p, text_lower) for p in EXCLUDE_CITIES_PATTERNS):
        return False

    # 4. Отсекаем брейк-данс, расписания, наборы и мусор
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
        "Привет! Ищу Hip-Hop и All Styles баттлы строго в Москве и МО (без брейк-данса и мусора). Нажми кнопку ниже.", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "🔍 Найти баттлы")
def search_battles(message):
    bot.send_message(message.chat.id, "Фильтрую анонсы баттлов (Москва и МО)...")
    
    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        
        # Точечные поисковые запросы
        queries = [
            "москва танцевальный баттл",
            "москва hip hop battle OR москва all styles battle",
            "лобня баттл OR москва баттл танцы"
        ]
        
        raw_items = []
        for q in queries:
            res = vk.newsfeed.search(q=q, count=200)
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
            bot.send_message(message.chat.id, "Пока что подходящих баттлов по вашим критериям не найдено.")
            
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
