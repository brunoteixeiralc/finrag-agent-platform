BEGIN;

CREATE TABLE documents (
    id uuid PRIMARY KEY,
    status varchar(20) NOT NULL,
    title varchar(200) NOT NULL,
    original_filename varchar(255) NOT NULL,
    mime_type varchar(100) NOT NULL,
    sha256 text NOT NULL UNIQUE,
    page_count integer,
    character_count integer NOT NULL,
    chunks_count integer NOT NULL,
    source_name varchar(200),
    source_url text,
    published_at date,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT documents_status_indexed CHECK (status = 'indexed'),
    CONSTRAINT documents_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT documents_filename_not_blank CHECK (btrim(original_filename) <> ''),
    CONSTRAINT documents_mime_type_supported CHECK (
        mime_type IN ('text/markdown', 'text/plain', 'application/pdf')
    ),
    CONSTRAINT documents_sha256_format CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT documents_page_count_limit CHECK (
        page_count IS NULL OR page_count BETWEEN 1 AND 50
    ),
    CONSTRAINT documents_character_count_limit CHECK (
        character_count BETWEEN 1 AND 500000
    ),
    CONSTRAINT documents_chunks_count_positive CHECK (chunks_count > 0),
    CONSTRAINT documents_source_name_not_blank CHECK (
        source_name IS NULL OR btrim(source_name) <> ''
    ),
    CONSTRAINT documents_source_url_http CHECK (
        source_url IS NULL OR source_url ~* '^https?://'
    ),
    CONSTRAINT documents_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE chunks (
    id uuid PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    character_count integer NOT NULL,
    provider_token_count integer,
    page_index integer,
    page_label varchar(50),
    section varchar(500),
    contains_table boolean NOT NULL DEFAULT false,
    embedding vector(768) NOT NULL,
    embedding_model varchar(100) NOT NULL,
    embedding_dimensions smallint NOT NULL,
    CONSTRAINT chunks_document_index_unique UNIQUE (document_id, chunk_index),
    CONSTRAINT chunks_index_non_negative CHECK (chunk_index >= 0),
    CONSTRAINT chunks_content_not_blank CHECK (btrim(content) <> ''),
    CONSTRAINT chunks_character_count_limit CHECK (
        character_count BETWEEN 1 AND 2400
    ),
    CONSTRAINT chunks_token_count_non_negative CHECK (
        provider_token_count IS NULL OR provider_token_count >= 0
    ),
    CONSTRAINT chunks_page_index_positive CHECK (page_index IS NULL OR page_index >= 1),
    CONSTRAINT chunks_page_label_not_blank CHECK (
        page_label IS NULL OR btrim(page_label) <> ''
    ),
    CONSTRAINT chunks_section_not_blank CHECK (section IS NULL OR btrim(section) <> ''),
    CONSTRAINT chunks_embedding_model_not_blank CHECK (btrim(embedding_model) <> ''),
    CONSTRAINT chunks_embedding_dimensions_fixed CHECK (embedding_dimensions = 768)
);

COMMIT;
