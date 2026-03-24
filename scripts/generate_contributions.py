#!/usr/bin/env python3
"""Generate a dark-themed GitHub contribution graph SVG for a specific year."""

import json
import urllib.request
import sys
import os
from datetime import date, timedelta

USERNAME = os.environ.get("GITHUB_USERNAME", "CryptoPilot16")
YEAR = int(os.environ.get("CONTRIB_YEAR", "2026"))
TOKEN = os.environ.get("GH_TOKEN", "")

# GitHub GraphQL query for contributions
QUERY = """
query($username: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $username) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            color
          }
        }
      }
    }
  }
}
"""

def fetch_contributions():
    variables = {
        "username": USERNAME,
        "from": f"{YEAR}-01-01T00:00:00Z",
        "to": f"{YEAR}-12-31T23:59:59Z",
    }
    body = json.dumps({"query": QUERY, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "contribution-graph-generator",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def color_for_count(count):
    """GitHub-green palette on dark background."""
    if count == 0:
        return "#161b22"  # dark empty cell
    elif count <= 3:
        return "#0e4429"
    elif count <= 6:
        return "#006d32"
    elif count <= 9:
        return "#26a641"
    else:
        return "#39d353"


def generate_svg(calendar):
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    cell = 28
    gap = 5
    size = cell + gap
    margin_left = 65
    margin_top = 55
    margin_bottom = 80

    width = margin_left + len(weeks) * size + 10
    height = margin_top + 7 * size + margin_bottom

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%">')
    lines.append(f'<rect width="{width}" height="{height}" fill="#0d1117" rx="6"/>')

    # Month labels
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_positions = {}
    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            d = date.fromisoformat(day["date"])
            if d.day <= 7 and d.month not in month_positions:
                month_positions[d.month] = wi

    for month_num, wi in month_positions.items():
        x = margin_left + wi * size
        lines.append(f'<text x="{x}" y="{margin_top - 16}" fill="#8b949e" '
                      f'font-family="monospace" font-size="28">{months[month_num - 1]}</text>')

    # Day labels
    day_labels = ["", "Mon", "", "Wed", "", "Fri", ""]
    for di, label in enumerate(day_labels):
        if label:
            y = margin_top + di * size + cell - 2
            lines.append(f'<text x="2" y="{y}" fill="#8b949e" '
                          f'font-family="monospace" font-size="16">{label}</text>')

    # Cells
    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            d = date.fromisoformat(day["date"])
            di = d.weekday()  # 0=Mon
            # GitHub uses Sun=0, but Python weekday is Mon=0
            # Remap: Sun=top row (0), Mon=1, ..., Sat=6
            row = (d.weekday() + 1) % 7
            x = margin_left + wi * size
            y = margin_top + row * size
            color = color_for_count(day["contributionCount"])
            count = day["contributionCount"]
            lines.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                          f'rx="2" fill="{color}">'
                          f'<title>{day["date"]}: {count} contribution{"s" if count != 1 else ""}</title>'
                          f'</rect>')

    # Count days with data (up to today)
    today = date.today()
    days_elapsed = 0
    for week in weeks:
        for day in week["contributionDays"]:
            d = date.fromisoformat(day["date"])
            if d <= today:
                days_elapsed += 1
    daily_avg = total / max(days_elapsed, 1)

    # Total + daily average label
    lines.append(f'<text x="{margin_left}" y="{height - 14}" fill="#40c463" '
                  f'font-family="monospace" font-size="28" font-weight="bold">'
                  f'{total} contributions in {YEAR}'
                  f'</text>')
    lines.append(f'<text x="{width - 10}" y="{height - 14}" fill="#40c463" '
                  f'font-family="monospace" font-size="28" font-weight="bold" text-anchor="end">'
                  f'{daily_avg:.1f} / day avg'
                  f'</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def main():
    calendar = fetch_contributions()
    svg = generate_svg(calendar)
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "contributions.svg")
    with open(out, "w") as f:
        f.write(svg)
    print(f"Generated {out} — {calendar['totalContributions']} contributions in {YEAR}")


if __name__ == "__main__":
    main()
