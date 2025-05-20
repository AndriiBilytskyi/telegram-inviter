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
MAX_INVITES_PER_DAY = 20
MAX_MESSAGES_PER_DAY = 5
DELAY_BETWEEN_ACTIONS = 120  # секунд между действиями
MAX_GROUPS_PER_CYCLE = 3     # снижено для обхода ограничений
GROUP_RETRY_DELAY = 14400    # 4 часа в секундах

# === Аккаунты ===
ACCOUNTS = [
    {
        "session": "inviter_session_1",
        "api_id": int(os.getenv("API_ID_1")),
        "api_hash": os.getenv("API_HASH_1")
    },
    {
        "session": "inviter_session_2",
        "api_id": int(os.getenv("API_ID_2")),
        "api_hash": os.getenv("API_HASH_2")
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

GROUP_PROGRESS_FILE = "group_progress.json"
MODE_FILE = "bot_mode.json"

# === Получение очередной порции групп ===
def get_next_group_batch():
    try:
        with open(GROUP_PROGRESS_FILE, 'r') as f:
            state = json.load(f)
    except:
        state = {"last_index": 0}

    start = state["last_index"]
    end = min(start + MAX_GROUPS_PER_CYCLE, len(GROUPS_TO_PARSE))
    batch = GROUPS_TO_PARSE[start:end]

    state["last_index"] = 0 if end >= len(GROUPS_TO_PARSE) else end
    with open(GROUP_PROGRESS_FILE, 'w') as f:
        json.dump(state, f)
    return batch

# === Смена режима: auto переключает между parse/invite ===
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

# === Основная логика ===
async def parse_users(client):
    users_dict = {}
    for group in get_next_group_batch():
        print(f"📡 Парсинг группы: {group}")
        try:
            await asyncio.sleep(5)
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
            print("📤 Отправка users_to_invite.json в Избранное...")
            await client.send_file('me', USERS_FILE, caption="👥 Список пользователей для инвайта")
        except Exception as e:
            print(f"❌ Не удалось отправить файл: {e}")
    else:
        print("⚠️ Пользователи не найдены. Файл не создан.")

async def invite_users(client):
    if not os.path.exists(USERS_FILE):
        print("❌ Файл пользователей не найден")
        return

    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)

    count_invited = 0
    count_messaged = 0
    for user in users:
        try:
            if count_invited >= MAX_INVITES_PER_DAY and count_messaged >= MAX_MESSAGES_PER_DAY:
                print("⏹️ Достигнут дневной лимит приглашений и сообщений")
                break

            entity = await client.get_entity(user['id'])
            try:
                await client(InviteToChannelRequest(YOUR_GROUP, [entity]))
                print(f"✅ Приглашён: {user['id']}")
                count_invited += 1
            except (UserAlreadyParticipantError):
                print(f"⚠️ Уже в группе: {user['id']}")
            except (UserPrivacyRestrictedError, RPCError):
                if count_messaged < MAX_MESSAGES_PER_DAY:
                    await client.send_message(entity, INVITE_MESSAGE)
                    print(f"📩 Сообщение отправлено: {user['id']}")
                    count_messaged += 1
            await asyncio.sleep(DELAY_BETWEEN_ACTIONS)
        except FloodWaitError as e:
            print(f"⏳ FloodWait: ждём {e.seconds} секунд...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"⚠️ Ошибка: {user['id']} — {e}")

async def main():
    mode = get_effective_mode()
    print(f"▶️ Режим: {mode.upper()}")

    for account in ACCOUNTS:
        client = TelegramClient(account["session"], account["api_id"], account["api_hash"])
        await client.start()
        print(f"🚀 Работаем через сессию: {account['session']}")

        try:
            if mode == "parse":
                await parse_users(client)
            elif mode == "invite":
                await invite_users(client)
            else:
                print(f"⚠️ Неизвестный режим: {mode}")
        except FloodWaitError as e:
            print(f"⏳ FloodWait: Telegram требует паузу {e.seconds} сек. Ждём...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"❌ Ошибка с аккаунтом {account['session']}: {e}")
        finally:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
