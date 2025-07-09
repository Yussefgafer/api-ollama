# استخدم صورة بايثون خفيفة كنقطة بداية
FROM python:3.9-slim

# ثبت الأدوات اللازمة (curl) و Ollama نفسه
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://ollama.ai/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# أنشئ مستخدمًا غير مسؤول (لأمان أفضل)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH="/home/user/.local/bin:$PATH"
WORKDIR $HOME/app

# انسخ ملف المتطلبات وثبتها
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# انسخ باقي ملفات التطبيق
COPY --chown=user . .

# أعطِ صلاحيات التنفيذ لسكربت البداية
RUN chmod +x start.sh

# الأمر الذي سيتم تشغيله عند بدء الحاوية
CMD ["./start.sh"]