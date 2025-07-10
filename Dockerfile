# --- المرحلة الأولى: البنّاء (Builder) ---
# نستخدم صورة كاملة تحتوي على أدوات البناء اللازمة
FROM python:3.10 as builder

# تحديث وتثبيت حزم النظام:
# build-essential: ضرورية لتجميع بعض مكتبات بايثون
# ffmpeg: ضرورية لمعالجة الفيديو
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# إنشاء بيئة بايثون افتراضية معزولة (ممارسة جيدة)
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# نسخ ملف الاعتماديات وتثبيت المكتبات داخل البيئة الافتراضية
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# --- المرحلة الثانية: الصورة النهائية (Final Image) ---
# نعود إلى الصورة النحيفة للحفاظ على الحجم الصغير
FROM python:3.10-slim

# من مرحلة البناء، انسخ فقط ما نحتاجه:
# 1. برنامج ffmpeg
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
# 2. البيئة الافتراضية الكاملة مع كل المكتبات المثبتة
COPY --from=builder /opt/venv /opt/venv

# تفعيل البيئة الافتراضية في الصورة النهائية
ENV PATH="/opt/venv/bin:$PATH"

# إعداد مجلد العمل ونسخ كود التطبيق
WORKDIR /app
COPY main.py .

# الأمر النهائي لتشغيل البوت
CMD ["python", "main.py"]