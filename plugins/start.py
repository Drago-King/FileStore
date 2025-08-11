# Don't Remove Credit @CodeFlix_Bots, @rohit_1888
# Ask Doubt on telegram @CodeflixSupport
#
# Copyright (C) 2025 by Codeflix-Bots@Github, < https://github.com/Codeflix-Bots >.
#
# This file is part of < https://github.com/Codeflix-Bots/FileStore > project,
# and is released under the MIT License.
# Please see < https://github.com/Codeflix-Bots/FileStore/blob/master/LICENSE >
#
# All rights reserved.
#

import asyncio
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode, ChatAction
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, ChatInviteLink, ChatPrivileges
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, UserNotParticipant
from bot import Bot
from config import *
from helper_func import *
from database.database import *
import re

BAN_SUPPORT = f"{BAN_SUPPORT}"

# Global owner thumbnail configuration
OWNER_THUMB_CONFIG = {
    "file_id": None,          # file_id of the thumbnail photo
    "active": False,          # whether custom thumbnail is currently applied
    "remaining": None,        # if set to an int, apply for next N files then turn off
    "local_path": None        # cached local path for the downloaded thumbnail
}

async def _get_owner_thumb_path(client: Client):
    if not (OWNER_THUMB_CONFIG.get("active") and OWNER_THUMB_CONFIG.get("file_id")):
        return None
    cached_path = OWNER_THUMB_CONFIG.get("local_path")
    if cached_path and os.path.exists(cached_path):
        return cached_path
    try:
        path = await client.download_media(OWNER_THUMB_CONFIG["file_id"])  # downloads to temp dir
        OWNER_THUMB_CONFIG["local_path"] = path
        return path
    except Exception as e:
        print(f"Failed to download owner thumbnail: {e}")
        return None

def _consume_thumb_quota_if_any():
    remaining = OWNER_THUMB_CONFIG.get("remaining")
    if isinstance(remaining, int):
        new_remaining = remaining - 1
        OWNER_THUMB_CONFIG["remaining"] = new_remaining
        if new_remaining <= 0:
            OWNER_THUMB_CONFIG["active"] = False
            OWNER_THUMB_CONFIG["local_path"] = None

def combine_captions(old_caption, custom_caption, filename=None):
    old_caption = old_caption or ""
    if filename:
        return f"{old_caption}\n{custom_caption.format(filename=filename, previouscaption=old_caption)}"
    else:
        return f"{old_caption}\n{custom_caption.format(previouscaption=old_caption)}"

# Whitelisted handles and URLs to preserve in captions
WHITELISTED_HANDLES = {"@echoflix_tv"}
WHITELISTED_TME_URLS = {"https://t.me/echoflix_tv", "http://t.me/echoflix_tv", "t.me/echoflix_tv"}

def _preserve_or_strip_username(match):
    handle = match.group(0)
    if handle.lower() in WHITELISTED_HANDLES:
        return handle
    return ''

def _preserve_or_strip_url(match):
    url = match.group(0)
    if url.lower().rstrip('/') in WHITELISTED_TME_URLS:
        return url
    return ''


def clean_caption(caption):
    """
    Remove all embedded links, any line with 'Powered By' and '@BoB_Files1', all @usernames except whitelisted, and the golden emoji from the caption.
    Preserves @EchoFlix_TV and its t.me link.
    """
    if not caption:
        return caption
    # Remove all markdown and HTML links, preserving anchor text
    caption = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', caption)
    caption = re.sub(r'<a\s+href=["\"][^"\"]+["\"][^>]*>(.*?)<\/a>', r'\1', caption, flags=re.IGNORECASE)
    # Remove plain URLs except whitelisted
    caption = re.sub(r'https?://\S+|t\.me/\S+', _preserve_or_strip_url, caption, flags=re.IGNORECASE)
    # Remove any line containing both 'Powered By' and '@BoB_Files1' (case-insensitive)
    caption = re.sub(r'^.*powered\s*by.*@bob_files1.*$', '', caption, flags=re.IGNORECASE | re.MULTILINE)
    # Remove all @usernames except whitelisted
    caption = re.sub(r'@\w+', _preserve_or_strip_username, caption)
    # Remove the golden emoji ⚜️ everywhere
    caption = caption.replace('⚜️', '')
    # Cleanup extra spaces and blank lines
    caption = re.sub(r'\n{2,}', '\n', caption)
    caption = re.sub(r' +', ' ', caption)
    return caption.strip()

