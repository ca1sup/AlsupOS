# convert_epubs_v2.py
import sys
import time
from pathlib import Path
from typing import List
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def convert_epub_to_text(epub_path: Path):
    """
    Extracts text from a SINGLE EPUB using ebooklib and saves it as a .txt file.
    """
    
    output_txt_path = epub_path.with_suffix('.txt')
    print(f"\n--- Processing: {epub_path.name} ---")

    try:
        # 1. Open the EPUB file
        print(f"  - Loading '{epub_path.name}'...")
        book = epub.read_epub(epub_path)
        
        full_text_parts = []
        
        # 2. Loop through all items in the book
        print("  - Extracting text items...")
        for item in book.get_items():
            # We only want text items (chapters, sections, etc.)
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # Get the raw content (which is usually HTML)
                raw_content = item.get_content()
                
                # Use BeautifulSoup to parse the HTML and get only the text
                soup = BeautifulSoup(raw_content, 'html.parser')
                text = soup.get_text()
                
                if text and text.strip():
                    full_text_parts.append(text.strip())

        if not full_text_parts:
            print("  - ❌ FAILED: No text content found in this EPUB.")
            return

        # 3. Join all text parts together
        final_content = "\n\n".join(full_text_parts) # Separate chapters/sections
        print(f"  - Successfully extracted {len(final_content)} characters.")

        # 4. Save to .txt file
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        print(f"  - ✅ Success! Text saved to: {output_txt_path.name}")
        
    except Exception as e:
        print(f"  - ❌ FAILED to process file: {e}")
        print("  - This may be a corrupted or DRM-protected EPUB file.")

def process_folder(folder_path_str: str):
    """
    Finds all EPUBs in a folder (and its subfolders) and runs conversion.
    """
    folder_path = Path(folder_path_str)
    if not folder_path.is_dir():
        print(f"Error: Path is not a valid directory: {folder_path}")
        return

    print(f"Scanning for EPUBs in: {folder_path}...")
    epub_files = list(folder_path.rglob('*.epub'))
    
    if not epub_files:
        print("No EPUB files found.")
        return
        
    total_count = len(epub_files)
    print(f"Found {total_count} EPUB files. Starting batch conversion...")
    start_time = time.time()
    
    for i, epub_path in enumerate(epub_files):
        print(f"\n{'='*60}")
        print(f"Processing file {i + 1} of {total_count}...")
        convert_epub_to_text(epub_path) # Pass the Path object
        
    end_time = time.time()
    print(f"\n{'='*60}")
    print(f"Batch complete. Processed {total_count} files in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 convert_epubs_v2.py /path/to/your/FOLDER_of_epubs")
    else:
        folder_to_process = sys.argv[1]
        process_folder(folder_to_process)
