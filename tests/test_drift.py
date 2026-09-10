from __future__ import annotations

from lexdrift.collector import collect_source
from lexdrift.drift import compare


def project_of(source: object) -> None:
    class Fake:
        modules = [collect_source(source, module="app.mod")]
        project_roots = {"app"}
        root = "."

    return Fake()


def rules_fired(source: object, baseline: object = None) -> None:
    return {f.rule for f in compare(project_of(source), baseline)}


GET_ONLY = "def get_user():\n    pass\n"
GET_AND_FETCH = "def get_user():\n    pass\n\ndef fetch_account():\n    pass\n"


def baseline_of(source: object) -> None:
    from lexdrift.project import glossary

    return glossary(project_of(source))


def test_without_a_baseline_every_synonym_is_reported() -> None:
    assert "D001" in rules_fired(GET_AND_FETCH)


def test_a_verb_absent_from_the_baseline_is_a_drift() -> None:
    assert "D001" in rules_fired(GET_AND_FETCH, baseline_of(GET_ONLY))


def test_a_verb_already_in_the_baseline_is_accepted() -> None:
    assert "D001" not in rules_fired(GET_AND_FETCH, baseline_of(GET_AND_FETCH))


def test_a_brand_new_family_with_one_verb_is_not_a_drift() -> None:
    source = GET_ONLY + "\ndef save_account():\n    pass\n"
    assert "D001" not in rules_fired(source, baseline_of(GET_ONLY))


def test_the_drift_names_the_new_verb_and_the_established_one() -> None:
    finding = next(
        f
        for f in compare(project_of(GET_AND_FETCH), baseline_of(GET_ONLY))
        if f.rule == "D001"
    )
    assert "fetch" in finding.message
    assert "get" in finding.message


def test_a_new_abbreviation_of_a_used_word_is_a_drift() -> None:
    source = "def read_user():\n    pass\n\ndef read_usr_file():\n    pass\n"
    assert "D002" in rules_fired(source, baseline_of("def read_user():\n    pass\n"))


def test_docstring_disagreement_fails_with_or_without_a_baseline() -> None:
    source = 'def save_config():\n    """Supprime la configuration."""\n'
    assert "D003" in rules_fired(source)
    assert "D003" in rules_fired(source, baseline_of(source))
