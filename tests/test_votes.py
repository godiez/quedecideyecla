from actas import votes


def test_split_group_stance_is_not_made_up():
    assert votes.stance({"favor": 1, "contra": 1, "abstencion": 0}) == "dividido"
    assert votes.stance({"favor": 2, "contra": 1, "abstencion": 0}) == "favor"
    assert votes.stance({"favor": 0, "contra": 0, "abstencion": 0}) is None


def test_split_group_does_not_count_as_agreement():
    v = {"final": True, "unanimidad": False,
         "votos": {"PP": {"favor": 1, "contra": 1}, "PSOE": {"favor": 1, "contra": 1}}}
    assert votes.agreements([v])[("PP", "PSOE")] == (0, 0)


def test_legislature_by_groups_then_date():
    from datetime import date
    old = {"PP": {}, "PSOE": {}, "Cs": {}, "IU-Verdes": {}}
    new = {"PP": {}, "PSOE": {}, "Vox": {}, "IU-Verdes": {}}
    # Two plenary sessions on 17-06-2023: the outgoing and the incoming councils.
    assert votes.legislature_of(old, date(2023, 6, 17)) == "2019-2023"
    assert votes.legislature_of(new, date(2023, 6, 17)) == "2023-2027"
    assert votes.legislature_of({"PP": {}}, date(2022, 3, 1)) == "2019-2023"
    assert votes.legislature_of({}, date(2024, 3, 1)) == "2023-2027"


def test_legislature_of_year_is_the_one_in_force_at_year_end():
    assert votes.legislature_of_year(2021) == "2019-2023"
    assert votes.legislature_of_year(2023) == "2023-2027"
    assert votes.legislature_of_year(2026) == "2023-2027"


def test_agreements_use_the_groups_of_the_legislature():
    v = {"final": True, "unanimidad": False,
         "votos": {"PP": {"favor": 12}, "PSOE": {"contra": 5}, "Cs": {"favor": 2}, "IU-Verdes": {"contra": 2}}}
    a = votes.agreements([v], votes.LEGISLATURES["2019-2023"])
    assert a[("PP", "Cs")] == (1, 1) and a[("PSOE", "IU-Verdes")] == (1, 1) and ("PP", "Vox") not in a
