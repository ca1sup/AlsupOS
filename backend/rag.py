import os
import sys
import time
import logging
import asyncio
import hashlib
import threading
import numpy as np
from typing import List, Dict, Tuple, Any, Optional
from pathlib import Path

# === CRITICAL SAFETY CONFIGURATION ===
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["ALLOW_RESET"] = "True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

# FIX: Import Settings for robust client configuration
from chromadb import PersistentClient, Collection
from chromadb.config import Settings
from sentence_transformers import CrossEncoder, SentenceTransformer
import torch # Imported for device checking

try:
    import mlx.core as mx
    from mlx_lm import load, stream_generate, generate
    HAS_MLX = True
except ImportError:
    HAS_MLX = False

from backend.config import (
    DB_PATH, WHOOSH_PATH, CHROMA_PATH,
    MODELS_DIR, DEFAULT_MLX_MODEL, DEFAULT_RERANKER_MODEL,
    EMBEDDING_MODEL_NAME, sanitize_collection_name
)
from backend.database import get_all_settings, get_personas, get_cached_response, cache_response

from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID, NUMERIC
from whoosh.qparser import QueryParser, OrGroup
from whoosh.query import Term, Or

logger = logging.getLogger(__name__)
# Force logger to stdout for debugging
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

RRF_K_CONSTANT = 60

# === GLOBAL STATE ===
g_chroma_client: Optional[PersistentClient] = None
g_chroma_lock = asyncio.Lock()

g_embed_model: Any = None
g_embed_lock = asyncio.Lock()

g_llm_model: Any = None
g_llm_tokenizer: Any = None
g_llm_lock = asyncio.Lock()

g_reranker: Any = None 
g_reranker_lock = asyncio.Lock()

_collection_cache: Dict[str, Tuple[Collection, float]] = {}
_cache_lock = asyncio.Lock()
_settings: Dict[str, str] = {}
CACHE_TTL = 300

WHOOSH_SCHEMA = Schema(
    doc_id=ID(stored=True, unique=True),
    content=TEXT(stored=True), 
    filename=ID(stored=True),
    folder=ID(stored=True),
    source=ID(stored=True),
    page=NUMERIC(stored=True),
    chunk_index=NUMERIC(stored=True),
    title=TEXT(stored=True),
    author=TEXT(stored=True)
)

