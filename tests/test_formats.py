from shorts.formats import FORMATS, formats_for


def test_fiction_formats():
    assert {f.id for f in formats_for("fiction")} == {"trope_hook", "read_this_line", "books_that_feel_like"}


def test_journal_formats():
    assert {f.id for f in formats_for("journal")} == {"prompt_of_the_day", "flip_through"}


def test_devotional():
    assert "word_for_today" in {f.id for f in formats_for("devotional")}


def test_nonfiction():
    assert "idea_in_30" in {f.id for f in formats_for("nonfiction")}


def test_all_targets_under_60():
    assert len(FORMATS) == 7
    for fmt in FORMATS.values():
        assert 20 <= fmt.target_seconds[0] <= fmt.target_seconds[1] <= 45
        assert fmt.beats and fmt.beats[-1] == "cta"
