"""Tests for JournalService (memory/journal.py)."""

from datetime import date
from pathlib import Path

import pytest

from gregory.memory.journal import JournalService


@pytest.fixture()
def journal(tmp_path: Path) -> JournalService:
    return JournalService(memory_path=tmp_path)


# ---------------------------------------------------------------------------
# append_entry
# ---------------------------------------------------------------------------

def test_append_entry_creates_file(journal: JournalService, tmp_path: Path):
    today = journal.today()
    journal.append_entry("test entry")
    assert (tmp_path / f"{today.isoformat()}.md").exists()


def test_append_entry_returns_date_and_line(journal: JournalService):
    today = journal.today()
    entry_date, line = journal.append_entry("something happened")
    assert entry_date == today
    assert "something happened" in line
    assert line.startswith("- [")


def test_append_entry_writes_header_on_new_file(journal: JournalService, tmp_path: Path):
    today = journal.today()
    journal.append_entry("first entry")
    content = (tmp_path / f"{today.isoformat()}.md").read_text()
    assert f"# Journal {today.isoformat()}" in content


def test_append_entry_includes_timestamp(journal: JournalService, tmp_path: Path):
    today = journal.today()
    journal.append_entry("timestamped entry")
    content = (tmp_path / f"{today.isoformat()}.md").read_text()
    # Expect [HH:MM] pattern
    import re
    assert re.search(r"\[\d{2}:\d{2}\]", content)


def test_append_entry_includes_user_id(journal: JournalService, tmp_path: Path):
    today = journal.today()
    journal.append_entry("user note", user_id="alice")
    content = (tmp_path / f"{today.isoformat()}.md").read_text()
    assert "[alice]" in content


def test_append_entry_omits_user_id_when_empty(journal: JournalService, tmp_path: Path):
    today = journal.today()
    journal.append_entry("anonymous note", user_id="")
    content = (tmp_path / f"{today.isoformat()}.md").read_text()
    # Should not have an empty bracket
    assert "[]" not in content


def test_append_entry_appends_to_existing(journal: JournalService, tmp_path: Path):
    today = journal.today()
    journal.append_entry("first entry")
    journal.append_entry("second entry")
    content = (tmp_path / f"{today.isoformat()}.md").read_text()
    assert "first entry" in content
    assert "second entry" in content


def test_append_entry_strips_whitespace(journal: JournalService):
    _, line = journal.append_entry("  padded entry  ")
    assert "padded entry" in line
    assert "  padded entry  " not in line


def test_append_entry_specific_date(journal: JournalService, tmp_path: Path):
    target = date(2024, 1, 15)
    journal.append_entry("past entry", for_date=target)
    assert (tmp_path / "2024-01-15.md").exists()


# ---------------------------------------------------------------------------
# read_date / read_today
# ---------------------------------------------------------------------------

def test_read_date_returns_empty_for_missing_file(journal: JournalService):
    result = journal.read_date(date(2020, 1, 1))
    assert result == ""


def test_read_date_returns_content(journal: JournalService):
    d = date(2024, 3, 10)
    journal.append_entry("hello world", for_date=d)
    content = journal.read_date(d)
    assert "hello world" in content


def test_read_today_returns_todays_content(journal: JournalService):
    journal.append_entry("today's event")
    content = journal.read_today()
    assert "today's event" in content


# ---------------------------------------------------------------------------
# write_summary
# ---------------------------------------------------------------------------

def test_write_summary_adds_section(journal: JournalService, tmp_path: Path):
    d = journal.today()
    journal.append_entry("some entry")
    journal.write_summary(d, "Today was productive.")
    content = journal.read_date(d)
    assert "## Summary" in content
    assert "Today was productive." in content


def test_write_summary_replaces_existing_summary(journal: JournalService):
    d = journal.today()
    journal.append_entry("entry")
    journal.write_summary(d, "First summary.")
    journal.write_summary(d, "Updated summary.")
    content = journal.read_date(d)
    assert "Updated summary." in content
    assert "First summary." not in content
    # Should only have one ## Summary header
    assert content.count("## Summary") == 1


