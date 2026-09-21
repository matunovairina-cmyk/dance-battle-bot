import os
import threading
import telebot
import vk_api
from flask import Flask

# === НАСТРОЙКИ ТОКЕНОВ ===
# Вставьте сюда ваши настоящие токены внутри кавычек
TELEGRAM_TOKEN = "8311376717:AAEftfCMxf_GdMIf8h7gcFBV0RAvraMuSQw"
VK_TOKEN = "bd024558bd024558bd02455812be41a353bbd02bd024558d7adb85384607e6310595f8c"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# === СЕРВЕР ДЛЯ RENDER (держит порт открытым 24/7) ===
@app.route("/")
def home():
    return "Бот работает в облаке!"

# === ТОЧНАЯ ЛОГИКА ПОИСКА ===
@bot.message_handler(commands=['start'])
def start_message(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🔍 Найти баттлы"))
    bot.send_message(
        message.chat.id, 
        "Привет! Я бот для поиска танцевальных баттлов (Hip-Hop, All Styles) по Москве и МО. Нажми кнопку ниже.", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "🔍 Найти баттлы")
def search_battles(message):
    bot.send_message(message.chat.id, "Сканирую ВКонтакте по расширенным фильтрам...")
    
    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        
        # Точный поисковый запрос по ВК (сканирует до 200 свежих постов)
        query = "танцевальный баттл OR танцевальный батл OR hip hop battle OR all styles OR dance battle"
        response = vk.newsfeed.search(q=query, count=200)
        items = response.get('items', [])
        found_battles = []
        
        # Расширенный список городов Москвы и МО (включая Лобню)
        mo_cities = [
            'москва', 'мытищи', 'королёв', 'королев', 'раменское', 'люберцы', 
            'подольск', 'лобня', 'долгопрудный', 'химки', 'балашиха', 'красногорск', 
            'одинцово', 'щёлково', 'щелково', 'электросталь', 'жуковский', 'пушкино'
        ]
        
        # Исключение нецелевых тем
        bad_words = [
            'рэп', 'вокал', 'пение', 'rap battle', 'mc battle', 'рэп-баттл', 'рэп батл',
            'битбокс', 'beatbox', 'стихи', 'поэт', 'кулинар', 'маникюр', 'продам', 
            'куплю', 'аренда', 'вакансия', 'работа', 'фотограф', 'визажист', 'скидка'
        ]
        
        # Обязательный танцевальный контекст
        dance_words = [
            'танец', 'танцы', 'танцевальный', 'hip-hop', 'hip hop', 'all styles', 
            'break', 'popping', 'house', 'dancer', 'батл', 'баттл'
        ]
        
        for item in items:
            text = item.get('text', '').lower()
            
            has_dance_context = any(word in text for word in dance_words)
            has_city = any(city in text for city in mo_cities)
            has_junk = any(bad in text for bad in bad_words)
            
            if has_city and has_dance_context and not has_junk:
                owner_id = item.get('owner_id')
                post_id = item.get('id')
                link = f"https://vk.com/wall{owner_id}_{post_id}"
                
                preview = item.get('text', '')[:250].replace('\n', ' ') + "..."
                found_battles.append(f"🔥 {preview}\n\n🔗 Ссылка: {link}")
        
        # Убираем дубликаты
        found_battles = list(set(found_battles))
        
        if found_battles:
            for battle in found_battles[:15]:
                bot.send_message(message.chat.id, battle)
        else:
            bot.send_message(message.chat.id, "Подходящих танцевальных баттлов пока не найдено.")
            
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
    # Запускаем бота в фоновом режиме
    bot_thread = threading.Thread(target=run_telegram_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем сервер для удерживания порта на Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
