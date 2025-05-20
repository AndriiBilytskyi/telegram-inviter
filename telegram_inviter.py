import asyncio
import json
import os
import re
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import (
    UserPrivacyRestrictedError, UserAlreadyParticipantError,
    FloodWaitError, PeerIdInvalidError
)
from telethon.tl.functions.channels import InviteToChannelRequest

# === Константы ===
MAX_INVITES_PER_DAY = 20
MAX_MESSAGES_PER_DAY = 5
DELAY_BETWEEN_ACTIONS = 120
USERS_FILE = 'users_to_invite.json'
INVITE_MESSAGE = "\ud83d\udc4b Добрый день! Я адвокат, который помогает украинцам в Германии. Приглашаю вас посетить мой сайт: https://andriibilytskyi.com - буду рад помочь!"
YOUR_GROUP = 'advocate_ua_1'
AUTO_MODE = os.getenv("BOT_MODE", "parse")

ACCOUNTS = [
    {"session": "inviter_session_1", "api_id": 26735008, "api_hash": "6c35a6247e6b6502e5b79173b22af871"},
    {"session": "inviter_session_2", "api_id": 20903513, "api_hash": "0eb01bf47aeac4cbfd89fff140a4e06d"}
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

async def parse_users(client):
    users_dict = {}
    for group in GROUPS_TO_PARSE:
        try:
            async for message in client.iter_messages(group, limit=1000):
                if message.sender_id and getattr(message, "text", None):
                    text = re.sub(r'[^\w\s]', '', message.text.lower())
                    if any(kw in text for kw in KEYWORDS):
                        sender = await message.get_sender()
                        uid = sender.id
                        if uid not in users_dict:
                            users_dict[uid] = {"id": uid, "username": sender.username}
        except Exception as e:
            log_error(f"{group}: {e}")

    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(users_dict.values()), f, ensure_ascii=False, indent=2)

    try:
        await client.send_file('me', USERS_FILE, caption="\ud83d\udc65 Список пользователей для инвайта")
    except Exception as e:
        log_error(f"Не удалось отправить файл: {e}")

async def process_invites(client):
    if not os.path.exists(USERS_FILE):
        log_error("Файл users_to_invite.json не найден")
        return

    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)

    group = await client.get_entity(YOUR_GROUP)
    invited = 0
    messaged = 0

    for user in users[:]:
        if invited >= MAX_INVITES_PER_DAY and messaged >= MAX_MESSAGES_PER_DAY:
            break

        try:
            entity = await client.get_entity(f"@{user['username']}") if user.get("username") else await client.get_entity(user['id'])

            if invited < MAX_INVITES_PER_DAY:
                await client(InviteToChannelRequest(group, [entity]))
                invited += 1
            else:
                raise UserPrivacyRestrictedError(None)

        except UserPrivacyRestrictedError:
            if messaged < MAX_MESSAGES_PER_DAY and user.get("username"):
                try:
                    await client.send_message(f"@{user['username']}", INVITE_MESSAGE)
                    messaged += 1
                except Exception as e:
                    log_error(f"Ошибка сообщения {user['id']}: {e}")
        except UserAlreadyParticipantError:
            pass
        except Exception as e:
            log_error(f"Ошибка {user['id']}: {e}")

        users.remove(user)
        await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

async def main():
    for account in ACCOUNTS:
        client = TelegramClient(account["session"], account["api_id"], account["api_hash"])
        await client.start()

        try:
            if AUTO_MODE == "parse":
                await parse_users(client)
            elif AUTO_MODE == "invite":
                await process_invites(client)
            else:
                log_error(f"Неизвестный режим: {AUTO_MODE}")
        except FloodWaitError as e:
            log_error(f"FloodWait {e.seconds} сек для {account['session']}")
            continue
        except Exception as e:
            log_error(f"Ошибка аккаунта {account['session']}: {e}")
        finally:
            await client.disconnect()

        break

def log_error(msg):
    with open("log.txt", "a", encoding="utf-8") as log:
        log.write(f"[{datetime.now()}] {msg}\n")

if __name__ == "__main__":
    asyncio.run(main())
