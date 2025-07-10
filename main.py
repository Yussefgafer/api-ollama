import os
import logging
import yt_dlp
import re
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    MessageHandler,
    filters,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)
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

# حالات المحادثة
WAITING_FOR_QUALITY = 1

# دالة لتنظيف مجلد التحميل المؤقت
def clean_temp_dir():
    if os.path.exists(TEMP_DOWNLOAD_DIR) and os.path.isdir(TEMP_DOWNLOAD_DIR):
        for f in os.listdir(TEMP_DOWNLOAD_DIR):
            os.remove(os.path.join(TEMP_DOWNLOAD_DIR, f))
        logger.info(f"تم تنظيف مجلد التحميل المؤقت: {TEMP_DOWNLOAD_DIR}")

def find_video_urls(text: str):
    """يبحث عن روابط الفيديوهات في النص."""
    # نمط شامل لروابط الفيديو يدعم مواقع مثل TikTok و YouTube
    # يمكن توسيعه ليشمل المزيد من المواقع إذا لزم الأمر
    pattern = r'https?://(?:www\.)?(?:tiktok\.com/[^\s]+|youtube\.com/watch\?v=[^\s]+|youtu\.be/[^\s]+)'
    return re.findall(pattern, text)

def extract_video_info_and_qualities(url: str):
    """يستخرج معلومات الفيديو وخيارات الجودة المتاحة."""
    ydl_opts = {
        'quiet': True,
        'nocheckcertificate': True, # مفيد لبعض المواقع
        'skip_download': True, # لا تقم بالتحميل، فقط استخرج المعلومات
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            if 'formats' in info:
                # تصفية الفيديوهات التي تحتوي على صوت وفيديو (أو فيديو فقط)
                # وترتيبها حسب الجودة
                formats = sorted([
                    f for f in info['formats'] 
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('ext') == 'mp4'
                ], key=lambda x: x.get('height', 0), reverse=True)
            
            # بناء قائمة بخيارات الجودة الفريدة
            quality_options = []
            seen_qualities = set()
            for f in formats:
                quality_label = f.get('format_note') or f.get('format_id')
                if f.get('height'):
                    quality_label = f"{f['height']}p"
                elif f.get('resolution'):
                    quality_label = f['resolution']
                
                if quality_label and quality_label not in seen_qualities:
                    quality_options.append({
                        'label': quality_label,
                        'format_id': f['format_id']
                    })
                    seen_qualities.add(quality_label)
            
            # ⚠️ تم تصحيح هذا السطر ⚠️
            quality_options.insert(0, {'label': 'أفضل جودة (Best)', 'format_id': 'best'})

            return info, quality_options
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"خطأ في استخراج معلومات الفيديو من {url}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"حدث خطأ عام أثناء استخراج معلومات الفيديو: {e}", exc_info=True)
        return None, None

async def download_and_send_video(
    chat_id: int,
    video_url: str,
    context: ContextTypes.DEFAULT_TYPE,
    reply_to_message_id: int,
    format_id: str = 'best'
):
    """يقوم بتحميل فيديو وإرسال الصورة المصغرة ثم الفيديو."""
    processing_message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"جاري معالجة الفيديو: {video_url} ⏳",
        reply_to_message_id=reply_to_message_id
    )

    file_path = None
    thumbnail_path = None
    try:
        os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'writethumbnail': True, # لكتابة الصورة المصغرة
            'postprocessors': [{ # لتحويل الصورة المصغرة إلى JPG إذا لزم الأمر
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }, {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }, {
                'key': 'EmbedThumbnail',
                'already_have_thumbnail': False # لتضمين الصورة المصغرة في الفيديو (اختياري)
            }],
            'quiet': True,
            'noplaylist': True,
            'nooverwrites': True,
            'retries': 3,
            'external_downloader_args': ['-loglevel', 'error'],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            
            # البحث عن مسار الصورة المصغرة
            if 'thumbnails' in info_dict and info_dict['thumbnails']:
                thumbnail_url = info_dict['thumbnails'][-1]['url'] # آخر صورة مصغرة هي الأعلى جودة
                thumbnail_ext = thumbnail_url.split('.')[-1].split('?')[0]
                thumbnail_path = os.path.join(TEMP_DOWNLOAD_DIR, f"{info_dict['id']}.{thumbnail_ext}")
                # yt-dlp تقوم بتنزيل الصورة المصغرة تلقائيًا مع writethumbnail
                # لذا يجب أن يكون الملف موجودًا بالفعل
                if not os.path.exists(thumbnail_path):
                    # في بعض الحالات قد لا تكون اللاحقة jpg/webp
                    # نبحث عن أي ملف صورة مصغرة تم تنزيله
                    for fname in os.listdir(TEMP_DOWNLOAD_DIR):
                        if fname.startswith(info_dict['id']) and (fname.endswith('.jpg') or fname.endswith('.webp')):
                            thumbnail_path = os.path.join(TEMP_DOWNLOAD_DIR, fname)
                            break
            
            if not os.path.exists(file_path):
                raise Exception("فشل تحميل الفيديو: الملف غير موجود بعد عملية yt-dlp.")

            logger.info(f"تم تحميل الفيديو بنجاح: {file_path}")
            file_size = os.path.getsize(file_path)
            logger.info(f"حجم الملف: {file_size / 1024/1024:.2f} MB")

            caption = f"تم التحميل بواسطة بوت Rikka ❤️\n\n[الرابط الأصلي]({video_url})"

            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"جاري إرسال الصورة المصغرة: {thumbnail_path}")
                with open(thumbnail_path, 'rb') as thumb_file:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=thumb_file,
                        caption=f"صورة مصغرة للفيديو من: {video_url}",
                        reply_to_message_id=reply_to_message_id
                    )
                await asyncio.sleep(1) # انتظر قليلاً قبل إرسال الفيديو

            if file_size > TELEGRAM_MAX_FILE_SIZE:
                logger.warning("حجم الفيديو كبير جدًا، سيتم إرسال رابط مباشر بدلاً من الملف.")
                message = f"الفيديو كبير جدًا للتحميل المباشر ({file_size / 1024 / 1024:.2f} MB).\n\n**الرابط الأصلي:** {video_url}"
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
                        reply_to_message_id=reply_to_message_id,
                        read_timeout=180, # زيادة المهلة
                        write_timeout=180, # زيادة المهلة
                        connect_timeout=60 # زيادة المهلة
                    )
                await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)

    except Exception as e:
        logger.error(f"حدث خطأ أثناء تحميل أو إرسال الفيديو: {e}", exc_info=True)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_message.message_id,
            text=f"عذرًا، فشلت معالجة الفيديو من {video_url}. 😞 الخطأ: {e}"
        )
    finally:
        clean_temp_dir()

