import asyncio
import json
import os
import re
import time
from telethon import TelegramClient, events
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.contacts import ResolveUsernameRequest

# === ВАША КОНФИГУРАЦИЯ ===
API_ID = 26735008
API_HASH = '6c35a6247e6b6502e5b79173b22af871'
SESSION_NAME = 'inviter_session'
GROUPS_TO_PARSE = [
    '@NRWanzeigen', '@ukraineingermany1', '@ukrainians_in_germany1',
    '@berlin_ukrainians', '@deutscheukraine', '@ukraincifrankfurt',
    '@jobinde', '@hamburg_ukrainians', '@UkraineinMunich',
    '@workeuropeplus', '@UA_in_Germany', '@dusseldorfukrain',
    '@TruckingNordrheinWestfalen', '@Berlin_UA2025', '@bonn_help',
    '@GermanyTop1', '@germany_chatik', '@nrw_anzeige', '@bochum_ua',
    '@POZITYV_PUTESHESTVIYA', '@uahelpkoelnanzeigen', '@cologne_help',
    '@TheGermany1', '@germania_migranty', '@GLOBUSEXPRESS',
    '@nashipomogut', '@reklamnaia_ploshadka', '@ukr_de_essen',
    '@solingen_UA', '@keln_baraholka', '@baraholkaNRW',
    '@ukraine_dortmund', '@ukrainischinDortmund', '@UADuesseldorf',
    '@beauty_dusseldorf', '@pomoshukraineaachen', '@AhlenNRW',
    '@alsdorfua', '@aschafenburg', '@NA6R_hilft', '@bad4ua',
    '@badenbaden_lkr', '@kreiskleve', '@Bernkastel_Wittlich',
    '@bielefeldhelps', '@ukraine_bochum_support', '@uahelp_ruhrgebiet',
    '@DeutschlandBottrop', '@BS_UA_HELP', '@refugeesbremen',
    '@Bruchsal_Chat', '@Ukrainians_in_Calw', '@hilfe_ukraine_chemnitz',
    '@cottbus_ua', '@hamburg_ukraine_chat', '@Magdeburg_ukrainian',
    '@Fainy_Kiel', '@ukraine_in_Hanover', '@uahelfen_arbeit',
    '@bremen_hannover_dresden', '@ukraine_in_dresden', '@BavariaLife',
    '@ErfurtUA', '@save_ukraine_de_essen', '@MunchenBavaria',
    '@refugees_help_Koblenz', '@KaiserslauternUA', '@Karlsruhe_Ukraine',
    '@MunchenGessenBremen', '@chatFreiburg', '@Pfaffenhofen',
    '@deutschland_diaspora', '@Manner_ClubNRW', '@Ukrainer_in_Deutschland',
    '@Ukrainer_in_Wuppertal', '@ukrainians_in_hamburg_ua', '@ukrainians_berlin',
    '@berlinhelpsukrainians', '@Bayreuth_Bamberg'
]
KEYWORDS = [
    'адвокат', 'адвоката', 'адвокатом', 'адвокату',
    'юрист', 'юриста', 'юристу', 'юристом',
    'помощь адвоката', 'полиция', 'прокуратура',
    'поліція', 'прокурор',
    'lawyer', 'attorney', 'police', 'prosecutor', 'court',
    'anwalt', 'rechtsanwalt', 'polizei', 'staatsanwalt', 'gericht'
]
YOUR_GROUP = 'advocate_ua_1'  # Ваша группа для инвайтов
USERS_FILE = 'users_to_invite.json'
AUTO_MODE = os.getenv("BOT_MODE", "parse")  # parse или invite

# === Вспомогательные функции ===
def normalize(text):
    return re.sub(r'[^\w\s]', '', text.lower()).strip()

async def parse_users(client):
    users_set = set()

    for group in GROUPS_TO_PARSE:
        print(f"Парсинг группы: {group}")
        async for message in client.iter_messages(group, limit=1000):
            if message.sender_id and message.text:
                normalized_text = normalize(message.text)
                if any(kw in normalized_text for kw in KEYWORDS):
                    users_set.add(message.sender_id)
                    print(f"✅ Найден пользователь: {message.sender_id}")

    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(users_set), f, ensure_ascii=False, indent=2)

    print(f"📝 Всего найдено: {len(users_set)} пользователей")

async def invite_users(client):
    if not os.path.exists(USERS_FILE):
        print("❌ Сначала выполните парсинг пользователей!")
        return

    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)

    try:
        target_group = await client.get_entity(YOUR_GROUP)
    except:
        print("❌ Ошибка получения вашей группы. Проверьте имя группы.")
        return

    invited_today = 0

    for user_id in users[:]:
        if invited_today >= 50:
            print("📅 Дневной лимит 50 инвайтов достигнут!")
            break

        try:
            await client(InviteToChannelRequest(target_group, [user_id]))
            print(f"✅ Пользователь {user_id} приглашен")
            users.remove(user_id)
            invited_today += 1
            time.sleep(60)  # Задержка между приглашениями (1 минута)
        except Exception as e:
            print(f"❌ Ошибка приглашения {user_id}: {e}")
            users.remove(user_id)
            continue

    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    print(f"🚀 Инвайты закончены, осталось пользователей: {len(users)}")

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    if AUTO_MODE == "parse":
        print("▶️ Автоматический режим: ПАРСИНГ")
        await parse_users(client)
    elif AUTO_MODE == "invite":
        print("▶️ Автоматический режим: ИНВАЙТ")
        await invite_users(client)
    else:
        print("❌ BOT_MODE не распознан. Используйте 'parse' или 'invite'")

if __name__ == "__main__":
    asyncio.run(main())
