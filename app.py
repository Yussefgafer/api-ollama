from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import requests
import json

app = FastAPI()

# عنوان Ollama الداخلي داخل الحاوية
OLLAMA_BASE_URL = "http://localhost:11434"

# نقطة نهاية للدردشة (الأكثر أهمية)
@app.post("/v1/chat/completions")
async def ollama_chat(body: dict):
    url = f"{OLLAMA_BASE_URL}/api/chat"
    try:
        # أعد توجيه الطلب إلى Ollama مع دعم التدفق (streaming)
        response = requests.post(url, json=body, stream=True)
        response.raise_for_status()

        # قم ببث الاستجابة مرة أخرى إلى العميل
        def generate():
            for chunk in response.iter_lines():
                if chunk:
                    # تحويل استجابة Ollama لتكون متوافقة مع شكل OpenAI
                    ollama_response = json.loads(chunk)
                    openai_response = {
                        "id": f"chatcmpl-{ollama_response.get('created_at')}",
                        "object": "chat.completion.chunk",
                        "created": ollama_response.get('created_at'),
                        "model": ollama_response.get('model'),
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "content": ollama_response.get('message', {}).get('content', '')
                            },
                            "finish_reason": ollama_response.get('done')
                        }]
                    }
                    yield f"data: {json.dumps(openai_response)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")

# نقطة نهاية لجلب قائمة النماذج (متوافقة مع OpenAI)
@app.get("/v1/models")
async def list_models():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags")
        response.raise_for_status()
        models_data = response.json()
        
        # تحويل قائمة نماذج Ollama لتكون متوافقة مع شكل OpenAI
        openai_models = {
            "object": "list",
            "data": [
                {
                    "id": model["name"],
                    "object": "model",
                    "created": model["modified_at"],
                    "owned_by": "user"
                } for model in models_data.get("models", [])
            ]
        }
        return openai_models
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))