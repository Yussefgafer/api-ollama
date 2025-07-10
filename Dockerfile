# الخطوة 1: استخدم صورة Python رسمية كأساس
FROM python:3.10-slim

# الخطوة 2: تعيين مجلد العمل داخل الحاوية
WORKDIR /app

# الخطوة 3: تثبيت الأدوات اللازمة (ffmpeg)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# الخطوة 4: نسخ ملف الاعتماديات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# الخطوة 5: نسخ كود البوت إلى مجلد العمل
COPY main.py .

# الخطوة 6: تحديد الأمر لتشغيل البوت بشكل دائم
CMD ["python", "main.py"]