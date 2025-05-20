import os
import json
import logging
from datetime import datetime

from telethon import TelegramClient, errors, types
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest

# Logging configuration
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# Telegram API credentials from environment
API_ID = int(os.environ.get('TELEGRAM_API_ID', 0))
API_HASH = os.environ.get('TELEGRAM_API_HASH', None)
if not API_ID or not API_HASH:
    logging.error("API_ID or API_HASH not set. Please set TELEGRAM_API_ID and TELEGRAM_API_HASH.")
    raise SystemExit(1)

# Session file names
SESSION_NAME1 = 'inviter_session_1'
SESSION_NAME2 = 'inviter_session_2'

# File paths
BOT_MODE_FILE = 'bot_mode.json'
GROUP_PROGRESS_FILE = 'group_progress.json'
USERS_FILE = 'users_to_invite.json'
DM_COUNTER_FILE = 'dm_counter.json'

# Groups and keywords lists (provided by user)
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

async def main():
    # Determine current mode from file (auto toggle between parse and invite)
    current_mode = 'parse'
    if os.path.exists(BOT_MODE_FILE):
        try:
            with open(BOT_MODE_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, str):
                    mode = data
                elif isinstance(data, dict) and 'mode' in data:
                    mode = data['mode']
                else:
                    mode = str(data)
                if mode:
                    current_mode = mode.lower()
        except Exception as e:
            logging.error(f"Could not read {BOT_MODE_FILE}: {e}")
            current_mode = 'parse'
    # Determine next mode and save it
    next_mode = 'invite' if current_mode == 'parse' else 'parse'
    try:
        with open(BOT_MODE_FILE, 'w') as f:
            json.dump({"mode": next_mode}, f)
    except Exception as e:
        logging.error(f"Failed to write next mode to {BOT_MODE_FILE}: {e}")
    logging.info(f"Running in mode: {current_mode.upper()}")

    # Initialize Telegram clients
    client1 = TelegramClient(SESSION_NAME1, API_ID, API_HASH)
    client2 = None
    # Connect and authenticate first client
    await client1.connect()
    if not await client1.is_user_authorized():
        logging.error("Session 1 is not authorized. Please ensure session login is completed.")
        await client1.disconnect()
        return
    # Initialize second client only if needed (for invite mode)
    if current_mode == 'invite':
        client2 = TelegramClient(SESSION_NAME2, API_ID, API_HASH)
        await client2.connect()
        if not await client2.is_user_authorized():
            logging.warning("Session 2 not authorized or not available. Proceeding with one account.")
            await client2.disconnect()
            client2 = None

    try:
        if current_mode == 'parse':
            # Parse mode: scan groups for keywords and save users
            start_index = 0
            if os.path.exists(GROUP_PROGRESS_FILE):
                try:
                    with open(GROUP_PROGRESS_FILE, 'r') as f:
                        gp = json.load(f)
                        if isinstance(gp, dict):
                            start_index = gp.get('next_index', 0)
                        elif isinstance(gp, int):
                            start_index = gp
                        else:
                            start_index = int(gp)
                except Exception as e:
                    logging.warning(f"Failed to read {GROUP_PROGRESS_FILE}: {e}")
                    start_index = 0
            num_groups = len(GROUPS_TO_PARSE)
            if num_groups == 0:
                logging.error("No groups to parse. GROUPS_TO_PARSE list is empty.")
            # Determine subset of groups to parse this run (max 20)
            groups_slice = []
            if num_groups > 0:
                if start_index >= num_groups:
                    start_index = 0
                end_index = start_index + 20
                if end_index > num_groups:
                    end_index = num_groups
                groups_slice = GROUPS_TO_PARSE[start_index:end_index]
                # Calculate next index for subsequent run
                next_index = 0 if end_index >= num_groups else end_index
                try:
                    with open(GROUP_PROGRESS_FILE, 'w') as f:
                        json.dump({"next_index": next_index}, f)
                except Exception as e:
                    logging.warning(f"Failed to write {GROUP_PROGRESS_FILE}: {e}")
                logging.info(f"Parsing groups index {start_index} to {end_index-1}")
            found_users = {}
            for group in groups_slice:
                try:
                    entity = await client1.get_entity(group)
                except Exception as e:
                    logging.error(f"Cannot access group {group}: {e}")
                    continue
                title = entity.title if hasattr(entity, 'title') else str(group)
                logging.info(f"Scanning group: {title}")
                try:
                    messages = await client1.get_messages(entity, limit=100)
                except Exception as e:
                    logging.error(f"Failed to fetch messages from {title}: {e}")
                    continue
                for msg in messages:
                    if not msg or not getattr(msg, 'message', None):
                        continue
                    text = msg.message.lower()
                    if any(kw in text for kw in [k.lower() for k in KEYWORDS]):
                        try:
                            sender = await msg.get_sender()
                        except Exception as e:
                            logging.error(f"Failed to get sender in {title}: {e}")
                            sender = None
                        if sender and isinstance(sender, types.User):
                            if sender.id not in found_users:
                                found_users[sender.id] = sender
                                logging.info(f"Found user {sender.id} (@{sender.username}) in {title}")
            # Load existing users_to_invite file
            existing_users = []
            if os.path.exists(USERS_FILE):
                try:
                    with open(USERS_FILE, 'r') as f:
                        existing_users = json.load(f)
                        if not isinstance(existing_users, list):
                            existing_users = []
                except Exception as e:
                    logging.error(f"Failed to read {USERS_FILE}: {e}")
                    existing_users = []
            existing_ids = {u.get('id') for u in existing_users if u.get('id')}
            new_entries = []
            for uid, user in found_users.items():
                if uid in existing_ids:
                    continue
                username = user.username if getattr(user, 'username', None) else None
                new_entries.append({"id": uid, "username": username})
                existing_ids.add(uid)
            if new_entries:
                existing_users.extend(new_entries)
                try:
                    with open(USERS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(existing_users, f, indent=2, ensure_ascii=False)
                    logging.info(f"Added {len(new_entries)} new users to invite list.")
                except Exception as e:
                    logging.error(f"Error writing {USERS_FILE}: {e}")
            else:
                logging.info("No new users found this run.")
            # Send the JSON file to Saved Messages
            try:
                if not os.path.exists(USERS_FILE):
                    with open(USERS_FILE, 'w') as f:
                        json.dump([], f, indent=2)
                await client1.send_file('me', USERS_FILE)
                logging.info(f"Sent {USERS_FILE} to Saved Messages.")
            except Exception as e:
                logging.error(f"Failed to send file to Saved Messages: {e}")

        elif current_mode == 'invite':
            # Invite mode: invite users or DM them
            users_list = []
            if os.path.exists(USERS_FILE):
                try:
                    with open(USERS_FILE, 'r') as f:
                        users_list = json.load(f)
                        if not isinstance(users_list, list):
                            users_list = []
                except Exception as e:
                    logging.error(f"Failed to read {USERS_FILE}: {e}")
                    users_list = []
            if not users_list or len(users_list) == 0:
                logging.info("No users to invite.")
            else:
                to_process = users_list[:20]
                logging.info(f"Processing {len(to_process)} users in invite mode.")
                target_group = 'advocate_ua_1'
                target_entity1 = None
                target_entity2 = None
                try:
                    target_entity1 = await client1.get_entity(target_group)
                except Exception as e:
                    logging.error(f"Account1 cannot access target group: {e}")
                if client2:
                    try:
                        target_entity2 = await client2.get_entity(target_group)
                    except Exception as e:
                        logging.error(f"Account2 cannot access target group: {e}")
                # Determine invite method
                chat_invite_mode = False
                target_entity = target_entity1 or target_entity2
                if target_entity:
                    if isinstance(target_entity, types.Chat) or getattr(target_entity, 'gigagroup', False):
                        chat_invite_mode = True
                    elif isinstance(target_entity, types.Channel):
                        if getattr(target_entity, 'broadcast', False):
                            logging.error("Target group is a broadcast channel, cannot invite members.")
                            to_process = []
                        else:
                            chat_invite_mode = False
                else:
                    logging.error("No access to target group entity. Aborting invites.")
                    to_process = []
                # Load or init DM counter
                dm_counter = {}
                today_str = datetime.utcnow().strftime("%Y-%m-%d")
                if os.path.exists(DM_COUNTER_FILE):
                    try:
                        with open(DM_COUNTER_FILE, 'r') as f:
                            dm_counter = json.load(f)
                    except Exception as e:
                        logging.warning(f"Could not read {DM_COUNTER_FILE}: {e}")
                        dm_counter = {}
                # Default values for counters
                for acc_key in ['inviter_session_1', 'inviter_session_2']:
                    if acc_key not in dm_counter:
                        dm_counter[acc_key] = {"date": today_str, "count": 0}
                    if dm_counter[acc_key].get("date") != today_str:
                        dm_counter[acc_key]["date"] = today_str
                        dm_counter[acc_key]["count"] = 0
                # Shortcut references
                acc1_count = dm_counter['inviter_session_1']['count']
                acc2_count = dm_counter['inviter_session_2']['count']
                current_client = client1
                current_entity = target_entity1 if target_entity1 else target_entity2
                current_session = 'inviter_session_1'
                switched_for_invites = False

                processed_ids = set()
                needs_dm = []
                stop_invites = False
                for user in to_process:
                    if stop_invites:
                        break
                    user_id = user.get('id')
                    username = user.get('username')
                    try:
                        if chat_invite_mode:
                            chat_id = current_entity.id if isinstance(current_entity, types.Chat) else getattr(current_entity, 'id', None)
                            if chat_id is None:
                                raise Exception("Invalid chat target.")
                            await current_client(AddChatUserRequest(chat_id, user_id, fwd_limit=0))
                        else:
                            await current_client(InviteToChannelRequest(current_entity, [user_id]))
                        # success:
                        processed_ids.add(user_id)
                        logging.info(f"Invited user {user_id}" + (f" (@{username})" if username else ""))
                    except errors.UserPrivacyRestrictedError:
                        logging.info(f"Cannot invite user {user_id} (@{username}) due to privacy, will send DM.")
                        needs_dm.append(user)
                    except errors.UserAlreadyParticipantError:
                        logging.info(f"User {user_id} (@{username}) is already in target group, will send DM.")
                        needs_dm.append(user)
                    except errors.ChatAdminRequiredError:
                        logging.warning(f"Account {current_session} lacks admin rights to invite in target group.")
                        if not switched_for_invites and client2:
                            logging.info("Switching to second account for inviting.")
                            current_client = client2
                            current_entity = target_entity2 if target_entity2 else target_entity1
                            current_session = 'inviter_session_2'
                            switched_for_invites = True
                            try:
                                if chat_invite_mode:
                                    chat_id = current_entity.id if isinstance(current_entity, types.Chat) else getattr(current_entity, 'id', None)
                                    if chat_id is None:
                                        raise Exception("Invalid chat target.")
                                    await current_client(AddChatUserRequest(chat_id, user_id, fwd_limit=0))
                                else:
                                    await current_client(InviteToChannelRequest(current_entity, [user_id]))
                                processed_ids.add(user_id)
                                logging.info(f"Invited user {user_id} with second account.")
                            except errors.UserPrivacyRestrictedError:
                                logging.info(f"Cannot invite user {user_id} with account2 (privacy), will send DM.")
                                needs_dm.append(user)
                            except errors.UserAlreadyParticipantError:
                                logging.info(f"User {user_id} already in group (account2 view), will send DM.")
                                needs_dm.append(user)
                            except errors.ChatAdminRequiredError:
                                logging.error("Second account also lacks admin rights. Cannot invite users via API.")
                                needs_dm.append(user)
                                stop_invites = True
                            except errors.FloodWaitError as e:
                                logging.warning(f"Flood wait {e.seconds}s on account2 while inviting.")
                                needs_dm.append(user)
                                stop_invites = True
                            except errors.RPCError as e:
                                logging.error(f"Invite error with account2: {e}")
                                needs_dm.append(user)
                        else:
                            logging.error("No account with admin rights available. Stopping invites.")
                            needs_dm.append(user)
                            stop_invites = True
                    except errors.FloodWaitError as e:
                        logging.warning(f"FloodWait of {e.seconds}s on account {current_session}")
                        if not switched_for_invites and client2:
                            logging.info("Switching to second account due to FloodWait.")
                            current_client = client2
                            current_entity = target_entity2 if target_entity2 else target_entity1
                            current_session = 'inviter_session_2'
                            switched_for_invites = True
                            try:
                                if chat_invite_mode:
                                    chat_id = current_entity.id if isinstance(current_entity, types.Chat) else getattr(current_entity, 'id', None)
                                    if chat_id is None:
                                        raise Exception("Invalid chat target.")
                                    await current_client(AddChatUserRequest(chat_id, user_id, fwd_limit=0))
                                else:
                                    await current_client(InviteToChannelRequest(current_entity, [user_id]))
                                processed_ids.add(user_id)
                                logging.info(f"Invited user {user_id} with second account after floodwait.")
                            except errors.UserPrivacyRestrictedError:
                                logging.info(f"Cannot invite user {user_id} with account2 (privacy), will send DM.")
                                needs_dm.append(user)
                            except errors.UserAlreadyParticipantError:
                                logging.info(f"User {user_id} already in group (account2), will send DM.")
                                needs_dm.append(user)
                            except errors.ChatAdminRequiredError:
                                logging.warning("Account2 not admin, cannot invite after switch.")
                                needs_dm.append(user)
                            except errors.FloodWaitError as e2:
                                logging.error(f"FloodWait on second account as well ({e2.seconds}s). Stopping invites.")
                                needs_dm.append(user)
                                stop_invites = True
                            except errors.RPCError as e2:
                                logging.error(f"Error inviting with account2 after switch: {e2}")
                                needs_dm.append(user)
                        else:
                            logging.error("FloodWait on second account or no second account. Stopping invites.")
                            needs_dm.append(user)
                            stop_invites = True
                    except errors.PeerFloodError as e:
                        logging.error(f"PeerFlood (spam) error on account {current_session}: {e}")
                        if not switched_for_invites and client2:
                            logging.info("Switching to second account due to PeerFlood.")
                            current_client = client2
                            current_entity = target_entity2 if target_entity2 else target_entity1
                            current_session = 'inviter_session_2'
                            switched_for_invites = True
                            try:
                                if chat_invite_mode:
                                    chat_id = current_entity.id if isinstance(current_entity, types.Chat) else getattr(current_entity, 'id', None)
                                    if chat_id is None:
                                        raise Exception("Invalid chat target.")
                                    await current_client(AddChatUserRequest(chat_id, user_id, fwd_limit=0))
                                else:
                                    await current_client(InviteToChannelRequest(current_entity, [user_id]))
                                processed_ids.add(user_id)
                                logging.info(f"Invited user {user_id} with second account after PeerFlood.")
                            except errors.RPCError as e2:
                                logging.error(f"Second account failed to invite user {user_id}: {e2}")
                                needs_dm.append(user)
                                stop_invites = True
                        else:
                            logging.error("Second account also impacted or not available. Stopping invites.")
                            needs_dm.append(user)
                            stop_invites = True
                    except errors.InputUserDeactivatedError:
                        logging.warning(f"User {user_id} is deleted. Removing from list.")
                        processed_ids.add(user_id)
                    except errors.RPCError as e:
                        logging.error(f"Unexpected invite error for user {user_id}: {e}")
                        # Remove user to skip future attempts if unknown error
                        processed_ids.add(user_id)
                # end for invite loop

                # Decide which account to use for DMs
                current_dm_client = client2 if switched_for_invites and client2 else client1
                current_dm_session = 'inviter_session_2' if (switched_for_invites and client2) else 'inviter_session_1'
                # Now send DMs to those collected
                for user in needs_dm:
                    user_id = user.get('id')
                    username = user.get('username')
                    # Check DM limit for current account
                    if current_dm_session == 'inviter_session_1':
                        if dm_counter['inviter_session_1']['count'] >= 5:
                            if client2 and dm_counter['inviter_session_2']['count'] < 5:
                                logging.info("Account 1 DM limit reached, switching to account 2 for DMs.")
                                current_dm_client = client2
                                current_dm_session = 'inviter_session_2'
                            else:
                                logging.info("Daily DM limit reached, stopping further DMs.")
                                break
                    else:
                        if dm_counter['inviter_session_2']['count'] >= 5:
                            if client1 and dm_counter['inviter_session_1']['count'] < 5:
                                logging.info("Account 2 DM limit reached, switching to account 1 for DMs.")
                                current_dm_client = client1
                                current_dm_session = 'inviter_session_1'
                            else:
                                logging.info("Daily DM limit reached on account 2, stopping DMs.")
                                break
                    try:
                        dm_text = "Привет! Приглашаем вас в наш Telegram-чат Advocate UA."
                        target = username if username else user_id
                        await current_dm_client.send_message(target, dm_text)
                        logging.info(f"Sent DM to user {user_id}" + (f" (@{username})" if username else ""))
                        dm_counter[current_dm_session]['count'] += 1
                        processed_ids.add(user_id)
                    except errors.PeerFloodError:
                        logging.error(f"PeerFlood: account {current_dm_session} cannot send more DMs.")
                        if current_dm_session == 'inviter_session_1' and client2:
                            logging.info("Switching to account 2 for DMs due to PeerFlood on account 1.")
                            current_dm_client = client2
                            current_dm_session = 'inviter_session_2'
                            try:
                                dm_counter['inviter_session_2']['date'] = today_str
                                # Ensure account2 is connected (should be)
                                if dm_counter['inviter_session_2']['count'] < 5:
                                    target = username if username else user_id
                                    await current_dm_client.send_message(target, dm_text)
                                    logging.info(f"Sent DM to user {user_id} with account 2")
                                    dm_counter['inviter_session_2']['count'] += 1
                                    processed_ids.add(user_id)
                                else:
                                    logging.info("Account 2 DM limit reached, cannot send DM.")
                            except errors.PeerFloodError:
                                logging.error("Account 2 also blocked from sending DMs. Stopping DM process.")
                                break
                            except Exception as e2:
                                logging.error(f"Failed to send DM with account 2: {e2}")
                                # Skip DM for this user (do not mark processed, try later maybe)
                        else:
                            logging.error("No alternate account to send DM or second account also blocked. Stopping DMs.")
                            break
                    except errors.UserPrivacyRestrictedError:
                        logging.info(f"User {user_id} disallows DMs. Removing from list.")
                        processed_ids.add(user_id)
                    except errors.InputUserDeactivatedError:
                        logging.info(f"User {user_id} is deleted. Removing from list.")
                        processed_ids.add(user_id)
                    except errors.UserIsBlockedError:
                        logging.info(f"User {user_id} blocked us. Removing from list.")
                        processed_ids.add(user_id)
                    except errors.RPCError as e:
                        logging.error(f"Error sending DM to user {user_id}: {e}")
                        processed_ids.add(user_id)
                # end for DM loop

                # Save DM counter
                try:
                    with open(DM_COUNTER_FILE, 'w') as f:
                        json.dump(dm_counter, f, indent=2)
                except Exception as e:
                    logging.warning(f"Failed to update {DM_COUNTER_FILE}: {e}")

                # Update users file by removing processed users
                remaining_users = [u for u in users_list if u.get('id') not in processed_ids]
                try:
                    with open(USERS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(remaining_users, f, indent=2, ensure_ascii=False)
                    logging.info(f"Updated {USERS_FILE}: {len(processed_ids)} users processed, {len(remaining_users)} remaining.")
                except Exception as e:
                    logging.error(f"Failed to update {USERS_FILE}: {e}")
    except Exception as e:
        logging.exception(f"Unhandled exception: {e}")
    finally:
        # Disconnect clients
        await client1.disconnect()
        if client2:
            await client2.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
