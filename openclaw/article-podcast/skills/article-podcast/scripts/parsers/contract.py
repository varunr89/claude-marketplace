"""Parser output contract: all parsers must produce output matching this schema."""

REQUIRED_TOP_KEYS = {"source_type", "title", "metadata", "sections", "total_words"}
REQUIRED_SECTION_KEYS = {"title", "text", "word_count", "index"}


def validate_parser_output(data: dict) -> bool:
    """Validate that parser output conforms to the contract."""
    if not isinstance(data, dict):
        return False
    if not REQUIRED_TOP_KEYS.issubset(data.keys()):
        return False
    sections = data.get("sections")
    if not isinstance(sections, list) or len(sections) == 0:
        return False
    for section in sections:
        if not REQUIRED_SECTION_KEYS.issubset(section.keys()):
            return False
        if not section["text"].strip():
            return False
    return True
