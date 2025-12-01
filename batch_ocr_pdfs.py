import pytesseract
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
import sys
import time
from pathlib import Path
from typing import List

def ocr_pdf_to_text(pdf_path: Path):
    """
    Extracts text from a SINGLE PDF and saves it as a .txt file.
    It first tries to extract text directly. If that fails (or finds no text),
    it performs OCR on each page.
    """
    
    output_txt_path = pdf_path.with_suffix('.txt')
    print(f"\n--- Processing: {pdf_path.name} ---")

    # --- Step 1: Try to extract text directly ---
    print("  - Attempt 1: Extracting digital text...")
    full_text: List[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"  - Found {total_pages} pages.")
            
            for i, page in enumerate(pdf.pages):
                if (i + 1) % 50 == 0:
                    print(f"    - Reading text from page {i + 1}/{total_pages}...")
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    full_text.append(page_text)
            print("  - Text extraction complete.")

    except Exception as e:
        print(f"  - Error during text extraction: {e}. Will try OCR.")
        full_text = [] # Clear any partial text

    # --- Step 2: If no text was found, perform OCR ---
    if not full_text:
        print("  - Attempt 2: No digital text found. Performing OCR...")
        
        try:
            # 1. Convert PDF to a list of images
            print(f"  - Converting PDF to images (this may take a while)...")
            images = convert_from_path(pdf_path)
            total_pages = len(images)
            print(f"  - Converted {total_pages} pages to images.")

            # 2. Run OCR on each image
            for i, img in enumerate(images):
                print(f"  - OCR'ing page {i + 1}/{total_pages}...")
                page_text = pytesseract.image_to_string(img)
                full_text.append(page_text)
            
            print("  - OCR complete.")
        
        except Exception as e:
            print(f"\n  - ❌ FATAL ERROR: Could not perform OCR on this file.")
            print(f"  - Make sure 'tesseract' and 'poppler' are installed on your system.")
            print(f"  - Error details: {e}")
            return # Skip this file

    # --- Step 3: Save the results to a text file ---
    final_content = "\n\n".join(full_text) # Separate pages with newlines
    try:
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        print(f"  - ✅ Success! Text saved to: {output_txt_path.name}")
        
    except Exception as e:
        print(f"  - ❌ FAILED to write text file: {e}")

def process_folder(folder_path_str: str):
    """
    Finds all PDFs in a folder (and its subfolders) and runs OCR on them.
    """
    folder_path = Path(folder_path_str)
    if not folder_path.is_dir():
        print(f"Error: Path is not a valid directory: {folder_path}")
        return

    print(f"Scanning for PDFs in: {folder_path}...")
    # Use rglob to find all PDFs recursively
    pdf_files = list(folder_path.rglob('*.pdf'))
    
    if not pdf_files:
        print("No PDF files found.")
        return
        
    total_count = len(pdf_files)
    print(f"Found {total_count} PDF files. Starting batch conversion...")
    start_time = time.time()
    
    for i, pdf_path in enumerate(pdf_files):
        print(f"\n{'='*60}")
        print(f"Processing file {i + 1} of {total_count}...")
        ocr_pdf_to_text(pdf_path) # Pass the Path object
        
    end_time = time.time()
    print(f"\n{'='*60}")
    print(f"Batch complete. Processed {total_count} files in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    # Check if a folder path was provided as an argument
    if len(sys.argv) < 2:
        print("Usage: python3 batch_ocr_pdfs.py /path/to/your/FOLDER_of_pdfs")
    else:
        folder_to_process = sys.argv[1]
        process_folder(folder_to_process)
