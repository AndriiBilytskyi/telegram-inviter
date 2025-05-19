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

async def invite_users_with_fallback():
    for account in ACCOUNTS:
        client = TelegramClient(account["session"], account["api_id"], account["api_hash"])
        await client.start()
        print(f"🚀 Работаем через сессию: {account['session']}")

        try:
            await process_invites(client)
            break  # Успешно — выходим
        except FloodWaitError as e:
            print(f"⏳ FloodWait: Telegram требует паузу {e.seconds} сек. Ждём...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"❌ Ошибка с аккаунтом {account['session']}: {e}")
        finally:
            await client.disconnect()

async def process_invites(client):
    if not os.path.exists(USERS_FILE):
        print("❌ Нет файла пользователей")
        return

    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)

    group = await client.get_entity(YOUR_GROUP)
    invited = 0
    messaged = 0

    for user in users[:]:
        if invited >= MAX_INVITES_PER_DAY and messaged >= MAX_MESSAGES_PER_DAY:
            print("⛔️ Достигнут дневной лимит")
            break

        try:
            if user.get("username"):
                entity = await client.get_input_entity(f"@{user['username']}")
            else:
                entity = await client.get_input_entity(user['id'])

            if invited < MAX_INVITES_PER_DAY:
                await client(InviteToChannelRequest(group, [entity]))
                print(f"✅ Приглашён: {user['id']}")
                invited += 1
            else:
                raise UserPrivacyRestrictedError(None)

        except UserPrivacyRestrictedError:
            if messaged < MAX_MESSAGES_PER_DAY and user.get("username"):
                try:
                    await client.send_message(f"@{user['username']}", INVITE_MESSAGE)
                    print(f"✉️ Сообщение: @{user['username']}")
                    messaged += 1
                except Exception as e:
                    print(f"⚠️ Ошибка сообщения {user['id']}: {e}")
        except Exception as e:
            print(f"⚠️ Ошибка: {user['id']} — {e}")

        users.remove(user)
        await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    print(f"🏁 Завершено: {invited} инвайтов, {messaged} сообщений")

if __name__ == "__main__":
    asyncio.run(invite_users_with_fallback())
