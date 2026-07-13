#!/usr/bin/env python3
"""Per-edition long summary images (presentation layer, not in the CI gate).

Reads the committed v0.2.1 result CSVs, writes one self-contained HTML page
per edition, then screenshots each with headless Chrome at exact content
height (two passes: measure via --dump-dom, then capture at 2x).
"""

from __future__ import annotations

import csv
import html
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "figures" / "summary"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WIDTH = 1240

# Validated palette (dataviz reference instance, light mode)
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"
SURFACE = "#fcfcfb"
PLANE = "#f9f9f7"
BORDER = "rgba(11,11,11,0.10)"
BLUE = "#2a78d6"      # series-1 / diverging cool pole
RED = "#e34948"       # diverging warm pole

STAGE_SHORT = {
    "round_of_32": "R32", "round_of_16": "R16", "quarter_final": "QF",
    "semi_final": "SF", "final": "Final",
}
EDITION_HOSTS = {2014: "Brazil", 2018: "Russia", 2022: "Qatar",
                 2026: "Canada / Mexico / United States"}


def read(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load():
    results = REPO / "data" / "derived" / "results"
    return {
        "teams": read(results / "team-suspension-exposure.csv"),
        "players": read(results / "player-suspension-exposure.csv"),
        "match": read(results / "match-exposure.csv"),
        "summary": read(results / "edition-summary.csv"),
        "depth": read(results / "depth-check.csv"),
        "matches": read(REPO / "data" / "derived" / "source" / "matches.csv"),
    }


def esc(value):
    return html.escape(str(value))


def fmt(value, digits=2):
    return f"{float(value):.{digits}f}"


def winner_rows(data, edition, field):
    winners = {
        int(row["match_number"]): row["winner_team_id"]
        for row in data["matches"]
        if int(row["edition"]) == edition
        and row["stage"] not in {"group", "third_place"}
    }
    rows = [
        row for row in data["match"]
        if int(row["edition"]) == edition
        and winners.get(int(row["match_number"])) == row["team_id"]
    ]
    rows.sort(key=lambda row: (-float(row[field]), int(row["match_number"])))
    return rows


def bar_block(label_html, value, vmax, color=BLUE, label_width=270):
    width_pct = 0.0 if vmax == 0 else max(0.0, float(value)) / vmax * 92
    return f"""
<div class="row">
  <div class="rlabel" style="width:{label_width}px">{label_html}</div>
  <div class="rtrack">
    <div class="rbar" style="width:{width_pct:.3f}%;background:{color}"></div>
    <span class="rval" style="left:calc({width_pct:.3f}% + 8px)">{fmt(value)}</span>
  </div>
</div>"""


def diverging_block(label_html, value, vmax, label_width=330):
    value = float(value)
    half_pct = 0.0 if vmax == 0 else abs(value) / vmax * 45
    color = BLUE if value >= 0 else RED
    side = "left:50%" if value >= 0 else f"left:{50 - half_pct:.3f}%"
    radius = "0 4px 4px 0" if value >= 0 else "4px 0 0 4px"
    # A tip label that would leave the track moves inside the bar (white ink).
    if half_pct > 36:
        val_pos = (
            f"left:calc(50% + {half_pct:.3f}% - 8px);transform:translateX(-100%);color:#fff"
            if value >= 0
            else f"left:calc(50% - {half_pct:.3f}% + 8px);color:#fff"
        )
    else:
        val_pos = (
            f"left:calc(50% + {half_pct:.3f}% + 8px)" if value >= 0
            else f"right:calc(50% + {half_pct:.3f}% + 8px)"
        )
    return f"""
<div class="row">
  <div class="rlabel" style="width:{label_width}px">{label_html}</div>
  <div class="rtrack dtrack">
    <div class="dmid"></div>
    <div class="dbar" style="{side};width:{half_pct:.3f}%;background:{color};border-radius:{radius}"></div>
    <span class="dval" style="{val_pos}">{fmt(value, 1)}</span>
  </div>
</div>"""


def tile(label, value, sub=""):
    sub_html = f'<div class="tsub">{sub}</div>' if sub else ""
    return f"""
<div class="tile">
  <div class="tlabel">{label}</div>
  <div class="tvalue">{value}</div>
  {sub_html}
</div>"""


def page(data, edition):
    year = str(edition)
    summary = next(r for r in data["summary"] if r["edition"] == year)
    depth = next(r for r in data["depth"] if r["edition"] == year)
    teams = sorted(
        (r for r in data["teams"]
         if r["edition"] == year and r["primary_cohort"] == "yes"),
        key=lambda r: -float(r["exp_susp_per_foul_all"]),
    )
    served_ko = sum(
        int(r["served_suspension_matches"]) for r in data["players"]
        if r["edition"] == year
    )
    delta_rows = winner_rows(data, edition, "d_exp_match")
    prime_rows = winner_rows(data, edition, "d_exp_match_per_foul")

    provisional = edition == 2026
    scope_badge = (
        '<span class="badge">PROVISIONAL · through M100 · 截至 M100</span>'
        if provisional else '<span class="badge ok">COMPLETE · 全赛事</span>'
    )

    team_max = max(float(r["exp_susp_per_foul_all"]) for r in teams)
    team_bars = "".join(
        bar_block(
            (f"<b>{esc(r['team'])}</b>" if r["team"] == "Argentina"
             else esc(r["team"]))
            + f'<span class="rk">#{i}</span>',
            r["exp_susp_per_foul_all"], team_max,
        )
        for i, r in enumerate(teams, 1)
    )

    dmax = max(abs(float(r["d_exp_match"])) for r in delta_rows)
    delta_bars = "".join(
        diverging_block(
            f'M{int(r["match_number"])} <span class="st">{STAGE_SHORT[r["stage"]]}</span> '
            f"{esc(r['team'])} <span class='vs'>v</span> {esc(r['opponent'])}",
            r["d_exp_match"], dmax,
        )
        for r in delta_rows
    )
    pmax = max(abs(float(r["d_exp_match_per_foul"])) for r in prime_rows)
    prime_bars = "".join(
        diverging_block(
            f'M{int(r["match_number"])} <span class="st">{STAGE_SHORT[r["stage"]]}</span> '
            f"{esc(r['team'])} <span class='vs'>v</span> {esc(r['opponent'])}",
            r["d_exp_match_per_foul"], pmax,
        )
        for r in prime_rows
    )

    depth_p = fmt(depth["p_permutation"], 4)
    tiles = "".join([
        tile("Pooled e_s per foul · 每犯规合并禁赛暴露",
             fmt(summary["pooled_exp_susp_per_foul"]),
             "Σ E_s ÷ Σ fouls · ρ=2, μ=1.25"),
        tile("Knockout teams · 淘汰赛球队",
             summary["knockout_teams"],
             f'{summary["included_matches"]} matches included'),
        tile("Player cards · 球员牌",
             summary["player_cards"],
             f'{summary["in_play_player_cards"]} shown in play'),
        tile("Served bans in knockout · 淘汰赛服刑场次",
             str(served_ko), "group-stage service excluded"),
        tile("Depth check τ_b · 深度检查",
             fmt(depth["tau_b"], 3),
             f"permutation p = {depth_p} · n = {depth['teams']}"),
    ])

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{WIDTH}px; background:{PLANE}; color:{INK};
  font-family:system-ui,-apple-system,"Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif;
  padding:28px; }}
