# Dockerfile
# استخدم صورة Node.js كاملة. هذا أكثر موثوقية لتبعيات معقدة.
FROM node:20

# تعيين دليل العمل داخل الحاوية
WORKDIR /app

# نسخ ملفات package.json و package-lock.json (إن وجد)
COPY package*.json ./

# تثبيت تبعيات Node.js
RUN npm install --omit=dev

# نسخ باقي كود التطبيق إلى دليل العمل
COPY . .

# تعيين المنفذ الذي يستمع إليه التطبيق داخل الحاوية
EXPOSE 3000

# الأمر الذي سيتم تنفيذه عند بدء تشغيل الحاوية
CMD [ "npm", "start" ]