import asyncio
import json
import os
import re
import time
from telethon import TelegramClient
from telethon.errors import UserPrivacyRestrictedError, UserAlreadyParticipantError, FloodWaitError
from telethon.tl.functions.channels import InviteToChannelRequest

# === Telegram Limits ===
MAX_INVITES_PER_DAY = 20
MAX_MESSAGES_PER_DAY = 5
DELAY_BETWEEN_ACTIONS = 120  # секунд между действиями

# === Аккаунты ===
ACCOUNTS = [
    {
        "session": "inviter_session_1",
        "api_id": 26735008,
        "api_hash": "6c35a6247e6b6502e5b79173b22af871"
    },
    {
        "session": "inviter_session_2",
        "api_id": 20903513,
        "api_hash": "0eb01bf47aeac4cbfd89fff140a4e06d"
    }
]

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

YOUR_GROUP = 'advocate_ua_1'
USERS_FILE = 'users_to_invite.json'
INVITE_MESSAGE = "👋 Добрый день! Я адвокат, который помогает украинцам в Германии. Приглашаю вас посетить мой сайт: https://andriibilytskyi.com — буду рад помочь!"

async def parse_users(client):
    users_dict = {}
    for group in GROUPS_TO_PARSE:
        print(f"📡 Парсинг группы: {group}")
        try:
            async for message in client.iter_messages(group, limit=1000):
                if message.sender_id and message.text:
                    text = re.sub(r'[^\w\s]', '', message.text.lower())
                    if any(kw in text for kw in KEYWORDS):
                        sender = await message.get_sender()
                        uid = sender.id
                        if uid not in users_dict:
                            users_dict[uid] = {"id": uid, "username": sender.username}
                            print(f"✅ Найден пользователь: {uid} @{sender.username or '—'}")
        except Exception as e:
            print(f"❌ Ошибка в {group}: {e}")

    print(f"📊 Найдено пользователей: {len(users_dict)}")

    if users_dict:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(users_dict.values()), f, ensure_ascii=False, indent=2)

        try:
            print("📤 Пытаемся отправить users_to_invite.json в Избранное...")
            await client.send_file('me', USERS_FILE, caption="👥 Список пользователей для инвайта")
            print("✅ Файл отправлен в Saved Messages")
        except Exception as e:
            print(f"❌ Не удалось отправить файл: {e}")
    else:
        print("⚠️ Пользователи не найдены. Файл не создан.")

async def invite_users_with_fallback():
    for account in ACCOUNTS:
        client = TelegramClient(account["session"], account["api_id"], account["api_hash"])
        await client.start()
        print(f"🚀 Работаем через сессию: {account['session']}")

        try:
            await parse_users(client)
            break
        except FloodWaitError as e:
            print(f"⏳ FloodWait: Telegram требует паузу {e.seconds} сек. Ждём...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"❌ Ошибка с аккаунтом {account['session']}: {e}")
        finally:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(invite_users_with_fallback())