.card {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:12px;
  padding:26px 30px; margin-bottom:18px; }}
.eyebrow {{ font-size:12px; letter-spacing:.14em; color:{MUTED};
  text-transform:uppercase; margin-bottom:8px; }}
h1 {{ font-size:30px; font-weight:700; letter-spacing:-.01em; }}
.subtitle {{ font-size:15px; color:{INK2}; margin-top:6px; }}
.meta {{ font-size:12.5px; color:{MUTED}; margin-top:12px; line-height:1.6; }}
.badge {{ display:inline-block; font-size:11px; letter-spacing:.08em;
  border:1px solid {BORDER}; color:{INK2}; border-radius:999px;
  padding:3px 10px; margin-left:10px; vertical-align:2px; }}
.badge.ok {{ color:{INK2}; }}
.tiles {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; }}
.tile {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:12px;
  padding:16px 18px; }}
.tlabel {{ font-size:11.5px; color:{INK2}; line-height:1.45; min-height:32px; }}
.tvalue {{ font-size:30px; font-weight:600; margin-top:6px; }}
.tsub {{ font-size:11px; color:{MUTED}; margin-top:5px; line-height:1.4; }}
h2 {{ font-size:17px; font-weight:650; }}
.chartsub {{ font-size:12.5px; color:{INK2}; margin:5px 0 18px; line-height:1.55; }}
.key {{ display:inline-block; width:10px; height:10px; border-radius:2px;
  vertical-align:-1px; margin:0 4px 0 10px; }}
