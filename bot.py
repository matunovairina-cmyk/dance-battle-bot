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
    r'\bзеленоград\b', r'\bзеленограде\b',
    r'\bподмосковье\b', r'\bподмосковья\b'
]

# Черный список других городов (исправлен синтаксис \b)
EXCLUDE_CITIES_PATTERNS = [
    r'\bнижний новгород\b', r'\bсамара\b', r'\bсимферополь\b', r'\bчебоксары\b',
    r'\bказань\b', r'\bекатеринбург\b', r'\bновосибирск\b', r'\bкраснодар\b',
    r'\bсочи\b', r'\bростов\b', r'\bуфа\b', r'\bпермь\b', r'\bчелябинск\b',
    r'\bомск\b', r'\bвладивосток\b', r'\bхабаровск\b', r'\bворонеж\b',
    r'\bновошахтинск\b', r'\bтихорецк\b', r'\bтихорецке\b', r'\bтверь\b', r'\bтула\b'
]

# Исключаем контекст, где Москва упоминается лишь как родина участника/судьи
ORIGIN_MOSCOW_PATTERNS = [
    r'из\s+(г\.\s*)?москв', r'педагог\s+из\s+москв', r'гость\s+из\0москв',
    r'судья\s+из\s+москв', r'приедет\s+из\s+москв', r'г\.\s*москва\)'
]

# Обязательные ключевые слова анонса баттла
BATTLE_PATTERNS = [
    r'\bбатл\b', r'\bбаттл\b', r'\bбатлы\b', r'\bбаттлы\b', 
    r'\bbattle\b', r'\battles\b'
]

# Прошедшие события, результаты и победы
PAST_EVENTS_PATTERNS = [
    r'вошел в', r'вошла в', r'занял', r'заняла', r'победитель', r'победил',
    r'победила', r'место', r'результаты', r'итоги', r'диплом', r'кубок',
    r'поздравляем', r'гордимся', r'состоялся', r'состоялось', r'прошел баттл',
    r'прошел батл', r'прошли баттлы', r'вспомним', r'как это было'
]

# Интенсивы, мастер-классы и мусор без баттлов
JUNK_PATTERNS = [
    # Брейк-данс
    r'брейк', r'брейкинг', r'breakdance', r'breaking', r'bboy', r'bgirl',
    # Обучение и мастер-классы
    r'интенсив', r'мастер-класс', r'мастер класс', r'воркшоп', r'лаборатор',
    r'представляем педагогов', r'представляем экспертов', r'набор в группу',
    r'занятия в студии', r'открыт набор',
    # Разное
    r'караоке', r'вокал', r'пение', r'рэп', r'кавказск', r'тодес', r'k-pop',
    r'аренда зала', r'розыгрыш', r'скидка', r'абонемент', r'вакансия', r'работа'
]

def get_text_snippet(text):
    """Создает очищенный фрагмент текста для предотвращения дубликатов спама"""
    cleaned = re.sub(r'\W+', '', text.lower())
    return cleaned[:80]

def is_valid_battle_post(text):
    text_lower = text.lower()

    # 1. Наличие слова "баттл"
    if not any(re.search(p, text_lower) for p in BATTLE_PATTERNS):
        return False

    # 2. Исключаем прошлые результаты и отчеты о победах
    if any(re.search(p, text_lower) for p in PAST_EVENTS_PATTERNS):
        return False

    # 3. Исключаем мастер-классы, брейк-данс и рекламу
    if any(re.search(p, text_lower) for p in JUNK_PATTERNS):
        return False

    # 4. Исключаем другие города
    if any(re.search(p, text_lower) for p in EXCLUDE_CITIES_PATTERNS):
        return False

    # 5. Проверяем, что Москва/МО не указаны просто как город происхождения педагога
    if any(re.search(p, text_lower) for p in ORIGIN_MOSCOW_PATTERNS):
        # Если при этом нет прямого указания на проведение в Москве
        if not re.search(r'пройдет в москве|место проведения:?\s*москва|г\.\s*москва,', text_lower):
            return False

    # 6. Обязательное наличие Москвы или Подмосковья
    if not any(re.search(p, text_lower) for p in MOSCOW_MO_PATTERNS):
        return False

    return True

# === ЛОГИКА БОТА ===
@bot.message_handler(commands=['start'])
def start_message(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🔍 Найти баттлы"))
    bot.send_message(
        message.chat.id, 
        "Привет! Ищу Hip-Hop и All Styles баттлы (Москва и МО). Нажми кнопку ниже.", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "🔍 Найти баттлы")
def search_battles(message):
    bot.send_message(message.chat.id, "Сканирую актуальные анонсы баттлов в Москве и МО...")
    
    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        
        # Запросы нацелены строго на анонсы мероприятий
        queries = [
            "москва танцевальный баттл анонс OR регистрация",
            "москва hip hop battle OR all styles battle",
            "лобня баттл OR троицк баттл OR лыткарино баттл"
        ]
        
        raw_items = []
        for q in queries:
            res = vk.newsfeed.search(q=q, count=200)
            raw_items.extend(res.get('items', []))
            
        found_battles = []
        seen_links = set()
        seen_texts = set()
        
        for item in raw_items:
            text = item.get('text', '')
            if not text:
                continue
                
            owner_id = item.get('owner_id')
            post_id = item.get('id')
            link = f"https://vk.com/wall{owner_id}_{post_id}"
            
            # Проверка дубликатов по ссылке и по содержанию текста
            text_snippet = get_text_snippet(text)
            if link in seen_links or text_snippet in seen_texts:
                continue
                
            if is_valid_battle_post(text):
                seen_links.add(link)
                seen_texts.add(text_snippet)
                preview = text[:250].replace('\n', ' ') + "..."
                found_battles.append(f"🔥 {preview}\n\n🔗 Ссылка: {link}")
        
        if found_battles:
            for battle in found_battles[:10]:
                bot.send_message(message.chat.id, battle)
        else:
            bot.send_message(message.chat.id, "На ближайшее время актуальных баттлов в Москве и МО не найдено.")
            
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
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
