# Dockerfile
# استخدم صورة أساسية تحتوي على نظام تشغيل خفيف (مثل Alpine)
FROM alpine/git:latest as builder

# تثبيت curl و jq (لتحليل JSON إذا احتجت)
RUN apk add --no-cache curl jq

# تثبيت Ollama (نفس طريقة install.sh)
RUN curl -fsSL https://ollama.com/install.sh | sh

# سحب النموذج المطلوب
# يمكنك تغيير llama2 إلى أي نموذج آخر تريده (مثال: mistral, gemma)
# هذا سيجعل الصورة أكبر، ولكن النموذج سيكون متاحًا فورًا عند التشغيل
RUN ollama pull llama2 || true # || true لتجنب فشل البناء إذا كان السحب بطيئًا أو فشل مؤقتًا

# قم بإنشاء مستخدم غير جذر لتشغيل التطبيق بشكل آمن
RUN adduser -D ollama -u 1000
USER ollama

# تعيين مجلد العمل
WORKDIR /home/ollama

# تعريض المنفذ الافتراضي لـ Ollama
EXPOSE 11434

# أمر بدء التشغيل
# قم بتشغيل Ollama serve
CMD ["ollama", "serve"]