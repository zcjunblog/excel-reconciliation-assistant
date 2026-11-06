"""Only explicitly requested text normalization; never coerces identifiers."""
import unicodedata


def normalize_text(value: str, operations: list[str]) -> str:
    for operation in operations:
        if operation=='trim': value=value.strip()
        elif operation=='casefold': value=value.casefold()
        elif operation=='nfkc': value=unicodedata.normalize('NFKC',value)
        else: raise ValueError('不支持的规范化规则')
    return value
