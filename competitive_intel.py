"""
competitive_intel.py — Competitive Intelligence & Pricing Module
==============================================================

The intel flagged pricing as a major enterprise opportunity: legacy vendors
(Eightfold, Paradox, HireVue) charge $35k-100k+/year. RecruitProof
targets $10k/year — a 90%+ cost reduction.

This module exposes that competitive data programmatically so the demo can
show:
  1. A pricing comparison table
  2. A feature matrix (where each competitor is weak vs RecruitProof)
  3. A "cost savings calculator" that takes a team size and computes the
     annual savings vs each competitor.

Run as a CLI:
    python competitive_intel.py                 # print the table
    python competitive_intel.py --team 50       # compute savings for a 50-seat team
    python competitive_intel.py --json          # JSON export
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import ui


# ----------------------------------------------------------------- data

@dataclass
class Competitor:
    name: str
    annual_cost_usd: int                 # list price, per year
    model: str                            # "per-seat", "flat", "enterprise"
    seats_included: Optional[int] = None # if per-seat, how many seats at this price
    weaknesses: List[str] = field(default_factory=list)
    category: str = "ATS"                 # ATS / AI Recruiter / Video / etc.


# Pricing intel from the brief, plus our positioning
COMPETITORS: List[Competitor] = [
    Competitor(
        name="Manatal", annual_cost_usd=15*12*1,  # $15/user/mo × 12 × 1 user
        model="per-seat", seats_included=1,
        weaknesses=["Limited AI", "Per-seat costs scale fast", "No local-first option"],
        category="SMB ATS",
    ),
    Competitor(
        name="Truffle", annual_cost_usd=149*12,  # $99-149/mo flat
        model="flat", seats_included=10,
        weaknesses=["SMB-focused", "Limited semantic search", "No agentic AI"],
        category="SMB ATS",
    ),
    Competitor(
        name="Workable", annual_cost_usd=299*12,  # $299+/mo
        model="flat", seats_included=5,
        weaknesses=["SMB-focused, limited AI", "Cloud-only", "No local-first"],
        category="Mid-market ATS",
    ),
    Competitor(
        name="HireVue", annual_cost_usd=35_000,
        model="enterprise", seats_included=50,
        weaknesses=["Video-only", "Expensive", "Limited full-pipeline AI"],
        category="Video screening",
    ),
    Competitor(
        name="Eightfold", annual_cost_usd=75_000,  # $50k-100k+/year midpoint
        model="enterprise", seats_included=100,
        weaknesses=["Cloud-only", "$50k+", "Proprietary black-box AI"],
        category="AI Recruiter",
    ),
    Competitor(
        name="Paradox", annual_cost_usd=75_000,  # $50k-100k+/year midpoint
        model="enterprise", seats_included=100,
        weaknesses=["Limited search", "Complex deployment", "Cloud-only"],
        category="AI Recruiter",
    ),
    Competitor(
        name="SeekOut", annual_cost_usd=60_000,
        model="enterprise", seats_included=50,
        weaknesses=["Hard to integrate", "Expensive", "Cloud-only"],
        category="Talent search",
    ),
    Competitor(
        name="LinkedIn Recruiter", annual_cost_usd=10_800,  # $900/mo × 12
        model="per-seat", seats_included=1,
        weaknesses=["Limited semantic", "Cloud-only", "Per-seat pricing", "LinkedIn dependency"],
        category="Talent search",
    ),
]

# RecruitProof positioning (per the brief: $10k/year, 90% cheaper)
RECRUITPROOF_PRICE_USD = 10_000
RECRUITPROOF_SEATS_INCLUDED = 50  # team license

RECRUITPROOF_ADVANTAGES = [
    "Local-first (data never leaves your servers)",
    "Open-source core (audit + extend)",
    "Agentic multi-agent pipeline (4-agent)",
    "Hybrid retrieval (dense + sparse via RRF)",
    "Explainable scoring (every rank has a reason)",
    "Self-hosted or managed",
    "MIT-licensed core",
]


# ----------------------------------------------------------------- calculations

def cost_per_seat(competitor: Competitor) -> float:
    """Annual cost per seat for a competitor."""
    seats = competitor.seats_included or 1
    return competitor.annual_cost_usd / seats


def savings_vs(team_size: int, competitor: Competitor) -> Dict:
    """Compute annual savings for `team_size` recruiters vs one competitor.

    Assumes the RecruitProof license covers the whole team at flat $10k/year.
    """
    recruitproof_total = RECRUITPROOF_PRICE_USD  # flat
    if competitor.model == "per-seat":
        comp_total = cost_per_seat(competitor) * team_size
    elif competitor.model == "flat":
        # If team_size > seats_included, buy extra seat licenses at same per-seat rate
        if competitor.seats_included and team_size > competitor.seats_included:
            extra = team_size - competitor.seats_included
            comp_total = competitor.annual_cost_usd + extra * cost_per_seat(competitor)
        else:
            comp_total = competitor.annual_cost_usd
    else:  # enterprise — assume covers team_size up to seats_included
        comp_total = competitor.annual_cost_usd
        if competitor.seats_included and team_size > competitor.seats_included:
            # Enterprise deals usually add ~10% per extra seat block
            blocks_needed = (team_size - competitor.seats_included + 49) // 50
            comp_total += blocks_needed * 15_000

    savings = comp_total - recruitproof_total
    pct = (savings / comp_total * 100) if comp_total > 0 else 0.0
    return {
        "competitor": competitor.name,
        "competitor_annual": comp_total,
        "recruitproof_annual": recruitproof_total,
        "annual_savings": savings,
        "savings_pct": pct,
    }


# ----------------------------------------------------------------- rendering

def render_pricing_table() -> str:
    """Pretty-print the competitive pricing table."""
    out: List[str] = []
    out.append(ui.c("╔" + "═" * 78, ui._C.BRIGHT_CYAN, ui._C.BOLD))
    out.append(ui.c("║", ui._C.BRIGHT_CYAN, ui._C.BOLD)
              + ui.c("  RecruitProof — Competitive Intelligence & Pricing", ui._C.BOLD)
              + " " * 25 + ui.c("║", ui._C.BRIGHT_CYAN, ui._C.BOLD))
    out.append(ui.c("╚" + "═" * 78, ui._C.BRIGHT_CYAN, ui._C.BOLD))
    out.append("")
    out.append(f"  {ui.c('Competitor', ui._C.BOLD):<22}{ui.c('Annual', ui._C.GRAY):>14}"
               f"{ui.c('Per seat', ui._C.GRAY):>12}{ui.c('Category', ui._C.GRAY):<22}")
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    for c in COMPETITORS:
        cps = cost_per_seat(c)
        out.append(f"  {c.name:<22}${c.annual_cost_usd:>12,}{cps:>11,.0f}  {c.category:<20}")
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    recruitproof_cps = RECRUITPROOF_PRICE_USD / RECRUITPROOF_SEATS_INCLUDED
    out.append(f"  {ui.c('RecruitProof', ui._C.BOLD, ui._C.BRIGHT_GREEN):<22}"
               f"{ui.c(f'${RECRUITPROOF_PRICE_USD:,}', ui._C.BRIGHT_GREEN, ui._C.BOLD):>14}"
               f"{recruitproof_cps:>11,.0f}  {ui.c('Open-source AI', ui._C.BRIGHT_GREEN):<20}")
    out.append("")
    return "\n".join(out)


def render_savings(team_size: int) -> str:
    """Pretty-print the savings table for a given team size."""
    out: List[str] = []
    out.append(ui.c("  Cost Savings Calculator", ui._C.BOLD) + "  "
              + ui.c(f"(team size = {team_size} recruiters)", ui._C.GRAY))
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    out.append(f"  {ui.c('Competitor', ui._C.BOLD):<22}{ui.c('Their cost', ui._C.GRAY):>14}"
               f"{ui.c('RecruitProof cost', ui._C.GRAY):>12}{ui.c('Annual savings', ui._C.GRAY):>18}"
               f"{ui.c('Savings %', ui._C.GRAY):>12}")
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    for c in COMPETITORS:
        s = savings_vs(team_size, c)
        pct_color = (ui._C.BRIGHT_GREEN if s["savings_pct"] >= 80
                     else ui._C.YELLOW if s["savings_pct"] >= 50
                     else ui._C.RED)
        pct_str = f"{s['savings_pct']:.0f}%"
        out.append(f"  {c.name:<22}${s['competitor_annual']:>12,}"
                   f"  ${s['recruitproof_annual']:>9,}  ${s['annual_savings']:>14,}"
                   f"{ui.c(pct_str, pct_color, ui._C.BOLD):>11}")
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    # Average
    avg_pct = sum(savings_vs(team_size, c)["savings_pct"] for c in COMPETITORS) / len(COMPETITORS)
    out.append(f"  {ui.c('Average savings:', ui._C.BOLD)} "
              + ui.c(f"{avg_pct:.0f}% vs all competitors", ui._C.BRIGHT_GREEN, ui._C.BOLD))
    out.append("")
    return "\n".join(out)


def render_advantages() -> str:
    """Pretty-print the RecruitProof competitive advantages."""
    out: List[str] = []
    out.append(ui.c("  Why RecruitProof Wins", ui._C.BOLD))
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    for adv in RECRUITPROOF_ADVANTAGES:
        out.append(f"  {ui.c('✓', ui._C.BRIGHT_GREEN)} {adv}")
    out.append("")
    return "\n".join(out)


def render_weaknesses() -> str:
    """Pretty-print the competitor weaknesses matrix."""
    out: List[str] = []
    out.append(ui.c("  Competitor Weaknesses", ui._C.BOLD))
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    for c in COMPETITORS:
        out.append(f"  {ui.c(c.name, ui._C.BOLD)}  {ui.c(f'({c.category})', ui._C.DIM)}")
        for w in c.weaknesses:
            out.append(f"    {ui.c('✗', ui._C.RED)} {w}")
    out.append("")
    return "\n".join(out)


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Competitive intelligence & pricing for RecruitProof")
    ap.add_argument("--team", type=int, default=None,
                    help="Team size (number of recruiters) for the savings calculator")
    ap.add_argument("--json", action="store_true",
                    help="Output as JSON instead of a styled table")
    args = ap.parse_args()

    if args.json:
        payload = {
            "recruitproof_price_usd": RECRUITPROOF_PRICE_USD,
            "recruitproof_seats_included": RECRUITPROOF_SEATS_INCLUDED,
            "recruitproof_advantages": RECRUITPROOF_ADVANTAGES,
            "competitors": [
                {
                    "name": c.name, "annual_cost_usd": c.annual_cost_usd,
                    "model": c.model, "seats_included": c.seats_included,
                    "cost_per_seat": cost_per_seat(c),
                    "category": c.category, "weaknesses": c.weaknesses,
                    "savings_vs_apex": (savings_vs(args.team or 50, c) if args.team
                                        else savings_vs(50, c)),
                }
                for c in COMPETITORS
            ],
        }
        print(json.dumps(payload, indent=2))
        return

    print(render_pricing_table())
    if args.team:
        print(render_savings(args.team))
    else:
        print(render_savings(50))  # default team size for the demo
        print(ui.c("  (use --team N to compute for a different team size)", ui._C.DIM))
        print("")
    print(render_advantages())
    print(render_weaknesses())


if __name__ == "__main__":
    main()
