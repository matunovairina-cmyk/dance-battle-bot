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

# === СЕРВЕР ДЛЯ RENDER (чтобы не было ошибки портов) ===
@app.route("/")
def home():
    return "Сервер работает, бот активен!"

# === ЛОГИКА БОТА ===
@bot.message_handler(commands=['start'])
def start_message(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🔍 Найти баттлы"))
    bot.send_message(message.chat.id, 
                     "Привет! Я бот для поиска танцевальных баттлов (Hip-Hop, All Styles) по Москве и МО. Нажми кнопку ниже.", 
                     reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🔍 Найти баттлы")
def search_battles(message):
    bot.send_message(message.chat.id, "Сканирую ВКонтакте (ищу до 200 свежих постов)...")
    
    try:
        # Авторизация ВК
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        
        # Поиск по ВК (увеличили сканирование до 200 постов!)
        response = vk.newsfeed.search(q="танцевальный баттл OR hip hop battle OR all styles battle", count=200)
        items = response.get('items', [])
        found_battles = []
        
        # Целевые города МО и фильтр мусора
        mo_cities = ['москва', 'мытищи', 'королёв', 'королев', 'раменское', 'люберцы', 'подольск']
        bad_words = ['рэп', 'вокал', 'пение', 'rap battle', 'mc battle']
        
        for item in items:
            text = item.get('text', '').lower()
            
            # Умная фильтрация: ищем города и исключаем рэп
            if any(city in text for city in mo_cities) and not any(bad in text for bad in bad_words):
                owner_id = item.get('owner_id')
                post_id = item.get('id')
                link = f"https://vk.com/wall{owner_id}_{post_id}"
                
                # Короткое превью текста
                preview = item.get('text', '')[:250].replace('\n', ' ') + "..."
                found_battles.append(f"🔥 {preview}\n\n🔗 Ссылка: {link}")
        
        # Дедупликация
        found_battles = list(set(found_battles))
        
        if found_battles:
            # Отправляем все найденные баттлы (до 15 штук за раз)
            for battle in found_battles[:15]:
                bot.send_message(message.chat.id, battle)
        else:
            bot.send_message(message.chat.id, "К сожалению, сейчас в МО подходящих баттлов не найдено.")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при подключении к ВК: {e}")

# === ФОНОВЫЙ ЗАПУСК (чтобы избежать ошибки 409 Conflict) ===
def run_telegram_bot():
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling(none_stop=True)

if __name__ == "__main__":
    # 1. Запускаем Телеграм-бота в отдельном потоке
    bot_thread = threading.Thread(target=run_telegram_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # 2. Запускаем обязательный веб-сервер на порту Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
