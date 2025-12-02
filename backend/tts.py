# backend/tts.py
import os
import time
import logging
import asyncio
import warnings
import tempfile
import re
import numpy as np
import soundfile as sf
from pathlib import Path
from backend.config import MODELS_DIR

# Suppress warnings from libraries
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. CONFIGURATION & CONSTANTS
# ==============================================================================

# TTS Settings
KOKORO_REPO_ID = "mlx-community/Kokoro-82M-bf16" 
DEFAULT_VOICE = "af_heart"
SAMPLE_RATE = 24000

# STT Settings
WHISPER_MODEL = "mlx-community/whisper-turbo"

# Voice Mapping Reference (Useful for UI/Settings)
KOKORO_VOICES = {
    'a': {  # American English
        'male': ['am_adam', 'am_michael', 'am_eric', 'am_fenrir', 'am_liam', 'am_onyx', 'am_puck'],
        'female': ['af_heart', 'af_bella', 'af_nicole', 'af_sarah', 'af_sky', 'af_aoede', 'af_kore']
    },
    'b': {  # British English
        'male': ['bm_lewis', 'bm_george', 'bm_daniel', 'bm_fable'],
        'female': ['bf_emma', 'bf_isabella', 'bf_alice', 'bf_lily']
    },
    'j': {  # Japanese
        'male': ['jm_kumo'],
        'female': ['jf_alpha', 'jf_gongitsune', 'jf_nezumi', 'jf_tebukuro']
    },
    'z': {  # Chinese
        'male': ['zm_yunjian', 'zm_yunxi', 'zm_zhibin'],
        'female': ['zf_xiaobei', 'zf_xiaoni', 'zf_xiaoxiao', 'zf_xiaoyi']
    }
}

# --- GLOBAL MODEL CACHE ---
g_tts_pipeline = None
g_stt_model = None
g_model_lock = asyncio.Lock()

# ==============================================================================
# 2. SPEECH-TO-TEXT (Whisper)
# ==============================================================================

async def get_whisper_model():
    """
    Lazy-loads MLX Whisper for transcription.
    Returns the model object or None if import fails.
    """
    global g_stt_model
    if g_stt_model is not None:
        return g_stt_model

    async with g_model_lock:
        if g_stt_model is not None:
            return g_stt_model
            
        try:
            logger.info(f"🎤 Loading Whisper Model: {WHISPER_MODEL}")
            import mlx_whisper
            
            # Create a simple wrapper class to match the expected interface if needed
            class WhisperWrapper:
                def transcribe(self, audio_path, **kwargs):
                    # Default settings for medical audio
                    defaults = {
                        "path_or_hf_repo": WHISPER_MODEL,
                        "verbose": False
                    }
                    defaults.update(kwargs)
                    return mlx_whisper.transcribe(audio_path, **defaults)
            
            g_stt_model = WhisperWrapper()
            logger.info("✅ Whisper Model Loaded Successfully.")
            return g_stt_model
            
        except ImportError:
            logger.error("❌ mlx_whisper not installed. STT disabled. Run: pip install mlx-whisper")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to load Whisper: {e}", exc_info=True)
            return None

async def load_whisper_model():
    """Background task to pre-warm the Whisper model on startup."""
    await get_whisper_model()

# ==============================================================================
# 3. TEXT-TO-SPEECH (Kokoro)
# ==============================================================================

async def get_kokoro_pipeline():
    """
    Lazy-loads Kokoro TTS Pipeline.
    Uses 'kokoro' pip package for stability.
    """
    global g_tts_pipeline
    if g_tts_pipeline is not None:
        return g_tts_pipeline

    async with g_model_lock:
        if g_tts_pipeline is not None:
            return g_tts_pipeline

        try:
            logger.info(f"🗣️ Loading Kokoro TTS Pipeline...")
            
            # Check import with clear error if missing
            try:
                from kokoro import KPipeline
            except ImportError:
                logger.error("❌ 'kokoro' package not found. TTS disabled.")
                logger.error("👉 FIX: Run command: pip install kokoro>=0.3.4 soundfile")
                return None

            # Initialize with American English
            pipeline = KPipeline(lang_code='a', model=False) 
            
            g_tts_pipeline = pipeline
            logger.info("✅ Kokoro TTS Loaded.")
            return g_tts_pipeline
            
        except Exception as e:
            logger.error(f"❌ Failed to load Kokoro TTS: {e}", exc_info=True)
            return None

