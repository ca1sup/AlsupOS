from huggingface_hub import snapshot_download
from pathlib import Path

# 1. Define Local Model Directory
BASE_DIR = Path("/Users/christopheralsup/development/Alsup-vault/models")
BASE_DIR.mkdir(exist_ok=True)

print(f"💾 Downloading models to: {BASE_DIR} ...")

# 2. Download LLM (Phi-4 Mini 8-bit)
# Matches your Config!
print("\n[1/3] Downloading LLM: mlx-community/Phi-4-mini-instruct-8bit...")
snapshot_download(
    repo_id="mlx-community/Phi-4-mini-instruct-8bit",
    local_dir=str(BASE_DIR / "mlx-community/Phi-4-mini-instruct-8bit"),
    local_dir_use_symlinks=False,
    allow_patterns=["*.mlx", "*.safetensors", "*.json", "*.model", "*.txt"] 
)

# 3. Download Embedder (Nomic v1.5)
print("\n[2/3] Downloading Embedder: nomic-ai/nomic-embed-text-v1.5...")
snapshot_download(
    repo_id="nomic-ai/nomic-embed-text-v1.5",
    local_dir=str(BASE_DIR / "nomic-ai/nomic-embed-text-v1.5"),
    local_dir_use_symlinks=False
)

# 4. Download Reranker (MiniLM)
print("\n[3/3] Downloading Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2...")
snapshot_download(
    repo_id="cross-encoder/ms-marco-MiniLM-L-6-v2",
    local_dir=str(BASE_DIR / "cross-encoder/ms-marco-MiniLM-L-6-v2"),
    local_dir_use_symlinks=False
)

print("\n✅ All models downloaded successfully.")