# backend/ingest.py
import os
import sys
import gc
import json
import hashlib
import logging
import sqlite3
import asyncio
import threading
import queue
import time
import concurrent.futures
from datetime import timedelta
from pathlib import Path
from typing import List, Generator, Tuple, Optional, Any, Set
from dataclasses import dataclass

# --- WHOOSH IMPORTS ---
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID, NUMERIC
from whoosh.analysis import StandardAnalyzer
from whoosh.query import Term, And

print("DEBUG: backend/ingest.py initializing...")

# 1. CONFIGURATION & SAFETY
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

logging.getLogger("chromadb").setLevel(logging.CRITICAL)
logging.getLogger("posthog").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

from chromadb import PersistentClient
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

from backend.config import (
    CHROMA_PATH, DOCS_PATH, STEWARD_INGEST_FOLDER, DB_PATH,
    SUPPORTED_EXTENSIONS, sanitize_collection_name, EMBEDDING_MODEL_NAME,
    WHOOSH_PATH
)

# --- PERFORMANCE TUNING (M1 Ultra Optimized) ---
# Utilizing 64GB Unified Memory & 64-Core GPU
EMBEDDING_BATCH_SIZE = 16
WRITER_QUEUE_SIZE = 100

# Match physical core count (20 Cores) for file processing
MAX_WORKERS = 18

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- WHOOSH SCHEMA ---
WHOOSH_SCHEMA = Schema(
    doc_id=ID(stored=True, unique=True),
    content=TEXT(stored=True, analyzer=StandardAnalyzer()), 
    filename=ID(stored=True),
    folder=ID(stored=True),
    source=ID(stored=True),
    page=NUMERIC(stored=True),
    chunk_index=NUMERIC(stored=True),
    title=TEXT(stored=True),
    author=TEXT(stored=True)
)

# --- STATUS MONITOR ---
class IngestStatus:
    def __init__(self):
        self.current_action = "Initializing"
        self.start_time = time.time()
        self.lock = threading.Lock()
        self.last_file = ""
        self.chunks_done = 0
        self.chunks_total = 0

    def update(self, action, file_name="", chunks_done=0, chunks_total=0):
        with self.lock:
            self.current_action = action
            if file_name: self.last_file = file_name
            self.chunks_done = chunks_done
            self.chunks_total = chunks_total
            self.start_time = time.time()

    def get_status(self):
        with self.lock:
            elapsed = time.time() - self.start_time
            return self.current_action, self.last_file, self.chunks_done, self.chunks_total, elapsed

def heartbeat_worker(ingest_status, stop_event, status_queue):
    while not stop_event.is_set():
        time.sleep(5) 
        if stop_event.is_set(): break
        
        action, file_name, done, total, elapsed = ingest_status.get_status()
        if total > 0:
            pct = (done / total * 100) if total > 0 else 0
            msg = f"  ⚡  {action} | {done}/{total} chunks ({pct:.0f}%)"
        else:
            file_info = f" | {file_name}" if file_name else ""
            msg = f"  ⚡  {action}{file_info}"
        print(msg)
        sys.stdout.flush() # Force flush to console

# --- DATA STRUCTURES ---
@dataclass
class IngestTask:
    file_path: Path
    collection: str
    known_hash: Optional[str]
    known_mtime: float = 0.0

@dataclass
class LightweightChunk:
    text: str
    chunk_index: int
    parent_header: str
    chunk_id: str

@dataclass
class FileResult:
    file_path: Path
    collection: str
    file_hash: str
    file_mtime: float
    chunks: List[LightweightChunk]
    skipped: bool = False
    error: str = ""

@dataclass
class WriteTask:
    vectors: List[List[float]]
    documents: List[str]
    metadatas: List[dict]
    ids: List[str]
    collection_name: str
    doc_tracking: List[Tuple[str, str, str, float]]

