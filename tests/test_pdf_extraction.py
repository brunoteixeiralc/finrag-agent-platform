"""Unit tests for safe textual PDF extraction."""

from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.constants import PageLabelStyle
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import app.ingestion.pdf_extraction as pdf_extraction_module
from app.ingestion import (
    DocumentValidationError,
    ExtractedBlockKind,
    IngestionErrorCode,
    ReceivedDocumentFile,
    extract_pdf_document,
    validate_document_input,
)
from app.ingestion.text_extraction import MAX_EXTRACTED_CHARACTERS


def pdf_bytes(
    page_texts: list[str],
    *,
    page_label_prefix: str | None = None,
    encrypted: bool = False,
    active_content: bool = False,
) -> bytes:
    """Create a small in-memory PDF fixture using only pypdf."""

    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)

    for page_text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
        )
        escaped_lines = [
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            for line in page_text.split("\n")
        ]
        text_operations = " T* ".join(f"({line}) Tj" for line in escaped_lines)
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 14 TL 72 720 Td {text_operations} ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)

    if page_label_prefix is not None and page_texts:
        writer.set_page_label(
            0,
            len(page_texts) - 1,
            style=PageLabelStyle.DECIMAL,
            prefix=page_label_prefix,
            start=1,
        )
    if active_content:
        writer.add_attachment("ignored.txt", b"attachment must not be extracted")
        writer.add_js("app.alert('this must never execute')")
    if encrypted:
        writer.encrypt("test-only-password", algorithm="RC4-128")

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def validated_pdf(content: bytes, *, title: str | None = None):
    return validate_document_input(
        ReceivedDocumentFile(
            filename="synthetic_report.pdf",
            mime_type="application/pdf",
            content=content,
        ),
        title=title,
    )


def test_textual_pages_are_ordered_and_never_share_blocks() -> None:
    source = validated_pdf(pdf_bytes(["First page text", "Second page text"]))

    extracted = extract_pdf_document(source)

    assert extracted.title == "synthetic report"
    assert [page.page_index for page in extracted.pages] == [1, 2]
    assert [page.content for page in extracted.pages] == [
        "First page text",
        "Second page text",
    ]
    assert extracted.character_count == len("First page textSecond page text")
    assert all(len(page.blocks) == 1 for page in extracted.pages)
    assert extracted.pages[0].blocks[0].content == "First page text"
    assert extracted.pages[1].blocks[0].content == "Second page text"
    assert all(
        block.kind is ExtractedBlockKind.PARAGRAPH
        for page in extracted.pages
        for block in page.blocks
    )


def test_explicit_page_labels_are_preserved() -> None:
    source = validated_pdf(pdf_bytes(["Alpha", "Beta"], page_label_prefix="A-"))

    extracted = extract_pdf_document(source)

    assert [page.page_label for page in extracted.pages] == ["A-1", "A-2"]


def test_page_labels_with_control_characters_are_rejected() -> None:
    source = validated_pdf(pdf_bytes(["Text"], page_label_prefix="\u202e"))

    with pytest.raises(DocumentValidationError) as captured_error:
        extract_pdf_document(source)

    assert captured_error.value.code is IngestionErrorCode.PDF_MALFORMED


def test_default_generated_page_numbers_are_not_claimed_as_explicit_labels() -> None:
    source = validated_pdf(pdf_bytes(["Only page"]))

    extracted = extract_pdf_document(source)

    assert extracted.pages[0].page_label is None


def test_provided_title_takes_precedence_over_filename() -> None:
    source = validated_pdf(pdf_bytes(["Text"]), title="Contract title")

    extracted = extract_pdf_document(source)

    assert extracted.title == "Contract title"


def test_active_content_and_attachments_are_ignored() -> None:
    source = validated_pdf(pdf_bytes(["Visible page text"], active_content=True))

    extracted = extract_pdf_document(source)

    assert extracted.pages[0].content == "Visible page text"
    assert "attachment" not in extracted.pages[0].content
    assert "app.alert" not in extracted.pages[0].content


def test_blank_image_only_pdf_reports_ocr_as_unsupported() -> None:
    source = validated_pdf(pdf_bytes([""]))

    with pytest.raises(DocumentValidationError) as captured_error:
        extract_pdf_document(source)

    assert captured_error.value.code is IngestionErrorCode.PDF_OCR_UNSUPPORTED


def test_encrypted_pdf_is_rejected_without_attempting_decryption() -> None:
    source = validated_pdf(pdf_bytes(["Secret text"], encrypted=True))

    with pytest.raises(DocumentValidationError) as captured_error:
        extract_pdf_document(source)

    assert captured_error.value.code is IngestionErrorCode.PDF_ENCRYPTED


def test_pdf_above_fifty_pages_is_rejected_before_page_extraction() -> None:
    source = validated_pdf(pdf_bytes([""] * 51))

    with pytest.raises(DocumentValidationError) as captured_error:
        extract_pdf_document(source)

    assert captured_error.value.code is IngestionErrorCode.PDF_PAGE_LIMIT_EXCEEDED


def test_pdf_at_exactly_fifty_pages_is_accepted() -> None:
    source = validated_pdf(pdf_bytes([f"Page {index}" for index in range(1, 51)]))

    extracted = extract_pdf_document(source)

    assert len(extracted.pages) == 50
    assert extracted.pages[-1].page_index == 50


def test_malformed_pdf_returns_safe_error() -> None:
    rejected_content = b"%PDF-1.7\nnot-a-valid-pdf-containing-sensitive-data"
    source = validated_pdf(rejected_content)

    with pytest.raises(DocumentValidationError) as captured_error:
        extract_pdf_document(source)

    assert captured_error.value.code is IngestionErrorCode.PDF_MALFORMED
    assert "sensitive-data" not in str(captured_error.value)
    assert "sensitive-data" not in repr(captured_error.value)


def test_global_extracted_character_limit_is_enforced() -> None:
    source = validated_pdf(pdf_bytes(["x" * (MAX_EXTRACTED_CHARACTERS + 1)]))

    with pytest.raises(DocumentValidationError) as captured_error:
        extract_pdf_document(source)

    assert captured_error.value.code is IngestionErrorCode.EXTRACTED_TEXT_TOO_LARGE


def test_page_content_stream_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    source = validated_pdf(pdf_bytes(["Visible text"]))
    monkeypatch.setattr(pdf_extraction_module, "MAX_PDF_PAGE_CONTENT_STREAM_BYTES", 1)

    with pytest.raises(DocumentValidationError) as captured_error:
        extract_pdf_document(source)

    assert captured_error.value.code is IngestionErrorCode.PDF_CONTENT_STREAM_TOO_LARGE


def test_same_pdf_produces_equal_structure() -> None:
    source = validated_pdf(pdf_bytes(["First", "Second"]))

    first = extract_pdf_document(source)
    second = extract_pdf_document(source)

    assert first == second


def test_non_pdf_input_is_rejected_by_pdf_extractor() -> None:
    source = validate_document_input(
        ReceivedDocumentFile(
            filename="notes.txt",
            mime_type="text/plain",
            content=b"Plain text",
        )
    )

    with pytest.raises(DocumentValidationError) as captured_error:
        extract_pdf_document(source)

    assert captured_error.value.code is IngestionErrorCode.UNSUPPORTED_EXTRACTION_TYPE
