import asyncio
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatAction
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, UserNotParticipant
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from database.database import db
from helper_func import (
    decode,
    get_messages,
    get_exp_time,
    is_sub,
    is_subscribed,
    schedule_auto_delete,
)

# Config variables
BAN_SUPPORT = "https://t.me/your_support"  # change this
START_PIC = "https://example.com/start.jpg"
FORCE_PIC = "https://example.com/force.jpg"
START_MSG = "<b>Hello {first}!</b>"
FORCE_MSG = "<b>Please join the channels below:</b>"
CUSTOM_CAPTION = ""
DISABLE_CHANNEL_BUTTON = False
PROTECT_CONTENT = False
FSUB_LINK_EXPIRY = 0


@Client.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    # Add user if not already present
    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except Exception:
            pass

    # Check if user is banned
    banned_users = await db.get_ban_users()
    if user_id in banned_users:
        return await message.reply_text(
            "<b>⛔️ You are Bᴀɴɴᴇᴅ from using this bot.</b>\n\n"
            "<i>Contact support if you think this is a mistake.</i>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Contact Support", url=BAN_SUPPORT)]]
            )
        )

    # ✅ Force Subscription
    if not await is_subscribed(client, user_id):
        return await not_joined(client, message)

    FILE_AUTO_DELETE = await db.get_del_timer()
    text = message.text or ""
    has_start_arg = len(text.split()) > 1

    # Helper to build monospace caption but keep @echoflix_tv line normal
    def build_caption(original_caption: str, custom_caption: str) -> str:
        merged = "\n\n".join([s for s in [original_caption.strip(), custom_caption.strip()] if s]).strip()
        if not merged:
            return ""
        lines = merged.splitlines()
        brand_lines = [ln for ln in lines if "@echoflix_tv" in ln]
        main_lines = [ln for ln in lines if "@echoflix_tv" not in ln]
        code_text = "\n".join(main_lines).strip()
        cap_parts = []
        if code_text:
            cap_parts.append(f"<pre>{code_text}</pre>")
        if brand_lines:
            cap_parts.append("\n".join(brand_lines))
        caption = "\n\n".join([p for p in cap_parts if p]).strip()
        if len(caption) > 1024:
            caption = caption[:1021] + "..."
        return caption

    if has_start_arg:
        try:
            base64_string = text.split(" ", 1)[1]
        except IndexError:
            base64_string = None

        if base64_string:
            string = await decode(base64_string)
            argument = string.split("-")

            ids = []
            if len(argument) == 3:
                try:
                    start = int(int(argument[1]) / abs(client.db_channel.id))
                    end = int(int(argument[2]) / abs(client.db_channel.id))
                    ids = list(range(start, end + 1)) if start <= end else list(range(start, end - 1, -1))
                except Exception as e:
                    print(f"Error decoding IDs: {e}")
            elif len(argument) == 2:
                try:
                    ids = [int(int(argument[1]) / abs(client.db_channel.id))]
                except Exception as e:
                    print(f"Error decoding ID: {e}")

            if ids:
                temp_msg = await message.reply("<b>Please wait...</b>")
                try:
                    messages = await get_messages(client, ids)
                except Exception as e:
                    await message.reply_text("Something went wrong!")
                    print(f"Error getting messages: {e}")
                    return
                finally:
                    await temp_msg.delete()

                codeflix_msgs = []
                for msg in messages:
                    original_caption = msg.caption.html if getattr(msg, "caption", None) else ""
                    custom_caption = ""
                    if CUSTOM_CAPTION:
                        if getattr(msg, "document", None) and hasattr(msg.document, "file_name"):
                            try:
                                custom_caption = CUSTOM_CAPTION.format(
                                    previouscaption=original_caption,
                                    filename=msg.document.file_name
                                )
                            except Exception:
                                custom_caption = CUSTOM_CAPTION
                        else:
                            try:
                                custom_caption = CUSTOM_CAPTION.format(
                                    previouscaption=original_caption,
                                    filename=""
                                )
                            except Exception:
                                custom_caption = CUSTOM_CAPTION

                    caption = build_caption(original_caption, custom_caption)
                    reply_markup = None if DISABLE_CHANNEL_BUTTON else getattr(msg, "reply_markup", None)

                    try:
                        copied_msg = await msg.copy(
                            chat_id=message.from_user.id,
                            caption=caption if caption else None,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            protect_content=PROTECT_CONTENT
                        )
                        await asyncio.sleep(0.1)
                        codeflix_msgs.append(copied_msg)
                    except Exception as e:
                        print(f"Failed to send message: {e}")

                # Schedule deletion
                if FILE_AUTO_DELETE and FILE_AUTO_DELETE > 0 and codeflix_msgs:
                    notification_msg = await message.reply(
                        f"<b>Tʜɪs Fɪʟᴇ ᴡɪʟʟ ʙᴇ Dᴇʟᴇᴛᴇᴅ ɪɴ {get_exp_time(FILE_AUTO_DELETE)}. "
                        f"Pʟᴇᴀsᴇ sᴀᴠᴇ ᴏʀ ғᴏʀᴡᴀʀᴅ ɪᴛ ᴛᴏ ʏᴏᴜʀ sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs ʙᴇғᴏʀᴇ ɪᴛ ɢᴇᴛs Dᴇʟᴇᴛᴇᴅ.</b>"
                    )
                    reload_url = (
                        f"https://t.me/{client.username}?start={message.command[1]}"
                        if getattr(message, "command", None) and len(message.command) > 1 else None
                    )
                    asyncio.create_task(
                        schedule_auto_delete(client, codeflix_msgs, notification_msg, FILE_AUTO_DELETE, reload_url)
                    )
                return

    # Default start screen
    reply_markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("• ᴍᴏʀᴇ ᴄʜᴀɴɴᴇʟs •", url="https://t.me/addlist/pPNOE3JuW8Q1NzFl")],
            [
                InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
                InlineKeyboardButton("ʜᴇʟᴘ •", callback_data="help"),
            ],
        ]
    )
    await message.reply_photo(
        photo=START_PIC,
        caption=START_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else '@' + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=reply_markup,
        message_effect_id=5104841245755180586
    )