# --- OPTIMIZED WORKER MODEL ---
class WorkerModel:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        import torch
        
        self.lock = threading.Lock() # Protect GPU Access
        
        # M1 Ultra Hardware Acceleration (MPS)
        if torch.backends.mps.is_available():
            self.device = "mps"
            print(f"  [HARDWARE] 🚀 M1 Ultra GPU Activated (MPS)")
        else:
            self.device = "cpu"
            print(f"  [HARDWARE] ⚠️ MPS not found, using CPU")
        
        # Single thread for the model itself
        torch.set_num_threads(1) 

        self.model = SentenceTransformer(
            EMBEDDING_MODEL_NAME, 
            device=self.device, 
            trust_remote_code=True
        )
        self.model.max_seq_length = 2048
        
        # JIT compile warmup
        self.model.encode(["warmup"], convert_to_numpy=True)

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts: return []
        
        max_chars = 6000
        texts = [t[:max_chars] for t in texts]
        
        if "nomic" in EMBEDDING_MODEL_NAME:
            prefix = "search_document: "
        else:
            prefix = ""
            
        texts_with_prefix = [prefix + t for t in texts]
        
        try:
            # CRITICAL FIX: Serialize GPU access to prevent MPS contention/crashes
            # while keeping text processing parallel
            with self.lock:
                embeddings = self.model.encode(
                    texts_with_prefix,
                    batch_size=EMBEDDING_BATCH_SIZE, 
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    convert_to_numpy=True
                )
            return embeddings.tolist()
        except Exception as e:
            print(f"  ⚠️  Encoding error: {e}")
            return []

# --- FILE PROCESSOR ---
def get_file_hash_sync(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while b := f.read(131072):
                h.update(b)
        return h.hexdigest()
    except: return ""

def process_file_task(task: IngestTask, model_instance: WorkerModel) -> Tuple[FileResult, Optional[WriteTask]]:
    current_mtime = task.file_path.stat().st_mtime
    
    # Fast MTIME check
    if task.known_mtime == current_mtime:
        return FileResult(task.file_path, task.collection, task.known_hash or "", current_mtime, [], skipped=True), None

    current_hash = get_file_hash_sync(task.file_path)
    
    if task.known_hash == current_hash:
        return FileResult(task.file_path, task.collection, current_hash, current_mtime, [], skipped=True), None

    try:
        with open(task.file_path, 'rb') as f_bin:
            head = f_bin.read(1024)
            if b'\0' in head:
                return FileResult(task.file_path, task.collection, current_hash, current_mtime, [], error="Binary file"), None

        with open(task.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text_content = f.read()

        headers = [("#", "H1"), ("##", "H2"), ("###", "H3")]
        parent_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers, strip_headers=False)
        child_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=150)
        
        fname = task.file_path.name
        parents = parent_splitter.split_text(text_content)
        
        chunk_texts = []
        metas = []
        ids = []
        doc_tracking = [(task.collection, fname, current_hash, current_mtime)]
        
        chunks_data = []

        for i, p_doc in enumerate(parents):
            children = child_splitter.split_text(p_doc.page_content)
            for j, child_text in enumerate(children):
                stable_id = hashlib.md5(f"{fname}::{i}::{j}".encode()).hexdigest()
                
                chunk_texts.append(child_text)
                metas.append({
                    "filename": fname,
                    "collection": task.collection,
                    "doc_id": f"{task.collection}::{fname}",
                    "file_hash": current_hash,
                    "chunk_index": j,
                    "parent_header": p_doc.metadata.get("H1", "") or p_doc.metadata.get("H2", ""),
                    "page": j + 1 
                })
                ids.append(stable_id)
                
                chunks_data.append(LightweightChunk(
                    text=child_text,
                    chunk_index=j,
                    parent_header=p_doc.metadata.get("H1", ""),
                    chunk_id=stable_id
                ))
        
        if chunk_texts:
            # Calls the shared model (which handles locking internally)
            vectors = model_instance.encode_batch(chunk_texts)
            write_task = WriteTask(vectors, chunk_texts, metas, ids, task.collection, doc_tracking)
            
            # Explicitly clear memory
            gc.collect()
            
            return FileResult(task.file_path, task.collection, current_hash, current_mtime, chunks_data, skipped=False), write_task
            
        return FileResult(task.file_path, task.collection, current_hash, current_mtime, [], skipped=False), None

    except Exception as e:
        return FileResult(task.file_path, task.collection, current_hash, current_mtime, [], error=str(e)), None

