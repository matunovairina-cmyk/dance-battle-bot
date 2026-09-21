import telebot
from telebot import types
import vk_api
import time
import re
from datetime import datetime, timedelta

# ВСТАВЬТЕ ВАШИ КЛЮЧИ СЮДА
VK_TOKEN = 'bd024558bd024558bd02455812be41a353bbd02bd024558d7adb85384607e6310595f8c'
TG_TOKEN = '8311376717:AAEftfCMxf_GdMIf8h7gcFBV0RAvraMuSQw'

bot = telebot.TeleBot(TG_TOKEN)

# --- Настройки поиска ВКонтакте ---
SEARCH_QUERIES = [
    "баттл хип-хоп", "battle hip-hop", "баттл hip-hop",
    "баттл all styles", "баттл allstyles", "танцевальный баттл", 
    "dance battle", "танцевальные баттлы", "хип хоп баттл"
]

LOCAL_STUDIOS_MO = [
    'kidsinballet', 'impulse_mytishchi', 'himki_dance', 'balashikha_dance_life',
    'podolsk_dance_hall', 'korolev_dance', 'odintsovo_dance_club', 'krg_dance',
    'lubertsy_hiphop', 'serpuhov_dance', 'kolomna_dance_events', 'dolgoprudny_dance',
    'pushkin_dancers', 'schelkovo_dance', 'zhukovskiy_dance'
]

TARGET_MONTHS_STRICT = [
    r'\b(?:[1-9]|[12]\d|3[01])\s*(?:январ|феврал|март|апрел|ма[яей]|октябр|ноябр|декабр)',
    r'\b(?:в|на)\s+(?:январ|феврал|март|апрел|ма[яей]|октябр|ноябр|декабр)',
    r'\b(?:января|февраля|марта|апреля|мая|октября|ноября|декабря)\b'
]

MO_CITIES = [
    'лобн', 'мытищ', 'химк', 'балаших', 'подольск', 'королев', 'королёв',
    'одинцов', 'красногорск', 'люберц', 'серпухов', 'коломн', 'дольгопрудн',
    'пушкин', 'щелков', 'жуковск', 'реутов', 'сергиев посад',
    'раменск', 'истр', 'дубн', 'электросталь', 'железнодорожн',
    'подмосковь', 'московской област'
]

FOREIGN_REGIONS = [
    'уфа', 'башкортостан', 'симферополь', 'крым', 'красноярск', 
    'самар', 'тверь', 'минусинск', 'тихорецк', 'казань', 'екатеринбург',
    'новосибирск', 'нижний новгород', 'санкт-петербург', 'спб', 'питер', 
    'новочебоксарск', 'пр-кт октября', 'проспект октября'
]

def is_valid_event(text, group_city):
    text_lower = text.lower()
    if 'рэп' in text_lower or 'rap' in text_lower or 'fan bingbing' in text_lower:
        return False
    if any(region in text_lower for region in FOREIGN_REGIONS):
        return False
    if not any(re.search(m, text_lower) for m in TARGET_MONTHS_STRICT):
        return False
    has_battle = any(word in text_lower for word in ['баттл', 'battle', 'джем', 'jam', 'контест', 'contest'])
    if not has_battle:
        return False
    has_dance = any(word in text_lower for word in ['hip-hop', 'хип-хоп', 'all styles', 'allstyles', 'брейкинг', 'breaking', 'house', 'locking', 'popping', 'танец', 'танцор'])
    if not has_dance:
        return False
    text_for_loc = re.sub(r'(г\.\s*москва|г\.москва|из\s+москвы)', '', text_lower)
    loc_in_text = any(loc in text_for_loc for loc in ['москв', 'мск'] + MO_CITIES)
    loc_in_profile = any(city in group_city for city in ['москва'] + MO_CITIES)
    return loc_in_text or loc_in_profile

def get_word_fingerprint(text):
    words = re.findall(r'[а-яa-z]{4,}', text.lower())
    return set(words[:25])

