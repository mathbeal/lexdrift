from __future__ import annotations

from lexdrift.collector import collect_source
from lexdrift.rules import measure


def findings_for(source: object) -> None:
    modules = [collect_source(source, module="app.mod")]
    return measure(modules, project_roots={"app"})


def rules_fired(source: object) -> None:
    return {f.rule for f in findings_for(source)}


def test_L001_reports_two_verbs_of_the_same_family() -> None:
    source = "def get_user():\n    pass\n\ndef fetch_account():\n    pass\n"
    finding = next(f for f in findings_for(source) if f.rule == "L001")
    assert "fetch" in finding.message
    assert "get" in finding.message


def test_L001_silent_when_a_single_verb_of_the_family_is_used() -> None:
    source = "def get_user():\n    pass\n\ndef get_account():\n    pass\n"
    assert "L001" not in rules_fired(source)


def test_L002_reports_a_function_whose_name_has_no_verb() -> None:
    source = "def user_data():\n    pass\n"
    assert "L002" in rules_fired(source)


def test_L002_silent_on_a_verb_led_name() -> None:
    source = "def build_report():\n    pass\n"
    assert "L002" not in rules_fired(source)


def test_L003_reports_a_docstring_verb_of_another_family() -> None:
    source = 'def save_config():\n    """Supprime la configuration."""\n'
    assert "L003" in rules_fired(source)


def test_L003_silent_when_docstring_agrees_with_the_name() -> None:
    source = 'def save_config():\n    """Enregistre la configuration."""\n'
    assert "L003" not in rules_fired(source)


def test_L004_reports_an_abbreviation_of_a_word_used_elsewhere() -> None:
    source = "def read_usr_file():\n    pass\n\ndef read_user_name():\n    pass\n"
    finding = next(f for f in findings_for(source) if f.rule == "L004")
    assert "usr" in finding.message
    assert "user" in finding.message


def test_L005_reports_one_verb_covering_disjoint_worlds() -> None:
    source = (
        "import requests\n"
        "import numpy\n"
        "def process_payment():\n"
        "    return requests.post()\n"
        "def process_image():\n"
        "    return numpy.array()\n"
    )
    assert "L005" in rules_fired(source)


def test_L005_silent_when_the_verb_stays_in_one_world() -> None:
    source = (
        "import requests\n"
        "def process_payment():\n"
        "    return requests.post()\n"
        "def process_refund():\n"
        "    return requests.post()\n"
    )
    assert "L005" not in rules_fired(source)


def test_findings_carry_a_location() -> None:
    source = "def user_data():\n    pass\n"
    finding = findings_for(source)[0]
    assert finding.module == "app.mod"
    assert finding.lineno == 1


def test_a_verb_belongs_to_exactly_one_family() -> None:
    from lexdrift.rules import load_families

    seen = {}
    for family, verbs in load_families().items():
        for verb in verbs:
            assert verb not in seen, f"« {verb} » est dans {seen.get(verb)} et {family}"
            seen[verb] = family
