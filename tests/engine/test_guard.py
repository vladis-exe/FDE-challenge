import pytest

from screening.config import MessageLimits, load_config
from screening.guard import check_reply, not_names, strip_label, trim_reply, wrong_vocative

LIMITS = MessageLimits()
NOT_NAMES = not_names(load_config())


@pytest.mark.parametrize(
    "text",
    [
        "¡Genial, Laura! ¿En qué ciudad y barrio vives?",  # the spec's own example
        "Perfecto, anotado. ¿Buscas jornada completa, media jornada o fines de semana?",
        "¿Tienes carnet de conducir en vigor? 🚗",  # emoji after the question is fine
    ],
)
def test_good_replies_pass(text):
    assert check_reply(text, asks=True, limits=LIMITS, name="Laura") == []


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


# E18: never address the candidate by a name they haven't given


@pytest.mark.parametrize(
    "text, name",
    [
        ("Genial, Simón. ¿Me dices tu nombre y apellido?", None),  # evals' V8 run
        ("Gracias, Pedro. ¿En qué ciudad vives?", "Laura"),
    ],
)
def test_a_vocative_name_that_isnt_theirs_is_a_problem(text, name):
    assert "addresses them by a name they haven't given" in check_reply(
        text, asks=True, limits=LIMITS, name=name
    )


@pytest.mark.parametrize(
    "text, name",
    [
        ("Genial, Laura. ¿En qué ciudad vives?", "Laura"),
        ("genial, laura. ¿En qué ciudad vives?", "Laura"),
        ("Perfecto, anotado. ¿En qué ciudad vives?", None),  # not a name
        ("Hola, soy Alex. ¿Empezamos?", None),
    ],
)
def test_their_own_name_or_no_name_is_fine(text, name):
    assert check_reply(text, asks=True, limits=LIMITS, name=name) == []


def test_trim_drops_a_wrong_vocative():
    trimmed = trim_reply(
        "Genial, Simón. ¿Me dices tu nombre y apellido?", asks=True, limits=LIMITS, name=None
    )
    assert trimmed == "Genial. ¿Me dices tu nombre y apellido?"


# Lead review of E18: a capitalized word after a comma is usually a place or platform


@pytest.mark.parametrize(
    "text",
    [
        "Perfecto, Madrid es una de nuestras ciudades. ¿Tienes carnet?",
        "Genial, Glovo cuenta como experiencia. ¿Cuántos años?",
        "Great, Barcelona works for us. Do you have a license?",
        "Entendido, Monterrey. ¿Desde cuándo podrías empezar?",
    ],
)
def test_places_and_platforms_are_not_vocatives(text):
    assert wrong_vocative(text, "Laura", not_names=NOT_NAMES) is None
    assert check_reply(text, asks=True, limits=LIMITS, name="Laura", not_names=NOT_NAMES) == []


# E20 (1): a meta label from a retry must never reach the candidate


@pytest.mark.parametrize(
    "text",
    [
        "Corrected: Anotado, el lunes 19 de octubre. ¿Tienes licencia de manejo?",
        "Revised: Anotado, el lunes 19 de octubre. ¿Tienes licencia de manejo?",
        "Mensaje: Anotado, el lunes 19 de octubre. ¿Tienes licencia de manejo?",
        "Mensaje corregido: Anotado, el lunes 19 de octubre. ¿Tienes licencia de manejo?",
        "Here is the corrected message: Anotado, el lunes 19 de octubre. "
        "¿Tienes licencia de manejo?",
        "Aquí tienes el mensaje: Anotado, el lunes 19 de octubre. ¿Tienes licencia de manejo?",
        '"Anotado, el lunes 19 de octubre. ¿Tienes licencia de manejo?"',
    ],
)
def test_a_leading_meta_label_or_quotes_are_stripped(text):
    assert strip_label(text) == "Anotado, el lunes 19 de octubre. ¿Tienes licencia de manejo?"


@pytest.mark.parametrize(
    "text",
    [
        "Anotado: el lunes 19 de octubre. ¿Tienes licencia?",  # not a label
        "Perfecto, Madrid. ¿Tienes carnet?",
    ],
)
def test_ordinary_text_is_untouched(text):
    assert strip_label(text) == text