def get_all_tasks() -> List[IngestTask]:
    ignored = {".git", "node_modules", "venv", "__pycache__", "chroma_db", "whoosh_index", ".trash", "models", ".DS_Store"}
    tasks = []
    known_files = {} 
    
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute("SELECT collection_name, file_name, file_hash, file_mtime FROM documents")
                for row in cur.fetchall(): 
                    known_files[(row[0], row[1])] = (row[2], row[3] or 0.0)
            except:
                cur = conn.cursor()
                cur.execute("SELECT collection_name, file_name, file_hash FROM documents")
                for row in cur.fetchall(): 
                    known_files[(row[0], row[1])] = (row[2], 0.0)
            conn.close()
        except: pass

    if DOCS_PATH.exists():
        for d in DOCS_PATH.iterdir():
            if d.is_dir() and d.name not in ignored and not d.name.startswith('.'):
                col = sanitize_collection_name(d.name)
                for f in d.rglob("*"):
                    if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS and not f.name.startswith('.'):
                        known_h, known_t = known_files.get((col, f.name), (None, 0.0))
                        tasks.append(IngestTask(f, col, known_h, known_t))
    return tasks

# --- WRITER THREAD (WITH WHOOSH & CHROMA) ---
def writer_thread_func(write_queue: queue.Queue, stop_event):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;") 
    conn.execute("PRAGMA synchronous=NORMAL;")
    
    # Init Chroma
    chroma_client = PersistentClient(path=str(CHROMA_PATH))
    collections = {}
    
    # Init Whoosh
    if not WHOOSH_PATH.exists():
        os.makedirs(WHOOSH_PATH)
        ix = create_in(WHOOSH_PATH, WHOOSH_SCHEMA)
    else:
        try: ix = open_dir(WHOOSH_PATH)
        except: ix = create_in(WHOOSH_PATH, WHOOSH_SCHEMA)
    
    def get_collection(name):
        if name not in collections:
            collections[name] = chroma_client.get_or_create_collection(name)
        return collections[name]
    
    while not stop_event.is_set():
        try:
            task = write_queue.get(timeout=0.1)
        except queue.Empty: continue
            
        if task is None: break
        
        try:
            # 1. SQLite Metadata
            for col, fname, fhash, fmtime in task.doc_tracking:
                doc_row = conn.execute("SELECT doc_id FROM documents WHERE collection_name=? AND file_name=?", (col, fname)).fetchone()
                if doc_row: conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_row[0],))
                
                conn.execute("""
                    INSERT INTO documents (collection_name, file_name, file_hash, file_mtime, last_processed_at, status) 
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 'active') 
                    ON CONFLICT(collection_name, file_name) 
                    DO UPDATE SET file_hash=excluded.file_hash, file_mtime=excluded.file_mtime, last_processed_at=CURRENT_TIMESTAMP
                """, (col, fname, fhash, fmtime))
            conn.commit()

            # 2. Chroma (Vectors)
            chroma_col = get_collection(task.collection_name)
            chroma_col.add(ids=task.ids, embeddings=task.vectors, documents=task.documents, metadatas=task.metadatas)

            # 3. SQLite Chunks
            sqlite_chunks = []
            for i, chunk_id in enumerate(task.ids):
                fname = task.metadatas[i]['filename']
                col = task.collection_name
                doc_id_row = conn.execute("SELECT doc_id FROM documents WHERE collection_name=? AND file_name=?", (col, fname)).fetchone()
                if doc_id_row:
                    doc_id = doc_id_row[0]
                    chunk_hash = hashlib.sha256(task.documents[i].encode()).hexdigest()
                    sqlite_chunks.append((doc_id, chunk_id, chunk_hash, json.dumps(task.metadatas[i])))
            
            if sqlite_chunks:
                conn.executemany("INSERT INTO chunks (doc_id, vector_db_id, chunk_hash, metadata_json) VALUES (?,?,?,?)", sqlite_chunks)
                conn.commit()

            # 4. Whoosh (Keywords)
            try:
                writer = ix.writer()
                for col, fname, _, _ in task.doc_tracking:
                    q = And([Term("filename", fname), Term("folder", col)])
                    writer.delete_by_query(q)
                
                for i, chunk_id in enumerate(task.ids):
                    meta = task.metadatas[i]
                    writer.add_document(
                        doc_id=chunk_id,
                        content=task.documents[i],
                        filename=meta.get('filename'),
                        folder=task.collection_name,
                        source="ingest",
                        page=meta.get('page'),
                        chunk_index=meta.get('chunk_index'),
                        title=meta.get('filename'),
                        author="User"
                    )
                writer.commit()
            except Exception as we:
                print(f"  ⚠️ Whoosh Write Error: {we}")
            
        except Exception as e:
            print(f"  ❌ Write Error: {e}")
        finally:
            write_queue.task_done()
    
    conn.close()

