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

GROUPS_TO_PARSE = [ ... ]  # Список групп остаётся прежним

KEYWORDS = [ ... ]  # Список ключевых слов остаётся прежним

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

async def process_invites(client):
    if not os.path.exists(USERS_FILE):
        print("❌ Файл users_to_invite.json не найден")
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
            entity = None
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
        except UserAlreadyParticipantError:
            print(f"➡️ Уже в группе: {user['id']}")
        except Exception as e:
            print(f"⚠️ Ошибка: {user['id']} — {e}")

        users.remove(user)
        await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    print(f"🏁 Завершено: {invited} инвайтов, {messaged} сообщений")

AUTO_MODE = os.getenv("BOT_MODE", "parse")

async def main():
    for account in ACCOUNTS:
        client = TelegramClient(account["session"], account["api_id"], account["api_hash"])
        await client.start()
        print(f"🚀 Работаем через сессию: {account['session']}")

        try:
            if AUTO_MODE == "parse":
                print("▶️ Режим: ПАРСИНГ")
                await parse_users(client)
            elif AUTO_MODE == "invite":
                print("▶️ Режим: ИНВАЙТ")
                await process_invites(client)
            else:
                print(f"⚠️ Неизвестный режим: {AUTO_MODE}")
            break
        except FloodWaitError as e:
            print(f"⏳ FloodWait: Telegram требует паузу {e.seconds} сек. Ждём...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"❌ Ошибка с аккаунтом {account['session']}: {e}")
        finally:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
