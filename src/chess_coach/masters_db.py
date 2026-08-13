from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from chess_coach.logutil import log
from chess_coach.names import normalize_player_name, search_name_variants

HEADER_RE = re.compile(rb'\[(\w+)\s+"((?:\\.|[^"\\])*)"\]')
YEAR_RE = re.compile(r"(?:19|20)\d{2}")


@dataclass
class LocalGameHit:
    row_id: int
    path: Path
    offset: int
    white: str
    black: str
    year: int | None
    event: str
    eco: str
    result: str

    @property
    def gid(self) -> str:
        return f"local-{self.row_id}"


def _surname(name: str) -> str:
    """
    Index key for player surname.

    Gigabase / Scid PGNs use \"Last, First\" — must NOT take the final token
    (that is the given name: \"Carlsen, Magnus\" → magnus).
    """
    text = (name or "").strip()
    if not text:
        return ""
    if "," in text:
        last_part = text.split(",", 1)[0]
        last_part = re.sub(r"\([^)]*\)", " ", last_part)
        last_part = re.sub(r"\b(dr|jr|sr|phd|prof)\.?\b", " ", last_part, flags=re.I)
        parts = normalize_player_name(last_part).split()
        return parts[-1].lower() if parts else last_part.strip().lower()
    cleaned = re.sub(r"\([^)]*\)", " ", text)
    parts = normalize_player_name(cleaned).split()
    return parts[-1].lower() if parts else ""


def _year_from_date(date: str) -> int | None:
    match = YEAR_RE.search(date or "")
    return int(match.group(0)) if match else None


