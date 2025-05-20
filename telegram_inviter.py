import asyncio
import json
import os
import re
import time
from telethon import TelegramClient
from telethon.errors import (
    UserPrivacyRestrictedError, UserAlreadyParticipantError,
    FloodWaitError, PeerIdInvalidError, RPCError
)
from telethon.tl.functions.channels import InviteToChannelRequest

# === Telegram Limits ===
MAX_INVITES_PER_DAY = 50
MAX_MESSAGES_PER_DAY = 5
DELAY_BETWEEN_ACTIONS = 120  # секунд между действиями
MAX_GROUPS_PER_CYCLE = 3
PARSE_ONCE_EVERY_SECONDS = 86400  # каждая группа — один раз в сутки

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

GROUP_LOG = 'group_parse_log.json'
MODE_FILE = 'bot_mode.json'
ACCOUNT_INDEX_FILE = 'account_index.json'


def get_effective_mode():
    mode = os.getenv("BOT_MODE", "auto").lower()
    if mode != "auto":
        return mode

    try:
        with open(MODE_FILE, 'r') as f:
            data = json.load(f)
            last = data.get("last", "invite")
    except:
        last = "invite"

    next_mode = "parse" if last == "invite" else "invite"
    with open(MODE_FILE, 'w') as f:
        json.dump({"last": next_mode}, f)
    return next_mode


def get_next_account():
    try:
        with open(ACCOUNT_INDEX_FILE, 'r') as f:
            idx = json.load(f).get("last", 0)
    except:
        idx = 0

    next_idx = (idx + 1) % len(ACCOUNTS)
    with open(ACCOUNT_INDEX_FILE, 'w') as f:
        json.dump({"last": next_idx}, f)
    return ACCOUNTS[next_idx]


def should_parse(group):
    try:
        with open(GROUP_LOG, 'r') as f:
            log = json.load(f)
    except:
        log = {}

    now = time.time()
    last_time = log.get(group, 0)
    if now - last_time >= PARSE_ONCE_EVERY_SECONDS:
        log[group] = now
        with open(GROUP_LOG, 'w') as f:
            json.dump(log, f)
        return True
    return False


async def parse_users(client):
    users_dict = {}
    for group in GROUPS_TO_PARSE:
        if not should_parse(group):
            continue
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
    else:
        print("⚠️ Пользователи не найдены. Файл не создан.")


async def invite_users(client):
    if not os.path.exists(USERS_FILE):
        print("⚠️ Файл users_to_invite.json не найден.")
        return

    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)

    invited_today = 0
    for user in users:
        if invited_today >= MAX_INVITES_PER_DAY:
            print("✅ Лимит приглашений на сегодня исчерпан.")
            break

        try:
            entity = await client.get_entity(user['id'])
            await client(InviteToChannelRequest(YOUR_GROUP, [entity]))
            print(f"🎯 Приглашён: {user['id']} @{user.get('username')}")
            invited_today += 1
            await asyncio.sleep(DELAY_BETWEEN_ACTIONS)
        except UserAlreadyParticipantError:
            print(f"➡️ Уже в группе: {user['id']}")
        except UserPrivacyRestrictedError:
            print(f"⛔ Приватность: {user['id']}")
        except FloodWaitError as e:
            print(f"⏳ FloodWait: ждём {e.seconds} сек...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"⚠️ Ошибка: {user['id']} — {e}")

if __name__ == "__main__":
    asyncio.run(main())
