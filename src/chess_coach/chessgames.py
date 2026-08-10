from __future__ import annotations

import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from chess_coach.logutil import log
from chess_coach.names import normalize_player_name, search_name_variants

BASE = "https://www.chessgames.com"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ChessgamesHit:
    gid: str
    white: str
    black: str
    year: str
    result: str
    event: str
    eco: str
    url: str


@dataclass
class FetchResult:
    pgn: str
    hit: ChessgamesHit
    path: Path | None = None


def _hit_year(hit: ChessgamesHit) -> int | None:
    m = re.search(r"(?:19|20)\d{2}", hit.year or "")
    return int(m.group(0)) if m else None


def _filter_hits_by_year(
    hits: list[ChessgamesHit],
    year: int | None,
    *,
    soft: bool = False,
) -> list[ChessgamesHit]:
    """Prefer exact year. Keep blank-year rows. Optionally allow ±1 year."""
    if year is None:
        return hits
    exact = [h for h in hits if _hit_year(h) == year]
    if exact:
        return exact
    # Chessgames sometimes omits year in the row; still usable (PGN has Date)
    unknown = [h for h in hits if _hit_year(h) is None]
    if unknown:
        return unknown
    if soft:
        close = [
            h
            for h in hits
            if (hy := _hit_year(h)) is not None and abs(hy - year) <= 1
        ]
        return close
    return []


