"""
ui.py — Terminal UI helpers for the Million-Candidate Search Engine.

Provides ANSI-color output, score bars, signal bars, and the polished
"magazine-style" results renderer used by `search.py`.

Designed to degrade gracefully: if stdout is piped (not a TTY), all color
codes are stripped automatically so JSON processors and grep still work.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional


# ----------------------------------------------------------------- color

_IS_TTY = sys.stdout.isatty()
_NO_COLOR = os.environ.get("NO_COLOR") is not None
_USE_COLOR = _IS_TTY and not _NO_COLOR


class _C:
    """Tiny ANSI wrapper. Returns the bare string when color is disabled."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"
    UNDER   = "\033[4m"
    # Foreground
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    GRAY    = "\033[90m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW= "\033[93m"
    BRIGHT_CYAN  = "\033[96m"


def c(text, *codes: str) -> str:
    """Wrap text in ANSI codes if color is enabled."""
    if not _USE_COLOR or not codes:
        return text
    return "".join(codes) + text + _C.RESET


# ----------------------------------------------------------------- bars

# Block characters for a smoother bar
_BAR_FULL = "━"
_BAR_HALF = "╸"
_BAR_EMPTY = "─"

_SIGNAL_GLYPHS = {
    # (glyph, color code) for each signal
    "semantic":   ("SEM", _C.CYAN),
    "role_fit":   ("ROL", _C.BLUE),
    "skills":     ("SKL", _C.GREEN),
    "behavioral": ("BEH", _C.YELLOW),
    "career":     ("CAR", _C.MAGENTA),
}


def score_bar(score_10: float, width: int = 10) -> str:
    """A 10-cell bar like ████████░░ with color tied to the score band."""
    filled = int(round(score_10 / 10 * width))
    bar = _BAR_FULL * filled + _BAR_EMPTY * (width - filled)
    if score_10 >= 8.0:
        color = _C.BRIGHT_GREEN
    elif score_10 >= 6.5:
        color = _C.YELLOW
    elif score_10 >= 5.0:
        color = _C.BRIGHT_YELLOW
    else:
        color = _C.RED
    return c(bar, color)


def signal_bar(value_01: float, width: int = 10) -> str:
    """A 0-1 signal bar with a smoother 20-step resolution."""
    filled = int(round(value_01 * width))
    filled = max(0, min(width, filled))
    if value_01 >= 0.75:
        color = _C.BRIGHT_GREEN
    elif value_01 >= 0.5:
        color = _C.YELLOW
    else:
        color = _C.RED
    return c(_BAR_FULL * filled + _BAR_EMPTY * (width - filled), color)


def score_color(score_10: float) -> str:
    if score_10 >= 8.0: return _C.BRIGHT_GREEN
    if score_10 >= 6.5: return _C.YELLOW
    if score_10 >= 5.0: return _C.BRIGHT_YELLOW
    return _C.RED


def rank_glyph(rank: int) -> str:
    if rank == 1: return c(" ① ", _C.BRIGHT_GREEN, _C.BOLD)
    if rank == 2: return c(" ② ", _C.CYAN, _C.BOLD)
    if rank == 3: return c(" ③ ", _C.YELLOW, _C.BOLD)
    return f" {rank:>2} "


# ----------------------------------------------------------------- render

def render_jd_card(jd: Dict) -> str:
    """A compact summary of the parsed JD — shows the recruiter what we extracted."""
    lines = []
    lines.append(c("┌─ PARSED JOB DESCRIPTION " + "─" * 60, _C.DIM))
    lines.append(c("│ ", _C.DIM) + c("Title:      ", _C.GRAY) + c(jd.get("title") or "(unknown)", _C.BOLD))
    lines.append(c("│ ", _C.DIM) + c("Seniority:  ", _C.GRAY) + jd.get("seniority", "?"))
    req = jd.get("required_skills") or []
    nice = jd.get("nice_to_have") or []
    lines.append(c("│ ", _C.DIM) + c("Required:   ", _C.GRAY) + (c(", ".join(req), _C.GREEN) if req else c("(none detected)", _C.DIM)))
    if nice:
        lines.append(c("│ ", _C.DIM) + c("Nice-to-have: ", _C.GRAY) + c(", ".join(nice), _C.BRIGHT_CYAN))
    extras = []
    if jd.get("min_yoe"):
        extras.append(f"min YoE: {jd['min_yoe']}")
    if jd.get("location"):
        extras.append(f"loc: {jd['location']}")
    if jd.get("remote_ok"):
        extras.append(c("remote-ok", _C.BRIGHT_GREEN))
    if jd.get("visa_required"):
        extras.append(c("visa-sponsor", _C.YELLOW))
    if extras:
        lines.append(c("│ ", _C.DIM) + c("Constraints: ", _C.GRAY) + "  ".join(str(e) for e in extras))
    lines.append(c("└" + "─" * 75, _C.DIM))
    return "\n".join(lines)


def render_result_card(r: Dict, verbose_signals: bool) -> List[str]:
    """One result card → list of lines (no trailing newline)."""
    name = r["name"]
    title = (r.get("current_title") or "")[:28]
    company = (r.get("current_company") or "")[:20]
    yoe = r.get("years_experience")
    yoe_str = f"{yoe}y" if yoe is not None else "?"
    loc = (r.get("location") or "")[:22]
    sig = r["signals"]
    sc = r["score_10"]

    # Header line: rank | score bar | score | name @ company · yoe · loc
    head = (
        rank_glyph(r["rank"]) + " "
        + score_bar(sc) + " "
        + c(f"{sc:>4.1f}", score_color(sc), _C.BOLD) + c("/10", _C.GRAY)
        + "  "
        + c(name[:24], _C.BOLD)
        + c(f"  {title}", _C.DIM)
    )
    sub = (
        "         "
        + c("@ ", _C.GRAY) + c(company[:20], _C.CYAN)
        + c(f"  ·  {yoe_str}", _C.GRAY)
        + (c(f"  ·  {loc}", _C.DIM) if loc else "")
    )
    lines = [head, sub]

    if verbose_signals:
        # Per-signal compact bars on one line
        sig_cells = []
        for key, (lbl, color) in _SIGNAL_GLYPHS.items():
            v = sig.get(key, 0.0)
            sig_cells.append(f"{c(lbl, color)} {signal_bar(v, 8)} {v:.2f}")
        lines.append("         " + "  ".join(sig_cells))

    # Matched skills (green) and missing skills (red)
    matched = r.get("matched_skills") or []
    missing = r.get("missing_skills") or []
    skill_chunks = []
    for s in matched[:6]:
        skill_chunks.append(c(s, _C.BRIGHT_GREEN))
    line = "         " + c("✓ ", _C.BRIGHT_GREEN) + (", ".join(skill_chunks) if skill_chunks else c("(no matched required skills)", _C.DIM))
    lines.append(line)
    if missing:
        miss_chunks = [c(s, _C.RED) for s in missing[:6]]
        lines.append("         " + c("✗ ", _C.RED) + ", ".join(miss_chunks))

    # Reasoning line (italic-style via dim)
    lines.append("         " + c("→ ", _C.BRIGHT_CYAN) + c(r["reasoning"], _C.DIM))
    return lines


def render_results(
    results: List[Dict],
    jd: Optional[Dict],
    timing: Optional[Dict],
    show_signals_for_all: bool = False,
) -> str:
    """Top-level renderer: returns the full styled output as a string."""
    out: List[str] = []

    # ---- Banner
    banner_top = c("╔" + "═" * 78, _C.BRIGHT_CYAN, _C.BOLD)
    banner_mid = c("║", _C.BRIGHT_CYAN, _C.BOLD) + c("  RecruitProof — Enterprise Candidate Intelligence", _C.BOLD) + " " * 27 + c("║", _C.BRIGHT_CYAN, _C.BOLD)
    banner_bot = c("╚" + "═" * 78, _C.BRIGHT_CYAN, _C.BOLD)
    out += [banner_top, banner_mid, banner_bot, ""]

    # ---- JD card
    if jd:
        out.append(render_jd_card(jd))
        out.append("")

    # ---- Timing mini-summary
    if timing:
        cells = []
        # Standard stages
        for k in ("parse_ms", "load_ms", "embed_ms"):
            v = timing.get(k)
            if v is not None:
                label = k.replace("_ms", "").upper()
                cells.append(f"{c(label, _C.GRAY)} {v:>5.0f}ms")
        # Retrieval stage — show faiss+sparse+fuse breakdown for hybrid, else faiss only
        faiss_ms = timing.get("faiss_ms")
        sparse_ms = timing.get("sparse_ms")
        fuse_ms = timing.get("fuse_ms")
        if sparse_ms is not None:
            # Hybrid mode
            cells.append(f"{c('FAISS', _C.GRAY)} {faiss_ms:>5.0f}ms")
            cells.append(f"{c('BM25', _C.GRAY)} {sparse_ms:>5.0f}ms")
            cells.append(f"{c('RRF', _C.GRAY)} {fuse_ms:>5.0f}ms")
        elif faiss_ms is not None:
            cells.append(f"{c('FAISS', _C.GRAY)} {faiss_ms:>5.0f}ms")
        for k in ("rank_ms",):
            v = timing.get(k)
            if v is not None:
                label = k.replace("_ms", "").upper()
                cells.append(f"{c(label, _C.GRAY)} {v:>5.0f}ms")
        total = timing.get("total_ms", 0.0)
        cells.append(f"{c('TOTAL', _C.BOLD)} {c(f'{total:.0f}ms', _C.BRIGHT_GREEN, _C.BOLD)}")
        out.append("  " + "  ".join(cells))
        out.append("")

    # ---- Result cards
    out.append(c(f"  Top {len(results)} Candidates", _C.BOLD))
    out.append(c("  " + "─" * 76, _C.DIM))
    out.append("")
    for i, r in enumerate(results):
        verbose = show_signals_for_all or i < 3
        out.extend(render_result_card(r, verbose_signals=verbose))
        out.append("")

    # ---- Footer with #1 deep-dive
    out.append(c("  " + "═" * 76, _C.BRIGHT_CYAN))
    if results:
        top1 = results[0]
        out.append(
            "  " + c("TOP MATCH  ", _C.BOLD, _C.BRIGHT_GREEN)
            + c(top1["name"], _C.BOLD)
            + "  "
            + c(f"{top1['score_10']}/10", score_color(top1["score_10"]), _C.BOLD)
        )
        if top1.get("missing_skills"):
            miss = ", ".join(top1["missing_skills"])
            out.append("  " + c("WHY NOT 10/10:  ", _C.YELLOW) + c(f"missing {miss}", _C.RED))
        else:
            out.append("  " + c("WHY NOT 10/10:  ", _C.YELLOW) + c("no missing required skills — full skills coverage", _C.BRIGHT_GREEN))
        out.append("  " + c("REASONING:       ", _C.GRAY) + top1["reasoning"])
    out.append(c("  " + "═" * 76, _C.BRIGHT_CYAN))
    out.append("")
    return "\n".join(out)


def render_explain(jd: Dict, candidate: Dict, cs_signals: Dict, matched: List[str], missing: List[str],
                   reasoning: str, sim: float, weights: Dict[str, float]) -> str:
    """Detailed per-candidate trace — used by `search.py --explain`."""
    out: List[str] = []
    out.append(c("╔" + "═" * 78, _C.MAGENTA, _C.BOLD))
    out.append(c("║", _C.MAGENTA, _C.BOLD) + c("  CANDIDATE EXPLANATION TRACE", _C.BOLD) + " " * 49 + c("║", _C.MAGENTA, _C.BOLD))
    out.append(c("╚" + "═" * 78, _C.MAGENTA, _C.BOLD))
    out.append("")
    out.append(f"  {c('Candidate:', _C.GRAY)} {c(candidate.get('name', '?'), _C.BOLD)}  "
               + c(f"({candidate.get('id', '?')})", _C.DIM))
    out.append(f"  {c('Title:    ', _C.GRAY)} {candidate.get('current_title', '')} @ {candidate.get('current_company', '')}")
    out.append(f"  {c('YoE:      ', _C.GRAY)} {candidate.get('years_experience', '?')}  "
               + c(f"Location: ", _C.GRAY) + f"{candidate.get('location', '')}")
    out.append("")
    out.append(c("  JD target:", _C.BOLD) + f"  {jd.get('title', '')}  ({jd.get('seniority', '')})")
    out.append("")
    # Signals table
    out.append(c("  Signal breakdown", _C.BOLD))
    out.append(c("  " + "─" * 76, _C.DIM))
    header = (f"  {'Signal':<14}{'Value':>8}  {'Bar':<22}{'Weight':>8}  {'Contribution':>14}")
    out.append(c(header, _C.GRAY))
    out.append(c("  " + "─" * 76, _C.DIM))
    total_contrib = 0.0
    for key, (lbl, color) in _SIGNAL_GLYPHS.items():
        v = cs_signals.get(key, 0.0)
        w = weights.get({"semantic": "semantic", "role_fit": "role_fit", "skills": "skills",
                         "behavioral": "behavioral", "career": "career"}[key], 0.0)
        contrib = v * w * 10  # contribution to final 0-10 score
        total_contrib += contrib
        bar = signal_bar(v, 20)
        out.append(f"  {c(lbl, color):<14}{v:>8.3f}  {bar}  {w*100:>6.0f}%  {contrib:>12.2f}/10")
    out.append(c("  " + "─" * 76, _C.DIM))
    out.append(f"  {'FINAL':<14}{'':>8}  {'':<22}{'':>8}  {c(f'{total_contrib:.2f}/10', _C.BOLD, score_color(total_contrib)):>14}")
    out.append("")
    # Skills
    out.append(c("  Skills analysis", _C.BOLD))
    out.append(c("  " + "─" * 76, _C.DIM))
    out.append("  " + c("✓ Matched:  ", _C.BRIGHT_GREEN) + (", ".join(c(s, _C.BRIGHT_GREEN) for s in matched) or c("(none)", _C.DIM)))
    out.append("  " + c("✗ Missing:  ", _C.RED) + (", ".join(c(s, _C.RED) for s in missing) or c("(none — full coverage)", _C.BRIGHT_GREEN)))
    out.append("")
    out.append(c("  Reasoning", _C.BOLD))
    out.append(c("  " + "─" * 76, _C.DIM))
    out.append(f"  {c(reasoning, _C.DIM)}")
    out.append("")
    return "\n".join(out)
