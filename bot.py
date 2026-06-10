import asyncio
import os
import re
import tempfile
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import yt_dlp

BOT_TOKEN = "8813233773:AAHxoJvOtw4_OYoGjSsi8PS1fnhCOCsf_pY"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
DOWNLOAD_DIR = tempfile.gettempdir()
user_urls = {}

def get_info(url):
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return {"ok": True, "title": info.get("title", "Video"), "uploader": info.get("uploader", ""), "duration": info.get("duration", 0)}
    except:
        return {"ok": False}

def find_file(folder, vid_id):
    for f in os.listdir(folder):
        if vid_id in f:
            return os.path.join(folder, f)
    return None

def dl_video(url):
    out = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    for fmt in ["bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", "best"]:
        try:
            opts = {"format": fmt, "outtmpl": out, "quiet": True, "merge_output_format": "mp4",
                    "http_headers": {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "Video")
                vid_id = info.get("id", "")
                fp = ydl.prepare_filename(info)
                if not os.path.exists(fp):
                    fp = str(Path(fp).with_suffix(".mp4"))
                if not os.path.exists(fp):
                    fp = find_file(DOWNLOAD_DIR, vid_id)
                if fp and os.path.exists(fp):
                    size = os.path.getsize(fp) / 1024 / 1024
                    if size > 50:
                        os.remove(fp)
                        return {"ok": False, "error": f"Fayl juda katta ({size:.0f} MB)"}
                    return {"ok": True, "path": fp, "title": title}
        except Exception as e:
            continue
    return {"ok": False, "error": "Yuklab bolmadi"}

def dl_audio(url):
    out = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    try:
        opts = {"format": "bestaudio/best", "outtmpl": out, "quiet": True,
                "http_headers": {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"},
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Audio")
            vid_id = info.get("id", "")
            fp = str(Path(ydl.prepare_filename(info)).with_suffix(".mp3"))
            if not os.path.exists(fp):
                fp = find_file(DOWNLOAD_DIR, vid_id)
            if fp and os.path.exists(fp):
                return {"ok": True, "path": fp, "title": title}
            return {"ok": False, "error": "Fayl topilmadi"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@dp.message(CommandStart())
async def start(msg: Message):
    await msg.answer("👋 Salom! Men Video Yuklovchi botman.\n\nQollab-quvvatlaydi:\n• youtube\n• instagram\n• tiktok\n• twitter / x\n• facebook\n\nshunchaki havola yuboring!")

@dp.message(F.text.regexp(r"https?://"))
async def handle_url(msg: Message):
    url = msg.text.strip()
    user_urls[msg.from_user.id] = url
    loading = await msg.answer("Malumot olinmoqda...")
    info = await asyncio.get_event_loop().run_in_executor(None, lambda: get_info(url))
    if info["ok"]:
        dur = ""
        if info["duration"]:
            m, s = divmod(int(info["duration"]), 60)
            dur = f"\nDavomiyligi: {m}:{s:02d}"
        text = f"Video: {info['title']}\n{info['uploader']}{dur}\n\nFormat tanlang:"
    else:
        text = "Format tanlang:"
    kb = InlineKeyboardBuilder()
    kb.button(text="Video (MP4)", callback_data="video")
    kb.button(text="Audio (MP3)", callback_data="audio")
    kb.button(text="Bekor", callback_data="cancel")
    kb.adjust(2, 1)
    await loading.edit_text(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data.in_({"video", "audio", "cancel"}))
async def handle_choice(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    if cb.data == "cancel":
        await cb.message.edit_text("Bekor qilindi.")
        user_urls.pop(uid, None)
        return
    url = user_urls.get(uid)
    if not url:
        await cb.message.edit_text("Havola topilmadi. Qaytadan yuboring.")
        return
    audio = cb.data == "audio"
    await cb.message.edit_text("Yuklanmoqda... Kuting.")
    if audio:
        result = await asyncio.get_event_loop().run_in_executor(None, lambda: dl_audio(url))
    else:
        result = await asyncio.get_event_loop().run_in_executor(None, lambda: dl_video(url))
    if not result["ok"]:
        await cb.message.edit_text(f"Xatolik: {result['error']}")
        user_urls.pop(uid, None)
        return
    fp = result["path"]
    title = result["title"]
    try:
        await cb.message.edit_text("Yuborilmoqda...")
        file = FSInputFile(fp)
        if audio:
            await cb.message.answer_audio(audio=file, title=title[:64], caption=title[:200])
        else:
            await cb.message.answer_video(video=file, caption=title[:200], supports_streaming=True)
        await cb.message.edit_text("Muvaffaqiyatli yuborildi!")
    except Exception as e:
        await cb.message.edit_text(f"Yuborishda xatolik: {e}")
    finally:
        if fp and os.path.exists(fp):
            os.remove(fp)
        user_urls.pop(uid, None)

@dp.message()
async def non_url(msg: Message):
    await msg.answer("Video havolasini yuboring.\nMasalan: https://youtube.com/watch?v=...")

async def main():
    if "BU_YERNI" in BOT_TOKEN:
        print("BOT_TOKEN ni to'ldiring!")
        return
    print("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())