import os
import logging
import yt_dlp
import re
import random
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ContextTypes
from telegram.constants import ParseMode
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler

# ------------------------------------------------------------------
# ⚠️ إعدادات البوت ⚠️
# ------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "7959473244:AAFtDfPzND8kbdcp6qLVfA6SPWvWsRSit3o"
TARGET_CHAT_ID = -1002707790272
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# ⚠️ مصادر TikTok للبحث العشوائي ⚠️
# يمكنك إضافة هاشتاجات (مثل "funny", "cats") أو أسماء مستخدمين (مثل "@charlidamelio")
# yt-dlp يمكنه استخراج الفيديوهات من صفحات الهاشتاج أو صفحات المستخدمين.
# كلما زادت المصادر، زادت العشوائية.
# ------------------------------------------------------------------
TIKTOK_SOURCES = [
    "funny",      # هاشتاج: https://www.tiktok.com/tag/funny
    "cats",       # هاشتاج: https://www.tiktok.com/tag/cats
    "dance",      # هاشتاج: https://www.tiktok.com/tag/dance
    "@charlidamelio", # اسم مستخدم: https://www.tiktok.com/@charlidamelio
    "@khaby.lame", # اسم مستخدم
    # أضف المزيد من الهاشتاجات أو أسماء المستخدمين هنا
]
# ------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024
TEMP_DOWNLOAD_DIR = '/tmp/downloads'

scheduler_job_id = "random_tiktok_job"
scheduler = BackgroundScheduler()

def find_tiktok_url(text: str):
    pattern = r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+'
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None

def download_video(url: str):
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

async def send_random_tiktok_video_to_group(context: ContextTypes.DEFAULT_TYPE):
    """دالة للبحث عن فيديو TikTok عشوائي وإرساله."""
    if not TIKTOK_SOURCES:
        logger.warning("لا توجد مصادر TikTok محددة في قائمة TIKTOK_SOURCES.")
        return

    selected_source = random.choice(TIKTOK_SOURCES)
    
    # بناء رابط البحث/الصفحة على TikTok
    if selected_source.startswith('@'):
        # اسم مستخدم
        tiktok_search_url = f"https://www.tiktok.com/{selected_source}"
    else:
        # هاشتاج
        tiktok_search_url = f"https://www.tiktok.com/tag/{selected_source}"

    logger.info(f"جاري البحث عن فيديو عشوائي من مصدر TikTok: {tiktok_search_url}")

    video_url_to_download = None
    try:
        # استخدام yt-dlp لاستخراج معلومات عن الفيديوهات من الصفحة
        # download=False لاستخراج المعلومات فقط دون تنزيل الكل
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'noplaylist': True}) as ydl:
            info = ydl.extract_info(tiktok_search_url, download=False)
            
            entries = []
            if 'entries' in info:
                entries = [e for e in info['entries'] if e and e.get('url')]
            elif info.get('url'): # في حالة كانت صفحة فيديو واحدة مباشرة
                entries = [info]

            if not entries:
                logger.warning(f"لم يتم العثور على فيديوهات من المصدر: {tiktok_search_url}")
                await context.bot.send_message(
                    chat_id=TARGET_CHAT_ID,
                    text=f"عذرًا، لم أجد فيديوهات من مصدر TikTok: {selected_source} 😔"
                )
                return
            
            # اختيار فيديو عشوائي من النتائج
            random_entry = random.choice(entries)
            video_url_to_download = random_entry['url']
            logger.info(f"تم اختيار فيديو عشوائي: {video_url_to_download}")

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"خطأ في استخراج معلومات TikTok من {tiktok_search_url}: {e}")
        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"عذرًا، حدث خطأ أثناء البحث في TikTok عن {selected_source} 😔"
        )
        return
    except Exception as e:
        logger.error(f"حدث خطأ عام أثناء البحث في TikTok: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"عذرًا، حدث خطأ غير متوقع أثناء البحث في TikTok 😔: {e}"
        )
        return

    # إذا تم العثور على رابط فيديو، قم بتحميله وإرساله
    if video_url_to_download:
        file_path = None
        try:
            file_path = download_video(video_url_to_download)

            if not file_path:
                await context.bot.send_message(
                    chat_id=TARGET_CHAT_ID,
                    text=f"عذرًا، فشل تحميل الفيديو العشوائي: {video_url_to_download} 😞"
                )
                return

            file_size = os.path.getsize(file_path)
            logger.info(f"حجم الملف العشوائي: {file_size / 1024 / 1024:.2f} MB")

            caption = f"فيديو عشوائي من TikTok بواسطة بوت Rikka ❤️"

            if file_size > TELEGRAM_MAX_FILE_SIZE:
                logger.warning("حجم الفيديو العشوائي كبير جدًا، سيتم إرسال رسالة نصية.")
                message = f"الفيديو العشوائي كبير جدًا للتحميل المباشر ({file_size / 1024 / 1024:.2f} MB).\n\n**الرابط الأصلي:** {video_url_to_download}"
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
    
    if not TIKTOK_SOURCES:
        await update.message.reply_text("عذرًا، لا توجد مصادر TikTok محددة للبحث. يرجى إضافة هاشتاجات أو أسماء مستخدمين في الكود.")
        return

    scheduler.add_job(
        send_random_tiktok_video_to_group, # تم تغيير اسم الدالة
        'interval',
        seconds=10,
        id=scheduler_job_id,
        args=[context]
    )
    scheduler.start()
    logger.info("تم بدء إرسال الفيديوهات العشوائية من TikTok كل 10 ثوانٍ.")
    await update.message.reply_text("تم بدء إرسال الفيديوهات العشوائية من TikTok كل 10 ثوانٍ!")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يعالج أمر /stop ويوقف إرسال الفيديوهات العشوائية."""
    if update.message.chat_id != int(TARGET_CHAT_ID):
        await update.message.reply_text("أنا أعمل فقط في المجموعة المحددة.")
        return

    if scheduler.get_job(scheduler_job_id):
        scheduler.remove_job(scheduler_job_id)
        logger.info("تم إيقاف إرسال الفيديوهات العشوائية من TikTok.")
        await update.message.reply_text("تم إيقاف إرسال الفيديوهات العشوائية من TikTok.")
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
        file_path = download_video(tiktok_url)

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