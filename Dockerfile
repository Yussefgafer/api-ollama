# --- المرحلة الأولى: البنّاء (Builder Stage) ---
# نستخدم صورة Python كاملة تحتوي على جميع أدوات البناء اللازمة
# هذا يضمن أن أي مكتبة Python تحتاج إلى تجميع (compilation) ستجد الأدوات المناسبة.
FROM python:3.10 as builder

# تحديث قائمة الحزم وتثبيت الحزم الأساسية للنظام:
# - build-essential: مجموعة من الأدوات الضرورية لتجميع البرامج.
# - pkg-config: أداة مساعدة للعثور على المكتبات المطلوبة أثناء التجميع.
# - libssl-dev, libffi-dev: تبعيات شائعة لبعض مكتبات Python المتعلقة بالشبكات والأمان.
# - ffmpeg: الأداة الأساسية لمعالجة الفيديوهات التي تعتمد عليها yt-dlp.
# --no-install-recommends: لتجنب تثبيت حزم إضافية غير ضرورية وتقليل حجم الصورة.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libssl-dev \
    libffi-dev \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# إنشاء بيئة Python افتراضية معزولة (Virtual Environment)
# هذه ممارسة جيدة لفصل تبعيات المشروع عن تبعيات النظام.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
# إضافة المسار الخاص بالبيئة الافتراضية إلى متغير PATH
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# نسخ ملف الاعتماديات (requirements.txt) إلى مجلد العمل وتثبيت المكتبات.
# تتم هذه الخطوة في مرحلة البناء لأننا نحتاج أدوات التجميع هنا.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# --- المرحلة الثانية: الصورة النهائية (Final Image) ---
# نعود إلى الصورة النحيفة (slim) لتقليل حجم الصورة النهائية قدر الإمكان.
FROM python:3.10-slim

# من مرحلة البناء (builder)، انسخ فقط ما نحتاجه لتشغيل التطبيق:
# 1. برنامج ffmpeg: ضروري لـ yt-dlp
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
# 2. البيئة الافتراضية الكاملة: تحتوي على جميع مكتبات Python المثبتة مسبقًا.
COPY --from=builder /opt/venv /opt/venv

# تفعيل البيئة الافتراضية في الصورة النهائية.
ENV PATH="/opt/venv/bin:$PATH"

# إعداد مجلد العمل داخل الحاوية ونسخ كود التطبيق.
WORKDIR /app
COPY main.py .

# الأمر النهائي الذي سيتم تشغيله عند بدء تشغيل الحاوية.
# هذا الأمر يقوم بتشغيل ملف main.py الذي يحتوي على كود البوت.
CMD ["python", "main.py"]