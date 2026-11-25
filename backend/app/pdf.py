from io import BytesIO
import re

from pypdf import PdfReader


def extract_chunks(raw: bytes, max_pages: int, max_chunks: int):
    if not raw.startswith(b'%PDF-'):
        raise ValueError('This file is not a valid PDF.')
    try:
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported. Upload an unlocked copy.')
        if len(reader.pages) > max_pages:
            raise ValueError(f'Please upload a PDF with at most {max_pages} pages.')
        chunks = []
        for page_number, page in enumerate(reader.pages, 1):
            content = re.sub(r'\s+', ' ', page.extract_text() or '').strip()
            words = content.split()
            # Page boundaries are never crossed, so every citation has an exact PDF page.
            for start in range(0, len(words), 190):
                body = ' '.join(words[start:start + 230])
                if body:
                    chunks.append((page_number, body))
                if len(chunks) > max_chunks:
                    raise ValueError('This PDF contains too much text. Split it into smaller files.')
                if start + 230 >= len(words):
                    break
        if not chunks:
            raise ValueError('No selectable text found. Scanned PDFs need OCR before upload.')
        return len(reader.pages), chunks
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('The PDF could not be read. Try exporting a fresh PDF.') from exc
