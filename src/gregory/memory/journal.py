"""Journal service - daily Markdown journal files for Gregory's long-term memory."""

import logging
from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path

from gregory.config import get_settings

logger = logging.getLogger(__name__)


class JournalService:
    """Read and write daily journal files (YYYY-MM-DD.md) and compressed monthly files (YYYY-MM.md)."""

    def __init__(self, memory_path: Path | None = None) -> None:
        path = memory_path or get_settings().memory_path
        self._base = Path(path)
        self._base.mkdir(parents=True, exist_ok=True)

    # --- Path helpers ---

    def _daily_path(self, for_date: date) -> Path:
        return self._base / f"{for_date.isoformat()}.md"

    def compressed_path(self, year: int, month: int) -> Path:
        return self._base / f"{year:04d}-{month:02d}.md"

    def today(self) -> date:
        return date.today()

    # --- Daily entry writes ---

    def append_entry(
        self,
        text: str,
        for_date: date | None = None,
        user_id: str = "",
    ) -> tuple[date, str]:
        """Append a timestamped journal entry to the day's file.

        Returns (entry_date, formatted_line) so the caller can immediately index
        the entry without re-reading the file.
        """
        target_date = for_date or self.today()
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%H:%M")
        prefix = f"[{timestamp}]" + (f" [{user_id}]" if user_id else "")
        line = f"- {prefix} {text.strip()}"
        p = self._daily_path(target_date)
        try:
            if not p.exists():
                p.write_text(
                    f"# Journal {target_date.isoformat()}\n\n",
                    encoding="utf-8",
                )
            with p.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            logger.debug("[journal] Appended entry for %s", target_date)
        except OSError as e:
            logger.warning("[journal] Could not write entry for %s: %s", target_date, e)
        return target_date, line

    def write_summary(self, for_date: date, summary: str) -> None:
        """Write or replace the ## Summary section of a daily journal file."""
        p = self._daily_path(for_date)
        try:
            existing = p.read_text(encoding="utf-8") if p.exists() else ""
            # Remove existing summary block
            if "\n## Summary\n" in existing:
                existing = existing[: existing.index("\n## Summary\n")]
            content = existing.rstrip() + f"\n\n## Summary\n{summary.strip()}\n"
            p.write_text(content, encoding="utf-8")
            logger.debug("[journal] Wrote summary for %s", for_date)
        except OSError as e:
            logger.warning("[journal] Could not write summary for %s: %s", for_date, e)

    # --- Reads ---

    def read_date(self, for_date: date) -> str:
        """Read a daily journal file. Returns empty string if missing."""
        p = self._daily_path(for_date)
        if not p.exists():
            return ""
        try:
            return p.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("[journal] Could not read journal for %s: %s", for_date, e)
            return ""

    def read_today(self) -> str:
        return self.read_date(self.today())

    def read_month(self, year: int, month: int) -> str:
        """Concatenate all daily files for a given month, sorted by date."""
        parts: list[str] = []
        _, days_in_month = monthrange(year, month)
        for day in range(1, days_in_month + 1):
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            content = self.read_date(d)
            if content.strip():
                parts.append(content.strip())
        return "\n\n".join(parts)

    # --- Directory scanning ---

    def list_journal_dates(self) -> list[date]:
        """List all dates with daily journal files, sorted ascending."""
        dates: list[date] = []
        for f in self._base.iterdir():
            if not (f.is_file() and f.suffix == ".md"):
                continue
            # Daily file: exactly YYYY-MM-DD (10 chars)
            if len(f.stem) == 10:
                try:
                    dates.append(date.fromisoformat(f.stem))
                except ValueError:
                    pass
        return sorted(dates)

    def list_months_with_daily_files(self) -> list[tuple[int, int]]:
        """Return (year, month) pairs for complete past months that have daily files.

        A month is 'complete' if it is not the current month.
        """
        today = self.today()
        seen: set[tuple[int, int]] = set()
        for d in self.list_journal_dates():
            ym = (d.year, d.month)
            # Skip current month — still accumulating entries
            if ym == (today.year, today.month):
                continue
            seen.add(ym)
        return sorted(seen)

    # --- Monthly compression ---

    def write_compressed(self, year: int, month: int, content: str) -> None:
        """Write the compressed YYYY-MM.md file."""
        p = self.compressed_path(year, month)
        try:
            p.write_text(content.strip() + "\n", encoding="utf-8")
            logger.info("[journal] Wrote compressed file %s", p.name)
        except OSError as e:
            logger.warning("[journal] Could not write compressed file %s: %s", p.name, e)

    def delete_daily_files_for_month(self, year: int, month: int) -> list[str]:
        """Delete all YYYY-MM-DD.md files for the given month. Returns list of deleted filenames."""
        _, days_in_month = monthrange(year, month)
        deleted: list[str] = []
        for day in range(1, days_in_month + 1):
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            p = self._daily_path(d)
            if p.exists():
                try:
                    p.unlink()
                    deleted.append(p.name)
                    logger.debug("[journal] Deleted daily file %s", p.name)
                except OSError as e:
                    logger.warning("[journal] Could not delete %s: %s", p.name, e)
        if deleted:
            logger.info("[journal] Deleted %d daily files for %04d-%02d", len(deleted), year, month)
        return deleted