def _clean_text_for_tts(text: str) -> str:
    """
    AGGRESSIVE text cleaning for Kokoro TTS compatibility.
    
    Kokoro's G2P (grapheme-to-phoneme) model is VERY sensitive to:
    - Special characters (bullets, asterisks, pipes)
    - Numbers written as digits
    - Markdown formatting
    - Multiple consecutive punctuation marks
    - Unusual spacing
    
    This function sanitizes text to maximize synthesis success.
    """
    if not text: 
        return ""
    
    # 1. Remove ALL markdown formatting
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)      # Italic
    text = re.sub(r'__(.+?)__', r'\1', text)      # Bold alt
    text = re.sub(r'_(.+?)_', r'\1', text)        # Italic alt
    text = re.sub(r'#+\s?', '', text)             # Headers
    text = re.sub(r'`(.+?)`', r'\1', text)        # Code
    
    # 2. Replace bullets/dashes with periods for natural pauses
    text = re.sub(r'^[\s\-•*]+', '', text, flags=re.MULTILINE)
    text = text.replace('- ', '. ').replace('• ', '. ')
    
    # 3. Convert numbers to words (critical for G2P)
    # Simple approach for common cases
    number_map = {
        '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
        '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine',
        '10': 'ten', '11': 'eleven', '12': 'twelve', '13': 'thirteen',
        '14': 'fourteen', '15': 'fifteen', '16': 'sixteen', '17': 'seventeen',
        '18': 'eighteen', '19': 'nineteen', '20': 'twenty', '30': 'thirty',
        '40': 'forty', '50': 'fifty', '60': 'sixty', '70': 'seventy',
        '80': 'eighty', '90': 'ninety', '100': 'one hundred'
    }
    
    # Replace standalone numbers with words
    for num, word in number_map.items():
        text = re.sub(rf'\b{num}\b', word, text)
    
    # 4. Remove URLs entirely
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    
    # 5. Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)
    
    # 6. Clean up special characters that break G2P
    # Keep only: letters, spaces, basic punctuation
    text = re.sub(r'[^\w\s.,!?;:\'-]', '', text)
    
    # 7. Fix multiple punctuation
    text = re.sub(r'([.!?]){2,}', r'\1', text)
    
    # 8. Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n+', '. ', text)  # Convert newlines to periods
    
    # 9. Remove leading/trailing whitespace
    text = text.strip()
    
    # 10. Split long text into sentences (Kokoro works best with shorter chunks)
    # Max ~200 characters per sentence
    sentences = re.split(r'(?<=[.!?])\s+', text)
    cleaned_sentences = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # If sentence is too long, split on commas
        if len(sentence) > 200:
            parts = sentence.split(',')
            for part in parts:
                part = part.strip()
                if part and not part[-1] in '.!?':
                    part += '.'
                if part:
                    cleaned_sentences.append(part)
        else:
            # Ensure sentence ends with punctuation
            if sentence and sentence[-1] not in '.!?':
                sentence += '.'
            cleaned_sentences.append(sentence)
    
    # Join with spaces
    final_text = ' '.join(cleaned_sentences)
    
    # 11. Final validation: remove any remaining problematic chars
    final_text = re.sub(r'[^\w\s.,!?;:\'-]', '', final_text)
    
    # 12. Log if text was heavily modified (useful for debugging)
    if len(final_text) < len(text) * 0.5:
        logger.warning(f"⚠️ Text heavily cleaned: {len(text)} -> {len(final_text)} chars")
    
    return final_text

def _synthesize_worker(pipeline, text, voice):
    """
    Worker function to run synthesis in a thread.
    
    CRITICAL FIXES:
    1. Splits text into smaller chunks to avoid G2P failures
    2. Validates audio output at each step
    3. Handles 'inhomogeneous shape' errors
    4. Falls back gracefully on failures
    """
    try:
        # Split text into manageable chunks (Kokoro works best with ~100-150 char chunks)
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        all_audio_chunks = []
        failed_chunks = 0
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
                
            try:
                # Generate for this sentence
                # speed=1.0 is default, lang='a' for American English
                generator = pipeline(
                    sentence, 
                    voice=voice, 
                    speed=1.0,
                    lang='a'  # Explicitly set language
                )
                
                # Collect audio from generator
                sentence_audio = []
                for gs, ps, audio in generator:
                    if audio is None:
                        continue
                        
                    # Validate and convert to numpy array
                    if not isinstance(audio, np.ndarray):
                        try:
                            audio = np.array(audio, dtype=np.float32)
                        except Exception:
                            continue
                    
                    # Ensure float32 dtype
                    if audio.dtype != np.float32:
                        audio = audio.astype(np.float32)
                    
                    # Flatten if needed
                    if audio.ndim > 1:
                        audio = audio.flatten()
                        
                    if audio.size > 0:
                        sentence_audio.append(audio)
                
                # If this sentence produced audio, add it
                if sentence_audio:
                    sentence_combined = np.concatenate(sentence_audio)
                    all_audio_chunks.append(sentence_combined)
                else:
                    failed_chunks += 1
                    logger.warning(f"⚠️ Chunk {i+1} produced no audio: '{sentence[:50]}...'")
                    
            except Exception as chunk_error:
                failed_chunks += 1
                logger.warning(f"⚠️ Failed to synthesize chunk {i+1}: {chunk_error}")
                continue
        
        # Report on failures
        if failed_chunks > 0:
            logger.warning(f"⚠️ {failed_chunks}/{len(sentences)} chunks failed synthesis")
        
        if not all_audio_chunks:
            logger.error("❌ TTS produced no valid audio chunks after processing all sentences")
            return None, SAMPLE_RATE
        
        # Concatenate all successful chunks
        final_audio = np.concatenate(all_audio_chunks)
        
        # Normalize audio to prevent clipping
        max_val = np.abs(final_audio).max()
        if max_val > 0:
            final_audio = final_audio / max_val * 0.95  # Leave headroom
        
        logger.info(f"✅ Successfully synthesized {len(all_audio_chunks)}/{len(sentences)} chunks")
        
        return final_audio, SAMPLE_RATE
        
    except Exception as e:
        logger.error(f"❌ Synthesis worker failed: {e}", exc_info=True)
        raise e

