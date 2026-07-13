"""Generate dependency-free SVG figures and the descriptive results report."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .config import EDITIONS, FIGURES, RESULTS, ROOT
from .io import read_csv, write_csv


EDITION_RESULT_FIELDS = (
    "rank", "edition", "team_id", "team", "exposed_players", "mean_omega",
    "exp_susp_min", "fouls_all", "exp_susp_per_foul_all", "fouls_knockout",
    "exp_susp_per_foul_knockout",
)


def _number(value: str | int | float | None) -> str:
    if value in ("", None):
        return ""
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


def _bar_svg(
    path: Path,
    title: str,
    subtitle: str,
    rows: list[tuple[str, float]],
    *,
    zero_centered: bool,
    axis_label: str,
) -> None:
    width = 1120
    left, right, top, row_height, bottom = 380, 90, 116, 28, 72
    height = top + row_height * len(rows) + bottom
    plot_width = width - left - right
    values = [value for _, value in rows]
    if zero_centered:
        # Pad the numerical domain so end labels remain inside the canvas and
        # do not collide with long match labels at the left plot edge.
        bound = 1.18 * max([abs(value) for value in values] + [1.0])
        scale_min, scale_max = -bound, bound
    else:
        scale_min, scale_max = 0.0, 1.14 * max(values + [1.0])

    def x(value: float) -> float:
        return left + (value - scale_min) / (scale_max - scale_min) * plot_width

    axis_x = x(0.0)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title>',
        f'<desc id="desc">{escape(subtitle)}</desc>',
        f'<rect width="{width}" height="{height}" fill="#fbfaf7"/>',
        f'<text x="36" y="44" font-family="Arial, sans-serif" font-size="24" '
        f'font-weight="700" fill="#162434">{escape(title)}</text>',
        f'<text x="36" y="76" font-family="Arial, sans-serif" font-size="14" '
        f'fill="#4e5b68">{escape(subtitle)}</text>',
        f'<line x1="{axis_x:.2f}" y1="{top - 18}" x2="{axis_x:.2f}" '
        f'y2="{top + row_height * len(rows)}" stroke="#687683" stroke-width="1"/>',
    ]
    for index, (label, value) in enumerate(rows):
        y = top + index * row_height
        bar_start, bar_end = sorted((axis_x, x(value)))
        bar_width = max(1.0, bar_end - bar_start)
        color = "#2f718c" if value >= 0 else "#b65b4f"
        label_value = _number(value)
        parts.extend([
            f'<text x="{left - 12}" y="{y + 17}" text-anchor="end" '
            f'font-family="Arial, sans-serif" font-size="13" fill="#263747">{escape(label)}</text>',
            f'<rect x="{bar_start:.2f}" y="{y + 4}" width="{bar_width:.2f}" height="17" '
            f'rx="2" fill="{color}"/>',
            f'<text x="{(bar_end + 7 if value >= 0 else bar_start - 7):.2f}" y="{y + 17}" '
            f'text-anchor="{"start" if value >= 0 else "end"}" '
            f'font-family="Arial, sans-serif" font-size="12" fill="#263747">{label_value}</text>',
        ])
    parts.extend([
        f'<text x="{width / 2:.0f}" y="{height - 30}" text-anchor="middle" '
        f'font-family="Arial, sans-serif" font-size="13" fill="#4e5b68">{escape(axis_label)}</text>',
        '</svg>',
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _winner_match_rows(
    build: dict, edition: int, sort_field: str = "d_exp_match"
) -> list[dict]:
    """Select one winner-perspective row per knockout match, high to low."""
    if sort_field not in {"d_exp_match", "d_exp_match_per_foul"}:
        raise ValueError(f"unsupported winner-perspective sort field: {sort_field}")
    winners = {
        int(row["match_number"]): row["winner_team_id"]
        for row in build["source"]["matches"]
        if int(row["edition"]) == edition
        and row["stage"] not in {"group", "third_place"}
    }
    missing = sorted(number for number, team_id in winners.items() if not team_id)
    if missing:
        raise ValueError(f"{edition}: knockout matches lack winner IDs: {missing}")
    selected = [
        row for row in build["match"]
        if int(row["edition"]) == edition
        and int(row["match_number"]) in winners
        and row["team_id"] == winners[int(row["match_number"])]
    ]
    if len(selected) != len(winners):
        observed = {int(row["match_number"]) for row in selected}
        raise ValueError(
            f"{edition}: missing winner-perspective exposure rows for "
            f"{sorted(set(winners) - observed)}"
        )
    return sorted(
        selected,
        key=lambda row: (-float(row[sort_field]), int(row["match_number"])),
    )


def generate_figures(build: dict, figure_root: Path = FIGURES) -> list[Path]:
    """Create three official, fully spelled-out SVG figures per edition."""
    generated = []
    for edition in EDITIONS:
        team_rows = [
            row for row in build["teams"]
            if int(row["edition"]) == edition and row["primary_cohort"] == "yes"
        ]
        suspension = sorted(
            ((row["team"], float(row["exp_susp_per_foul_all"])) for row in team_rows),
            key=lambda item: (item[1], item[0]),
        )
        suspension_path = figure_root / str(edition) / "suspension-exposure-per-foul.svg"
        _bar_svg(
            suspension_path,
            f"{edition} World Cup: suspension exposure per foul",
            "Knockout-stage teams; primary rho = 2, mu = 1.25; all-tournament foul denominator.",
            suspension,
            zero_centered=False,
            axis_label="Suspension-exposure minutes per foul (descriptive; not a causal estimate)",
        )
        generated.append(suspension_path)

        match_rows = _winner_match_rows(build, edition)
        match_delta = [
            (
                f"M{int(row['match_number'])} {row['team']} vs {row['opponent']}",
                float(row["d_exp_match"]),
            )
            for row in match_rows
        ]
        match_path = figure_root / str(edition) / "knockout-match-exposure-difference.svg"
        _bar_svg(
            match_path,
            f"{edition} World Cup: winner-perspective knockout ΔE_m",
            "Winner minus opponent; sorted high to low; primary dismissal multiplier rho = 2.",
            match_delta,
            zero_centered=True,
            axis_label="Winner-perspective ΔE_m in minutes (descriptive; not a causal estimate)",
        )
        generated.append(match_path)

        prime_rows = _winner_match_rows(build, edition, "d_exp_match_per_foul")
        prime_delta = [
            (
                f"M{int(row['match_number'])} {row['team']} vs {row['opponent']}",
                float(row["d_exp_match_per_foul"]),
            )
            for row in prime_rows
        ]
        prime_path = (
            figure_root / str(edition)
            / "knockout-match-exposure-per-foul-difference.svg"
        )
        _bar_svg(
            prime_path,
            f"{edition} World Cup: winner-perspective knockout ΔE_m′",
            "Winner E_m/fouls minus opponent E_m/fouls; sorted high to low; rho = 2.",
            prime_delta,
            zero_centered=True,
            axis_label=(
                "Winner-perspective ΔE_m′ in minutes per foul "
                "(descriptive; not a causal estimate)"
            ),
        )
        generated.append(prime_path)
    return generated


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    # Source-audit values use ``|`` to separate team perspectives. Escape it
    # here so those values remain inside one Markdown table cell.
    def cell(value: str) -> str:
        return str(value).replace("|", r"\|").replace("\n", "<br>")

    lines = [
        "| " + " | ".join(cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def generate_results(build: dict, path: Path = ROOT / "docs" / "RESULTS.md") -> Path:
    summaries = build["summaries"]
    sensitivity = build["sensitivity"]
    summary_rows = [
        [
            str(row["edition"]), str(row["included_matches"]), str(row["player_cards"]),
            str(row["in_play_player_cards"]), str(row["team_fouls"]),
            str(row["knockout_teams"]), str(row["served_suspension_matches"]),
            str(row["deferred_suspensions"]), str(row["suspension_conflicts"]),
            _number(row["pooled_exp_susp_per_foul"]),
        ]
        for row in summaries
    ]
    sensitivity_rows = []
    for edition in EDITIONS:
        all_denominator = [
            float(row["pooled_exp_susp_per_foul"]) for row in sensitivity
            if int(row["edition"]) == edition and row["denominator"] == "all"
        ]
        knockout_denominator = [
            float(row["pooled_exp_susp_per_foul"]) for row in sensitivity
            if int(row["edition"]) == edition and row["denominator"] == "knockout"
        ]
        sensitivity_rows.append([
            str(edition),
            f"{min(all_denominator):.3f}–{max(all_denominator):.3f}",
            f"{min(knockout_denominator):.3f}–{max(knockout_denominator):.3f}",
        ])
    clock_rows = {
        (int(row["edition"]), row["clock_variant"]): row
        for row in build["suspension_clock_sensitivity"] if row["denominator"] == "all"
    }
    independent_checks = read_csv(ROOT / "data" / "sources" / "independent-match-checks.csv")
    independent_table = _markdown_table(
        ["Edition", "Match", "Field", "Primary", "Independent", "Status", "Source"],
        [
            [
                row["edition"], f"M{int(row['match_number'])}", row["field"],
                row["primary_value"], row["independent_value"], row["status"],
                f"[link]({row['independent_source_url']})",
            ]
            for row in independent_checks
        ],
    )
    detailed_sections = []
    for edition in EDITIONS:
        summary = next(row for row in summaries if int(row["edition"]) == edition)
        matches = _winner_match_rows(build, edition)
        match_table = _markdown_table(
            ["Match", "Stage", "Winner", "Opponent", "E_m", "Opponent E_m", "Delta E_m", "e_m", "Opponent e_m", "Delta e_m"],
            [
                [
                    f"M{int(row['match_number'])}", row["stage"].replace("_", " "),
                    row["team"], row["opponent"], _number(row["exp_match_min"]),
                    _number(row["opponent_exp_match_min"]), _number(row["d_exp_match"]),
                    _number(row["exp_match_per_foul"]),
                    _number(row["opponent_exp_match_per_foul"]),
                    _number(row["d_exp_match_per_foul"]),
                ]
                for row in matches
            ],
        )
        prime_matches = _winner_match_rows(
            build, edition, "d_exp_match_per_foul"
        )
        prime_match_table = _markdown_table(
            [
                "Match", "Winner", "Opponent", "Winner E_m/fouls",
                "Opponent E_m/fouls", "Delta E_m prime",
            ],
            [
                [
                    f"M{int(row['match_number'])}", row["team"], row["opponent"],
                    _number(row["exp_match_per_foul"]),
                    _number(row["opponent_exp_match_per_foul"]),
                    _number(row["d_exp_match_per_foul"]),
                ]
                for row in prime_matches
            ],
        )
        teams = sorted(
            (
                row for row in build["teams"]
                if int(row["edition"]) == edition and row["primary_cohort"] == "yes"
            ),
            key=lambda row: (-float(row["exp_susp_per_foul_all"]), row["team"]),
        )
        team_table = _markdown_table(
            ["Rank", "Team", "Exposed players", "Mean omega", "E_s", "All fouls", "e_s", "Knockout fouls", "Knockout-foul rate"],
            [
                [
                    str(rank), row["team"], str(row["exposed_players"]),
                    _number(row["mean_omega"]), _number(row["exp_susp_min"]),
                    str(row["fouls_all"]), _number(row["exp_susp_per_foul_all"]),
                    str(row["fouls_knockout"]), _number(row["exp_susp_per_foul_knockout"]),
                ]
                for rank, row in enumerate(teams, start=1)
            ],
        )
        source_clock = clock_rows[(edition, "source_end")]
        minus_one = clock_rows[(edition, "end_minus_one")]
        detailed_sections.append(f"""## {edition}

