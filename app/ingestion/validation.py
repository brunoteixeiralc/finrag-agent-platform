"""Pure validation for untrusted document inputs."""

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Mapping
from datetime import date
from json import JSONDecodeError
from pathlib import PurePosixPath
from types import MappingProxyType
from urllib.parse import urlsplit

from app.ingestion.errors import DocumentValidationError, IngestionErrorCode
from app.ingestion.models import (
    MetadataValue,
    ReceivedDocumentFile,
    SupportedMimeType,
    ValidatedDocumentInput,
)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
MAX_FILENAME_CHARACTERS = 255
MAX_TITLE_CHARACTERS = 200
MAX_SOURCE_NAME_CHARACTERS = 200
MAX_METADATA_BYTES = 4 * 1024
MAX_METADATA_KEYS = 20
MAX_METADATA_LIST_ITEMS = 20

SUPPORTED_EXTENSIONS = {
    ".md": SupportedMimeType.MARKDOWN,
    ".txt": SupportedMimeType.PLAIN_TEXT,
    ".pdf": SupportedMimeType.PDF,
}

RESERVED_METADATA_KEYS = frozenset(
    {
        "character_count",
        "chunks_count",
        "created_at",
        "embedding",
        "embedding_dimensions",
        "embedding_model",
        "id",
        "mime_type",
        "original_filename",
        "page_count",
        "published_at",
        "sha256",
        "source",
        "source_name",
        "source_url",
        "status",
        "title",
    }
)

ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_document_input(
    file: ReceivedDocumentFile,
    *,
    title: str | None = None,
    source_name: str | None = None,
    source_url: str | None = None,
    published_at: str | date | None = None,
    metadata: str | Mapping[str, object] | None = None,
) -> ValidatedDocumentInput:
    """Validate one untrusted file and its optional multipart fields without I/O."""

    original_filename = _normalize_filename(file.filename)
    mime_type = _validate_file_type(original_filename, file.mime_type, file.content)
    validated_metadata = _validate_metadata(metadata)

    return ValidatedDocumentInput(
        original_filename=original_filename,
        mime_type=mime_type,
        content=file.content,
        sha256=hashlib.sha256(file.content).hexdigest(),
        title=_validate_optional_text(
            title,
            field="title",
            maximum=MAX_TITLE_CHARACTERS,
            code=IngestionErrorCode.INVALID_TITLE,
        ),
        source_name=_validate_optional_text(
            source_name,
            field="source_name",
            maximum=MAX_SOURCE_NAME_CHARACTERS,
            code=IngestionErrorCode.INVALID_SOURCE_NAME,
        ),
        source_url=_validate_source_url(source_url),
        published_at=_validate_published_at(published_at),
        metadata=MappingProxyType(validated_metadata),
    )


def _normalize_filename(filename: str) -> str:
    if not isinstance(filename, str):
        _fail(IngestionErrorCode.INVALID_FILENAME, "A valid filename is required.", "file")

    normalized = unicodedata.normalize("NFKC", filename).replace("\\", "/")
    basename = normalized.rsplit("/", maxsplit=1)[-1].strip()
    display_name = "".join(
        "_" if unicodedata.category(character) in {"Cc", "Cf"} else character
        for character in basename
    )

    if display_name in {"", ".", ".."} or len(display_name) > MAX_FILENAME_CHARACTERS:
        _fail(IngestionErrorCode.INVALID_FILENAME, "A valid filename is required.", "file")

    return display_name


def _validate_file_type(
    filename: str,
    declared_mime_type: str,
    content: bytes,
) -> SupportedMimeType:
    if not isinstance(content, bytes):
        _fail(IngestionErrorCode.UNSAFE_FILE_CONTENT, "The file content is invalid.", "file")
    if not content:
        _fail(IngestionErrorCode.EMPTY_FILE, "The file is empty.", "file")
    if len(content) > MAX_FILE_SIZE_BYTES:
        _fail(
            IngestionErrorCode.FILE_TOO_LARGE,
            "The file exceeds the 5 MiB limit.",
            "file",
        )

    extension = PurePosixPath(filename).suffix.lower()
    expected_mime_type = SUPPORTED_EXTENSIONS.get(extension)
    if expected_mime_type is None:
        _fail(
            IngestionErrorCode.UNSUPPORTED_FILE_EXTENSION,
            "The file extension is not supported.",
            "file",
        )

    if not isinstance(declared_mime_type, str):
        _fail(
            IngestionErrorCode.UNSUPPORTED_MIME_TYPE,
            "The declared MIME type is not supported.",
            "file",
        )
    normalized_mime_type = declared_mime_type.partition(";")[0].strip().lower()
    try:
        mime_type = SupportedMimeType(normalized_mime_type)
    except ValueError:
        _fail(
            IngestionErrorCode.UNSUPPORTED_MIME_TYPE,
            "The declared MIME type is not supported.",
            "file",
        )

    if mime_type is not expected_mime_type:
        _fail(
            IngestionErrorCode.FILE_TYPE_MISMATCH,
            "The filename, MIME type, and content are incompatible.",
            "file",
        )

    if mime_type is SupportedMimeType.PDF:
        if not content.startswith(b"%PDF-"):
            _fail(
                IngestionErrorCode.FILE_TYPE_MISMATCH,
                "The filename, MIME type, and content are incompatible.",
                "file",
            )
    elif b"\x00" in content:
        _fail(
            IngestionErrorCode.UNSAFE_FILE_CONTENT,
            "Text files cannot contain NUL bytes.",
            "file",
        )

    return mime_type


