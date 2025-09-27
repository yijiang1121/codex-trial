#!/usr/bin/env python3
"""Simple Quadra Markdown to PDF converter.

This script implements a minimal renderer for a lightweight "Quadra" Markdown
format. It supports:
* Headings using leading `#` characters.
* Paragraphs separated by blank lines.
* Unordered lists with lines starting with `- `.

The output PDF is generated without external dependencies by constructing the
necessary PDF objects directly. The generated layout is basic but ensures the
content is readable and paginated when the text exceeds the current page.
"""

from __future__ import annotations

import argparse
import io
import textwrap
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


@dataclass
class Block:
    """Represents a parsed Quadra Markdown block."""

    type: str
    content: object


def parse_quadra_markdown(text: str) -> List[Block]:
    """Parse Quadra Markdown text into structured blocks."""

    blocks: List[Block] = []
    paragraph: List[str] = []
    current_list: List[str] | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            joined = " ".join(line.strip() for line in paragraph if line.strip())
            if joined:
                blocks.append(Block("paragraph", joined))
        paragraph = []

    def flush_list() -> None:
        nonlocal current_list
        if current_list:
            blocks.append(Block("list", current_list))
        current_list = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            flush_list()
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_text = stripped[level:].strip()
            blocks.append(Block("heading", (level, heading_text)))
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            if current_list is None:
                current_list = []
            current_list.append(stripped[2:].strip())
            continue

        flush_list()
        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    return blocks


