"""CSV cell guard for exports: a spreadsheet app must never execute an exported cell."""

FORMULA_PREFIXES = ("=", "+", "-", "@")


def cell(value) -> str:
    """A cell value with a leading apostrophe when it could be read as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in FORMULA_PREFIXES else text
