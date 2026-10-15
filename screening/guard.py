"""The message rules from the spec, checked in code on every composed reply.

At most 2 sentences and ~300 characters, exactly one question and it comes last
(none when the plan asks nothing), at most one emoji, plain text, and never
addressing the candidate by a name they haven't given (E18). The prompt asks
for all of this; the guard makes sure of it: a reply that breaks a rule is
regenerated once, and if it still breaks one, trimmed by `trim_reply`.
"""

import re

from screening.config import MessageLimits, ScreeningConfig
from screening.messages import PLATFORM_LABELS
from screening.validators.text import normalize

# A sentence ends at . ! ? or … followed by a space or the end. Spanish opening
# marks (¡ ¿) start a sentence, so "¡Genial, Laura! ¿Dónde vives?" is two.
_SENTENCE = re.compile(r"[^.!?…]*[.!?…]+(?:\s+|$)|[^.!?…]+$")
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⭐⭕]️?")
_FORMATTING = re.compile(r"\n|\*\*|__|^\s*[-•#]\s", re.M)


def sentences(text: str) -> list[str]:
    # Emoji are not words; they don't make a sentence of their own.
    parts = [part.strip() for part in _SENTENCE.findall(text)]
    return [part for part in parts if _EMOJI.sub("", part).strip()]


# An opener that addresses someone: "Genial, Simón." / "Thanks, Tom!" -> the name.
# The word must end the clause: "Perfecto, Madrid es una de nuestras ciudades" is a
# sentence about a city, not someone being addressed.
_VOCATIVE = re.compile(r"^\W*\w+(?: \w+)?, ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)(?=[.!,?])")
ALEX = "Alex"


def not_names(config: ScreeningConfig) -> frozenset[str]:
    """Capitalized words Alex says that aren't anyone's name: places and platforms.

    Acknowledging them is exactly what the location and experience steps do
    ("Entendido, Monterrey."), so they must never count as addressing someone.
    """
    words = {normalize(label) for label in PLATFORM_LABELS.values()} | {normalize(ALEX)}
    for area in config.service_areas.values():
        for city in area.cities:
            for term in [city.key, city.name, *city.aliases, *city.neighborhoods, *city.regions]:
                words.add(normalize(term))
    return frozenset(words)


def wrong_vocative(
    text: str, name: str | None, *, not_names: frozenset[str] = frozenset()
) -> str | None:
    """The name a reply opens by addressing, if it isn't the candidate's accepted one."""
    match = _VOCATIVE.match(text)
    if not match:
        return None
    word = match.group(1)
    if normalize(word) in not_names or word == ALEX:
        return None
    if name and word.casefold() == name.casefold():
        return None
    return word


# A model answering the retry feedback may preface the message: "Corrected:",
# "Mensaje corregido:", "Here is the corrected message:". Never meant for the candidate.
_LABEL = re.compile(
    r"""^\s*(?:corrected|revised|rewritten|fixed|updated|correction|corregido|corregida
    |corrección|revisado|versión\ corregida|mensaje(?:\ corregido)?|message|respuesta|reply
    |here(?:'s|\ is)[^:\n]{0,40}|aquí\ (?:tienes|está)[^:\n]{0,40})\s*:\s*""",
    re.IGNORECASE | re.VERBOSE,
)


def strip_label(text: str) -> str:
    """Drop a leading meta label and wrapping quotes; leave ordinary text untouched."""
    text = _LABEL.sub("", text, count=1).strip()
    if len(text) > 1 and text[0] in '"“' and text[-1] in '"”':
        text = text[1:-1].strip()
    return text


def check_reply(
    text: str,
    *,
    asks: bool,
    limits: MessageLimits,
    name: str | None = None,
    not_names: frozenset[str] = frozenset(),
) -> list[str]:
    """The rules `text` breaks, in plain words (empty when it's fine)."""
    problems: list[str] = []
    if len(text) > limits.max_chars:
        problems.append(f"over {limits.max_chars} characters")
    if len(sentences(text)) > limits.max_sentences:
        problems.append(f"more than {limits.max_sentences} sentences")
    questions = text.count("?")
    if asks:
        if questions == 0:
            problems.append("no question")
        elif questions > limits.max_questions:
            problems.append("more than one question")
        elif _EMOJI.sub("", text).rstrip()[-1:] != "?":
            problems.append("text after the question")
    elif questions:
        problems.append("has a question")
    if len(_EMOJI.findall(text)) > limits.max_emojis:
        problems.append("more than one emoji")
    if _FORMATTING.search(text):
        problems.append("formatting")
    if wrong_vocative(text, name, not_names=not_names):
        problems.append("addresses them by a name they haven't given")
    return problems


def trim_reply(
    text: str,
    *,
    asks: bool,
    limits: MessageLimits,
    name: str | None = None,
    not_names: frozenset[str] = frozenset(),
) -> str:
    """Cut a reply down to the rules without rewriting it. Deterministic."""
    wrong = wrong_vocative(text, name, not_names=not_names)
    if wrong:
        text = text.replace(f", {wrong}", "", 1)  # "Genial, Simón." -> "Genial."
    text = _FORMATTING.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    emoji = _EMOJI.findall(text)
    for extra in emoji[limits.max_emojis :]:
        text = _reverse_replace_once(text, extra)

    parts = sentences(text)
    if asks:
        last_question = max((i for i, part in enumerate(parts) if "?" in part), default=None)
        if last_question is not None:
            kept = [part for part in parts[:last_question] if "?" not in part]
            parts = kept + [parts[last_question]]
    else:
        parts = [part for part in parts if "?" not in part] or parts

    parts = parts[-limits.max_sentences :]
    while len(parts) > 1 and len(" ".join(parts)) > limits.max_chars:
        parts = parts[1:]  # the question is last; drop from the front
    return " ".join(parts)


def _reverse_replace_once(text: str, emoji: str) -> str:
    index = text.rfind(emoji)
    return (text[:index] + text[index + len(emoji) :]).replace("  ", " ").strip()