Primary pooled suspension exposure per foul is
`{_number(summary['pooled_exp_susp_per_foul'])}`. Under the `T_end - 1`
clock variant it is `{_number(minus_one['pooled_exp_susp_per_foul'])}` versus
`{_number(source_clock['pooled_exp_susp_per_foul'])}` under the source end clock.

### Knockout match ledger

Every fixture uses the FIFA-recorded winner's perspective and is ordered by
`Delta E_m` from highest to lowest. Reversing the teams reverses both
differences exactly. The third-place fixture is outside the match-exposure
scope and is not listed.

{match_table}

### Winner-perspective foul-normalized match ranking

`Delta E_m prime` is winner `E_m / match fouls` minus opponent
`E_m / match fouls`. It is the same numerical quantity as the methodology's
`Delta e_m`; the already normalized value is not divided a second time.

{prime_match_table}

### Knockout-team suspension-exposure ranking

Ranking is by the primary all-tournament-foul rate `e_s`. `Mean omega` is the
mean opportunity weight among the team's players with positive sanction
minutes; a blank means no player carried a positive term.

{team_table}
""")

    decisions = {}
    for row in build["suspensions"]:
        if not row["decision_type"]:
            continue
        key = (
            int(row["edition"]), row["team"], row["player"], row["decision_type"],
            row["decision_source_url"], row["decision_note"],
        )
        item = decisions.setdefault(key, {"matches": [], "statuses": set()})
        if row["service_match_number"]:
            item["matches"].append(int(row["service_match_number"]))
        item["statuses"].add(row["service_status"])
    decision_text = "\n".join(
        f"- {edition} {player} ({team}), `{decision_type}`: "
        f"service match(es) {', '.join(f'M{number}' for number in sorted(set(item['matches'])))}; "
        f"status {', '.join(sorted(item['statuses']))}. {note} [Source]({source_url})"
        for (edition, team, player, decision_type, source_url, note), item in sorted(decisions.items())
    ) or "- None."
    conflicts = [row for row in build["suspensions"] if row["service_status"] == "conflict"]
    conflict_text = "\n".join(
        f"- {row['edition']} {row['player']} ({row['team']}), trigger "
        f"M{row['trigger_match_number']}: {row['audit_note']}"
        for row in conflicts
    ) or "- None."
    depth_table = _markdown_table(
        ["Edition", "Status", "Teams", "Kendall tau-b", "Permutation p", "Note"],
        [
            [
                str(row["edition"]), row["edition_status"], str(row["teams"]),
                _number(row["tau_b"]), _number(row["p_permutation"]),
                row["note"] or "—",
            ]
            for row in build["depth"]
        ],
    )
    text = f"""# Results — methodology v0.2.1

