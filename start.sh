#!/bin/bash

# ابدأ تشغيل Ollama في الخلفية
ollama serve &

# انتظر قليلاً ليبدأ الخادم
sleep 5

# اسحب نموذجًا صغيرًا جدًا إذا لم يكن موجودًا
# هذا ضروري لأن موارد Koyeb المجانية محدودة
echo "Checking for tinyllama model..."
if ! ollama list | grep -q "tinyllama"; then
    echo "Pulling tinyllama... This might take a moment."
    ollama pull tinyllama
    echo "tinyllama model pulled."
else
    echo "tinyllama model already exists."
fi

# انتظر حتى يصبح Ollama جاهزًا (بحد أقصى 60 ثانية)
max_attempts=60
attempt=0
echo "Waiting for Ollama to become ready..."
while ! curl -s http://localhost:11434/api/tags >/dev/null; do
    sleep 1
    attempt=$((attempt + 1))
    if [ $attempt -eq $max_attempts ]; then
        echo "Ollama failed to start within 60 seconds. Exiting."
        exit 1
    fi
    # طباعة نقطة لإظهار التقدم
    printf "."
done
echo "\nOllama is ready."

# ابدأ تشغيل خادم FastAPI على المنفذ 8000 (المفضل لدى Koyeb)
echo "Starting FastAPI server..."
uvicorn app:app --host 0.0.0.0 --port 8000