# --- not_joined handler ---
chat_data_cache = {}

async def not_joined(client: Client, message: Message):
    temp = await message.reply("<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>")

    user_id = message.from_user.id
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()
        for total, item in enumerate(all_channels, start=1):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                chat_id, mode = item[0], item[1]
            else:
                chat_id = item
                mode = await db.get_channel_mode(chat_id)

            await message.reply_chat_action(ChatAction.TYPING)

            if not await is_sub(client, user_id, chat_id):
                try:
                    data = chat_data_cache.get(chat_id) or await client.get_chat(chat_id)
                    chat_data_cache[chat_id] = data
                    name = data.title

                    if mode == "on" and not data.username:
                        invite = await client.create_chat_invite_link(
                            chat_id=chat_id,
                            creates_join_request=True,
                            expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                        )
                        link = invite.invite_link
                    else:
                        if data.username:
                            link = f"https://t.me/{data.username}"
                        else:
                            invite = await client.create_chat_invite_link(
                                chat_id=chat_id,
                                expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                            )
                            link = invite.invite_link

                    buttons.append([InlineKeyboardButton(text=name, url=link)])
                    count += 1
                    try:
                        await temp.edit(f"<b>{'! ' * count}</b>")
                    except Exception:
                        pass

                except Exception as e:
                    print(f"Error with chat {chat_id}: {e}")
                    return await temp.edit(
                        f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ɪssᴜᴇs @Poseidon_xd</i></b>\n"
                        f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
                    )

        # Retry Button
        try:
            if getattr(message, "command", None) and len(message.command) > 1:
                buttons.append([
                    InlineKeyboardButton(
                        text='♻️ Tʀʏ Aɢᴀɪɴ',
                        url=f"https://t.me/{client.username}?start={message.command[1]}"
                    )
                ])
        except Exception:
            pass

        await message.reply_photo(
            photo=FORCE_PIC,
            caption=FORCE_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        print(f"Final Error: {e}")
        await temp.edit(
            f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ɪssᴜᴇs @Poseidon_xd</i></b>\n"
            f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
        )