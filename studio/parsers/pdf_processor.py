"""
studio.parsers.pdf_processor
============================
Architectural PDF Ingestion & Rasterizer.
Inspects vector/scanned architectural PDF documents, extracts page metadata,
renders high-resolution raster images (150-300 DPI) for computer vision processing,
and extracts native PDF text annotations.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
from utils.logging_config import logger


class PDFProcessor:
    """
    Processes architectural PDF blueprints and drawings.
    Renders vector pages into crisp high-DPI bitmaps for OpenCV analysis.
    """

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")

        self.doc = fitz.open(str(self.pdf_path))
        self.page_count: int = len(self.doc)

    def get_document_info(self) -> Dict[str, Any]:
        """Retrieve document metadata and page summary."""
        pages_summary = []
        for i in range(self.page_count):
            page = self.doc[i]
            rect = page.rect
            pages_summary.append({
                "page_index": i,
                "page_number": i + 1,
                "width_pt": round(rect.width, 2),
                "height_pt": round(rect.height, 2),
                "orientation": "Landscape" if rect.width > rect.height else "Portrait",
                "text_snippet": page.get_text()[:200].strip(),
            })

        return {
            "file_name": self.pdf_path.name,
            "page_count": self.page_count,
            "is_encrypted": self.doc.is_encrypted,
            "pages": pages_summary,
        }

    def render_page_to_image(
        self,
        page_index: int = 0,
        dpi: int = 200,
        output_dir: Optional[str | Path] = None
    ) -> Path:
        """
        Render a PDF page to a PNG bitmap.
        200 DPI offers optimal fidelity for architectural floor-plan edge detection.
        """
        if page_index < 0 or page_index >= self.page_count:
            raise IndexError(f"Page index {page_index} out of range (total pages: {self.page_count})")

        out_dir = Path(output_dir) if output_dir else self.pdf_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        target_path = out_dir / f"{self.pdf_path.stem}_page_{page_index + 1}.png"

        page = self.doc[page_index]
        # Calculate matrix scaling factor from 72 DPI base to requested DPI
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        pixmap.save(str(target_path))

        logger.info(
            f"Rendered PDF page {page_index + 1}/{self.page_count} to {target_path.name} "
            f"({pixmap.width}x{pixmap.height}px @ {dpi} DPI)"
        )
        return target_path

    def extract_page_text(self, page_index: int = 0) -> List[Dict[str, Any]]:
        """Extract positioned text blocks from the PDF page."""
        if page_index < 0 or page_index >= self.page_count:
            return []

        page = self.doc[page_index]
        blocks = page.get_text("blocks")
        text_entries = []
        for b in blocks:
            # b: (x0, y0, x1, y1, text, block_no, block_type)
            if len(b) >= 5 and b[4].strip():
                text_entries.append({
                    "bbox": [round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)],
                    "text": b[4].strip()
                })
        return text_entries

    def close(self):
        self.doc.close()