.row {{ display:flex; align-items:center; height:26px; }}
.rlabel {{ flex:none; font-size:12.5px; color:{INK}; text-align:right;
  padding-right:12px; white-space:nowrap; overflow:visible; }}
.rk {{ color:{MUTED}; font-size:11px; margin-left:6px; }}
.st {{ color:{MUTED}; font-size:11px; }}
.vs {{ color:{MUTED}; }}
.rtrack {{ flex:1; position:relative; height:22px;
  border-left:1px solid {BASE}; }}
.rbar {{ position:absolute; top:2px; height:18px;
  border-radius:0 4px 4px 0; }}
.rval {{ position:absolute; top:3px; font-size:11.5px; color:{INK2}; }}
.dtrack {{ border-left:none; }}
.dmid {{ position:absolute; left:50%; top:-2px; bottom:-2px; width:1px;
  background:{BASE}; }}
.dbar {{ position:absolute; top:2px; height:18px; }}
.dval {{ position:absolute; top:3px; font-size:11.5px; color:{INK2}; }}
.axisnote {{ font-size:11.5px; color:{MUTED}; margin-top:12px; }}
.foot {{ font-size:12px; color:{INK2}; line-height:1.75; }}
.foot b {{ color:{INK}; }}
.foot ul {{ margin:8px 0 12px 18px; }}
.prov {{ font-size:11px; color:{MUTED}; border-top:1px solid {GRID};
  padding-top:12px; margin-top:12px; line-height:1.7; }}
</style></head><body>

<div class="card">
  <div class="eyebrow">Eye of Poirot · sanction-exposure summary · 制裁暴露摘要</div>
  <h1>{year} FIFA World Cup <span style="color:{INK2};font-weight:500">— {esc(EDITION_HOSTS[edition])}</span>{scope_badge}</h1>
  <div class="subtitle">每张球员牌折算为"制裁暴露分钟"；停赛暴露只计对淘汰赛的影响。Methodology v0.2.1, frozen 2026-07-13 before M101.</div>
  <div class="meta">Primary parameters ρ = 2 (dismissal), μ = 1.25 (served suspension) · denominator = all tournament fouls excluding the third-place match · third-place events excluded · descriptive only, no causal claim · 描述性统计，不构成因果或裁判意图结论</div>
</div>

<div class="tiles" style="margin-bottom:18px">{tiles}</div>

<div class="card">
  <h2>Knockout-team suspension exposure per foul (e_s) · 各队每犯规禁赛暴露</h2>
  <div class="chartsub">ω-weighted sanction minutes ÷ all tournament fouls (excl. third place), knockout teams only, ranked. Group cards enter only as 2014–2022 carried-in cautions.</div>
  {team_bars}
  <div class="axisnote">minutes per foul · e_s = Σ_p ω_p · X_s(p) ÷ F_i</div>
