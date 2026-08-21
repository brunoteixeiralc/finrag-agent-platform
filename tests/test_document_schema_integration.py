"""Integration tests for the document and chunk relational schema."""

import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from psycopg import Connection, connect
from psycopg.errors import CheckViolation, DataException, UniqueViolation

from app.settings import Settings

VALID_VECTOR = "[" + ",".join(["0"] * 768) + "]"
SHORT_VECTOR = "[0,0,0]"


@pytest.fixture
def database_connection() -> Iterator[Connection[tuple[object, ...]]]:
    """Open an opted-in integration connection and roll back test data."""

    if os.getenv("FINRAG_RUN_INTEGRATION") != "1":
        pytest.skip("set FINRAG_RUN_INTEGRATION=1 to run PostgreSQL integration tests")

    settings = Settings(environment="test")
    if settings.database_url is None:
        pytest.fail("FINRAG_DATABASE_URL is required for integration tests")

    connection = connect(settings.database_url.get_secret_value())
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def insert_document(
    connection: Connection[tuple[object, ...]],
    *,
    document_id: UUID | None = None,
    sha256: str = "a" * 64,
) -> UUID:
    """Insert one valid indexed document for schema tests."""

    resolved_id = document_id or uuid4()
    connection.execute(
        """
        INSERT INTO documents (
            id,
            status,
            title,
            original_filename,
            mime_type,
            sha256,
            character_count,
            chunks_count
        )
        VALUES (%s, 'indexed', 'Synthetic document', 'synthetic.md',
                'text/markdown', %s, 1200, 1)
        """,
        (resolved_id, sha256),
    )
    return resolved_id


def insert_chunk(
    connection: Connection[tuple[object, ...]],
    *,
    document_id: UUID,
    embedding: str = VALID_VECTOR,
    embedding_dimensions: int = 768,
) -> UUID:
    """Insert one valid chunk unless a test overrides an embedding invariant."""

    chunk_id = uuid4()
    connection.execute(
        """
        INSERT INTO chunks (
            id,
            document_id,
            chunk_index,
            content,
            character_count,
            section,
            embedding,
            embedding_model,
            embedding_dimensions
        )
        VALUES (%s, %s, 0, 'Evidence grounded content.', 26, 'Overview',
                %s::vector, 'gemini-embedding-001', %s)
        """,
        (chunk_id, document_id, embedding, embedding_dimensions),
    )
    return chunk_id


@pytest.mark.integration
def test_schema_stores_vector_768_and_cascades_chunks(
    database_connection: Connection[tuple[object, ...]],
) -> None:
    document_id = insert_document(database_connection)
    chunk_id = insert_chunk(database_connection, document_id=document_id)

    metadata = database_connection.execute(
        "SELECT metadata FROM documents WHERE id = %s",
        (document_id,),
    ).fetchone()
    embedding_type = database_connection.execute(
        """
        SELECT format_type(attribute.atttypid, attribute.atttypmod)
        FROM pg_attribute AS attribute
        JOIN pg_class AS relation ON relation.oid = attribute.attrelid
        WHERE relation.relname = 'chunks'
          AND attribute.attname = 'embedding'
          AND attribute.attnum > 0
        """
    ).fetchone()

    assert metadata == ({},)
    assert embedding_type == ("vector(768)",)

    database_connection.execute("DELETE FROM documents WHERE id = %s", (document_id,))
    remaining_chunk = database_connection.execute(
        "SELECT id FROM chunks WHERE id = %s",
        (chunk_id,),
    ).fetchone()

    assert remaining_chunk is None


@pytest.mark.integration
def test_schema_rejects_duplicate_document_sha256(
    database_connection: Connection[tuple[object, ...]],
) -> None:
    insert_document(database_connection, sha256="b" * 64)

    with pytest.raises(UniqueViolation), database_connection.transaction():
        insert_document(database_connection, sha256="b" * 64)


@pytest.mark.integration
def test_schema_rejects_wrong_vector_size(
    database_connection: Connection[tuple[object, ...]],
) -> None:
    document_id = insert_document(database_connection, sha256="c" * 64)

    with pytest.raises(DataException), database_connection.transaction():
        insert_chunk(
            database_connection,
            document_id=document_id,
            embedding=SHORT_VECTOR,
        )


@pytest.mark.integration
def test_schema_rejects_wrong_embedding_dimension_metadata(
    database_connection: Connection[tuple[object, ...]],
) -> None:
    document_id = insert_document(database_connection, sha256="d" * 64)

    with pytest.raises(CheckViolation), database_connection.transaction():
        insert_chunk(
            database_connection,
            document_id=document_id,
            embedding_dimensions=767,
        )


@pytest.mark.integration
def test_schema_has_no_approximate_vector_index(
    database_connection: Connection[tuple[object, ...]],
) -> None:
    approximate_indexes = database_connection.execute(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'chunks'
          AND (indexdef ILIKE '%USING hnsw%' OR indexdef ILIKE '%USING ivfflat%')
        """
    ).fetchall()

    assert approximate_indexes == []
