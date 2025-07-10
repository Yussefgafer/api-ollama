import os
import logging
import yt_dlp
import re
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import asyncio # لاستخدام sleep في حالة الخطأ

# ------------------------------------------------------------------
# ⚠️ إعدادات البوت - ضع معلوماتك هنا مباشرة بناءً على طلبك ⚠️
# ------------------------------------------------------------------
# تحذير: لا تشارك هذا الكود مع أي شخص إذا كان يحتوي على التوكن!
TELEGRAM_BOT_TOKEN = "7322598673:AAHLPboj2lG4qNB7DiSdUG7YT_v_kuuYkc8"

# هام جدًا: يجب أن تحصل على معرّف المجموعة الرقمي.
# استبدل 0 بالمعرّف الصحيح بعد الحصول عليه. (مثال: -1001234567890)
TARGET_CHAT_ID = 0
# ------------------------------------------------------------------


# إعداد سجلات (logs) لمتابعة ما يفعله البوت على Koyeb
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING) # لتقليل سجلات مكتبة httpx
logger = logging.getLogger(__name__)

# الحد الأقصى لحجم الملف بالبايت (50 ميجابايت)
TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024

# مسار التنزيل المؤقت داخل الحاوية (يجب أن يكون قابل للكتابة)
TEMP_DOWNLOAD_DIR = '/tmp/downloads'

def find_tiktok_url(text: str):
    """يبحث عن رابط تيك توك في النص باستخدام تعبير نمطي."""
    pattern = r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+'
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None

def download_tiktok_video(url: str):
    """تقوم بتحميل فيديو من رابط TikTok."""
    # التأكد من وجود مجلد التحميل المؤقت
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    
    # إعدادات yt-dlp
    # 'nooverwrites': لا تعيد تنزيل الملف إذا كان موجودًا
    # 'noplaylist': لا تحاول تنزيل قوائم التشغيل
    # 'writedescription': لكتابة الوصف (اختياري)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'quiet': True, # لمنع طباعة الكثير من المعلومات في السجلات
        'noplaylist': True,
        'nooverwrites': True,
        'retries': 3, # محاولات إعادة التحميل
        'external_downloader_args': ['-loglevel', 'error'], # لتقليل سجلات ffmpeg
    }

    file_path = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # استخراج المعلومات أولاً دون تنزيل للتأكد من وجود الفيديو
            info_dict = ydl.extract_info(url, download=False)
            logger.info(f"معلومات الفيديو المستخرجة: {info_dict.get('title', 'بدون عنوان')}")
            
            # الآن نقوم بالتنزيل
            ydl.download([url])
            
            # الحصول على مسار الملف بعد التنزيل
            # قد يكون info_dict['_format_note'] أو info_dict['requested_downloads'][0]['filepath']
            # ولكن الطريقة الأكثر موثوقية هي استنتاج المسار من info_dict['id'] و info_dict['ext']
            # أو استخدام prepare_filename بعد التنزيل
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الدالة الرئيسية التي تعالج كل رسالة."""
    chat_id = update.message.chat_id
    message_text = update.message.text

    logger.info(f"رسالة مستلمة في الدردشة رقم: {chat_id} | النص: {message_text[:50]}...")

    # التحقق مما إذا كانت الرسالة من المجموعة المستهدفة
    # نستخدم int() للتأكد من أننا نقارن أرقامًا
    # إذا كان TARGET_CHAT_ID لا يزال 0، فهذا يعني أننا في وضع الكشف عن الـ ID
    if TARGET_CHAT_ID != 0 and chat_id != int(TARGET_CHAT_ID):
        logger.warning(f"تم تجاهل الرسالة من دردشة غير مستهدفة: {chat_id}")
        return

    tiktok_url = find_tiktok_url(message_text)
    if not tiktok_url:
        logger.info("لا يوجد رابط TikTok في الرسالة.")
        return # لا يوجد رابط، لا تفعل شيئًا

    logger.info(f"تم العثور على رابط TikTok: {tiktok_url}")
    
    # إرسال رسالة للمستخدم لإعلامه بأن المعالجة بدأت
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
                    read_timeout=120, # زيادة مهلة القراءة
                    write_timeout=120, # زيادة مهلة الكتابة
                    connect_timeout=30 # زيادة مهلة الاتصال
                )
            # حذف رسالة "جاري المعالجة" بعد الإرسال الناجح
            await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)

    except Exception as e:
        logger.error(f"حدث خطأ غير متوقع في معالجة الرسالة: {e}", exc_info=True) # exc_info=True لطباعة traceback
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_message.message_id,
            text=f"حدث خطأ أثناء الإرسال: {e}"
        )
        # انتظر قليلا قبل المحاولة مرة أخرى أو الإغلاق لتجنب الإغلاق المتكرر السريع
        await asyncio.sleep(5) 
    finally:
        # تأكد من حذف الملف المؤقت دائمًا
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"تم حذف الملف المؤقت: {file_path}")
        # تنظيف مجلد التحميل المؤقت في حالة وجود أي ملفات متبقية
        if os.path.exists(TEMP_DOWNLOAD_DIR) and os.path.isdir(TEMP_DOWNLOAD_DIR):
            for f in os.listdir(TEMP_DOWNLOAD_DIR):
                os.remove(os.path.join(TEMP_DOWNLOAD_DIR, f))
            logger.info(f"تم تنظيف مجلد التحميل المؤقت: {TEMP_DOWNLOAD_DIR}")


def main() -> None:
    """بدء تشغيل البوت."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("لم يتم العثور على توكن البوت! يرجى تعيينه في الكود.")
    
    if TARGET_CHAT_ID == 0:
        logger.warning("=================================================================")
        logger.warning("⚠️ تنبيه: لم يتم تعيين TARGET_CHAT_ID بعد! ⚠️")
        logger.warning("البوت سيستجيب في أي مجموعة تتم إضافته إليها.")
        logger.warning("للحصول على الـ ID: أضف البوت إلى مجموعتك، أرسل أي رسالة،")
        logger.warning("ثم انسخ الـ ID من سجلات Koyeb (Logs) وضعه في الكود وأعد النشر.")
        logger.warning("=================================================================")

    # إنشاء التطبيق
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # إضافة معالج للرسائل النصية والصور (التي قد تحتوي على روابط في التعليق)
    # filters.TEXT: لمعالجة الرسائل النصية
    # ~filters.COMMAND: لتجاهل الأوامر مثل /start
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("البوت بدأ التشغيل... ينتظر الرسائل...")
    # تشغيل البوت حتى يتم إيقافه يدويًا
    application.run_polling(poll_interval=1, timeout=30, read_timeout=30, connect_timeout=30) # زيادة المهلة
    logger.info("البوت توقف عن العمل.")


if __name__ == "__main__":
    main()