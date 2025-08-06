# ✅ EchoFlix Final Build 2025-08-06 — Full features: /start, force sub, auto-delete, caption sanitize

import asyncio
import os
import re
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatMemberStatus
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant

from config import *
from helper_func import *
from database.database import *

# Force Subscribe Check
async def check_force_sub(client, message):
    if FORCE_SUB:
        try:
            user = await client.get_chat_member(FORCE_SUB, message.from_user.id)
            if user.status == ChatMemberStatus.BANNED:
                await message.reply("🚫 You are banned from using this bot.")
                return False
        except UserNotParticipant:
            try:
                invite = await client.create_chat_invite_link(FORCE_SUB)
                button = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=invite.invite_link)]])
            except:
                button = None
            await message.reply("📛 You must join our channel to use this bot.", reply_markup=button)
            return False
        except Exception:
            return False
    return True

# Sanitize Caption Function
def sanitize_caption(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(@\w+|#\w+|https?://\S+|t\.me/\S+)", "🔗 <b>@EchoFlix_TV</b>", text, flags=re.I)
    return text.strip()

# START Command Handler
@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    if not await check_force_sub(client, message):
        return
    await add_user(message.from_user.id)
    start_msg = "👋 Welcome to <b>EchoFlix Bot</b>!

Send me any valid link to retrieve your files.
Files are auto-deleted after a few minutes due to copyright restrictions."
    buttons = [[InlineKeyboardButton("📢 Join Updates", url="https://t.me/EchoFlix_TV")]]
    await message.reply_photo(
        photo="https://graph.org/file/502bbf50a48d233cafedf.jpg",
        caption=start_msg,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# File Request Handler
@Client.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_normal_message(client, message: Message):
    if not await check_force_sub(client, message):
        return

    FILE_AUTO_DELETE = await db.get_del_timer()
    text = message.text

    if len(text) <= 7:
        return

    try:
        base64_string = text.split(" ", 1)[1]
    except IndexError:
        return

    try:
        decoded_string = await decode(base64_string)
    except Exception:
        await message.reply_text("Invalid or corrupted data.")
        return

    arguments = decoded_string.split("-")
    try:
        if len(arguments) == 3:
            start = int(int(arguments[1]) / abs(client.db_channel.id))
            end = int(int(arguments[2]) / abs(client.db_channel.id))
            ids = list(range(start, end + 1)) if start <= end else list(range(start, end - 1, -1))
        elif len(arguments) == 2:
            ids = [int(int(arguments[1]) / abs(client.db_channel.id))]
        else:
            return await message.reply_text("Invalid link format.")
    except Exception:
        return await message.reply_text("Error decoding ID.")

    temp_msg = await message.reply("<b>Please wait...</b>")
    try:
        messages = await get_messages(client, ids)
    except Exception:
        await message.reply_text("Failed to retrieve messages.")
        return
    finally:
        await temp_msg.delete()

    sent_msgs = []

    for msg in messages:
        try:
            orig = sanitize_caption(msg.caption.html if msg.caption else "")
            credit = "<b>𝚄𝙿𝙻𝙾𝙰𝙳𝙴𝙳 𝙱𝚈 @EchoFlix_TV</b>"
            caption = f"{orig}\n\n{credit}" if orig else credit
            caption = caption[:1024]

            markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None

            if msg.video:
                sent = await client.send_video(message.chat.id, msg.video.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup, protect_content=PROTECT_CONTENT)
            elif msg.document:
                sent = await client.send_document(message.chat.id, msg.document.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup, protect_content=PROTECT_CONTENT)
            elif msg.photo:
                sent = await client.send_photo(message.chat.id, msg.photo.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup, protect_content=PROTECT_CONTENT)
            elif msg.audio:
                sent = await client.send_audio(message.chat.id, msg.audio.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup, protect_content=PROTECT_CONTENT)
            elif msg.voice:
                sent = await client.send_voice(message.chat.id, msg.voice.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup, protect_content=PROTECT_CONTENT)
            else:
                sent = await msg.copy(chat_id=message.chat.id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup, protect_content=PROTECT_CONTENT)

            sent_msgs.append(sent)
            await asyncio.sleep(0.1)

        except Exception as e:
            print("Sending failed:", e)

    if FILE_AUTO_DELETE > 0 and sent_msgs:
        mins = FILE_AUTO_DELETE // 60
        sec = FILE_AUTO_DELETE % 60
        notify_text = f"⏳ These files will auto-delete in {mins} min{'' if mins == 1 else 's'} {f'{sec} sec' if sec else ''} due to copyright restrictions."
        notify = await message.reply(notify_text)

        await asyncio.sleep(FILE_AUTO_DELETE)
        for m in sent_msgs:
            try:
                await m.delete()
            except Exception as e:
                print("Delete failed:", e)
        try:
            await notify.delete()
        except:
            pass