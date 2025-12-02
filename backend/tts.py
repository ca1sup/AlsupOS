import tempfile
import os
import logging
import asyncio
import soundfile as sf
import numpy as np
from pathlib import Path
from backend.database import get_all_settings
from backend.config import STT_MODEL_NAME, TTS_MODEL_NAME, TTS_VOICE as DEFAULT_VOICE

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

# Valid voice mappings for Kokoro-82M-bf16
KOKORO_VOICES = {
    'a': {  # American English
        'male': ['am_adam', 'am_michael'],
        'female': ['af_heart', 'af_bella', 'af_nicole', 'af_sarah', 'af_sky']
    },
    'b': {  # British English
        'male': ['bm_lewis'],
        'female': ['bf_emma', 'bf_isabella']
    }
}

def get_valid_voice(requested_voice: str, lang_code: str) -> str:
    """Returns a valid voice, falling back to defaults if needed."""
    all_voices = KOKORO_VOICES.get(lang_code, {})
    valid_voices = all_voices.get('male', []) + all_voices.get('female', [])
    
    if requested_voice in valid_voices:
        return requested_voice
    
    # Fallback logic
    fallback = None
    if requested_voice.startswith('am_') or requested_voice.startswith('bm_'):
        fallback = all_voices.get('male', [None])[0]
    else:
        fallback = all_voices.get('female', [None])[0]
    
    if not fallback:
        fallback = valid_voices[0] if valid_voices else 'af_heart'
    
    return fallback

# --- MLX WHISPER WRAPPER (STT) ---
class MLXWhisperWrapper:
    """
    Wraps mlx_whisper to mimic the OpenAI Whisper API structure.
    """
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._is_ready = True

    def transcribe(self, audio_path: str, **kwargs) -> dict:
        if not MLX_WHISPER_AVAILABLE:
            raise RuntimeError("mlx-whisper library is not available.")
        
        prompt = kwargs.get('initial_prompt', "Voice dictation.")
        
        result = mlx_whisper.transcribe(
            audio_path, 
            path_or_hf_repo=self.model_path,
            initial_prompt=prompt,
            verbose=False
        )
        # Hallucination filter removed per user request
        return result

# Singleton Storage for STT
WHISPER_INSTANCE = None

async def load_whisper_model():
    global WHISPER_INSTANCE
    if not MLX_WHISPER_AVAILABLE: return None
    if WHISPER_INSTANCE: return WHISPER_INSTANCE

    logger.info(f"🎙️ Configuring MLX Whisper: {STT_MODEL_NAME}")
    try:
        wrapper = MLXWhisperWrapper(STT_MODEL_NAME)
        # WARMUP
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            header = b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
            tmp.write(header)
            tmp_path = tmp.name
        try:
            await asyncio.to_thread(wrapper.transcribe, tmp_path)
        except Exception: pass
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

        WHISPER_INSTANCE = wrapper
        return wrapper
    except Exception as e:
        logger.error(f"❌ Failed to initialize MLX Whisper: {e}")
        return None

async def get_whisper_model():
    global WHISPER_INSTANCE
    if WHISPER_INSTANCE: return WHISPER_INSTANCE
    return await load_whisper_model()

# --- KOKORO TTS WRAPPER ---
TTS_PIPELINE_INSTANCE = None

async def get_tts_pipeline(voice_code='a'):
    global TTS_PIPELINE_INSTANCE
    if not MLX_TTS_AVAILABLE: return None
    if TTS_PIPELINE_INSTANCE: return TTS_PIPELINE_INSTANCE

    logger.info(f"🗣️ Loading Kokoro TTS: {TTS_MODEL_NAME}")
    try:
        def _load():
            model = load_tts_model_raw(TTS_MODEL_NAME)
            return KokoroPipeline(lang_code=voice_code, model=model, repo_id=TTS_MODEL_NAME)

        TTS_PIPELINE_INSTANCE = await asyncio.to_thread(_load)
        logger.info("✅ Kokoro TTS Loaded.")
        return TTS_PIPELINE_INSTANCE
    except Exception as e:
        logger.error(f"❌ Failed to load Kokoro TTS: {e}")
        return None

