import os
from typing import List, TypedDict
import logging
import pdfplumber
import docx
from langchain_core.documents import Document
import chardet

logging.getLogger("pdfminer").setLevel(logging.ERROR)


class PageContent(TypedDict):
    page: int
    text: str


class DocParser:
    @staticmethod
    def parse_pdf_pages(file_path: str) -> List[PageContent]:
        pages: List[PageContent] = []
        with pdfplumber.open(file_path) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"page": idx, "text": text})
        return pages

    @staticmethod
    def parse_docx(file_path: str) -> str:
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    @staticmethod
    def parse_markdown(file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def parse_txt(file_path: str) -> str:
        with open(file_path, "rb") as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result["encoding"] or "utf-8"
        return raw_data.decode(encoding, errors="replace")

    @staticmethod
    def parse_pages(file_path: str) -> List[PageContent]:
        """Return document as page-segmented content.

        For non-paginated formats (docx/md/txt) returns single entry with page=1.
        Used so chunk metadata can carry true page numbers for PDFs.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return DocParser.parse_pdf_pages(file_path)
        if ext in [".docx", ".doc"]:
            return [{"page": 1, "text": DocParser.parse_docx(file_path)}]
        if ext in [".md", ".markdown"]:
            return [{"page": 1, "text": DocParser.parse_markdown(file_path)}]
        if ext == ".txt":
            return [{"page": 1, "text": DocParser.parse_txt(file_path)}]
        raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def parse(file_path: str) -> str:
        """Legacy flat-text parser kept for callers that just need raw content."""
        pages = DocParser.parse_pages(file_path)
        return "\n\n".join(p["text"] for p in pages)