class WorkerModel:
    def __init__(self):
        # FIX: Force CPU to avoid macOS MPS Rust Panics for Embeddings (Thread safety)
        # Note: Ingest uses a different WorkerModel optimized for MPS. This one is for queries.
        logger.info(f"Loading {EMBEDDING_MODEL_NAME} (CPU Enforced for Query Stability)")
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME, device='cpu', trust_remote_code=True)
        # Match Qwen safety limit
        self.model.max_seq_length = 8192

    def encode(self, texts: List[str]) -> np.ndarray:
        if isinstance(texts, str): texts = [texts]
        if not texts: return np.array([])
        
        embeddings = self.model.encode(
            texts,
            batch_size=len(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return embeddings

# --- INITIALIZATION ---

def get_setting(key: str) -> Optional[str]:
    return _settings.get(key)

async def init_llm():
    global g_llm_model, g_llm_tokenizer
    # If a model is already loaded, do nothing (prevents accidental reloads)
    if g_llm_model is not None: return
    if not HAS_MLX: return

    # 1. Determine which model to load
    target_model_name = get_setting("llm_model")
    if not target_model_name:
        target_model_name = DEFAULT_MLX_MODEL
    
    # 2. Resolve Path
    local_model_path = MODELS_DIR / target_model_name
    
    if local_model_path.exists():
        model_ref = str(local_model_path)
        logger.info(f"📂 Loading Local Model from: {model_ref}")
    else:
        model_ref = target_model_name
        logger.info(f"☁️ Loading Remote/Cache Model: {model_ref}")
    
    async with g_llm_lock:
        if g_llm_model is None:
            try:
                # 3. Load Model
                model, tokenizer = await asyncio.to_thread(
                    load, 
                    model_ref, 
                    tokenizer_config={"trust_remote_code": True}
                )
                g_llm_model = model
                g_llm_tokenizer = tokenizer
                logger.info(f"✅ MLX Model '{target_model_name}' Loaded Successfully.")
            except Exception as e:
                logger.error(f"❌ Failed to load MLX model '{target_model_name}': {e}")

async def reload_llm():
    """Unloads the current LLM and initializes the new one based on settings."""
    global g_llm_model, g_llm_tokenizer
    
    logger.info("♻️  Reloading LLM...")
    async with g_llm_lock:
        g_llm_model = None
        g_llm_tokenizer = None
        import gc
        gc.collect()
        
    await init_llm()

async def get_embedding_model():
    global g_embed_model
    if g_embed_model: return g_embed_model
    async with g_embed_lock:
        if g_embed_model is None:
            g_embed_model = await asyncio.to_thread(WorkerModel)
    return g_embed_model

# --- SEARCH & RETRIEVAL ---

def get_whoosh_index():
    if not WHOOSH_PATH.exists():
        os.makedirs(WHOOSH_PATH)
        return create_in(WHOOSH_PATH, WHOOSH_SCHEMA)
    try: return open_dir(WHOOSH_PATH)
    except: return create_in(WHOOSH_PATH, WHOOSH_SCHEMA)

async def get_chroma_client(force_reload: bool = False) -> Optional[PersistentClient]:
    global g_chroma_client
    if g_chroma_client and not force_reload: return g_chroma_client
    
    async with g_chroma_lock:
        if g_chroma_client and not force_reload: return g_chroma_client
        
        if force_reload:
             logger.info("🔄 Forcing ChromaDB Client Reload...")
             g_chroma_client = None

        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        
        client_settings = Settings(
            allow_reset=True,
            anonymized_telemetry=False
        )

        try:
            # Initialize directly
            g_chroma_client = PersistentClient(path=str(CHROMA_PATH), settings=client_settings)
            
            # Simple heartbeat check
            hb = g_chroma_client.heartbeat()
            logger.info(f"✅ ChromaDB Client Initialized (Heartbeat: {hb})")
            
        except BaseException as e: 
            logger.error(f"❌ ChromaDB Load Failed: {e}")
            logger.warning("⚠️ DB load failed. Please run 'backend/fix_db.py'.")
            return None

    return g_chroma_client

async def get_cached_collection(name: str, force_reload: bool = False) -> Optional[Collection]:
    async with _cache_lock:
        if not force_reload and name in _collection_cache and time.time() - _collection_cache[name][1] < CACHE_TTL:
            return _collection_cache[name][0]
        
        client = await get_chroma_client(force_reload=force_reload)
        if not client: return None

        try:
            col = await asyncio.to_thread(client.get_collection, name)
            _collection_cache[name] = (col, time.time())
            return col
        except: 
            return None 

async def load_settings():
    global _settings
    _settings = await get_all_settings()

async def get_reranker():
    global g_reranker
    if get_setting("reranking_enabled") == "false": return None
    if g_reranker: return g_reranker
    
    async with g_reranker_lock:
        if g_reranker is None:
            try: 
                model_name = get_setting("reranker_model") or DEFAULT_RERANKER_MODEL
                
                # Determine Hardware Acceleration
                device = "cpu"
                if torch.backends.mps.is_available():
                    device = "mps"
                    logger.info(f"🚀 Reranker using GPU (MPS)")
                
                # Load CrossEncoder with specific device
                g_reranker = await asyncio.to_thread(
                    CrossEncoder, 
                    model_name, 
                    device=device,
                    trust_remote_code=True,
                    model_kwargs={"cache_dir": str(MODELS_DIR)}
                )
            except Exception as e: 
                logger.error(f"Failed to load reranker: {e}")
                g_reranker = None
    return g_reranker

def reciprocal_rank_fusion(results_list: List[List[Tuple[str, Any]]], k: int = RRF_K_CONSTANT) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for results in results_list:
        for rank, (doc_id, _) in enumerate(results):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores

async def expand_query(query: str) -> str:
    return query 

async def resolve_collection_names(folder_name: str, client: PersistentClient, allow_reload: bool = True) -> List[Collection]:
    try:
        all_cols_refs = await asyncio.to_thread(client.list_collections)
        existing_names = [c.name for c in all_cols_refs]
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        existing_names = []
    
    if not existing_names and allow_reload:
        logger.warning("⚠️ No collections found in memory. Forcing Client Reload...")
        client = await get_chroma_client(force_reload=True)
        if client:
             return await resolve_collection_names(folder_name, client, allow_reload=False)
        return []

    if folder_name.lower() == "all":
        found_cols = []
        for name in existing_names:
            col = await get_cached_collection(name)
            if col: found_cols.append(col)
        return found_cols

    candidates = {
        folder_name,
        sanitize_collection_name(folder_name),
        folder_name.lower(),
        sanitize_collection_name(folder_name).lower()
    }

    matched_names = set()
    for cand in candidates:
        if cand in existing_names:
            matched_names.add(cand)
            
    if not matched_names:
        safe_search = sanitize_collection_name(folder_name).lower()
        if safe_search:
            for existing in existing_names:
                existing_lower = existing.lower()
                if safe_search in existing_lower or existing_lower in safe_search:
                    matched_names.add(existing)

    found_cols = []
    for name in matched_names:
        col = await get_cached_collection(name)
        if col: found_cols.append(col)
        
    if not found_cols and allow_reload and folder_name != "all":
         logger.info(f"🔍 Debug: Could not find '{folder_name}' in {existing_names}")

    return found_cols

async def search_file(collection_name: str, filename: str | List[str], query: str, k: int = 5) -> Tuple[List[str], List[Dict[str, Any]]]:
    logger.info(f"🔍 RAG Search: '{query}' in Folder='{collection_name}', File='{filename}'")
    
    # 1. Embed Query
    embed_model = await get_embedding_model()
    embeddings_array = await asyncio.to_thread(embed_model.encode, query)
    query_emb = embeddings_array[0].tolist()
    
    client = await get_chroma_client()
    if not client:
        logger.error("❌ ChromaDB client is unavailable.")
        return [], []

    cols = await resolve_collection_names(collection_name, client)
    
    if not cols:
        logger.warning(f"❌ No collections found for '{collection_name}'")
    else:
        logger.info(f"📚 Searching Collections: {[c.name for c in cols]}")

    async def run_vector_search(target_filename: Optional[str]) -> Tuple[List[Any], Dict[str, Any]]:
        v_results, d_map = [], {}
        where_clause = {"filename": target_filename} if target_filename and target_filename != "all" else None
        
        # Increase initial vector fetch to allow reranker to work its magic
        # If user requests K=20, we fetch K*5 = 100 candidates from vectors
        fetch_k = k * 5
        
        for col in cols:
            try:
                res = await asyncio.to_thread(
                    col.query, 
                    query_embeddings=[query_emb], 
                    n_results=fetch_k, 
                    where=where_clause, 
                    include=["documents", "metadatas"]
                )
                if res['ids'] and len(res['ids']) > 0:
                    count = len(res['ids'][0])
                    for i in range(count):
                        unique_id = res['ids'][0][i]
                        meta = res['metadatas'][0][i]
                        doc_text = res['documents'][0][i]
                        
                        v_results.append((unique_id, meta))
                        d_map[unique_id] = (doc_text, meta)
            except Exception as e:
                logger.warning(f"Vector search warning on {col.name}: {e}")
        return v_results, d_map

    vector_results, doc_map = await run_vector_search(filename if isinstance(filename, str) else "all")

    if not vector_results and filename and filename != "all":
        logger.info(f"⚠️ No results in file '{filename}'. Falling back to entire folder '{collection_name}'...")
        vector_results, doc_map = await run_vector_search("all")

    # 2. Keyword Search (Whoosh)
    ix = get_whoosh_index()
    keyword_results = []
    
    def _do_search():
        with ix.searcher() as s:
            q = QueryParser("content", schema=WHOOSH_SCHEMA, group=OrGroup.factory(0.9)).parse(query)
            filter_q = None
            if cols:
                terms = [Term("folder", c.name) for c in cols]
                filter_q = Or(terms)
            return [(h['doc_id'], h.fields()) for h in s.search(q, filter=filter_q, limit=k*5)]

    try:
        for did, f in await asyncio.to_thread(_do_search):
            keyword_results.append((did, f))
            if did not in doc_map: 
                doc_map[did] = (f['content'], f)
    except Exception as e:
        logger.warning(f"Whoosh search error: {e}")

    logger.info(f"📊 Stats: Vector Hits={len(vector_results)}, Keyword Hits={len(keyword_results)}")

    # 3. Hybrid Fusion
    fused = reciprocal_rank_fusion([vector_results, keyword_results])
    sorted_res = sorted(fused.items(), key=lambda x: x[1], reverse=True)
    
    # 4. Reranking
    reranker = await get_reranker()
    final_docs, final_metas, seen = [], [], set()
    top_n_limit = int(get_setting("reranker_top_n") or 100)
    top_n = sorted_res[:top_n_limit]

    if reranker:
        cands = [(doc_map[did][0], did) for did, _ in top_n if did in doc_map]
        if cands:
            # Rerank with GPU acceleration if enabled
            scores = await asyncio.to_thread(reranker.predict, [[query, c[0]] for c in cands])
            # Re-sort based on new scores
            top_n = sorted(zip(scores, [c[1] for c in cands]), key=lambda x: x[0], reverse=True)
    else:
        top_n = [(score, did) for did, score in top_n]

    for _, did in top_n:
        if did in doc_map and did not in seen:
            d, m = doc_map[did]
            final_docs.append(d)
            final_metas.append(m)
            seen.add(did)
            if len(final_docs) >= k: break
    
    logger.info(f"✅ RAG Complete. Found {len(final_docs)} docs.")
    return final_docs, final_metas

async def perform_rag_query(query: str, folder: str, file: Optional[str] = None) -> Tuple[List[str], List[Dict[str, Any]]]:
    k = int(get_setting("default_search_k") or 20)
    try:
        docs, metas = await search_file(folder, filename=file or "all", query=query, k=k)
        return docs, metas
    except Exception as e:
        logger.error(f"RAG Search Failed: {e}")
        return [], []

# --- GENERATION ---

def prepare_messages(query: str, context: List[str], history: List[Dict[str, str]], persona_name: str) -> List[Dict[str, str]]:
    sys_prompt = "You are a helpful AI assistant."
    ctx_str = ""
    if context:
        ctx_str = "Context:\n" + (chr(10).join(context) if isinstance(context, list) else context) + "\n\n"
    messages = [{"role": "system", "content": sys_prompt}] + history
    messages.append({"role": "user", "content": f"{ctx_str}Question: {query}"})
    return messages

async def generate_stream(query: str, context: List[str], history: List[Dict[str, str]] = [], persona_name: str = "Vault"):
    if not context and not history:
        q_hash = hashlib.md5(query.lower().encode()).hexdigest()
        cached = await get_cached_response(q_hash)
        if cached:
            yield cached
            return

    if g_llm_model is None: await init_llm()
    if g_llm_model is None:
        yield "Error: Model failed to load."
        return

    try:
        personas = await get_personas()
        persona_map = {p['name']: p['prompt'] for p in personas}
        sys_prompt = persona_map.get(persona_name) or "You are a helpful assistant."
    except: sys_prompt = "You are a helpful assistant."

    messages = [{"role": "system", "content": sys_prompt}] + history
    if context:
        ctx_str = chr(10).join(context) if isinstance(context, list) else context
        messages.append({"role": "user", "content": f"--- CONTEXT ---\n{ctx_str}\n\n--- QUESTION ---\n{query}"})
    else: messages.append({"role": "user", "content": query})

    try:
        if hasattr(g_llm_tokenizer, "apply_chat_template"):
            prompt = g_llm_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            prompt = ""
            for m in messages: prompt += f"<|{m['role']}|>\n{m['content']}<|end|>\n"
            prompt += "<|assistant|>\n"
        
        full_resp = ""
        def run_inference():
            return stream_generate(g_llm_model, g_llm_tokenizer, prompt, max_tokens=2048)
        
        for response in run_inference():
            text_chunk = response.text
            full_resp += text_chunk
            yield text_chunk
            await asyncio.sleep(0) 

    except Exception as e:
        logger.error(f"MLX Stream Error: {e}")
        yield f"[Error: {str(e)}]"

    if not context and not history and full_resp:
        q_hash = hashlib.md5(query.lower().encode()).hexdigest()
        await cache_response(q_hash, full_resp)

get_ai_response_stream = generate_stream

async def generate_bare_stream(query: str, history: List[Dict[str, str]] = [], persona_name: str = "Chat"):
    async for token in generate_stream(query, [], history, persona_name):
        yield token

async def get_ai_response(messages: List[Dict[str, str]], model: str = None) -> str:
    if g_llm_model is None: await init_llm()
    if g_llm_model is None: return "Error: Model failed to load."

    if hasattr(g_llm_tokenizer, "apply_chat_template"):
        prompt = g_llm_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        prompt = ""
        for m in messages: prompt += f"<|{m['role']}|>\n{m['content']}<|end|>\n"
        prompt += "<|assistant|>\n"

    try:
        response = await asyncio.to_thread(generate, g_llm_model, g_llm_tokenizer, prompt=prompt, max_tokens=2048, verbose=False)
        return response
    except Exception as e:
        logger.error(f"MLX Generate Error: {e}")
        return f"Error: {str(e)}"

async def check_ollama_status() -> bool: return True
async def init_ollama() -> bool: return True
async def summarize_long_text(text: str, chunk_size: int = 6000) -> str: return text[:chunk_size]

async def get_document_content(collection_name: str, filename: str) -> str:
    client = await get_chroma_client()
    if not client: return "Error: Database unavailable"
    
    cols = await resolve_collection_names(collection_name, client)
    if not cols: return "Error: Collection not found"
    
    col = cols[0] 
    res = await asyncio.to_thread(col.get, where={"filename": filename}, include=["documents", "metadatas"])
    chunks = sorted(zip(res['documents'], res['metadatas']), key=lambda x: (x[1].get('page', 0), x[1].get('chunk_index', 0)))
    return " ".join([d for d, m in chunks])