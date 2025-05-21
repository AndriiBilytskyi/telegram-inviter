import asyncio
import json
import os
import re
import time
from telethon import TelegramClient
from telethon.errors import (
    UserPrivacyRestrictedError, UserAlreadyParticipantError,
    FloodWaitError
)
from telethon.tl.functions.channels import InviteToChannelRequest

# === Telegram Limits ===
MAX_INVITES_PER_DAY = 50
DELAY_BETWEEN_ACTIONS = 120  # seconds
PARSE_ONCE_EVERY_SECONDS = 86400  # once per day per group

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
INVITE_MESSAGE = "👋 Добрый день! Я адвокат, который помогает украинцам в Германии. Приглашаю вас посетить мой сайт: https://andriibilytskyi.com — буду рад помочь!"

USERS_FILE = 'users_to_invite.json'
GROUP_LOG = 'group_parse_log.json'
INVITED_LOG = 'invited_log.json'

ACCOUNTS = [
    {"session": "inviter_session_1", "api_id": int(os.getenv("API_ID_1")), "api_hash": os.getenv("API_HASH_1")},
    {"session": "inviter_session_2", "api_id": int(os.getenv("API_ID_2")), "api_hash": os.getenv("API_HASH_2")}
]

async def parse_users(account):
    client = TelegramClient(account["session"], account["api_id"], account["api_hash"])
    await client.start()

    try:
        with open(GROUP_LOG, 'r') as f:
            group_log = json.load(f)
    except:
        group_log = {}

    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    except:
        users = []

    known_ids = {u["id"] for u in users}
    now = time.time()

    for group in GROUPS_TO_PARSE:
        last_parsed = group_log.get(account["session"], {}).get(group, 0)
        if now < last_parsed:
            continue

        print(f"📡 {account['session']} парсит {group}")
        count = 0
        try:
            async for message in client.iter_messages(group, limit=1000):
                if message.sender_id and message.text:
                    text = re.sub(r'[^\w\s]', '', message.text.lower())
                    if any(kw in text for kw in KEYWORDS):
                        sender = await message.get_sender()
                        uid = sender.id
                        if uid not in known_ids:
                            users.append({"id": uid, "username": sender.username})
                            known_ids.add(uid)
                            count += 1
                            if count >= MAX_INVITES_PER_DAY:
                                break
            print(f"✅ {account['session']} нашел {count} новых пользователей в {group}")

            group_log.setdefault(account["session"], {})[group] = now + PARSE_ONCE_EVERY_SECONDS

        except FloodWaitError as e:
            print(f"⏳ FloodWait при парсинге {group}: ждём {e.seconds} сек")
            group_log.setdefault(account["session"], {})[group] = now + e.seconds

        except Exception as e:
            print(f"❌ Ошибка при парсинге {group}: {e}")
            group_log.setdefault(account["session"], {})[group] = now + 3600  # 1 час паузы по умолчанию

        await asyncio.sleep(1)

    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    with open(GROUP_LOG, 'w') as f:
        json.dump(group_log, f)

    await client.disconnect()

import asyncio

async def invite_users(account):
    from telethon.errors import (
        FloodWaitError, UserAlreadyParticipantError,
        UserPrivacyRestrictedError
    )

    client = TelegramClient(account["session"], account["api_id"], account["api_hash"])
    await client.start()

    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
    except:
        users = []

    try:
        with open(INVITED_LOG, 'r', encoding='utf-8') as f:
            invited = json.load(f)
    except:
        invited = []

    invited_ids = {u["id"] for u in invited}
    to_invite = [u for u in users if u["id"] not in invited_ids]
    invited_today = 0

    for user in to_invite:
        if invited_today >= MAX_INVITES_PER_DAY:
            break

        if not user.get("username"):
            print(f"⛔ Пропускаю {user['id']} — нет username для get_entity()")
            continue

        try:
            entity = await client.get_entity(user["username"])
            await client(InviteToChannelRequest(YOUR_GROUP, [entity]))

            try:
                await client.send_message(entity, INVITE_MESSAGE)
            except Exception as e:
                print(f"⚠️ Не удалось отправить сообщение {user['username']}: {e}")

            print(f"🎯 {account['session']} пригласил: {user['id']} ({user['username']})")
            invited.append(user)
            invited_today += 1
            await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

        except UserAlreadyParticipantError:
            print(f"↪️ Уже в группе: {user['username']}")
            invited.append(user)

        except UserPrivacyRestrictedError:
            print(f"⛔ Приватность мешает: {user['username']}")
            invited.append(user)

        except FloodWaitError as e:
            print(f"⏳ FloodWait: ждём {e.seconds} сек...")
            await asyncio.sleep(e.seconds)

        except Exception as e:
            print(f"⚠️ Ошибка при приглашении {user['username']}: {str(e)}")

    with open(INVITED_LOG, 'w', encoding='utf-8') as f:
        json.dump(invited, f, ensure_ascii=False, indent=2)

    await client.disconnect()

import datetime

async def main():
    print(f"🔁 Автоматический режим с ротацией аккаунтов раз в час\n")

    rotate = 0  # счётчик для чередования аккаунтов

    while True:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n🕒 Запуск цикла: {now}")

        parse_index = rotate % 2
        invite_index = (rotate + 1) % 2

        parse_account = ACCOUNTS[parse_index]
        invite_account = ACCOUNTS[invite_index]

        print(f"🔍 PARSE | {parse_account['session']}")
        await parse_users(parse_account)

        print(f"🚀 INVITE | {invite_account['session']}")
        await invite_users(invite_account)

        rotate += 1
        print("⏳ Ожидание 1 часа до следующего запуска...\n")
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