def test_write_summary_creates_file_if_not_exists(journal: JournalService, tmp_path: Path):
    d = date(2024, 5, 5)
    journal.write_summary(d, "Standalone summary.")
    # File doesn't need to exist beforehand
    content = journal.read_date(d)
    assert "Standalone summary." in content


# ---------------------------------------------------------------------------
# list_journal_dates
# ---------------------------------------------------------------------------

def test_list_journal_dates_sorted(journal: JournalService):
    dates = [date(2024, 1, 3), date(2024, 1, 1), date(2024, 1, 2)]
    for d in dates:
        journal.append_entry("entry", for_date=d)
    result = journal.list_journal_dates()
    assert result == sorted(dates)


def test_list_journal_dates_excludes_monthly_files(journal: JournalService, tmp_path: Path):
    journal.append_entry("daily entry")
    # Manually create a monthly file
    (tmp_path / "2024-01.md").write_text("monthly content")
    dates = journal.list_journal_dates()
    # Monthly files (YYYY-MM, 7 chars) should not appear in daily dates
    for d in dates:
        assert len(d.isoformat()) == 10  # YYYY-MM-DD


def test_list_journal_dates_empty_directory(journal: JournalService):
    result = journal.list_journal_dates()
    assert result == []


# ---------------------------------------------------------------------------
# list_months_with_daily_files
# ---------------------------------------------------------------------------

def test_list_months_excludes_current_month(journal: JournalService):
    journal.append_entry("today")
    months = journal.list_months_with_daily_files()
    today = journal.today()
    assert (today.year, today.month) not in months


def test_list_months_includes_past_months(journal: JournalService):
    d = date(2023, 11, 15)
    journal.append_entry("past entry", for_date=d)
    months = journal.list_months_with_daily_files()
    assert (2023, 11) in months


def test_list_months_sorted(journal: JournalService):
    for d in [date(2023, 3, 1), date(2023, 1, 1), date(2023, 2, 1)]:
        journal.append_entry("entry", for_date=d)
    months = journal.list_months_with_daily_files()
    assert months == sorted(months)


# ---------------------------------------------------------------------------
# read_month
# ---------------------------------------------------------------------------

def test_read_month_concatenates_daily_files(journal: JournalService):
    journal.append_entry("day 1", for_date=date(2024, 2, 1))
    journal.append_entry("day 2", for_date=date(2024, 2, 15))
    content = journal.read_month(2024, 2)
    assert "day 1" in content
    assert "day 2" in content


def test_read_month_empty_when_no_files(journal: JournalService):
    content = journal.read_month(2020, 6)
    assert content == ""


# ---------------------------------------------------------------------------
# write_compressed / compressed_path / delete_daily_files_for_month
# ---------------------------------------------------------------------------

def test_compressed_path(journal: JournalService, tmp_path: Path):
    p = journal.compressed_path(2024, 2)
    assert p == tmp_path / "2024-02.md"


def test_write_compressed_creates_file(journal: JournalService, tmp_path: Path):
    journal.write_compressed(2024, 2, "# Feb 2024\n\nCompressed content.")
    assert (tmp_path / "2024-02.md").exists()
    content = (tmp_path / "2024-02.md").read_text()
    assert "Compressed content." in content


def test_delete_daily_files_for_month(journal: JournalService, tmp_path: Path):
    for day in [1, 5, 15]:
        journal.append_entry("entry", for_date=date(2024, 2, day))
    deleted = journal.delete_daily_files_for_month(2024, 2)
    assert len(deleted) == 3
    for day in [1, 5, 15]:
        assert not (tmp_path / f"2024-02-{day:02d}.md").exists()


def test_delete_daily_files_ignores_missing(journal: JournalService):
    # Should not raise even if no files exist for the month
    deleted = journal.delete_daily_files_for_month(2020, 1)
    assert deleted == []


def test_delete_daily_files_preserves_other_months(journal: JournalService, tmp_path: Path):
    journal.append_entry("feb entry", for_date=date(2024, 2, 1))
    journal.append_entry("mar entry", for_date=date(2024, 3, 1))
    journal.delete_daily_files_for_month(2024, 2)
    assert not (tmp_path / "2024-02-01.md").exists()
    assert (tmp_path / "2024-03-01.md").exists()
