"""Process local public or synthetic documents and print content-safe measurements."""

import argparse
import asyncio
import json
from pathlib import Path

from app.ingestion import ReceivedDocumentFile, process_document

REQUEST_ID = "00000000-0000-0000-0000-000000000000"
MIME_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
}


async def inspect_document(path: Path) -> dict[str, object]:
    """Run the complete local pipeline and return measurements without content."""

    suffix = path.suffix.lower()
    if suffix not in MIME_TYPES:
        raise ValueError("Only .md, .txt, and .pdf documents are supported.")

    result = await process_document(
        ReceivedDocumentFile(
            filename=path.name,
            mime_type=MIME_TYPES[suffix],
            content=path.read_bytes(),
        ),
        request_id=REQUEST_ID,
    )
    chunk_sizes = [chunk.character_count for chunk in result.chunks]
    return {
        "filename": result.original_filename,
        "sha256": result.sha256,
        "format": result.mime_type.value,
        "pages": result.page_count,
        "characters": result.character_count,
        "chunks": result.chunks_count,
        "smallest_chunk": min(chunk_sizes),
        "largest_chunk": max(chunk_sizes),
    }


async def inspect_documents(paths: list[Path]) -> list[dict[str, object]]:
    """Process documents sequentially to keep local resource use predictable."""

    return [await inspect_document(path) for path in paths]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate documents through the local FinRAG M2 pipeline."
    )
    parser.add_argument("documents", nargs="+", type=Path)
    arguments = parser.parse_args()

    try:
        measurements = asyncio.run(inspect_documents(arguments.documents))
    except (OSError, ValueError) as error:
        parser.error(str(error))

    for measurement in measurements:
        print(json.dumps(measurement, sort_keys=True))


if __name__ == "__main__":
    main()
