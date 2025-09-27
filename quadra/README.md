# Quadra Markdown PDF Generation

This directory contains a lightweight toolchain for converting Quadra Markdown
files (`*.quadra.md`) into PDF documents. The conversion script is implemented in
pure Python and does not rely on external packages, making it portable across
environments.

## Usage

```bash
python quadra/quadra_to_pdf.py path/to/document.quadra.md
```

When an explicit output path is not provided, the script writes the PDF next to
the source file using the same filename with a `.pdf` extension. Provide a
second argument to customise the destination:

```bash
python quadra/quadra_to_pdf.py path/to/document.quadra.md custom/output.pdf
```

Generated PDFs use a simple single-column layout with support for headings,
paragraphs, and unordered lists—the primary constructs of the Quadra Markdown
format requested for this project.