Generated by `python3 -m pipeline.build_all --from-derived`. These are
descriptive sanction-exposure quantities, not estimates of referee intent,
fairness, team quality, or causal effects.

## Primary snapshot

Primary parameters are `rho = 2`, `mu = 1.25`, the knockout-team cohort, and
the all-tournament team-foul denominator. The pooled value is
`sum(E_s) / sum(fouls)`; it is not the mean of team ratios.

{_markdown_table(
    ["Edition", "Matches", "Player cards", "In-play cards", "Team fouls", "Knockout teams", "Served bans", "Deferred", "Conflicts", "Pooled suspension exposure per foul"],
    summary_rows,
)}

The table is an edition-by-edition inventory. Differences between editions
are not interpreted as treatment effects because tournament format, match
mix, referee assignment, team behaviour, and the 2026 cutoff differ.

## Prespecified sensitivity

Ranges below cover every combination of `rho in {{1, 1.5, 2}}` and
`mu in {{1, 1.25, 1.5}}`. The two denominator choices are reported separately.

{_markdown_table(
    ["Edition", "All-tournament fouls", "Knockout-only fouls"], sensitivity_rows
)}

The complete 72-row grid is in
`data/derived/results/suspension-sensitivity.csv`. Match-level sensitivity for
all three dismissal multipliers is in
`data/derived/results/match-exposure-sensitivity.csv`. The end-clock boundary
check is published in `match-end-clock-sensitivity.csv` and
`suspension-end-clock-sensitivity.csv`; it replaces `T_end` with `T_end - 1`
only in components that use the observed final whistle clock.

