import os
import logging
import yt_dlp
import re
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ------------------------------------------------------------------
# ⚠️ إعدادات البوت - ضع معلوماتك هنا مباشرة بناءً على طلبك ⚠️
# ------------------------------------------------------------------
# تحذير: لا تشارك هذا الكود مع أي شخص إذا كان يحتوي على التوكن!
TELEGRAM_BOT_TOKEN = "7322598673:AAHLPboj2lG4qNB7DiSdUG7YT_v_kuuYkc8"

# هام جدًا: يجب أن تحصل على معرّف المجموعة الرقمي.
# استبدل 0 بالمعرّف الصحيح بعد الحصول عليه.
# تأكد من أنه رقم وليس نصًا.
TARGET_CHAT_ID = 0 
# ------------------------------------------------------------------

# إعداد سجلات (logs) لمتابعة ما يفعله البوت على Koyeb
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# الحد الأقصى لحجم الملف بالبايت (50 ميجابايت)
TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024

def find_tiktok_url(text: str):
    """يبحث عن رابط تيك توك في النص باستخدام تعبير نمطي."""
    pattern = r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+'
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None

def download_tiktok_video(url: str):
    """تقوم بتحميل فيديو من رابط TikTok."""
    temp_download_path = '/tmp/downloads'
    os.makedirs(temp_download_path, exist_ok=True)
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(temp_download_path, '%(id)s.%(ext)s'),
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            logger.info(f"تم تحميل الفيديو بنجاح: {file_path}")
            return file_path
    except Exception as e:
        logger.error(f"حدث خطأ أثناء التحميل: {e}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الدالة الرئيسية التي تعالج كل رسالة."""
    chat_id = update.message.chat_id
    message_text = update.message.text

    logger.info(f"رسالة مستلمة في الدردشة رقم: {chat_id}")

    # التحقق مما إذا كانت الرسالة من المجموعة المستهدفة
    # نستخدم int() للتأكد من أننا نقارن أرقامًا
    if TARGET_CHAT_ID != 0 and chat_id != int(TARGET_CHAT_ID):
        logger.warning(f"تم تجاهل الرسالة من دردشة غير مستهدفة: {chat_id}")
        return

    tiktok_url = find_tiktok_url(message_text)
    if not tiktok_url:
        return

    logger.info(f"تم العثور على رابط TikTok: {tiktok_url}")
    
    processing_message = await context.bot.send_message(
        chat_id=chat_id,
        text="جاري معالجة الرابط... ⏳",
        reply_to_message_id=update.message.message_id
    )

    file_path = None
    try:
        file_path = download_tiktok_video(tiktok_url)

        if not file_path:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_message.message_id,
                text="عذرًا، فشل تحميل الفيديو. 😞"
            )
            return

        file_size = os.path.getsize(file_path)
        logger.info(f"حجم الملف: {file_size / 1024 / 1024:.2f} MB")

        caption = f"تم التحميل بواسطة بوت Rikka ❤️"

        if file_size > TELEGRAM_MAX_FILE_SIZE:
            logger.warning("حجم الفيديو كبير جدًا، سيتم إرسال رسالة نصية.")
            message = f"الفيديو كبير جدًا للتحميل المباشر.\n\n**الرابط الأصلي:** {tiktok_url}"
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_message.message_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            logger.info("جاري إرسال الفيديو إلى Telegram...")
            with open(file_path, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=caption,
                    reply_to_message_id=update.message.message_id
                )
            await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)

    except Exception as e:
        logger.error(f"حدث خطأ غير متوقع في معالجة الرسالة: {e}")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_message.message_id,
            text=f"حدث خطأ: {e}"
        )
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"تم حذف الملف المؤقت: {file_path}")

def main() -> None:
    """بدء تشغيل البوت."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("لم يتم العثور على توكن البوت!")
    
    if TARGET_CHAT_ID == 0:
        logger.warning("لم يتم تعيين TARGET_CHAT_ID. البوت سيستجيب في أي مكان تتم إضافته إليه.")
        logger.warning("أرسل أي رسالة في مجموعتك، وانسخ الـ ID من السجلات (logs)، ثم ضعه في الكود وأعد النشر.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("البوت بدأ التشغيل...")
    application.run_polling()

if __name__ == "__main__":
    main()