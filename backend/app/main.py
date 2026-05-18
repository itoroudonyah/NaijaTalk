# FastAPI entry point

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict
import json
import base64
import asyncio
import os
from .websocket_manager import ConnectionManager
from .services.audio_processor import AudioProcessor

# Initialize FastAPI
app = FastAPI(
    title="NaijaTalk API",
    description="Real-time speech translation for Nigerian languages",
    version="1.0.0"
)

# CORS configuration for NaijaTalk frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:52427",  # Flutter web default
        "*"  # For development only - restrict in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
manager = ConnectionManager()
audio_processor = AudioProcessor()

@app.on_event("startup")
async def startup_event():
    import threading
    warmup_thread = threading.Thread(target=audio_processor.warmup_models, daemon=True)
    warmup_thread.start()

@app.get("/")
async def root():
    return {
        "app": "NaijaTalk",
        "version": "1.0.0",
        "status": "running",
        "message": "🇳🇬 Breaking language barriers across Nigeria!"
    }

@app.get("/languages")
async def get_languages():
    """Return supported languages for NaijaTalk"""
    return {
        "languages": [
            {"code": "en", "name": "English", "flag": "🇬🇧", "native_name": "English"},
            {"code": "yo", "name": "Yoruba", "flag": "🇳🇬", "native_name": "Èdè Yorùbá"},
            {"code": "ha", "name": "Hausa", "flag": "🇳🇬", "native_name": "Harshen Hausa"},
            {"code": "ig", "name": "Igbo", "flag": "🇳🇬", "native_name": "Asụsụ Igbo"}
        ],
        "default_source": "en",
        "default_target": "yo"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "NaijaTalk Backend"}

@app.websocket("/ws/translate/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time translation"""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message from Flutter client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "audio":
                # Decode base64 audio
                audio_bytes = base64.b64decode(message["data"])
                source_lang = message.get("source_lang", "en")
                target_lang = message.get("target_lang", "yo")
                tts_provider = message.get("tts_provider", "yarngpt")
                
                # Process audio to text first
                result = await audio_processor.transcribe_and_translate(
                    audio_bytes, 
                    source_lang, 
                    target_lang
                )
                
                # Send text immediately
                await manager.send_message(client_id, {
                    "type": "translation",
                    "original_text": result.get("original_text", ""),
                    "translated_text": result["text"],
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "timestamp": asyncio.get_event_loop().time()
                })

                # Send audio as a second message
                audio_base64 = await audio_processor.synthesize_translation_audio(
                    result["text"],
                    target_lang,
                    tts_provider,
                )
                await manager.send_message(client_id, {
                    "type": "translation_audio",
                    "audio": audio_base64,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "tts_provider": tts_provider,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        print(f"Client {client_id} disconnected")
    except Exception as e:
        print(f"Error: {e}")
        await manager.send_message(client_id, {
            "type": "error",
            "message": str(e)
        })
