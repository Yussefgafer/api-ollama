import os
import logging
import yt_dlp
import re
import random # لاختيار فيديو عشوائي
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ContextTypes
from telegram.constants import ParseMode
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler # لجدولة المهام

# ------------------------------------------------------------------
# ⚠️ إعدادات البوت - تم تحديثها بالتوكن والـ ID الجديدين ⚠️
# ------------------------------------------------------------------
# تحذير: لا تشارك هذا الكود إذا كان المستودع عامًا!
TELEGRAM_BOT_TOKEN = "7959473244:AAFtDfPzND8kbdcp6qLVfA6SPWvWsRSit3o"

# هذا هو معرف المجموعة الذي قدمته.
TARGET_CHAT_ID = -1002707790272
# ------------------------------------------------------------------

# قائمة بروابط TikTok العشوائية (أمثلة، يمكنك تغييرها أو إضافتها)
# يفضل أن تكون هذه الروابط لفيديوهات عامة ومتاحة للجميع.
RANDOM_TIKTOK_URLS = [
    "https://www.tiktok.com/@tiktok/video/7377508000000000000", # مثال
    "https://www.tiktok.com/@tiktok/video/7377508000000000001", # مثال
    "https://www.tiktok.com/@tiktok/video/7377508000000000002", # مثال
    # أضف المزيد من الروابط هنا
]

# إعداد سجلات (logs) لمتابعة ما يفعله البوت على Railway
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# الحد الأقصى لحجم الملف بالبايت (50 ميجابايت)
TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024

# مسار التنزيل المؤقت داخل الحاوية
TEMP_DOWNLOAD_DIR = '/tmp/downloads'

# متغير لتتبع حالة الجدولة
scheduler_job_id = "random_video_job"
scheduler = BackgroundScheduler()

def find_tiktok_url(text: str):
    pattern = r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+'
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None

def download_tiktok_video(url: str):
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'quiet': True,
        'noplaylist': True,
        'nooverwrites': True,
        'retries': 3,
        'external_downloader_args': ['-loglevel', 'error'],
    }

    file_path = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            logger.info(f"معلومات الفيديو المستخرجة: {info_dict.get('title', 'بدون عنوان')}")
            
            ydl.download([url])
            
            file_path = ydl.prepare_filename(info_dict)
            
            if os.path.exists(file_path):
                logger.info(f"تم تحميل الفيديو بنجاح: {file_path}")
                return file_path
            else:
                logger.error(f"فشل تحميل الفيديو: الملف غير موجود بعد عملية yt-dlp.")
                return None
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"خطأ في التنزيل من yt-dlp: {e}")
        return None
    except Exception as e:
        logger.error(f"حدث خطأ عام أثناء التحميل: {e}")
        return None

