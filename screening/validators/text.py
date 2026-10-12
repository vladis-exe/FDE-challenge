import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation: "Gràcia, BCN!" -> "gracia bcn"."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _NON_ALNUM.sub(" ", without_accents).strip()