@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    # Add user if not already present
    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except:
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
    # ✅ Check Force Subscription
    if not await is_subscribed(client, user_id):
        #await temp.delete()
        return await not_joined(client, message)

    # File auto-delete time in seconds (Set your desired time in seconds here)
    FILE_AUTO_DELETE = await db.get_del_timer()  # Example: 3600 seconds (1 hour)

    # Handle normal message flow
    text = message.text
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
        except IndexError:
            return

        string = await decode(base64_string)
        argument = string.split("-")

        ids = []
        if len(argument) == 3:
            try:
                start = int(int(argument[1]) / abs(client.db_channel.id))
                end = int(int(argument[2]) / abs(client.db_channel.id))
                ids = range(start, end + 1) if start <= end else list(range(start, end - 1, -1))
            except Exception as e:
                print(f"Error decoding IDs: {e}")
                return

        elif len(argument) == 2:
            try:
                ids = [int(int(argument[1]) / abs(client.db_channel.id))]
            except Exception as e:
                print(f"Error decoding ID: {e}")
                return

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
            # Get the old caption (if any)
            old_caption = ""
            filename = None

            if hasattr(msg, "caption") and msg.caption:
                old_caption = msg.caption.html if hasattr(msg.caption, "html") else msg.caption
            if hasattr(msg, "document") and msg.document:
                filename = msg.document.file_name
            elif hasattr(msg, "photo") and msg.photo:
                filename = "Photo"
            elif hasattr(msg, "video") and msg.video:
                filename = msg.video.file_name if hasattr(msg.video, "file_name") else "Video"
            elif hasattr(msg, "audio") and msg.audio:
                filename = msg.audio.file_name if hasattr(msg.audio, "file_name") else "Audio"

            # Combine captions
            caption = combine_captions(old_caption, CUSTOM_CAPTION, filename)
            caption = clean_caption(caption)

            reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None
            try:
                copied_msg = None
                if OWNER_THUMB_CONFIG.get("active") and OWNER_THUMB_CONFIG.get("file_id"):
                    thumb_path = await _get_owner_thumb_path(client)
                    try:
                        if hasattr(msg, "video") and msg.video:
                            copied_msg = await client.send_video(
                                chat_id=message.from_user.id,
                                video=msg.video.file_id,
                                caption=caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup,
                                protect_content=PROTECT_CONTENT,
                                thumbnail=thumb_path if thumb_path else None
                            )
                        elif hasattr(msg, "document") and msg.document:
                            copied_msg = await client.send_document(
                                chat_id=message.from_user.id,
                                document=msg.document.file_id,
                                caption=caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup,
                                protect_content=PROTECT_CONTENT,
                                thumbnail=thumb_path if thumb_path else None
                            )
                        elif hasattr(msg, "audio") and msg.audio:
                            copied_msg = await client.send_audio(
                                chat_id=message.from_user.id,
                                audio=msg.audio.file_id,
                                caption=caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup,
                                protect_content=PROTECT_CONTENT,
                                thumbnail=thumb_path if thumb_path else None
                            )
                        elif hasattr(msg, "photo") and msg.photo:
                            copied_msg = await client.send_photo(
                                chat_id=message.from_user.id,
                                photo=msg.photo.file_id,
                                caption=caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup,
                                protect_content=PROTECT_CONTENT
                            )
                        else:
                            copied_msg = await msg.copy(
                                chat_id=message.from_user.id,
                                caption=caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup,
                                protect_content=PROTECT_CONTENT
                            )
                        _consume_thumb_quota_if_any()
                    except Exception as inner_e:
                        print(f"Sending with custom thumbnail failed, falling back to copy: {inner_e}")
                        copied_msg = await msg.copy(
                            chat_id=message.from_user.id,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            protect_content=PROTECT_CONTENT
                        )
                else:
                    copied_msg = await msg.copy(
                        chat_id=message.from_user.id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
                await asyncio.sleep(0.1)
                codeflix_msgs.append(copied_msg)
            except Exception as e:
                print(f"Failed to send message: {e}")

        if FILE_AUTO_DELETE > 0:
            notification_msg = await message.reply(
                f"<b>Tʜɪs Fɪʟᴇ ᴡɪʟʟ ʙᴇ Dᴇʟᴇᴛᴇᴅ ɪɴ  {get_exp_time(FILE_AUTO_DELETE)}. Pʟᴇᴀsᴇ sᴀᴠᴇ ᴏʀ ғᴏʀᴡᴀʀᴅ ɪᴛ ᴛᴏ ʏᴏᴜʀ sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs ʙᴇғᴏʀᴇ ɪᴛ ɢᴇᴛs Dᴇʟᴇᴛᴇᴅ.</b>"
            )
            reload_url = (
                f"https://t.me/{client.username}?start={message.command[1]}"
                if message.command and len(message.command) > 1
                else None
            )
            asyncio.create_task(
                schedule_auto_delete(client, codeflix_msgs, notification_msg, FILE_AUTO_DELETE, reload_url)
            )
    else:
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("• ᴍᴏʀᴇ ᴄʜᴀɴɴᴇʟs •", url="https://t.me/addlist/pPNOE3JuW8Q1NzFl")],
                [
                    InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
                    InlineKeyboardButton('ʜᴇʟᴘ •', callback_data="help")
                ]
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
            reply_markup=reply_markup
        )  # 🔥
        return



