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
    assert "profile.location.value.city: None -> 'barcelona'" in output  # state diff


def test_fake_script_stops_at_a_knockout(tmp_path, capsys):
    script = tmp_path / "no_license.txt"
    script.write_text("sí\nPedro Gómez\nno\nthis line is never sent\n", encoding="utf-8")

    main(["--fake", "--country", "MX", "--script", str(script)])

    output = capsys.readouterr().out
    assert "licencia de manejo" in output
    assert "Final status: disqualified (no_license)" in output
    assert "this line is never sent" not in output