def find_battles():
    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
    except Exception:
        return "error"

    found_posts = []
    seen_urls = set()
    seen_group_ids = set()
    seen_fingerprints = []
    start_time = int((datetime.now() - timedelta(days=25)).timestamp())

    for query in SEARCH_QUERIES:
        try:
            response = vk.newsfeed.search(q=query, count=100, start_time=start_time, extended=1, fields='city')
            groups_cities = {g['id']: g.get('city', {}).get('title', '').lower() for g in response.get('groups', [])}

            for item in response.get('items', []):
                if item.get('owner_id', 0) >= 0: continue
                group_id = abs(item['owner_id'])
                if group_id in seen_group_ids: continue

                post_url = f"https://vk.com/wall{item['owner_id']}_{item['id']}"
                if post_url in seen_urls: continue
                
                text = item.get('text', '')
                post_fingerprint = get_word_fingerprint(text)
                is_duplicate = any(len(post_fingerprint & seen_fp) >= 10 for seen_fp in seen_fingerprints)
                if is_duplicate: continue

                group_city = groups_cities.get(group_id, "")
                if is_valid_event(text, group_city):
                    date_posted = datetime.fromtimestamp(item['date']).strftime('%d.%m.%Y')
                    found_posts.append({'date': date_posted, 'url': post_url, 'text': text[:400] + "..."})
                    seen_urls.add(post_url)
                    seen_group_ids.add(group_id)
                    seen_fingerprints.append(post_fingerprint)
            time.sleep(0.4)
        except Exception:
            pass

    for group in LOCAL_STUDIOS_MO:
        try:
            response = vk.wall.get(domain=group, count=25)
            for item in response.get('items', []):
                group_id = abs(item['owner_id'])
                if group_id in seen_group_ids: continue
                post_url = f"https://vk.com/wall{item['owner_id']}_{item['id']}"
                if post_url in seen_urls: continue
                text = item.get('text', '')
                post_fingerprint = get_word_fingerprint(text)
                if any(len(post_fingerprint & seen_fp) >= 10 for seen_fp in seen_fingerprints): continue

                if any(re.search(m, text.lower()) for m in TARGET_MONTHS_STRICT) and any(w in text.lower() for w in ['баттл', 'battle']):
                    date_posted = datetime.fromtimestamp(item['date']).strftime('%d.%m.%Y')
                    found_posts.append({'date': date_posted, 'url': post_url, 'text': text[:400] + "..."})
                    seen_urls.add(post_url)
                    seen_group_ids.add(group_id)
                    seen_fingerprints.append(post_fingerprint)
            time.sleep(0.4)
        except Exception:
            pass

    return found_posts

# --- Обработчики Телеграм-бота ---

@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("🔍 Найти баттлы")
    markup.add(btn)
    bot.send_message(message.chat.id, "Привет! Я бот для поиска танцевальных баттлов по Москве и Подмосковью. Нажми кнопку ниже, чтобы запустить сканирование ВКонтакте.", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🔍 Найти баттлы":
        bot.send_message(message.chat.id, "⏳ Запускаю поиск по ВК. Это займет около 1-2 минут, пожалуйста, подождите...")
        
        results = find_battles()
        
        if results == "error":
            bot.send_message(message.chat.id, "❌ Ошибка авторизации ВКонтакте. Проверьте VK_TOKEN.")
            return
            
        if not results:
            bot.send_message(message.chat.id, "Ничего нового не найдено 🤷‍♀️")
            return
            
        bot.send_message(message.chat.id, f"🎯 Найдено уникальных баттлов: {len(results)}")
        
        # Отправляем каждый пост отдельным сообщением
        for idx, post in enumerate(results, 1):
            msg = f"🔥 *Баттл #{idx}*\n📅 Опубликовано: {post['date']}\n\n{post['text']}\n\n👉 [Ссылка на пост ВК]({post['url']})"
            bot.send_message(message.chat.id, msg, parse_mode='Markdown', disable_web_page_preview=True)
            time.sleep(0.5) # Пауза, чтобы Телеграм не заблокировал за спам
    else:
        bot.send_message(message.chat.id, "Используйте кнопку '🔍 Найти баттлы' в меню.")

if __name__ == '__main__':
    print("Бот запущен. Напишите ему в Телеграме /start")
    bot.infinity_polling()