async def start_download_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يبدأ عملية تحميل الفيديو ويطلب الجودة."""
    chat_id = update.message.chat_id
    message_text = update.message.text

    if chat_id != int(TARGET_CHAT_ID):
        await update.message.reply_text("أنا أعمل فقط في المجموعة المحددة.")
        return ConversationHandler.END

    video_urls = find_video_urls(message_text)
    if not video_urls:
        await update.message.reply_text("الرجاء إرسال رابط فيديو صالح.")
        return ConversationHandler.END

    # تخزين الروابط في user_data لكي نصل إليها لاحقًا
    context.user_data['video_urls'] = video_urls
    
    # استخراج معلومات الجودة من أول رابط فقط لتقديم الخيارات
    # نفترض أن الجودة ستكون متشابهة لمعظم الفيديوهات من نفس الموقع
    first_url_info, quality_options = extract_video_info_and_qualities(video_urls[0])

    if not quality_options:
        await update.message.reply_text("عذرًا، لم أتمكن من العثور على خيارات جودة لهذا الفيديو. 😞")
        # حاول تنزيل أفضل جودة تلقائيا إذا لم تتوفر خيارات
        await download_and_send_video(
            chat_id, video_urls[0], context, update.message.message_id, 'best'
        )
        return ConversationHandler.END

    keyboard = []
    for option in quality_options:
        keyboard.append([InlineKeyboardButton(option['label'], callback_data=option['format_id'])])
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "الرجاء اختيار جودة الفيديو المطلوبة:",
        reply_markup=reply_markup,
        reply_to_message_id=update.message.message_id
    )
    return WAITING_FOR_QUALITY

async def handle_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعالج اختيار المستخدم للجودة ويبدأ التحميل."""
    query = update.callback_query
    await query.answer() # يجب استدعاء answer() لإنهاء استعلام رد الاتصال

    selected_format_id = query.data
    chat_id = query.message.chat_id
    original_message_id = query.message.reply_to_message.message_id if query.message.reply_to_message else query.message.message_id
    
    video_urls = context.user_data.get('video_urls', [])

    if not video_urls:
        await context.bot.send_message(chat_id, "حدث خطأ: لم أجد روابط الفيديو. الرجاء إعادة المحاولة.")
        return ConversationHandler.END

    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=query.message.message_id,
        text=f"تم اختيار الجودة: {selected_format_id}. جاري التحميل..."
    )

    for url in video_urls:
        await download_and_send_video(
            chat_id, url, context, original_message_id, selected_format_id
        )
        await asyncio.sleep(2) # انتظر قليلاً بين الفيديوهات إذا كانت متعددة

    context.user_data.clear() # تنظيف بيانات المستخدم بعد الانتهاء
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يلغي أي محادثة جارية."""
    await update.message.reply_text("تم إلغاء العملية.")
    context.user_data.clear()
    return ConversationHandler.END

async def send_random_tiktok_video_to_group(context: ContextTypes.DEFAULT_TYPE):
    """دالة للبحث عن فيديو TikTok عشوائي وإرساله."""
    if not TIKTOK_SOURCES:
        logger.warning("لا توجد مصادر TikTok محددة في قائمة TIKTOK_SOURCES.")
        return

    selected_source = random.choice(TIKTOK_SOURCES)
    
    if selected_source.startswith('@'):
        tiktok_search_url = f"https://www.tiktok.com/{selected_source}"
    else:
        tiktok_search_url = f"https://www.tiktok.com/tag/{selected_source}"

    logger.info(f"جاري البحث عن فيديو عشوائي من مصدر TikTok: {tiktok_search_url}")

    video_url_to_download = None
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'noplaylist': True}) as ydl:
            info = ydl.extract_info(tiktok_search_url, download=False)
            
            entries = []
            if 'entries' in info:
                entries = [e for e in info['entries'] if e and e.get('url')]
            elif info.get('url'):
                entries = [info]

            if not entries:
                logger.warning(f"لم يتم العثور على فيديوهات من المصدر: {tiktok_search_url}")
                await context.bot.send_message(
                    chat_id=TARGET_CHAT_ID,
                    text=f"عذرًا، لم أجد فيديوهات من مصدر TikTok: {selected_source} 😔"
                )
                return
            
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

    if video_url_to_download:
        await download_and_send_video(
            TARGET_CHAT_ID, video_url_to_download, context, None, 'best'
        )

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
        send_random_tiktok_video_to_group,
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


def main() -> None:
    """بدء تشغيل البوت."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("لم يتم العثور على توكن البوت! يرجى تعيينه في الكود.")
    
    logger.info("تم تعيين TARGET_CHAT_ID: %s", TARGET_CHAT_ID)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # معالج المحادثة لتحميل الفيديو وتحديد الجودة
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Chat(int(TARGET_CHAT_ID)), start_download_conversation)
        ],
        states={
            WAITING_FOR_QUALITY: [CallbackQueryHandler(handle_quality_selection)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))

    logger.info("البوت بدأ التشغيل... ينتظر الرسائل والأوامر...")
    application.run_polling(poll_interval=1, timeout=30, read_timeout=30, connect_timeout=30)
    logger.info("البوت توقف عن العمل.")


if __name__ == "__main__": # تم تصحيح هذا السطر أيضاً
    main()