def _validate_optional_text(
    value: str | None,
    *,
    field: str,
    maximum: int,
    code: IngestionErrorCode,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(code, f"The {field} field is invalid.", field)

    normalized = unicodedata.normalize("NFKC", value).strip()
    has_control_character = any(
        unicodedata.category(character) in {"Cc", "Cf"} for character in normalized
    )
    if not normalized or len(normalized) > maximum or has_control_character:
        _fail(code, f"The {field} field is invalid.", field)
    return normalized


def _validate_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(
            IngestionErrorCode.INVALID_SOURCE_URL,
            "The source_url field must be an HTTP or HTTPS URL.",
            "source_url",
        )

    normalized = value.strip()
    if any(unicodedata.category(character) == "Cc" for character in normalized):
        _fail(
            IngestionErrorCode.INVALID_SOURCE_URL,
            "The source_url field must be an HTTP or HTTPS URL.",
            "source_url",
        )

    try:
        parsed = urlsplit(normalized)
        _ = parsed.port
    except ValueError:
        parsed = None

    if parsed is None or parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        _fail(
            IngestionErrorCode.INVALID_SOURCE_URL,
            "The source_url field must be an HTTP or HTTPS URL.",
            "source_url",
        )
    return normalized


def _validate_published_at(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    if not isinstance(value, str) or ISO_DATE_PATTERN.fullmatch(value) is None:
        _fail(
            IngestionErrorCode.INVALID_PUBLISHED_AT,
            "The published_at field must use YYYY-MM-DD.",
            "published_at",
        )
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(
            IngestionErrorCode.INVALID_PUBLISHED_AT,
            "The published_at field must use YYYY-MM-DD.",
            "published_at",
        )


def _validate_metadata(
    value: str | Mapping[str, object] | None,
) -> dict[str, MetadataValue]:
    if value is None:
        return {}

    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_METADATA_BYTES:
            _fail_metadata_too_large()
        try:
            parsed = json.loads(value, object_pairs_hook=_metadata_object)
        except JSONDecodeError:
            _fail(
                IngestionErrorCode.INVALID_METADATA,
                "The metadata field must contain a JSON object.",
                "metadata",
            )
    else:
        parsed = value

    if not isinstance(parsed, Mapping):
        _fail(
            IngestionErrorCode.INVALID_METADATA,
            "The metadata field must contain a JSON object.",
            "metadata",
        )
    if len(parsed) > MAX_METADATA_KEYS:
        _fail(
            IngestionErrorCode.METADATA_TOO_MANY_KEYS,
            "Metadata cannot contain more than 20 keys.",
            "metadata",
        )

    validated: dict[str, MetadataValue] = {}
    for key, metadata_value in parsed.items():
        if (
            not isinstance(key, str)
            or not key.strip()
            or any(unicodedata.category(character) in {"Cc", "Cf"} for character in key)
        ):
            _fail(
                IngestionErrorCode.INVALID_METADATA,
                "Metadata keys must be non-empty strings.",
                "metadata",
            )
        normalized_key = key.strip()
        if normalized_key.lower() in RESERVED_METADATA_KEYS:
            _fail(
                IngestionErrorCode.METADATA_RESERVED_KEY,
                "Metadata cannot override a reserved field.",
                "metadata",
            )
        if normalized_key in validated:
            _fail(
                IngestionErrorCode.INVALID_METADATA,
                "Metadata keys must be unique after normalization.",
                "metadata",
            )
        validated[normalized_key] = _validate_metadata_value(metadata_value)

    encoded = json.dumps(
        validated,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_METADATA_BYTES:
        _fail_metadata_too_large()
    return validated


def _validate_metadata_value(value: object) -> MetadataValue:
    if _is_metadata_primitive(value):
        return value
    if isinstance(value, list):
        if len(value) > MAX_METADATA_LIST_ITEMS:
            _fail(
                IngestionErrorCode.INVALID_METADATA,
                "Metadata lists cannot contain more than 20 primitive values.",
                "metadata",
            )
        if not all(_is_metadata_primitive(item) for item in value):
            _fail(
                IngestionErrorCode.INVALID_METADATA,
                "Metadata values must be primitive values or short primitive lists.",
                "metadata",
            )
        return tuple(value)

    _fail(
        IngestionErrorCode.INVALID_METADATA,
        "Metadata values must be primitive values or short primitive lists.",
        "metadata",
    )


def _metadata_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(
                IngestionErrorCode.INVALID_METADATA,
                "Metadata keys must be unique after normalization.",
                "metadata",
            )
        result[key] = value
    return result


def _is_metadata_primitive(value: object) -> bool:
    if value is None or isinstance(value, str | bool | int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _fail_metadata_too_large() -> None:
    _fail(
        IngestionErrorCode.METADATA_TOO_LARGE,
        "Metadata exceeds the 4 KiB limit.",
        "metadata",
    )


def _fail(code: IngestionErrorCode, message: str, field: str) -> None:
    raise DocumentValidationError(code, message, field=field)