class PDFBuilder:
    """Create PDF content for parsed blocks using basic typography."""

    def __init__(self, width: float = 612.0, height: float = 792.0, margin: float = 72.0):
        self.width = width
        self.height = height
        self.margin = margin
        self.pages: List[List[Tuple[float, float, float, str]]] = []
        self._new_page()

    def _new_page(self) -> None:
        self.current_page: List[Tuple[float, float, float, str]] = []
        self.pages.append(self.current_page)
        self.cursor_y = self.height - self.margin

    def _ensure_space(self, line_height: float) -> None:
        if self.cursor_y - line_height < self.margin:
            self._new_page()

    def _add_line(self, text: str, font_size: float, indent: float = 0.0) -> None:
        line_height = font_size * 1.2
        self._ensure_space(line_height)
        x_position = self.margin + indent
        normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        self.current_page.append((font_size, x_position, self.cursor_y, normalized))
        self.cursor_y -= line_height

    def add_heading(self, level: int, text: str) -> None:
        size_map = {1: 24.0, 2: 18.0, 3: 16.0}
        font_size = size_map.get(level, 14.0)
        self.cursor_y -= font_size * 0.3
        self._add_line(text, font_size)
        self.cursor_y -= font_size * 0.3

    def add_paragraph(self, text: str, indent: float = 0.0, font_size: float = 12.0) -> None:
        max_width = self.width - 2 * self.margin - indent
        chars_per_line = max(int(max_width / (font_size * 0.55)), 20)
        wrapped = textwrap.wrap(text, width=chars_per_line)
        if not wrapped:
            wrapped = [""]
        for idx, line in enumerate(wrapped):
            prefix = "" if idx else ""
            self._add_line(prefix + line, font_size, indent)
        self.cursor_y -= font_size * 0.4

    def add_list(self, items: Sequence[str]) -> None:
        for item in items:
            bullet_prefix = "- "
            max_width = self.width - 2 * self.margin - 18.0
            chars_per_line = max(int(max_width / (12.0 * 0.55)), 20)
            wrapped = textwrap.wrap(item, width=chars_per_line)
            for idx, line in enumerate(wrapped):
                if idx == 0:
                    text_line = f"{bullet_prefix}{line}"
                else:
                    text_line = f"  {line}"
                self._add_line(text_line, 12.0, indent=18.0)
            self.cursor_y -= 12.0 * 0.4

    def build(self, blocks: Iterable[Block]) -> None:
        for block in blocks:
            if block.type == "heading":
                level, text = block.content  # type: ignore[misc]
                self.add_heading(level, text)
            elif block.type == "paragraph":
                self.add_paragraph(block.content)  # type: ignore[arg-type]
            elif block.type == "list":
                self.add_list(block.content)  # type: ignore[arg-type]

    def write_pdf(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        writer = PDFWriter(self.width, self.height, self.pages)
        writer.write(output_path)


class PDFWriter:
    """Serialize pages built by :class:`PDFBuilder` into a PDF file."""

    def __init__(self, width: float, height: float, pages: Sequence[Sequence[Tuple[float, float, float, str]]]):
        self.width = width
        self.height = height
        self.pages = pages

    @staticmethod
    def _escape_text(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _page_stream(self, page: Sequence[Tuple[float, float, float, str]]) -> bytes:
        commands = []
        for font_size, x_pos, y_pos, text in page:
            commands.append("BT")
            commands.append(f"/F1 {font_size:.2f} Tf")
            commands.append(f"1 0 0 1 {x_pos:.2f} {y_pos:.2f} Tm")
            commands.append(f"({self._escape_text(text)}) Tj")
            commands.append("ET")
        commands.append("")
        return "\n".join(commands).encode("latin-1")

    def write(self, output_path: Path) -> None:
        num_pages = len(self.pages)
        page_object_start = 3
        content_object_start = page_object_start + num_pages
        font_object_id = content_object_start + num_pages
        total_objects = font_object_id

        buffer = io.BytesIO()

        def write(data: str | bytes) -> None:
            if isinstance(data, str):
                data = data.encode("latin-1")
            buffer.write(data)

        xref_positions: List[int] = []

        def start_obj(obj_id: int) -> None:
            xref_positions.append(buffer.tell())
            write(f"{obj_id} 0 obj\n")

        write("%PDF-1.4\n")

        # 1 0 obj: Catalog
        start_obj(1)
        write("<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        # 2 0 obj: Pages container
        start_obj(2)
        kids = " ".join(f"{obj_id} 0 R" for obj_id in range(page_object_start, page_object_start + num_pages))
        write(f"<< /Type /Pages /Kids [ {kids} ] /Count {num_pages} >>\nendobj\n")

        # Page objects
        for index in range(num_pages):
            page_obj_id = page_object_start + index
            content_obj_id = content_object_start + index
            start_obj(page_obj_id)
            write(
                "<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {self.width:.0f} {self.height:.0f}] "
                f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> "
                f"/Contents {content_obj_id} 0 R >>\nendobj\n"
            )

        # Content streams
        for index, page in enumerate(self.pages):
            stream = self._page_stream(page)
            content_obj_id = content_object_start + index
            start_obj(content_obj_id)
            write(f"<< /Length {len(stream)} >>\nstream\n")
            buffer.write(stream)
            write("endstream\nendobj\n")

        # Font object (Helvetica)
        start_obj(font_object_id)
        write("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

        xref_start = buffer.tell()
        write(f"xref\n0 {total_objects + 1}\n")
        write("0000000000 65535 f \n")
        for pos in xref_positions:
            write(f"{pos:010} 00000 n \n")
        write(
            "trailer "
            f"<< /Size {total_objects + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        )

        output_path.write_bytes(buffer.getvalue())


def convert_quadra_markdown(input_path: Path, output_path: Path) -> None:
    blocks = parse_quadra_markdown(input_path.read_text(encoding="utf-8"))
    builder = PDFBuilder()
    builder.build(blocks)
    builder.write_pdf(output_path)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Convert Quadra Markdown to PDF.")
    parser.add_argument("input", type=Path, help="Path to the Quadra Markdown file.")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Optional output path for the generated PDF (defaults to <input>.pdf).",
    )
    args = parser.parse_args(argv)

    input_path = args.input
    if not input_path.exists():
        raise SystemExit(f"Input file '{input_path}' does not exist.")

    output_path = args.output or input_path.with_suffix(".pdf")
    convert_quadra_markdown(input_path, output_path)
    print(f"Generated PDF: {output_path}")


if __name__ == "__main__":
    main()
