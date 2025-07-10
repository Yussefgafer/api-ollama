# Dockerfile (النسخة النهائية القوية)

# 1. استخدم صورة Node.js كاملة (مبنية على Debian) كنقطة بداية
FROM node:20-bookworm

# 2. قم بتثبيت أدوات البناء الأساسية التي قد تحتاجها بعض حزم npm
#    - python3, make, g++ هي الأدوات الأكثر شيوعًا
#    - يتم تحديث قائمة الحزم أولاً لضمان الحصول على أحدث الإصدارات
RUN apt-get update && apt-get install -y \
    python3 \
    make \
    g++ \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 3. تعيين دليل العمل داخل الحاوية
WORKDIR /app

# 4. نسخ ملفات package.json للاستفادة من التخزين المؤقت لـ Docker
COPY package*.json ./

# 5. تثبيت تبعيات Node.js
#    الآن يجب أن ينجح هذا الأمر لأن أدوات البناء موجودة
RUN npm install --omit=dev

# 6. نسخ باقي كود التطبيق
COPY . .

# 7. تعيين المنفذ
EXPOSE 3000

# 8. الأمر الافتراضي لبدء التشغيل
CMD [ "npm", "start" ]