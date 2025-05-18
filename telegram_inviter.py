import asyncio
import json
import os
import re
import time
from telethon import TelegramClient, events
from telethon.tl.functions.channels import InviteToChannelRequest, GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsRecent
from telethon.errors import UserPrivacyRestrictedError, UserAlreadyParticipantError, FloodWaitError

API_ID = 26735008
API_HASH = '6c35a6247e6b6502e5b79173b22af871'
SESSION_NAME = 'inviter_session'

# === Telegram Limits ===
MAX_INVITES_PER_DAY = 50            # Телеграм ограничивает ~50 инвайтов в день
MAX_MESSAGES_PER_DAY = 20           # Телеграм разрешает отправить ~20 личных сообщений незнакомцам в сутки
DELAY_BETWEEN_ACTIONS = 60          # Задержка между действиями (секунд)

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
AUTO_MODE = os.getenv("BOT_MODE", "parse")

INVITE_MESSAGE = "👋 Добрый день! Я адвокат, который помогает украинцам в Германии. Приглашаю вас посетить мой сайт: https://andriibilytskyi.com — буду рад помочь!"

def normalize(text):
    return re.sub(r'[^\w\s]', '', text.lower()).strip()

async def parse_users(client):
    users_dict = {}
    for group in GROUPS_TO_PARSE:
        print(f"Парсинг группы: {group}")
        try:
            async for message in client.iter_messages(group, limit=1000):
                if message.sender_id and message.text:
                    text = normalize(message.text)
                    if any(kw in text for kw in KEYWORDS):
                        sender = await message.get_sender()
                        uid = sender.id
                        if uid not in users_dict:
                            users_dict[uid] = {"id": uid, "username": sender.username}
                            print(f"✅ Найден пользователь: {uid} @{sender.username or '—'}")
        except Exception as e:
            print(f"❌ Ошибка при парсинге {group}: {e}")

    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(users_dict.values()), f, ensure_ascii=False, indent=2)

    print(f"📝 Всего найдено: {len(users_dict)} пользователей")
    try:
        await client.send_file('me', USERS_FILE, caption="👥 Список пользователей для инвайта")
    except Exception as e:
        print(f"❌ Не удалось отправить файл: {e}")

async def is_member(client, group_entity, user):
    try:
        async for participant in client.iter_participants(group_entity, search=user.get("username") or str(user.get("id"))):
            if participant.id == user.get("id"):
                return True
    except:
        pass
    return False

async def invite_users(client):
    if not os.path.exists(USERS_FILE):
        print("❌ Сначала выполните парсинг пользователей!")
        return

    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)

    try:
        group_entity = await client.get_entity(YOUR_GROUP)
    except Exception as e:
        print(f"❌ Не удалось получить группу: {e}")
        return

    invited_today = 0
    messaged_today = 0

    for user in users[:]:
        if invited_today >= MAX_INVITES_PER_DAY and messaged_today >= MAX_MESSAGES_PER_DAY:
            print("🚫 Достигнуты лимиты на инвайты и сообщения")
            break

        try:
            if await is_member(client, group_entity, user):
                print(f"🔁 Уже состоит: {user['id']} (@{user.get('username', '-')})")
                users.remove(user)
                continue

            if user.get("username"):
                entity = await client.get_input_entity(f"@{user['username']}")
            else:
                entity = await client.get_input_entity(user['id'])

            if invited_today < MAX_INVITES_PER_DAY:
                await client(InviteToChannelRequest(group_entity, [entity]))
                print(f"✅ Приглашён: {user['id']} (@{user.get('username', '—')})")
                invited_today += 1
            else:
                raise UserPrivacyRestrictedError(None)

        except UserPrivacyRestrictedError:
            if messaged_today < MAX_MESSAGES_PER_DAY:
                try:
                    if user.get("username"):
                        await client.send_message(f"@{user['username']}", INVITE_MESSAGE)
                        print(f"✉️ Личное сообщение отправлено: @{user['username']}")
                        messaged_today += 1
                except Exception as e:
                    print(f"❌ Ошибка при отправке ЛС {user['id']}: {e}")
        except UserAlreadyParticipantError:
            print(f"🔁 Уже в группе: {user['id']}")
        except FloodWaitError as e:
            print(f"⏳ FloodWait: Telegram требует паузу {e.seconds} сек. Ждём...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"❌ Ошибка приглашения {user['id']}: {e}")

        users.remove(user)
        time.sleep(DELAY_BETWEEN_ACTIONS)

    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    print(f"🚀 Завершено: {invited_today} инвайтов, {messaged_today} сообщений. Осталось пользователей: {len(users)}")

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    if AUTO_MODE == "parse":
        print("▶️ Режим: ПАРСИНГ")
        await parse_users(client)
    elif AUTO_MODE == "invite":
        print("▶️ Режим: ИНВАЙТ")
        await invite_users(client)
    else:
        print("❌ BOT_MODE должен быть 'parse' или 'invite'")

if __name__ == "__main__":
    asyncio.run(main())