class ChessgamesClient:
    """Master games via chessgames.com (curl — site blocks plain Python HTTP clients)."""

    def __init__(self, delay_s: float = 1.5) -> None:
        self.delay_s = delay_s
        self._cookie_file = tempfile.NamedTemporaryFile(prefix="cg_cookies_", suffix=".txt", delete=False)
        self._cookie_path = Path(self._cookie_file.name)
        self._cookie_file.close()
        self._warmed = False
        self._empty_streak = 0

    def close(self) -> None:
        try:
            self._cookie_path.unlink(missing_ok=True)
        except OSError:
            pass

    def __enter__(self) -> ChessgamesClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _curl(self, url: str, *, referer: str | None = None) -> str:
        cmd = [
            "curl",
            "--http1.1",
            "-sS",
            "-L",
            "-A",
            UA,
            "-c",
            str(self._cookie_path),
            "-b",
            str(self._cookie_path),
        ]
        if referer:
            cmd.extend(["-H", f"Referer: {referer}"])
        cmd.append(url)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"curl failed ({result.returncode}): {result.stderr.strip()}")
        body = result.stdout
        if "awsWafCookieDomainList" in body and "gid=" not in body and "[Event" not in body:
            raise RuntimeError("Chessgames WAF challenge — retry later or open site in a browser first")
        return body

    def _warm(self) -> None:
        if self._warmed:
            return
        log("Chessgames: warming session (curl + cookies)...")
        self._curl(f"{BASE}/")
        self._warmed = True
        time.sleep(self.delay_s)
        log("Chessgames: session ready")

    def search(
        self,
        white: str | None = None,
        black: str | None = None,
        year: int | None = None,
        *,
        either_order: bool = True,
        max_hits: int = 25,
    ) -> list[ChessgamesHit]:
        self._warm()
        params = {
            "playercomp": "either" if either_order else "white",
            "player": white or "",
            "player2": black or "",
        }
        if year is not None:
            params["year"] = str(year)
            params["yearcomp"] = "exactly"
        url = f"{BASE}/perl/chess.pl?{urlencode(params)}"
        year_bit = str(year) if year is not None else "any"
        log("Chessgames search: %s vs %s (%s)...", white or "?", black or "?", year_bit)
        # back off when the site starts returning empty waves (rate limit / soft WAF)
        if self._empty_streak >= 6:
            pause = min(20.0, 4.0 + self._empty_streak)
            log("Chessgames: empty streak=%d — sleeping %.0fs", self._empty_streak, pause)
            time.sleep(pause)
        elif self._empty_streak >= 3:
            time.sleep(self.delay_s + 2.0)
        html = self._curl(url)
        time.sleep(self.delay_s)
        raw_hits = self._parse_search(html, max_hits=max_hits)
        # streak tracks site emptiness / soft-WAF, not year-filter rejects
        if raw_hits:
            self._empty_streak = 0
        else:
            self._empty_streak += 1
        hits = (
            _filter_hits_by_year(raw_hits, year, soft=False)
            if year is not None
            else raw_hits
        )
        log("Chessgames search: %d hit(s)", len(hits))
        return hits

    def _parse_search(self, html: str, *, max_hits: int) -> list[ChessgamesHit]:
        hits: list[ChessgamesHit] = []
        # Prefer rich rows when present
        row_re = re.compile(
            r'chessgame\?gid=(?P<gid>\d+)">(?P<label>[^<]+)</a>.*?'
            r"size=-1>(?P<result>.*?)</font>.*?"
            r"size=-1>(?P<moves>\d+)</font>.*?"
            r"size=-1>(?P<year>\d{4})</font>.*?"
            r'chess\.pl\?tid=\d+">(?P<event>[^<]*)</a>.*?'
            r'chessopening\?eco=(?P<eco>[A-E]\d{2})">',
            re.I | re.S,
        )
        for match in row_re.finditer(html):
            hits.append(self._hit_from_match(match))
            if len(hits) >= max_hits:
                return hits
        if hits:
            return hits
        for match in re.finditer(r'href="/perl/chessgame\?gid=(\d+)">([^<]+)</a>', html, re.I):
            label = re.sub(r"\s+", " ", match.group(2)).strip()
            if " vs " not in label.lower() and " vs. " not in label.lower():
                # chessgames uses "Alekhine vs Capablanca"
                if " vs " not in label:
                    continue
            white, black = [p.strip() for p in re.split(r"\s+vs\.?\s+", label, maxsplit=1, flags=re.I)]
            hits.append(
                ChessgamesHit(
                    gid=match.group(1),
                    white=white,
                    black=black,
                    year="",
                    result="",
                    event="",
                    eco="",
                    url=f"{BASE}/perl/chessgame?gid={match.group(1)}",
                )
            )
            if len(hits) >= max_hits:
                break
        return hits

    def _hit_from_match(self, match: re.Match) -> ChessgamesHit:
        label = re.sub(r"\s+", " ", match.group("label")).strip()
        if " vs " in label:
            white, black = [p.strip() for p in label.split(" vs ", 1)]
        else:
            white, black = label, "?"
        result = (
            match.group("result").replace("&#189;", "1/2").replace("½", "1/2").strip()
        )
        return ChessgamesHit(
            gid=match.group("gid"),
            white=white,
            black=black,
            year=match.group("year"),
            result=result,
            event=re.sub(r"\s+", " ", match.group("event")).strip(),
            eco=match.group("eco"),
            url=f"{BASE}/perl/chessgame?gid={match.group('gid')}",
        )

    def fetch_pgn(self, gid: str) -> str:
        self._warm()
        game_url = f"{BASE}/perl/chessgame?gid={gid}"
        log("Chessgames: fetching game page gid=%s...", gid)
        html = self._curl(game_url, referer=f"{BASE}/perl/chess.pl")
        time.sleep(self.delay_s)
        pgn = self._pgn_from_game_html(html)
        if pgn:
            log("Chessgames: PGN extracted from page (%d chars)", len(pgn))
            return pgn
        m = re.search(r'href="/pgn/([^"?]+)\?gid=' + re.escape(gid), html)
        slug = m.group(1) if m else f"game_{gid}.pgn"
        pgn_url = f"{BASE}/pgn/{slug}?gid={gid}"
        log("Chessgames: downloading PGN file %s...", slug)
        text = self._curl(pgn_url, referer=game_url).strip()
        if not text.startswith("["):
            raise RuntimeError(f"Chessgames returned non-PGN for gid={gid}")
        log("Chessgames: PGN download ok (%d chars)", len(text))
        return text + ("\n" if not text.endswith("\n") else "")

    def _pgn_from_game_html(self, html: str) -> str | None:
        match = re.search(r"id=\"olga-data\"[^>]*\spgn='(.*?)'\s", html, re.S)
        if not match:
            match = re.search(r'id="olga-data"[^>]*\spgn="(.*?)"\s', html, re.S)
        if not match:
            return None
        raw = match.group(1)
        raw = (
            raw.replace("&#039;", "'")
            .replace("&quot;", '"')
            .replace("&amp;", "&")
            .replace("&#41;", ")")
            .replace("&#40;", "(")
            .replace("&#10;", "\n")
            .replace("&#13;", "")
        )
        if "[Event" in raw:
            return raw.strip() + "\n"
        return None

    def fetch_best_match(
        self,
        white: str,
        black: str,
        year: int | None = None,
        event_hint: str | None = None,
        out_dir: Path | None = None,
    ) -> FetchResult | None:
        white_variants = search_name_variants(white)
        black_variants = search_name_variants(black)
        hits: list[ChessgamesHit] = []
        attempts: list[tuple[str, str, int | None]] = []
        for w in white_variants:
            for b in black_variants:
                attempts.append((w, b, year))
        # retry without year if needed
        if year is not None:
            for w in white_variants[:2]:
                for b in black_variants[:2]:
                    attempts.append((w, b, None))

        seen_attempt: set[tuple[str, str, int | None]] = set()
        unique_attempts = []
        for w, b, y in attempts:
            key = (w.lower(), b.lower(), y)
            if key in seen_attempt:
                continue
            seen_attempt.add(key)
            unique_attempts.append((w, b, y))
        log(
            "Chessgames match: trying %d name/year variant(s) for %s vs %s",
            len(unique_attempts),
            white,
            black,
        )
        for idx, (w, b, y) in enumerate(unique_attempts, start=1):
            log("  attempt %d/%d...", idx, len(unique_attempts))
            found = self.search(white=w, black=b, year=y, either_order=True)
            # yearless search: exact year, else blank year, else ±1
            if year is not None and y is None:
                found = _filter_hits_by_year(found, year, soft=True)
            elif year is not None:
                found = _filter_hits_by_year(found, year, soft=False)
            if found:
                hits = found
                white, black = w, b
                log("  matched with query %s vs %s year=%s", w, b, y)
                break
            # if site is clearly rate-limiting, stop burning variants
            if self._empty_streak >= 6 and idx >= 3:
                log("  aborting further variants (empty streak=%d)", self._empty_streak)
                break

        if not hits and year is not None and self._empty_streak < 6:
            # one-sided search: white surname + year, keep rows mentioning black
            b_last = normalize_player_name(black).split()[-1].lower() if black else ""
            for w in white_variants[:2]:
                log("  fallback one-sided: %s + year=%s (filter %s)...", w, year, b_last or "?")
                found = self.search(white=w, black=None, year=year, either_order=True)
                found = _filter_hits_by_year(found, year, soft=False)
                if b_last:
                    found = [
                        h
                        for h in found
                        if b_last in h.black.lower() or b_last in h.white.lower()
                    ]
                if found:
                    hits = found
                    log("  one-sided matched %d hit(s)", len(hits))
                    break
        elif not hits and self._empty_streak >= 6:
            log("  skip one-sided fallback (empty streak=%d)", self._empty_streak)

        if not hits:
            log("Chessgames match: no hits")
            return None
        hit = self._rank_hits(hits, white, black, event_hint, year)[0]
        log(
            "Chessgames best hit: gid=%s %s vs %s (%s, %s)",
            hit.gid,
            hit.white,
            hit.black,
            hit.year,
            hit.event or "no event",
        )
        pgn = self.fetch_pgn(hit.gid)
        path = None
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"cg_{hit.gid}.pgn"
            path.write_text(pgn if pgn.endswith("\n") else pgn + "\n", encoding="utf-8")
        return FetchResult(pgn=pgn, hit=hit, path=path)

    def _rank_hits(
        self,
        hits: list[ChessgamesHit],
        white: str,
        black: str,
        event_hint: str | None,
        year: int | None = None,
    ) -> list[ChessgamesHit]:
        w = normalize_player_name(white).lower()
        b = normalize_player_name(black).lower()
        w_last = w.split()[-1] if w else ""
        b_last = b.split()[-1] if b else ""
        hint = (event_hint or "").lower()
        hint_tokens = {t for t in re.findall(r"[a-z0-9]+", hint) if len(t) > 2}
        hits = _filter_hits_by_year(hits, year)

        def score(hit: ChessgamesHit) -> tuple[int, int]:
            hw, hb = hit.white.lower(), hit.black.lower()
            name_score = 0
            if w_last and w_last in hw:
                name_score += 3
            if b_last and b_last in hb:
                name_score += 3
            # prefer correct colors when both surnames present
            if w_last in hw and b_last in hb:
                name_score += 2
            elif w_last in hb and b_last in hw:
                name_score += 1
            event_score = 0
            event_l = hit.event.lower()
            if hint and hint in event_l:
                event_score += 4
            event_score += sum(1 for t in hint_tokens if t in event_l)
            # opening hints from book headers
            if "dutch" in hint and hit.eco.startswith("A8"):
                event_score += 3
            if "sicilian" in hint and hit.eco.startswith("B"):
                event_score += 2
            if "queen" in hint and "gambit" in hint and hit.eco.startswith("D"):
                event_score += 2
            # prefer J Corzo over E Corzo when black surname matches and initial hints "J"
            if " j " in f" {b} " or b.startswith("j ") or "j." in b:
                if re.search(r"\bj\.?\s*corzo\b", hb) or hb.strip().startswith("j "):
                    name_score += 2
            hy = _hit_year(hit) or 0
            return (name_score + event_score, hy)

        return sorted(hits, key=score, reverse=True)