## Prespecified depth check (methodology §5.1)

Kendall `tau-b` between an edition's knockout-team depth (matches played,
excluding the third-place match, so losing semi-finalists and finalists
differ) and the primary `e_s`, with a within-edition two-sided permutation
`p` (10,000 permutations, seed 20260713). Editions are never pooled. This is
a descriptive check of mechanical drift with tournament depth; depth is
partly endogenous to discipline itself, so the coefficient is not a causal
strength estimate.

{depth_table}

The full table is `data/derived/results/depth-check.csv`. The prespecified
Elo variant of this check awaits the archived pre-tournament rating table and
is not yet computed.

## Independent match-page audit

One match per edition was checked against ESPN or Opta. `AUDIT` means the
sources use different display conventions; the difference remains published
and the declared primary source is not silently overwritten.

{independent_table}

## Documented disciplinary decisions

{decision_text}

These rows override the automatic one-next-match default only where the
decision source names the service matches or formally defers execution. Every
claimed served match is still checked against the official lineup.

## Source conflicts

{conflict_text}

Pending sanctions after a team's last observed match are recorded in
`data/derived/stages/s4-suspensions.csv` but do not create served minutes.
The 2026 build contains M1–M100 only.

## Official figures

Each edition has three SVGs under `figures/official/<edition>/`:

