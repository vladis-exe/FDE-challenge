import pytest

from screening.config import MessageLimits
from screening.guard import check_reply, trim_reply

LIMITS = MessageLimits()


@pytest.mark.parametrize(
    "text",
    [
        "¡Genial, Laura! ¿En qué ciudad y barrio vives?",  # the spec's own example
        "Perfecto, anotado. ¿Buscas jornada completa, media jornada o fines de semana?",
        "¿Tienes carnet de conducir en vigor? 🚗",  # emoji after the question is fine
    ],
)
def test_good_replies_pass(text):
    assert check_reply(text, asks=True, limits=LIMITS) == []


def test_reply_without_an_ask_must_not_ask():
    assert check_reply("El pago depende de la ciudad.", asks=False, limits=LIMITS) == []
    assert check_reply("Depende. ¿Algo más?", asks=False, limits=LIMITS) == ["has a question"]


@pytest.mark.parametrize(
    "text, problem",
    [
        ("¡Genial! Barcelona, perfecto. ¿Qué horario prefieres?", "more than 2 sentences"),
        ("¿Jornada completa o parcial? Puedes combinarlos.", "text after the question"),
        ("Gracias. Ahora dime tu ciudad.", "no question"),
        ("¿Ciudad? ¿Y barrio?", "more than one question"),
        ("¡Genial! 🎉 ¿Cuándo empiezas? 🚀", "more than one emoji"),
        ("Hola.\n¿Cuándo empiezas?", "formatting"),
        ("**Genial**. ¿Cuándo empiezas?", "formatting"),
        ("a" * 300 + ". ¿Vale?", "over 300 characters"),
    ],
)
def test_each_rule_is_checked(text, problem):
    assert problem in check_reply(text, asks=True, limits=LIMITS)


def test_trim_drops_text_after_the_question():
    trimmed = trim_reply(
        "¿Jornada completa o parcial? Puedes combinarlos.", asks=True, limits=LIMITS
    )
    assert trimmed == "¿Jornada completa o parcial?"


def test_trim_keeps_the_question_and_the_sentence_before_it():
    text = "¡Genial, Laura! Gràcia queda en Barcelona. ¿Buscas jornada completa o media?"
    trimmed = trim_reply(text, asks=True, limits=LIMITS)
    assert trimmed == "Gràcia queda en Barcelona. ¿Buscas jornada completa o media?"
    assert check_reply(trimmed, asks=True, limits=LIMITS) == []


def test_trim_removes_formatting_and_extra_emoji():
    trimmed = trim_reply("**¡Genial!** 🎉\n¿Cuándo empiezas? 🚀", asks=True, limits=LIMITS)
    assert trimmed == "¡Genial! 🎉 ¿Cuándo empiezas?"


def test_trim_keeps_a_lead_in_inside_the_question_sentence():
    text = "Gracias, ¿en qué ciudad vives? Y el barrio también."
    assert trim_reply(text, asks=True, limits=LIMITS) == "Gracias, ¿en qué ciudad vives?"


def test_trim_keeps_only_the_last_question():
    trimmed = trim_reply("¿Ciudad? ¿Y en qué barrio vives?", asks=True, limits=LIMITS)
    assert trimmed == "¿Y en qué barrio vives?"


def test_trim_without_an_ask_drops_questions():
    trimmed = trim_reply("El pago depende de la ciudad. ¿Algo más?", asks=False, limits=LIMITS)
    assert trimmed == "El pago depende de la ciudad."


def test_trim_drops_leading_sentences_until_it_fits():
    text = "Primera frase muy larga. " * 15 + "¿Cuándo puedes empezar?"
    trimmed = trim_reply(text, asks=True, limits=LIMITS)
    assert len(trimmed) <= LIMITS.max_chars
    assert trimmed.endswith("¿Cuándo puedes empezar?")
