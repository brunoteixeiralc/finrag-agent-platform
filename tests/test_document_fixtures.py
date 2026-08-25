"""Reproducibility and public-safety tests for committed synthetic fixtures."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.ingestion import ReceivedDocumentFile, SupportedMimeType, process_document

FIXTURES_DIRECTORY = Path(__file__).parent / "fixtures" / "documents"
REQUEST_ID = "4b987954-6230-4f67-9c10-ecce963ddba9"


@dataclass(frozen=True, slots=True)
class FixtureExpectation:
    filename: str
    mime_type: str
    expected_type: SupportedMimeType
    sha256: str
    page_count: int
    chunk_count: int


FIXTURE_EXPECTATIONS = (
    FixtureExpectation(
        filename="synthetic_liquidity_report.md",
        mime_type="text/markdown",
        expected_type=SupportedMimeType.MARKDOWN,
        sha256="b6d5256af535cde1b96cdf0bccdefda0954c63bf61a8d4549ca8827cd6cb0dc0",
        page_count=1,
        chunk_count=4,
    ),
    FixtureExpectation(
        filename="synthetic_credit_notes.txt",
        mime_type="text/plain",
        expected_type=SupportedMimeType.PLAIN_TEXT,
        sha256="b834437fbcadfc929214ad888a97c43f06e2d411efc532543912d649b9f0222b",
        page_count=1,
        chunk_count=1,
    ),
    FixtureExpectation(
        filename="synthetic_risk_report.pdf",
        mime_type="application/pdf",
        expected_type=SupportedMimeType.PDF,
        sha256="db607d8ec92922379599ee666b6e91402b2ffd3bcbcc3d77c2570415f55384e7",
        page_count=2,
        chunk_count=2,
    ),
)


def process_fixture(expectation: FixtureExpectation):
    path = FIXTURES_DIRECTORY / expectation.filename
    return asyncio.run(
        process_document(
            ReceivedDocumentFile(
                filename=path.name,
                mime_type=expectation.mime_type,
                content=path.read_bytes(),
            ),
            request_id=REQUEST_ID,
        )
    )


@pytest.mark.parametrize("expectation", FIXTURE_EXPECTATIONS)
def test_fixture_pipeline_results_are_reproducible(expectation: FixtureExpectation) -> None:
    result = process_fixture(expectation)

    assert result.mime_type is expectation.expected_type
    assert result.sha256 == expectation.sha256
    assert result.page_count == expectation.page_count
    assert result.chunks_count == expectation.chunk_count == len(result.chunks)
    assert [chunk.chunk_index for chunk in result.chunks] == list(range(len(result.chunks)))
    assert all(0 < chunk.character_count <= 2_400 for chunk in result.chunks)


@pytest.mark.parametrize("expectation", FIXTURE_EXPECTATIONS)
def test_fixture_content_is_explicitly_synthetic_and_contains_no_private_markers(
    expectation: FixtureExpectation,
) -> None:
    result = process_fixture(expectation)
    extracted_content = "\n".join(chunk.content for chunk in result.chunks)
    normalized = extracted_content.lower()

    assert "synthetic" in normalized or "fictional" in normalized
    assert "begin private key" not in normalized
    assert "password=" not in normalized
    assert "api_key=" not in normalized
    assert "@actdigital" not in normalized
    assert "@sicoob" not in normalized
    assert "@itau" not in normalized
    assert result.source_name is None
    assert result.source_url is None
    assert result.metadata == {}


def test_committed_pdf_is_textual_passive_and_page_isolated() -> None:
    expectation = FIXTURE_EXPECTATIONS[-1]
    path = FIXTURES_DIRECTORY / expectation.filename
    reader = PdfReader(path, strict=True)

    assert reader.is_encrypted is False
    assert len(reader.pages) == 2
    assert all((page.extract_text() or "").strip() for page in reader.pages)
    names = reader.root_object.get("/Names", {})
    assert "/JavaScript" not in names
    assert "/EmbeddedFiles" not in names
    assert "/OpenAction" not in reader.root_object

    result = process_fixture(expectation)
    assert [chunk.page_index for chunk in result.chunks] == [1, 2]
    assert "Adverse Scenario" not in result.chunks[0].content
    assert "Scenario Overview" not in result.chunks[1].content


def test_prompt_injection_fixture_remains_document_content() -> None:
    result = process_fixture(FIXTURE_EXPECTATIONS[0])

    assert any("Ignore previous instructions" in chunk.content for chunk in result.chunks)