async def send_random_tiktok_video(context: ContextTypes.DEFAULT_TYPE):
    """دالة لإرسال فيديو TikTok عشوائي."""
    if not RANDOM_TIKTOK_URLS:
        logger.warning("لا توجد روابط TikTok في قائمة RANDOM_TIKTOK_URLS.")
        return

    random_url = random.choice(RANDOM_TIKTOK_URLS)
    logger.info(f"جاري إرسال فيديو عشوائي: {random_url}")

    file_path = None
    try:
        file_path = download_tiktok_video(random_url)

        if not file_path:
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"عذرًا، فشل تحميل الفيديو العشوائي من: {random_url} 😞"
            )
            return

        file_size = os.path.getsize(file_path)
        logger.info(f"حجم الملف العشوائي: {file_size / 1024 / 1024:.2f} MB")

        caption = f"فيديو عشوائي بواسطة بوت Rikka ❤️"

        if file_size > TELEGRAM_MAX_FILE_SIZE:
            logger.warning("حجم الفيديو العشوائي كبير جدًا، سيتم إرسال رسالة نصية.")
            message = f"الفيديو العشوائي كبير جدًا للتحميل المباشر ({file_size / 1024 / 1024:.2f} MB).\n\n**الرابط الأصلي:** {random_url}"
            await context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            logger.info("جاري إرسال الفيديو العشوائي إلى Telegram...")
            with open(file_path, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=TARGET_CHAT_ID,
                    video=video_file,
                    caption=caption,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=30
                )
    except Exception as e:
        logger.error(f"حدث خطأ في إرسال الفيديو العشوائي: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"حدث خطأ أثناء إرسال الفيديو العشوائي: {e}"
        )
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"تم حذف الملف المؤقت العشوائي: {file_path}")
        if os.path.exists(TEMP_DOWNLOAD_DIR) and os.path.isdir(TEMP_DOWNLOAD_DIR):
            for f in os.listdir(TEMP_DOWNLOAD_DIR):
                os.remove(os.path.join(TEMP_DOWNLOAD_DIR, f))
            logger.info(f"تم تنظيف مجلد التحميل المؤقت: {TEMP_DOWNLOAD_DIR}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يعالج أمر /start ويبدأ إرسال الفيديوهات العشوائية."""
    if update.message.chat_id != int(TARGET_CHAT_ID):
        await update.message.reply_text("أنا أعمل فقط في المجموعة المحددة.")
        return

    if scheduler.get_job(scheduler_job_id):
        await update.message.reply_text("البوت بالفعل يرسل فيديوهات عشوائية.")
        return
    
    # إضافة المهمة المجدولة
    scheduler.add_job(
        send_random_tiktok_video,
        'interval',
        seconds=10,
        id=scheduler_job_id,
        args=[context] # تمرير الكونتيكست للدالة المجدولة
    )
    scheduler.start()
    logger.info("تم بدء إرسال الفيديوهات العشوائية كل 10 ثوانٍ.")
    await update.message.reply_text("تم بدء إرسال الفيديوهات العشوائية كل 10 ثوانٍ!")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يعالج أمر /stop ويوقف إرسال الفيديوهات العشوائية."""
    if update.message.chat_id != int(TARGET_CHAT_ID):
        await update.message.reply_text("أنا أعمل فقط في المجموعة المحددة.")
        return

    if scheduler.get_job(scheduler_job_id):
        scheduler.remove_job(scheduler_job_id)
        logger.info("تم إيقاف إرسال الفيديوهات العشوائية.")
        await update.message.reply_text("تم إيقاف إرسال الفيديوهات العشوائية.")
    else:
        await update.message.reply_text("البوت لا يرسل فيديوهات عشوائية حاليًا.")

async def handle_tiktok_link_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الدالة التي تعالج الرسائل التي تحتوي على روابط TikTok."""
    chat_id = update.message.chat_id
    message_text = update.message.text

    if chat_id != int(TARGET_CHAT_ID):
        logger.warning(f"تم تجاهل الرسالة من دردشة غير مستهدفة: {chat_id}")
        return

    tiktok_url = find_tiktok_url(message_text)
    if not tiktok_url:
        return

    logger.info(f"تم العثور على رابط TikTok في رسالة المستخدم: {tiktok_url}")
    
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
                text="عذرًا، فشل تحميل الفيديو. 😞 ربما الرابط غير صالح أو الفيديو محمي."
            )
            return

        file_size = os.path.getsize(file_path)
        logger.info(f"حجم الملف: {file_size / 1024 / 1024:.2f} MB")

        caption = f"تم التحميل بواسطة بوت Rikka ❤️"

        if file_size > TELEGRAM_MAX_FILE_SIZE:
            logger.warning("حجم الفيديو كبير جدًا، سيتم إرسال رسالة نصية.")
            message = f"الفيديو كبير جدًا للتحميل المباشر ({file_size / 1024 / 1024:.2f} MB).\n\n**الرابط الأصلي:** {tiktok_url}"
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
                    reply_to_message_id=update.message.message_id,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=30
                )
            await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)

    except Exception as e:
        logger.error(f"حدث خطأ غير متوقع في معالجة الرسالة: {e}", exc_info=True)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_message.message_id,
            text=f"حدث خطأ أثناء الإرسال: {e}"
        )
        await asyncio.sleep(5) 
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"تم حذف الملف المؤقت: {file_path}")
        if os.path.exists(TEMP_DOWNLOAD_DIR) and os.path.isdir(TEMP_DOWNLOAD_DIR):
            for f in os.listdir(TEMP_DOWNLOAD_DIR):
                os.remove(os.path.join(TEMP_DOWNLOAD_DIR, f))
            logger.info(f"تم تنظيف مجلد التحميل المؤقت: {TEMP_DOWNLOAD_DIR}")


def main() -> None:
    """بدء تشغيل البوت."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("لم يتم العثور على توكن البوت! يرجى تعيينه في الكود.")
    
    logger.info("تم تعيين TARGET_CHAT_ID: %s", TARGET_CHAT_ID)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))

    # إضافة معالج لروابط TikTok في الرسائل النصية
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tiktok_link_message))

    logger.info("البوت بدأ التشغيل... ينتظر الرسائل والأوامر...")
    application.run_polling(poll_interval=1, timeout=30, read_timeout=30, connect_timeout=30)
    logger.info("البوت توقف عن العمل.")


if __name__ == "__main__":
    main()