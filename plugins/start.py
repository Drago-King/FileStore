import asyncio
import os
import re
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from bot import Bot
from config import *
from helper_func import *
from database.database import *

def sanitize_caption(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(@\w+|#\w+|https?://\S+|t\.me/\S+)", "🔗 <b>@EchoFlix_TV</b>", text, flags=re.I)
    return text.strip()

@Client.on_message(filters.private & filters.text)
async def handle_normal_message(client, message: Message):
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
    except Exception as e:
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
    except Exception as e:
        return await message.reply_text("Error decoding ID.")

    temp_msg = await message.reply("<b>Please wait...</b>")

    try:
        messages = await get_messages(client, ids)
    except Exception as e:
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

            reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None

            if msg.video:
                sent = await client.send_video(message.chat.id, msg.video.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
            elif msg.document:
                sent = await client.send_document(message.chat.id, msg.document.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
            elif msg.photo:
                sent = await client.send_photo(message.chat.id, msg.photo.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
            elif msg.audio:
                sent = await client.send_audio(message.chat.id, msg.audio.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
            elif msg.voice:
                sent = await client.send_voice(message.chat.id, msg.voice.file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
            else:
                sent = await msg.copy(chat_id=message.chat.id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_CONTENT)

            sent_msgs.append(sent)
            await asyncio.sleep(0.1)

        except Exception as e:
            print("Sending failed:", e)

    if FILE_AUTO_DELETE > 0 and sent_msgs:
        mins = FILE_AUTO_DELETE // 60
        sec = FILE_AUTO_DELETE % 60
        delete_text = f"⏳ These files will auto-delete in {mins} min{'' if mins == 1 else 's'} {f'{sec} sec' if sec else ''} due to copyright restrictions."
        notify = await message.reply(delete_text)

        await asyncio.sleep(FILE_AUTO_DELETE)
        try:
            for m in sent_msgs:
                await m.delete()
            await notify.delete()
        except Exception as e:
            print("Auto delete failed:", e)