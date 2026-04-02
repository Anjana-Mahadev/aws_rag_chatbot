import re
import subprocess

from pypdf import PdfReader


def extract_text_from_pdf(file_path: str) -> str:
    """Extract full text from a PDF (for backward compat)."""
    pages = extract_pages_from_pdf(file_path)
    return "\n".join(pages)


def extract_pages_from_pdf(file_path: str) -> list[str]:
    """Extract text per page. Returns a list where index = page number (0-based)."""
    reader = PdfReader(file_path)
    pages = []

    # Try pypdf first (text-based PDFs)
    all_empty = True
    for page in reader.pages:
        page_text = page.extract_text() or ""
        cleaned = _clean_text(page_text)
        pages.append(cleaned)
        if cleaned.strip():
            all_empty = False

    if not all_empty:
        return pages

    # Fallback: OCR via Tesseract for scanned PDFs
    return _ocr_pdf_pages(file_path, len(reader.pages))


def _ocr_pdf_pages(file_path: str, num_pages: int) -> list[str]:
    """Extract text per page from scanned PDF using pdftoppm + tesseract."""
    import glob
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            ["pdftoppm", "-gray", "-r", "300", file_path, os.path.join(tmpdir, "page")],
            check=True,
            capture_output=True,
        )

        pages = []
        for img_path in sorted(glob.glob(os.path.join(tmpdir, "page-*.pgm"))):
            result = subprocess.run(
                [
                    "tesseract", img_path, "stdout",
                    "--psm", "6",
                    "-l", "eng",
                ],
                capture_output=True,
                text=True,
            )
            page_text = _clean_text(result.stdout) if result.stdout else ""
            pages.append(page_text)

    # Pad if fewer images than expected pages
    while len(pages) < num_pages:
        pages.append("")
    return pages


def _clean_text(text: str) -> str:
    """Remove OCR noise and non-readable garbage from extracted text."""
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip lines that are mostly non-alphanumeric (OCR noise)
        alnum_chars = sum(c.isalnum() or c.isspace() for c in line)
        if len(line) > 0 and alnum_chars / len(line) < 0.5:
            continue
        # Skip very short lines (likely garbage)
        if len(line) < 3:
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks (no page tracking)."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


def chunk_pages(pages: list[str], chunk_size: int = 1000, overlap: int = 200) -> list[dict]:
    """Split per-page text into overlapping chunks, tracking page numbers.

    Returns list of dicts: {"text": str, "pages": [int, ...]}
    Page numbers are 1-based for display.
    """
    chunks = []
    # Build a flat text with page boundary markers
    segments = []  # (char_start, char_end, page_num_1based)
    offset = 0
    for i, page_text in enumerate(pages):
        if not page_text.strip():
            continue
        text_with_space = page_text + "\n"
        segments.append((offset, offset + len(text_with_space), i + 1))
        offset += len(text_with_space)
    
    if not segments:
        return []

    full_text = "\n".join(p for p in pages if p.strip()) + "\n"
    # Re-compute with consistent offsets
    full_text = ""
    for i, page_text in enumerate(pages):
        if page_text.strip():
            full_text += page_text + "\n"

    # Rebuild segments on the actual concatenated text
    segments = []
    offset = 0
    for i, page_text in enumerate(pages):
        if not page_text.strip():
            continue
        length = len(page_text) + 1  # +1 for \n
        segments.append((offset, offset + length, i + 1))
        offset += length

    start = 0
    while start < len(full_text):
        end = start + chunk_size
        chunk = full_text[start:end].strip()
        if chunk:
            # Find which pages this chunk spans
            chunk_pages_set = set()
            for seg_start, seg_end, page_num in segments:
                if start < seg_end and end > seg_start:
                    chunk_pages_set.add(page_num)
            chunks.append({
                "text": chunk,
                "pages": sorted(chunk_pages_set) if chunk_pages_set else [1],
            })
        start += chunk_size - overlap

    return chunks