async def generate_audio_briefing(text: str) -> str:
    """
    Generates an audio file from the text using local Kokoro TTS (MLX).
    Consumes the generator to handle streaming output correctly.
    """
    settings = await get_all_settings()
    requested_voice = settings.get("tts_voice", DEFAULT_VOICE)
    
    # Determine lang code & validate voice
    lang_code = 'b' if requested_voice.startswith(('bf_', 'bm_')) else 'a'
    voice = get_valid_voice(requested_voice, lang_code)
    
    pipeline = await get_tts_pipeline(lang_code)
    if not pipeline: 
        logger.error("TTS pipeline not available")
        return ""

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    try:
        logger.info(f"Generating TTS for {len(text)} chars using voice '{voice}'...")

        def _synthesize():
            try:
                # 1. Call Pipeline
                logger.info("🔵 Calling pipeline...")
                result = pipeline(text, voice=voice, speed=1.0)
                
                # 2. Consume Result (Generator vs Object)
                sample_rate = 24000
                audio_parts = []
                
                # Check for Generator (Streaming Mode)
                if hasattr(result, '__next__') or (hasattr(result, '__iter__') and not isinstance(result, (tuple, list, np.ndarray))):
                    logger.info("🟡 Result is a generator - consuming chunks...")
                    for chunk in result:
                        # Inspect Chunk
                        part = chunk
                        if isinstance(chunk, tuple):
                            if len(chunk) > 0: part = chunk[0]
                            if len(chunk) >= 2 and isinstance(chunk[1], int): sample_rate = chunk[1]
                        
                        # Convert Chunk to NumPy immediately
                        if hasattr(part, 'numpy'): part = part.numpy()
                        elif not isinstance(part, np.ndarray): part = np.array(part)
                        
                        audio_parts.append(part)
                    logger.info(f"🟡 Collected {len(audio_parts)} chunks")
                
                # Check for Tuple (Single Result)
                elif isinstance(result, tuple):
                    logger.info("🟡 Result is a tuple")
                    if len(result) > 0:
                        part = result[0]
                        if len(result) >= 2 and isinstance(result[1], int): sample_rate = result[1]
                        
                        if hasattr(part, 'numpy'): part = part.numpy()
                        elif not isinstance(part, np.ndarray): part = np.array(part)
                        audio_parts.append(part)
                
                # Direct Object (Single Result)
                else:
                    logger.info("🟡 Result is a direct object")
                    part = result
                    if hasattr(part, 'numpy'): part = part.numpy()
                    elif not isinstance(part, np.ndarray): part = np.array(part)
                    audio_parts.append(part)

                # 3. Concatenate
                if not audio_parts:
                    raise ValueError("No audio data produced by pipeline")
                
                if len(audio_parts) == 1:
                    audio_data = audio_parts[0]
                else:
                    audio_data = np.concatenate(audio_parts)
                
                # 4. Final Validation & Squeeze
                # Flattens (N, 1) or (1, N) to (N,) for soundfile
                audio_data = np.squeeze(audio_data)
                
                if audio_data.size == 0:
                    raise ValueError("Final audio data is empty")
                
                # 5. Write
                logger.info(f"🟣 Writing to {path}: shape={audio_data.shape}, sr={sample_rate}")
                sf.write(path, audio_data, sample_rate)
                logger.info(f"✅ Successfully wrote audio file")

            except Exception as e:
                logger.error(f"❌ Synthesis logic failed: {e}", exc_info=True)
                raise e

        await asyncio.to_thread(_synthesize)
        return path

    except Exception as e:
        logger.error(f"❌ TTS Generation Failed: {e}", exc_info=True)
        if os.path.exists(path):
            try: os.remove(path)
            except: pass
        return ""