def _decode_header_value(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    return text.replace('\\"', '"').replace("\\\\", "\\")


def iter_pgn_files(pgn_dir: Path) -> list[Path]:
    if not pgn_dir.exists():
        return []
    files = sorted(pgn_dir.rglob("*.pgn"))
    return [p for p in files if p.is_file()]


def extract_game_bytes(path: Path, offset: int) -> str:
    with path.open("rb") as handle:
        handle.seek(offset)
        chunks: list[bytes] = []
        while True:
            line = handle.readline()
            if not line:
                break
            if chunks and line.startswith(b"[Event "):
                break
            chunks.append(line)
    text = b"".join(chunks).decode("utf-8", errors="replace").strip()
    return text + ("\n" if text and not text.endswith("\n") else "")


class LocalMastersDB:
    """SQLite index over local master PGNs (e.g. Lumbra Gigabase OTB dumps)."""

    def __init__(self, index_path: Path, pgn_dir: Path | None = None) -> None:
        self.index_path = Path(index_path)
        self.pgn_dir = Path(pgn_dir) if pgn_dir else None

    @property
    def available(self) -> bool:
        if not self.index_path.is_file():
            return False
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) FROM games").fetchone()
            return bool(row and row[0] > 0)
        except sqlite3.Error:
            return False

    def game_count(self) -> int:
        if not self.index_path.is_file():
            return 0
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM games").fetchone()
        return int(row[0]) if row else 0

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.index_path))
        conn.row_factory = sqlite3.Row
        return conn

    def fix_surnames(self, *, batch_size: int = 50_000) -> int:
        """Recompute white_last/black_last from stored White/Black (no PGN re-read)."""
        if not self.index_path.is_file():
            raise FileNotFoundError(f"index not found: {self.index_path}")
        log("Masters surname repair: scanning %s...", self.index_path)
        updated = 0
        last_id = 0
        with self._connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM games").fetchone()[0])
            while True:
                rows = conn.execute(
                    """
                    SELECT id, white, black, white_last, black_last
                    FROM games
                    WHERE id > ?
                    ORDER BY id
                    LIMIT ?
                    """,
                    (last_id, batch_size),
                ).fetchall()
                if not rows:
                    break
                patch: list[tuple[str, str, int]] = []
                for row in rows:
                    wl = _surname(row["white"])
                    bl = _surname(row["black"])
                    if wl != row["white_last"] or bl != row["black_last"]:
                        patch.append((wl, bl, int(row["id"])))
                if patch:
                    conn.executemany(
                        "UPDATE games SET white_last = ?, black_last = ? WHERE id = ?",
                        patch,
                    )
                    conn.commit()
                    updated += len(patch)
                last_id = int(rows[-1]["id"])
                log(
                    "  surname repair id<=%d (%.1f%%) patched_batch=%d total_patched=%d",
                    last_id,
                    100.0 * last_id / max(total, 1),
                    len(patch),
                    updated,
                )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('surname_format', ?)",
                ("last_comma_first",),
            )
            conn.commit()
        log("Masters surname repair done: %d / %d rows updated", updated, total)
        return updated

    def build_index(self, pgn_dir: Path | None = None, *, reset: bool = True) -> int:
        root = Path(pgn_dir or self.pgn_dir or "")
        if not root.is_dir():
            raise FileNotFoundError(f"masters pgn_dir not found: {root}")
        files = iter_pgn_files(root)
        if not files:
            raise FileNotFoundError(f"no .pgn files under {root}")

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        if reset and self.index_path.exists():
            self.index_path.unlink()

        log("Masters index: %d PGN file(s) under %s", len(files), root)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE games (
                    id INTEGER PRIMARY KEY,
                    path TEXT NOT NULL,
                    offset INTEGER NOT NULL,
                    white TEXT NOT NULL,
                    black TEXT NOT NULL,
                    white_last TEXT NOT NULL,
                    black_last TEXT NOT NULL,
                    year INTEGER,
                    event TEXT,
                    eco TEXT,
                    result TEXT
                );
                CREATE INDEX idx_games_wby ON games(white_last, black_last, year);
                CREATE INDEX idx_games_bwy ON games(black_last, white_last, year);
                CREATE INDEX idx_games_year ON games(year);
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
                """
            )
            total = 0
            for file_idx, path in enumerate(files, start=1):
                rel = str(path.resolve())
                log("  indexing %d/%d %s...", file_idx, len(files), path.name)
                added = self._index_file(conn, path, rel)
                total += added
                log("  +%d games (running total %d)", added, total)
                conn.commit()
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('pgn_dir', ?)",
                (str(root.resolve()),),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('game_count', ?)",
                (str(total),),
            )
            conn.commit()
        log("Masters index done: %d games → %s", total, self.index_path)
        return total

    def _index_file(self, conn: sqlite3.Connection, path: Path, stored_path: str) -> int:
        added = 0
        game_offset: int | None = None
        headers: dict[str, str] = {}

        def flush() -> None:
            nonlocal added, game_offset, headers
            if game_offset is None:
                return
            white = headers.get("White", "")
            black = headers.get("Black", "")
            if not white or not black:
                game_offset = None
                headers = {}
                return
            year = _year_from_date(headers.get("Date", ""))
            conn.execute(
                """
                INSERT INTO games(
                    path, offset, white, black, white_last, black_last,
                    year, event, eco, result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stored_path,
                    game_offset,
                    white,
                    black,
                    _surname(white),
                    _surname(black),
                    year,
                    headers.get("Event", ""),
                    headers.get("ECO", ""),
                    headers.get("Result", ""),
                ),
            )
            added += 1
            game_offset = None
            headers = {}

        with path.open("rb") as handle:
            while True:
                offset = handle.tell()
                line = handle.readline()
                if not line:
                    break
                if line.startswith(b"[Event "):
                    flush()
                    game_offset = offset
                    headers = {}
                    match = HEADER_RE.match(line.rstrip(b"\r\n"))
                    if match:
                        headers[_decode_header_value(match.group(1))] = _decode_header_value(
                            match.group(2)
                        )
                    continue
                if game_offset is None:
                    continue
                if line.startswith(b"["):
                    match = HEADER_RE.match(line.rstrip(b"\r\n"))
                    if match:
                        key = _decode_header_value(match.group(1))
                        if key not in headers:
                            headers[key] = _decode_header_value(match.group(2))
        flush()
        return added

    def find(
        self,
        white: str,
        black: str,
        year: int | None = None,
        event_hint: str | None = None,
        *,
        soft_year: bool = True,
        limit: int = 40,
    ) -> LocalGameHit | None:
        if not self.available:
            return None
        white_lasts = {_surname(v) for v in search_name_variants(white) if _surname(v)}
        black_lasts = {_surname(v) for v in search_name_variants(black) if _surname(v)}
        if not white_lasts or not black_lasts:
            return None

        years: list[int | None] = []
        if year is not None:
            years.append(year)
            if soft_year:
                years.extend([year - 1, year + 1])
        years.append(None)

        seen_years: set[int | None] = set()
        with self._connect() as conn:
            for y in years:
                if y in seen_years:
                    continue
                seen_years.add(y)
                hits = self._query(conn, white_lasts, black_lasts, y, limit=limit)
                if hits:
                    ranked = self._rank(hits, white, black, year, event_hint)
                    if ranked:
                        best = ranked[0]
                        log(
                            "Masters local hit: %s vs %s %s (%s) id=%s",
                            best.white,
                            best.black,
                            best.year or "?",
                            best.event or "no event",
                            best.gid,
                        )
                        return best
        return None

    def _query(
        self,
        conn: sqlite3.Connection,
        white_lasts: set[str],
        black_lasts: set[str],
        year: int | None,
        *,
        limit: int,
    ) -> list[LocalGameHit]:
        w_list = sorted(white_lasts)
        b_list = sorted(black_lasts)
        w_ph = ",".join("?" * len(w_list))
        b_ph = ",".join("?" * len(b_list))
        params: list[object] = [*w_list, *b_list, *b_list, *w_list]
        year_sql = ""
        if year is not None:
            year_sql = " AND year = ?"
            params.append(year)
        sql = f"""
            SELECT id, path, offset, white, black, year, event, eco, result
            FROM games
            WHERE (
                (white_last IN ({w_ph}) AND black_last IN ({b_ph}))
                OR (white_last IN ({b_ph}) AND black_last IN ({w_ph}))
            )
            {year_sql}
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [
            LocalGameHit(
                row_id=int(row["id"]),
                path=Path(row["path"]),
                offset=int(row["offset"]),
                white=row["white"],
                black=row["black"],
                year=row["year"],
                event=row["event"] or "",
                eco=row["eco"] or "",
                result=row["result"] or "",
            )
            for row in rows
        ]

    def _rank(
        self,
        hits: list[LocalGameHit],
        white: str,
        black: str,
        year: int | None,
        event_hint: str | None,
    ) -> list[LocalGameHit]:
        w = normalize_player_name(white).lower()
        b = normalize_player_name(black).lower()
        w_last = w.split()[-1] if w else ""
        b_last = b.split()[-1] if b else ""
        hint = (event_hint or "").lower()
        hint_tokens = {t for t in re.findall(r"[a-z0-9]+", hint) if len(t) > 2}

        def score(hit: LocalGameHit) -> tuple[int, int, int]:
            hw, hb = hit.white.lower(), hit.black.lower()
            name_score = 0
            if w_last and w_last in hw:
                name_score += 3
            if b_last and b_last in hb:
                name_score += 3
            if w_last in hw and b_last in hb:
                name_score += 3
            elif w_last in hb and b_last in hw:
                name_score += 1
            event_score = 0
            event_l = hit.event.lower()
            if hint and hint in event_l:
                event_score += 4
            event_score += sum(1 for t in hint_tokens if t in event_l)
            year_score = 0
            if year is not None and hit.year is not None:
                if hit.year == year:
                    year_score = 5
                elif abs(hit.year - year) == 1:
                    year_score = 2
            return (name_score + event_score + year_score, year_score, hit.year or 0)

        return sorted(hits, key=score, reverse=True)

    def find_by_eco(self, eco: str, *, limit: int = 5) -> list[LocalGameHit]:
        """Sample master games sharing an ECO code (smart PGN similarity seed)."""
        code = (eco or "").strip().upper()
        if not code or not self.available:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, path, offset, white, black, year, event, eco, result
                FROM games
                WHERE eco = ?
                ORDER BY year DESC
                LIMIT ?
                """,
                (code, max(1, limit)),
            ).fetchall()
        return [
            LocalGameHit(
                row_id=int(row["id"]),
                path=Path(row["path"]),
                offset=int(row["offset"]),
                white=row["white"],
                black=row["black"],
                year=row["year"],
                event=row["event"] or "",
                eco=row["eco"] or "",
                result=row["result"] or "",
            )
            for row in rows
        ]

    def fetch_pgn(self, hit: LocalGameHit) -> str:
        if not hit.path.is_file():
            raise FileNotFoundError(f"indexed PGN missing: {hit.path}")
        return extract_game_bytes(hit.path, hit.offset)
