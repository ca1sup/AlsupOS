
# backend/tts.py
import tempfile
import os
import logging
import asyncio
import soundfile as sf
from pathlib import Path
from backend.config import STT_MODEL_NAME, TTS_MODEL_NAME, TTS_VOICE

logger = logging.getLogger(__name__)

# --- Robust Import for MLX Whisper (STT) ---
MLX_WHISPER_AVAILABLE = False
try:
    import mlx_whisper
    MLX_WHISPER_AVAILABLE = True
except ImportError:
    logger.warning("❌ mlx_whisper not installed. STT disabled. Run: pip install mlx-whisper")

# --- Robust Import for MLX Audio (Kokoro TTS) ---
MLX_TTS_AVAILABLE = False
try:
    from mlx_audio.tts.models.kokoro import KokoroPipeline
    from mlx_audio.tts.utils import load_model as load_tts_model_raw
    MLX_TTS_AVAILABLE = True
except ImportError:
    logger.warning("❌ mlx-audio not installed. TTS disabled. Run: pip install mlx-audio soundfile")

# --- MLX WHISPER WRAPPER (STT) ---
class MLXWhisperWrapper:
    """
    Wraps mlx_whisper to mimic the OpenAI Whisper API structure
    expected by the rest of the application (model.transcribe).
    """
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._is_ready = True # MLX loads lazily/instantly

    def transcribe(self, audio_path: str, **kwargs) -> dict:
        if not MLX_WHISPER_AVAILABLE:
            raise RuntimeError("mlx-whisper library is not available.")
        
        # Extract initial_prompt if present
        prompt = kwargs.get('initial_prompt', "Voice dictation.")
        
        # MLX Whisper transcribe function
        result = mlx_whisper.transcribe(
            audio_path, 
            path_or_hf_repo=self.model_path,
            initial_prompt=prompt,
            verbose=False
        )
        
        # --- HALLUCINATION FILTER ---
        text = result.get('text', '').strip()
        hallucinations = [
            "Thank you.", "Thank you", "Thanks.", "Thanks", 
            "Thank you for watching.", "You", "MBC News", 
            "Subscribe", "Bye."
        ]
        
        # Filter single char noise (e.g. ".")
        if len(text) < 2 and text in ['.', '?', '!', ',']:
             logger.info(f"🧹 Filtered punctuation: '{text}'")
             result['text'] = ""
             return result

        if text in hallucinations or text.lower() in [h.lower() for h in hallucinations]:
            logger.info(f"🧹 Filtered hallucination: '{text}'")
            result['text'] = ""
            
        return result

# Singleton Storage for STT
WHISPER_INSTANCE = None

async def load_whisper_model():
    """
    Initializes the MLX Whisper wrapper.
    """
    global WHISPER_INSTANCE
    
    if not MLX_WHISPER_AVAILABLE:
        logger.error("❌ mlx-whisper not installed. STT disabled.")
        return None

    if WHISPER_INSTANCE:
        return WHISPER_INSTANCE

    logger.info(f"🎙️ Configuring MLX Whisper: {STT_MODEL_NAME}")
    
    try:
        wrapper = MLXWhisperWrapper(STT_MODEL_NAME)
        
        # WARMUP
        logger.info("⏳ Warming up Whisper...")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            header = b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
            tmp.write(header)
            tmp_path = tmp.name
            
        try:
            await asyncio.to_thread(wrapper.transcribe, tmp_path)
            logger.info("✅ MLX Whisper Ready.")
        except Exception as e:
            logger.warning(f"⚠️ Whisper Warmup failed (non-critical): {e}")
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

        WHISPER_INSTANCE = wrapper
        return wrapper

    except Exception as e:
        logger.error(f"❌ Failed to initialize MLX Whisper: {e}")
        return None

async def get_whisper_model():
    global WHISPER_INSTANCE
    if WHISPER_INSTANCE:
        return WHISPER_INSTANCE
    return await load_whisper_model()


# --- KOKORO TTS WRAPPER ---

# Singleton Storage for TTS
TTS_PIPELINE_INSTANCE = None

async def get_tts_pipeline():
    """
    Lazy loads the Kokoro TTS pipeline.
    """
    global TTS_PIPELINE_INSTANCE
    if not MLX_TTS_AVAILABLE:
        logger.error("❌ mlx-audio (Kokoro) not installed.")
        return None

    if TTS_PIPELINE_INSTANCE:
        return TTS_PIPELINE_INSTANCE

    logger.info(f"🗣️ Loading Kokoro TTS: {TTS_MODEL_NAME}")
    try:
        def _load():
            model = load_tts_model_raw(TTS_MODEL_NAME)
            # lang_code 'a' = American English, 'b' = British English
            lang = 'a' if 'af_' in TTS_VOICE or 'am_' in TTS_VOICE else 'b'
            return KokoroPipeline(lang_code=lang, model=model, repo_id=TTS_MODEL_NAME)

        TTS_PIPELINE_INSTANCE = await asyncio.to_thread(_load)
        logger.info("✅ Kokoro TTS Loaded.")
        return TTS_PIPELINE_INSTANCE
    except Exception as e:
        logger.error(f"❌ Failed to load Kokoro TTS: {e}")
        return None

async def generate_audio_briefing(text: str) -> str:
    """
    Generates an audio file from the text using local Kokoro TTS (MLX).
    Returns the path to the temporary file.
    """
    pipeline = await get_tts_pipeline()
    
    if not pipeline:
        logger.warning("TTS Pipeline unavailable. Audio briefing generation skipped.")
        return ""

    try:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        logger.info(f"Generating TTS for {len(text)} chars...")

        def _synthesize():
            # Kokoro generation
            audio_data, sample_rate = pipeline(text, voice=TTS_VOICE, speed=1.0)
            sf.write(path, audio_data, sample_rate)
        
        await asyncio.to_thread(_synthesize)
        
        logger.info(f"Generated TTS audio at {path}")
        return path
    except Exception as e:
        logger.error(f"TTS Generation Failed: {e}")
        return ""