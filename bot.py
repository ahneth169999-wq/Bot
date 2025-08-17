import os
import re
import logging
import tempfile
import shutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters
)
import yt_dlp

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be",
    "tiktok.com", "instagram.com",
    "facebook.com", "fb.watch"
]

# Env vars
TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.getenv("PORT", 8000))

# Detect hosting platform (Render or Railway) and set webhook URL
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Manual override (Render recommended)
if not WEBHOOK_URL:
    if os.getenv("RAILWAY_STATIC_URL"):  # Railway
        WEBHOOK_URL = os.getenv("RAILWAY_STATIC_URL") + "/webhook"
    elif os.getenv("RENDER_EXTERNAL_URL"):  # Render
        WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + "/webhook"

# --- helper functions (same as before) ---
def is_supported_url(url: str) -> bool:
    domain = re.search(r"https?://([^/]+)", url)
    if domain:
        domain = domain.group(1).lower()
        return any(d in domain for d in SUPPORTED_DOMAINS)
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🖐 Yooo bro! Send me a link from:\n"
        "YouTube | TikTok | Instagram | Facebook\n"
        "I'll download it as MP3 or MP4 for you!"
    )

def extract_url(text: str) -> str:
    urls = re.findall(r"https?://\S+", text)
    return urls[0] if urls else None

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = extract_url(update.message.text)
    if url and is_supported_url(url):
        context.user_data["url"] = url
        keyboard = [
            [
                InlineKeyboardButton("MP3 🎵", callback_data="mp3"),
                InlineKeyboardButton("MP4 🎬", callback_data="mp4"),
            ]
        ]
        await update.message.reply_text(
            "Choose format:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            "❌ Unsupported URL. Send valid link from:\nYouTube/TikTok/Instagram/Facebook"
        )

def download_media(url: str, media_type: str) -> str:
    temp_dir = tempfile.mkdtemp()
    ydl_opts = {
        "outtmpl": os.path.join(temp_dir, "%(title).70s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "noplaylist": True,
        "max_filesize": 50 * 1024 * 1024,
    }

    if media_type == "mp3":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        if media_type == "mp4":
            return filename if os.path.exists(filename) else filename.replace(".webm", ".mp4")
        else:
            for file in os.listdir(temp_dir):
                if file.endswith(".mp3"):
                    return os.path.join(temp_dir, file)
            return filename.replace(".webm", ".mp3").replace(".m4a", ".mp3")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    media_type = query.data
    url = context.user_data.get("url")

    if not url:
        await query.edit_message_text("❌ URL missing. Send link again")
        return

    try:
        await query.edit_message_text(f"⬇️ Downloading {media_type.upper()}...")
        file_path = download_media(url, media_type)
        file_size = os.path.getsize(file_path) / (1024 * 1024)

        if file_size > 50:
            await query.edit_message_text(f"❌ File too big ({file_size:.1f}MB > 50MB)")
            shutil.rmtree(os.path.dirname(file_path))
            return

        if media_type == "mp3":
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=open(file_path, "rb"),
                title=os.path.basename(file_path)[:64],
            )
        else:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=open(file_path, "rb"),
                supports_streaming=True,
            )

        await query.edit_message_text(f"✅ {media_type.upper()} download complete!")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        await query.edit_message_text(f"❌ Error: {str(e)}")
    finally:
        if "file_path" in locals() and file_path and os.path.exists(os.path.dirname(file_path)):
            shutil.rmtree(os.path.dirname(file_path), ignore_errors=True)

def main() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_TOKEN environment variable not set")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_handler))

    if WEBHOOK_URL:
        logger.info(f"Running in WEBHOOK mode on {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            secret_token=os.getenv("SECRET_TOKEN", ""),  # optional
        )
    else:
        logger.info("Running in POLLING mode")
        application.run_polling()

if __name__ == "__main__":
    main()