# --- WORKER FUNCTION ---
def worker_entrypoint(task: IngestTask, model: WorkerModel):
    # Model is now passed in, no per-thread initialization needed!
    return process_file_task(task, model)

# --- MAIN ORCHESTRATOR ---
def run_ingest_process(status_queue, settings_dict):
    # Ensure logs output to console even in subprocess
    sys.stdout.reconfigure(line_buffering=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    try:
        def log_msg(msg):
            print(msg)
            sys.stdout.flush() 
            if status_queue: status_queue.put(msg)

        log_msg("🚀 Starting M1 Ultra Ingest (Optimized)...")
        
        ingest_status = IngestStatus()
        stop_heartbeat = threading.Event()
        hb_thread = threading.Thread(target=heartbeat_worker, args=(ingest_status, stop_heartbeat, status_queue), daemon=True)
        hb_thread.start()

        # 1. Run Magic Processors
        from backend.ingest_processors import process_ingest_folder
        async def run_processors():
            ingest_status.update("Processing Inbox")
            import aiosqlite
            async with aiosqlite.connect(DB_PATH) as db:
                targets = {"journal", "health", "finance", "web", "context", "reminders"}
                ingest_folder = settings_dict.get("steward_ingest_folder", STEWARD_INGEST_FOLDER)
                await process_ingest_folder(None, db, settings_dict, ingest_folder, targets)
        
        try: asyncio.run(run_processors())
        except Exception as e: log_msg(f"  ⚠️  Processor note: {e}")

        # 2. Init Writer
        write_queue = queue.Queue(maxsize=WRITER_QUEUE_SIZE)
        stop_writer = threading.Event()
        writer_thread = threading.Thread(target=writer_thread_func, args=(write_queue, stop_writer), daemon=True)
        writer_thread.start()

        # 3. Scan Tasks
        ingest_status.update("Scanning Files")
        tasks = get_all_tasks()
        if not tasks:
            log_msg("✅ System is up to date.")
            stop_heartbeat.set(); hb_thread.join(1)
            write_queue.put(None); stop_writer.set(); writer_thread.join(2)
            return

        total_files = len(tasks)
        log_msg(f"📊 Processing {total_files} files (Parallel)...")

        # 4. Processing Loop (Fixed for M1 Ultra Stability)
        processed_count = 0
        skipped_count = 0
        error_count = 0
        total_chunks = 0
        start_time = time.time()

        # Initialize ONE shared model on the main thread (Approx 0.5GB VRAM)
        log_msg("  🧬 Loading Shared Embedding Model...")
        shared_model = WorkerModel()

        # Use 20 workers to match CPU Cores for text splitting/hashing
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Pass the shared model to workers
            future_to_task = {executor.submit(worker_entrypoint, task, shared_model): task for task in tasks}
            
            for future in concurrent.futures.as_completed(future_to_task):
                processed_count += 1
                try:
                    result, write_payload = future.result()
                    
                    if result.skipped:
                        skipped_count += 1
                        continue
                    
                    if result.error:
                        error_count += 1
                        log_msg(f"  ❌ Error {result.file_path.name}: {result.error}")
                        continue

                    if write_payload:
                        write_queue.put(write_payload)
                        total_chunks += len(write_payload.vectors)
                        ingest_status.update("Embedded", result.file_path.name, total_chunks, 0)

                except Exception as e:
                    error_count += 1
                    print(f"Worker exception: {e}")

        # Cleanup
        ingest_status.update("Finalizing")
        log_msg("  💾 Writing final data to disk...")
        write_queue.join()
        write_queue.put(None)
        stop_writer.set()
        writer_thread.join(timeout=5)
        stop_heartbeat.set()
        hb_thread.join(timeout=1)

        total_time = time.time() - start_time
        
        log_msg(f"")
        log_msg(f"✅ INGEST COMPLETE in {total_time:.1f}s")
        log_msg(f"   • Files: {processed_count} processed, {skipped_count} skipped")
        log_msg(f"   • Chunks: {total_chunks}")
        
    except Exception as e:
        if status_queue: status_queue.put(f"CRITICAL: {e}")
        logger.error(f"Crash: {e}", exc_info=True)

if __name__ == "__main__":
    class Q: 
        def put(self, x): pass
    import asyncio
    run_ingest_process(Q(), {})