async def generate_audio_briefing(text: str) -> str:
    """
    Main entry point for generating audio files from text.
    
    Args:
        text (str): The text to read aloud.
    
    Returns:
        str: Filepath to the generated MP3/WAV, or "" if failed.
    """
    pipeline = await get_kokoro_pipeline()
    if not pipeline:
        logger.error("❌ TTS Pipeline unavailable (Check logs for missing package).")
        return ""

    # Clean text aggressively
    clean_text = _clean_text_for_tts(text)
    
    if not clean_text: 
        logger.warning("⚠️ TTS received empty text after cleaning.")
        return ""
    
    # Log the cleaning result for debugging
    logger.info(f"📝 Original text length: {len(text)} chars")
    logger.info(f"📝 Cleaned text length: {len(clean_text)} chars")
    logger.debug(f"📝 Cleaned text preview: {clean_text[:200]}...")

    logger.info(f"🎵 Generating audio using voice '{DEFAULT_VOICE}'...")
    
    try:
        # Offload blocking synthesis to a thread
        audio, rate = await asyncio.to_thread(_synthesize_worker, pipeline, clean_text, DEFAULT_VOICE)
        
        if audio is None or len(audio) == 0:
            logger.error("❌ Synthesis returned empty audio")
            return ""

        # Prepare Output Path
        temp_dir = Path("backend/temp_audio")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Use a unique filename
        filename = f"briefing_{int(time.time())}.wav"  # Use WAV for better compatibility
        filepath = temp_dir / filename
        
        # Write file using soundfile
        # Ensure audio is in correct format
        sf.write(str(filepath), audio, rate, subtype='PCM_16')
        
        size_mb = filepath.stat().st_size / (1024 * 1024)
        duration_sec = len(audio) / rate
        logger.info(f"✅ Audio generated: {filepath} ({size_mb:.2f} MB, {duration_sec:.1f}s)")
        
        return str(filepath)

    except Exception as e:
        logger.error(f"❌ Audio generation failed: {e}", exc_info=True)
        return ""

# ==============================================================================
# 4. UTILITIES & DIAGNOSTICS
# ==============================================================================

async def test_tts_simple():
    """
    Diagnostic function to test TTS with a simple phrase.
    Useful for troubleshooting.
    """
    test_text = "Hello. This is a test of the text to speech system."
    logger.info("🧪 Running TTS diagnostic test...")
    result = await generate_audio_briefing(test_text)
    if result:
        logger.info(f"✅ TTS test passed: {result}")
        return True
    else:
        logger.error("❌ TTS test failed")
        return False

async def check_audio_services():
    """
    Helper to check status of audio models for the Health Dashboard.
    """
    stt_status = "Ready" if g_stt_model else "Not Loaded"
    tts_status = "Ready" if g_tts_pipeline else "Not Loaded"
    
    # Optional: check if libraries are even installed
    try:
        import mlx_whisper
        stt_installed = True
    except: 
        stt_installed = False
    
    try:
        from kokoro import KPipeline
        tts_installed = True
    except: 
        tts_installed = False

    return {
        "stt": {
            "status": stt_status,
            "installed": stt_installed,
            "model": WHISPER_MODEL
        },
        "tts": {
            "status": tts_status,
            "installed": tts_installed,
            "voice": DEFAULT_VOICE
        }
    }

# End of File