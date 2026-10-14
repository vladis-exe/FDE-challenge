import pytest

from screening.cli import main

HAPPY_PATH = """
# consent, name, license, city, availability, schedule, experience, start date, confirm
sí
Laura Pérez
sí
Gràcia
media jornada y fines de semana
tardes
glovo 1,5
ya
sí
"""


def test_fake_script_runs_a_full_screening(tmp_path, capsys):
    script = tmp_path / "happy.txt"
    script.write_text(HAPPY_PATH, encoding="utf-8")

    assert main(["--fake", "--script", str(script)]) == 0

    output = capsys.readouterr().out
    assert "(IA)" in output  # the opening
    assert "Repasemos: Laura Pérez" in output  # the read-back
    assert "Final status: qualified" in output
    assert "profile.fields.location.value.city: None -> 'barcelona'" in output  # state diff
    assert '"summary": "[fake summary]"' in output  # the final record


def test_fake_script_stops_at_a_knockout(tmp_path, capsys):
    script = tmp_path / "no_license.txt"
    script.write_text("sí\nPedro Gómez\nno\nthis line is never sent\n", encoding="utf-8")

    main(["--fake", "--country", "MX", "--script", str(script)])

    output = capsys.readouterr().out
    assert "licencia de manejo" in output
    assert "Final status: disqualified (no_license)" in output
    assert "this line is never sent" not in output


def test_kitchen_prep_qualifies_without_a_license(tmp_path, capsys):
    script = tmp_path / "kitchen.txt"
    # consent, name, city, availability, schedule, start, license: no, certificate: yes, confirm
    script.write_text("sí\nAna Ruiz\nMalasaña\njornada completa\nmañanas\nya\nno\nsí\nsí\n")

    main(["--fake", "--vacancy", "kitchen_prep", "--script", str(script)])

    output = capsys.readouterr().out
    assert "puesto de ayudante de cocina" in output
    assert "carnet de conducir: no" in output  # read back, not a knockout
    assert "Final status: qualified" in output
    assert '"preference_score": 1.0' in output  # the certificate's weight; no license scores 0


def test_unknown_vacancy_is_an_argument_error(capsys):
    with pytest.raises(SystemExit):
        main(["--fake", "--vacancy", "astronaut"])
    assert "driver, kitchen_prep" in capsys.readouterr().err
