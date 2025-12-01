# backend/tts.py
import tempfile
import os
import logging
from pathlib import Path
import asyncio # <-- NEW IMPORT

# --- Robust Import for TTS ---
try:
    import edge_tts
except ImportError:
    edge_tts = None

# --- Robust Import for Whisper (ASR) ---
# Assuming the standard OpenAI/PyTorch whisper package is used: 'pip install whisper'
WHISPER_MODEL = None
try:
    import whisper 
except ImportError:
    whisper = None
    
logger = logging.getLogger(__name__)

# Voice Options: 
# en-US-ChristopherNeural (Male, Calm)
# en-US-EricNeural (Male, Authoritative)
# en-US-MichelleNeural (Female, Professional)
VOICE = "en-US-JennyNeural"

async def generate_audio_briefing(text: str) -> str:
    """
    Generates an MP3 file from the text using Edge TTS.
    Returns the path to the temporary file.
    """
    if not edge_tts:
        logger.warning("Edge TTS not installed. Audio briefing generation skipped.")
        return ""

    try:
        # Create a temp file
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(path)
        
        logger.info(f"Generated TTS briefing at {path}")
        return path
    except Exception as e:
        logger.error(f"TTS Generation Failed: {e}")
        return ""

# --- NEW WHISPER ASR LOGIC ---

async def load_whisper_model(model_name: str = "base"):
    global WHISPER_MODEL
    if WHISPER_MODEL is None and whisper:
        try:
            # Model loading is a blocking operation, so use asyncio.to_thread
            WHISPER_MODEL = await asyncio.to_thread(whisper.load_model, model_name)
            logger.info(f"Successfully loaded Whisper model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model '{model_name}': {e}")
            WHISPER_MODEL = False # Use False to indicate a failed attempt
    elif not whisper:
        WHISPER_MODEL = False
        
    return WHISPER_MODEL

async def get_whisper_model():
    """
    Returns the loaded Whisper model or None if unavailable.
    Loads the model if it hasn't been attempted yet.
    """
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        # Attempt to load the model on first call
        return await load_whisper_model()
    elif WHISPER_MODEL is False:
        # Return None if loading failed previously or library is missing
        return None
        
    return WHISPER_MODEL