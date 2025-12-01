#!/bin/bash

# 1. Navigate to the script's directory (Project Root)
cd "$(dirname "$0")"

# 2. Activate Environment (with check)
if [ -f "venv_stable/bin/activate" ]; then
    echo "✅ Activating virtual environment..."
    source venv_stable/bin/activate
else
    echo "❌ Error: 'venv_stable' not found. Please run setup first."
    exit 1
fi

# 3. Run Ingestion Script
echo "🧠 Starting Ingestion Process (MLX / Local)..."
# We use python -m to ensure imports work relative to project root
python -m backend.ingest

# 4. Keep Window Open
echo ""
echo "✅ Process Finished."
read -p "Press [Enter] to close..."