#=====================================================================================##
# Don't Remove Credit @CodeFlix_Bots, @rohit_1888
# Ask Doubt on telegram @CodeflixSupport



# Create a global dictionary to store chat data
chat_data_cache = {}

async def not_joined(client: Client, message: Message):
    temp = await message.reply("<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>")

    user_id = message.from_user.id
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()  # Should return list of (chat_id, mode) tuples
        for total, chat_id in enumerate(all_channels, start=1):
            mode = await db.get_channel_mode(chat_id)  # fetch mode 

            await message.reply_chat_action(ChatAction.TYPING)

            if not await is_sub(client, user_id, chat_id):
                try:
                    # Cache chat info
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data

                    name = data.title

                    # Generate proper invite link based on the mode
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
                                expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None)
                            link = invite.invite_link

                    buttons.append([InlineKeyboardButton(text=name, url=link)])
                    count += 1
                    await temp.edit(f"<b>{'! ' * count}</b>")

                except Exception as e:
                    print(f"Error with chat {chat_id}: {e}")
                    return await temp.edit(
                        f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @Poseidon_xd</i></b>\n"
                        f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
                    )

        # Retry Button
        try:
            buttons.append([
                InlineKeyboardButton(
                    text='♻️ Tʀʏ Aɢᴀɪɴ',
                    url=f"https://t.me/{client.username}?start={message.command[1]}"
                )
            ])
        except IndexError:
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
            f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @Poseidon_xd</i></b>\n"
            f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
        )

#=====================================================================================##

@Bot.on_message(filters.command('commands') & filters.private & admin)
async def bcmd(bot: Bot, message: Message):        
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data = "close")]])
    await message.reply(text=CMD_TXT, reply_markup = reply_markup, quote= True)

@Bot.on_message(filters.command(["thumb", "change_thumb"]) & filters.private & admin)
async def set_or_change_thumb(client: Client, message: Message):
    """Owner-only: Set or change the current thumbnail.
    Usage:
      - Reply to a photo with /thumb [N] to set and apply for next N files (or unlimited if N not provided)
      - Reply to a photo with /change_thumb [N] to replace the current one
    """
    # Parse optional count argument
    parts = message.text.split(maxsplit=1)
    count = None
    if len(parts) > 1 and parts[1].isdigit():
        count = int(parts[1])

    replied = message.reply_to_message
    if not replied or not replied.photo:
        return await message.reply_text("Reply to a photo with this command. Optionally add a number to limit how many files use it.")

    # Highest resolution photo's file_id
    thumb_file_id = replied.photo.file_id

    OWNER_THUMB_CONFIG["file_id"] = thumb_file_id
    OWNER_THUMB_CONFIG["active"] = True
    OWNER_THUMB_CONFIG["remaining"] = count

    limit_text = f" for next {count} file(s)" if count else " for all upcoming files"
    await message.reply_text(f"Thumbnail set successfully{limit_text}. Use /thumb_off to disable or /change_thumb to replace.")


@Bot.on_message(filters.command("thumb_off") & filters.private & admin)
async def thumb_off_handler(client: Client, message: Message):
    OWNER_THUMB_CONFIG["active"] = False
    OWNER_THUMB_CONFIG["remaining"] = None
    await message.reply_text("Custom thumbnail disabled.")


@Bot.on_message(filters.command("thumb_status") & filters.private & admin)
async def thumb_status_handler(client: Client, message: Message):
    if OWNER_THUMB_CONFIG["active"] and OWNER_THUMB_CONFIG["file_id"]:
        remaining = OWNER_THUMB_CONFIG["remaining"]
        rem_txt = f"next {remaining} file(s)" if isinstance(remaining, int) else "all upcoming files"
        await message.reply_text(f"Custom thumbnail is ON, applied to {rem_txt}.")
    else:
        await message.reply_text("Custom thumbnail is OFF.")

async def schedule_auto_delete(client, codeflix_msgs, notification_msg, file_auto_delete, reload_url):
    await asyncio.sleep(file_auto_delete)
    for snt_msg in codeflix_msgs:
        if snt_msg:
            try:
                await snt_msg.delete()
            except Exception as e:
                print(f"Error deleting message {snt_msg.id}: {e}")

    try:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ!", url=reload_url)]]
        ) if reload_url else None

        await notification_msg.edit(
            "<b>ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!\n\nᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ᴅᴇʟᴇᴛᴇᴅ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ 👇</b>",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Error updating notification with 'Get File Again' button: {e}")
