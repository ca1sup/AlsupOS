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
    import mlx.core as mx
    from mlx_audio.tts.models.kokoro import KokoroPipeline
    from mlx_audio.tts.utils import load_model as load_tts_model_raw
    MLX_TTS_AVAILABLE = True

    # --- MONKEYPATCH FOR KOKORO COMPATIBILITY ---
    # Fixes: KPipeline.__call__() got an unexpected keyword argument 'lang'
    # We patch the specific class imported from mlx_audio
    if hasattr(KokoroPipeline, '__call__'):
        _original_call = KokoroPipeline.__call__
        
        def _patched_call(self, *args, **kwargs):
            # Remove 'lang' if present, as newer Kokoro models/wrappers don't accept it here
            if 'lang' in kwargs:
                kwargs.pop('lang')
            return _original_call(self, *args, **kwargs)
            
        KokoroPipeline.__call__ = _patched_call
        logger.info("✅ Applied KokoroPipeline patch for 'lang' compatibility")
    # --------------------------------------------

except ImportError:
    logger.warning("❌ mlx-audio or mlx not installed. TTS disabled. Run: pip install mlx-audio soundfile")

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

def get_tts_pipeline_sync(voice_code='a'):
    """
    Synchronous loader for TTS Pipeline to avoid Metal threading crashes.
    """
    global TTS_PIPELINE_INSTANCE
    if not MLX_TTS_AVAILABLE: return None
    if TTS_PIPELINE_INSTANCE: return TTS_PIPELINE_INSTANCE

    logger.info(f"🗣️ Loading Kokoro TTS: {TTS_MODEL_NAME}")
    try:
        # Load model directly (not in a thread) to ensure Metal context is correct
        model = load_tts_model_raw(TTS_MODEL_NAME)
        
        # CRITICAL: Force evaluation of parameters to load weights into memory immediately.
        mx.eval(model.parameters())
        
        TTS_PIPELINE_INSTANCE = KokoroPipeline(lang_code=voice_code, model=model, repo_id=TTS_MODEL_NAME)
        logger.info("✅ Kokoro TTS Loaded.")
        return TTS_PIPELINE_INSTANCE
    except Exception as e:
        logger.error(f"❌ Failed to load Kokoro TTS: {e}")
        return None

async def generate_audio_briefing(text: str) -> str:
    """
    Generates an audio file from the text using local Kokoro TTS (MLX).
    """
    settings = await get_all_settings()
    requested_voice = settings.get("tts_voice", DEFAULT_VOICE)
    
    # Determine lang code & validate voice
    lang_code = 'b' if requested_voice.startswith(('bf_', 'bm_')) else 'a'
    voice = get_valid_voice(requested_voice, lang_code)
    
    # Call synchronous loader
    pipeline = get_tts_pipeline_sync(lang_code)
    
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
                
                # 2. Consume Result
                sample_rate = 24000
                audio_parts = []
                
                # Check for Generator (Streaming Mode)
                # MLX pipeline returns a generator yielding tuples/lists of (graphemes, phonemes, audio)
                is_generator = hasattr(result, '__next__') or (hasattr(result, '__iter__') and not isinstance(result, (tuple, list, np.ndarray)))
                
                if is_generator:
                    logger.info("🟡 Result is a generator - consuming chunks...")
                    for i, chunk in enumerate(result):
                        audio_part = None
                        
                        # Inspect structure: We look for a sequence of 3 items: (str, str, array)
                        if hasattr(chunk, '__len__') and len(chunk) == 3:
                            # Assume it's (graphemes, phonemes, audio)
                            try:
                                candidate = chunk[2]
                                # Verify it's not a string (phonemes are strings)
                                if not isinstance(candidate, (str, bytes)):
                                    audio_part = candidate
                            except IndexError:
                                pass
                        
                        # Fallback: if we couldn't extract from index 2, check if chunk itself is audio
                        if audio_part is None:
                            # If it's a big array/list, it's likely audio.
                            if hasattr(chunk, 'shape') and (len(chunk.shape) == 1 and chunk.shape[0] > 10):
                                audio_part = chunk
                            elif isinstance(chunk, list) and len(chunk) > 100: 
                                audio_part = chunk
                        
                        # Process audio_part
                        if audio_part is not None:
                            try:
                                # Convert MLX array or list to Numpy
                                if hasattr(audio_part, 'numpy'): 
                                    np_chunk = audio_part.numpy()
                                elif not isinstance(audio_part, np.ndarray):
                                    np_chunk = np.array(audio_part)
                                else:
                                    np_chunk = audio_part
                                
                                # FLATTEN to ensure 1D (samples,)
                                # This fixes the (1, N) vs (1, M) concatenation error
                                np_chunk = np_chunk.flatten()
                                
                                if np_chunk.size > 0:
                                    audio_parts.append(np_chunk)
                            except Exception as e:
                                logger.warning(f"⚠️ Chunk {i} conversion failed: {e}")
                                
                    logger.info(f"🟡 Collected {len(audio_parts)} chunks")
                
                # Handle Non-Generator (Single Result)
                else:
                    logger.info("🟡 Result is a single object")
                    part = result
                    # Unpack if tuple/list (graphemes, phonemes, audio)
                    if isinstance(result, (tuple, list)) and len(result) == 3:
                        part = result[2]
                    
                    if hasattr(part, 'numpy'): part = part.numpy()
                    elif not isinstance(part, np.ndarray): part = np.array(part)
                    
                    # Flatten here too
                    part = part.flatten()
                    
                    if part.size > 0:
                        audio_parts.append(part)

                # 3. Concatenate
                if not audio_parts:
                    raise ValueError("No audio data produced by pipeline")
                
                if len(audio_parts) == 1:
                    audio_data = audio_parts[0]
                else:
                    audio_data = np.concatenate(audio_parts)
                
                # 4. Final Validation & Squeeze
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

        # We run the synthesis loop in a thread, BUT the model is now fully loaded in the parent process.
        await asyncio.to_thread(_synthesize)
        return path

    except Exception as e:
        logger.error(f"❌ TTS Generation Failed: {e}", exc_info=True)
        if os.path.exists(path):
            try: os.remove(path)
            except: pass
        return ""