</div>

<div class="card">
  <h2>Winner-perspective in-match exposure differential (ΔE_m) · 胜者视角场内暴露差</h2>
  <div class="chartsub">Exact-clock exposure minutes, winner minus opponent, per knockout match (third place excluded), sorted high to low.
  <span class="key" style="background:{BLUE}"></span>winner carried more · 胜者暴露更多
  <span class="key" style="background:{RED}"></span>opponent carried more · 负者暴露更多</div>
  {delta_bars}
  <div class="axisnote">ΔE_m in minutes · reversing the teams reverses the sign exactly (antisymmetric)</div>
</div>

<div class="card">
  <h2>Winner-perspective per-foul differential (Δe_m) · 胜者视角每犯规暴露差</h2>
  <div class="chartsub">Winner E_m/fouls minus opponent E_m/fouls — the methodology's Δe_m, winner-oriented for presentation.
  <span class="key" style="background:{BLUE}"></span>winner higher
  <span class="key" style="background:{RED}"></span>opponent higher</div>
  {prime_bars}
  <div class="axisnote">Δe_m in minutes per foul</div>
</div>

<div class="card foot">
  <b>Frozen rules in one breath · 冻结口径一览</b>
  <ul>
    <li>Suspension exposure prices knockout impact only: a pending 2014–2022 group caution enters as if shown at minute 0 of the first knockout match (180 at a round of 16); 2026 group cautions never carry. 停赛暴露只计淘汰赛影响。</li>
    <li>A suspension-causing card stops the earlier caution's interval at minute granularity; service counts only in knockout matches. 分钟级停止；仅淘汰赛服刑计入 μ·90。</li>
    <li>Stoppage/extra-time and all semi-final/final cautions price the exact clock T_end − t. 补时/加时与半决赛决赛黄牌用精确钟。</li>
    <li>The third-place match is excluded at the event level; suspensions served there still count. 三四名决赛事件层排除。</li>
    <li>Depth check (per edition, never pooled): Kendall τ_b = {fmt(depth["tau_b"], 3)}, permutation p = {depth_p} (10,000 permutations, seed 20260713), depth = matches played excl. third place{" — provisional at the M100 cutoff" if provisional else ""}. 深度为描述性混杂检查，非实力因果估计。</li>
  </ul>
  <div class="prov">Eye of Poirot · Methodology v0.2.1 (frozen 2026-07-13, before 2026 M101; five pre-registration revisions disclosed in AMENDMENTS.md) · repo commit 411d419 · data: FIFA event feeds; 2014 T_end via archived FotMob periods; 2014 fouls via archived HuffPost/Opta · CC BY 4.0 documentation &amp; figures, MIT code · Chen Siyuan · github.com/AuroreYoshizawa/EyeOfPoirot · OSF registration DOI pending</div>
</div>

<script>document.documentElement.dataset.h = String(document.body.scrollHeight);</script>
</body></html>"""


def render(edition, html_text):
    html_path = OUT / f"summary-{edition}.html"
    html_path.write_text(html_text, encoding="utf-8")
    url = html_path.as_uri()
    dump = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={WIDTH},900", "--virtual-time-budget=2000",
         "--dump-dom", url],
        capture_output=True, text=True, check=True,
    ).stdout
    match = re.search(r'data-h="(\d+)"', dump)
    if not match:
        raise RuntimeError(f"no measured height for {edition}")
    height = int(match.group(1))
    png = OUT / f"summary-{edition}.png"
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={WIDTH},{height}", "--force-device-scale-factor=2",
         f"--screenshot={png}", url],
        capture_output=True, text=True, check=True,
    )
    print(f"{edition}: {height}px -> {png.name}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = load()
    for edition in (2014, 2018, 2022, 2026):
        render(edition, page(data, edition))


if __name__ == "__main__":
    main()