- `suspension-exposure-per-foul.svg`;
- `knockout-match-exposure-difference.svg`;
- `knockout-match-exposure-per-foul-difference.svg`.

The knockout `Delta E_m` figure uses the FIFA-recorded winner's perspective
for every fixture, including matches settled by penalties, and sorts the
winner-minus-opponent values from highest to lowest.

The per-foul figure reports `Delta E_m prime`, defined as winner `E_m` divided
by the winner's match fouls minus opponent `E_m` divided by the opponent's
match fouls. This is numerically identical to `Delta e_m` in the frozen
methodology and is not a second normalization.

The nine earlier images remain under `figures/draft-2026-07/` and are not v0.2
results.

{''.join(detailed_sections)}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def generate_edition_results(build: dict, result_root: Path = RESULTS) -> list[Path]:
    """Write one filterable primary team-ranking table per edition."""
    paths = []
    for edition in EDITIONS:
        teams = sorted(
            (
                row for row in build["teams"]
                if int(row["edition"]) == edition and row["primary_cohort"] == "yes"
            ),
            key=lambda row: (-float(row["exp_susp_per_foul_all"]), row["team"]),
        )
        rows = [
            {
                "rank": rank, "edition": edition,
                **{field: row[field] for field in EDITION_RESULT_FIELDS if field not in {"rank", "edition"}},
            }
            for rank, row in enumerate(teams, start=1)
        ]
        output = result_root / f"results_{edition}.csv"
        write_csv(output, rows, EDITION_RESULT_FIELDS)
        paths.append(output)
    return paths


def generate_injury_evidence(build: dict, path: Path = ROOT / "data" / "sources" / "injury-evidence.md") -> Path:
    rows = build["source"]["availability_evidence"]
    lines = [
        "# Injury and illness evidence audit", "",
        "Only documented positive intervals enter `I_p`. A substitution without explicit evidence is not coded as injury.", "",
        "| Edition | Match | Team | Player | Interval | Tier | Evidence note | Source |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        note = row["evidence_note"].replace("|", "\\|")
        source = f"[link]({row['source_url']})"
        lines.append(
            f"| {row['edition']} | M{int(row['match_number'])} | {row['team']} | {row['player']} | "
            f"{_number(row['start_minute'])}–{_number(row['end_minute'])} | {row['evidence_tier']} | {note} | {source} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def generate_reports(build: dict) -> list[Path]:
    paths = generate_figures(build)
    paths.extend(generate_edition_results(build))
    paths.append(generate_results(build))
    paths.append(generate_injury_evidence(build))
    return paths
