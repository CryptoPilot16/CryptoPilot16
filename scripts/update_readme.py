#!/usr/bin/env python3
"""Auto-update the projects table and tech stack in README.md using GitHub API."""

import json
import os
import re
import subprocess
import tempfile
import urllib.request

TOKEN = os.environ.get("GH_TOKEN", "")
USERNAME = os.environ.get("GITHUB_USERNAME", "CryptoPilot16")

# Project registry — emoji, description, and stack are manually curated; lines auto-counted.
# New repos not listed here are auto-discovered and appended with defaults.
PROJECTS = [
    {"repo": "pm-relay",          "emoji": "📊", "desc": "Multi-venue spread tracking and execution",         "stack": ["Python", "React", "Node.js", "Polygon"]},
    {"repo": "Tailwinds",         "emoji": "✈️",  "desc": "Flight data aggregation and alerting",              "stack": ["TypeScript", "Next.js", "Node.js"]},
    {"repo": "f1_analytics",      "emoji": "🏎️",  "desc": "F1 telemetry analysis and fantasy optimization",    "stack": ["JavaScript", "React"]},
    {"repo": "skybuddy",          "emoji": "🌍", "desc": "3D social flight tracker",                          "stack": ["JavaScript", "Cesium.js"]},
    {"repo": "TradingOdds",       "emoji": "🎯", "desc": "Prediction market execution layer",                 "stack": ["TypeScript"]},
    {"repo": "smartmoney-radar",  "emoji": "🔍", "desc": "On-chain wallet profiling and flow monitoring",     "stack": ["TypeScript"]},
    {"repo": "clawnux-v3",        "emoji": "🤖", "desc": "Multi-model coding agent",                          "stack": ["TypeScript"]},
    {"repo": "govdeals-platform", "emoji": "🏛️",  "desc": "Gov surplus property scraper with Zillow valuations", "stack": ["TypeScript", "Python", "Next.js"]},
    {"repo": "codex-control",     "emoji": "🖥️",  "desc": "Server provisioning and deployment toolkit",        "stack": ["Shell"]},
]

# Repos to never include (profile repo, forks, etc.)
IGNORE_REPOS = {USERNAME, USERNAME.lower(), ".github", "dotfiles"}

# Language → stack label mapping for auto-discovered repos
LANG_MAP = {
    "Python": "Python", "JavaScript": "JavaScript", "TypeScript": "TypeScript",
    "Shell": "Shell", "Go": "Go", "Rust": "Rust", "Java": "Java",
    "HTML": "HTML", "CSS": "CSS", "Vue": "Vue", "Svelte": "Svelte",
}

# File extensions to count
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".bash",
    ".css", ".html", ".json", ".sql", ".yml", ".yaml",
    ".rs", ".go", ".java", ".c", ".cpp", ".h",
    ".md", ".toml", ".cfg", ".ini", ".env",
    ".svelte", ".vue",
}

SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", ".next",
             "__pycache__", ".venv", "venv", "env", ".tox", "coverage",
             ".nyc_output", "target", "out"}


def gh_api(path):
    """Call GitHub API."""
    req = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "readme-updater",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  API error for {path}: {e}")
        return None


def count_lines(repo_name):
    """Clone repo shallow and count lines of code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        clone_url = f"https://x-access-token:{TOKEN}@github.com/{USERNAME}/{repo_name}.git"
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", clone_url, tmpdir + "/repo"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"  Clone failed for {repo_name}: {result.stderr.strip()}")
            return None

        total = 0
        repo_path = tmpdir + "/repo"
        for root, dirs, files in os.walk(repo_path):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            rel = os.path.relpath(root, repo_path)
            if any(s in rel for s in SKIP_DIRS):
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in CODE_EXTENSIONS:
                    try:
                        with open(os.path.join(root, f), "r", errors="ignore") as fh:
                            total += sum(1 for _ in fh)
                    except (OSError, UnicodeDecodeError):
                        pass
        return total


def format_lines(n):
    """Format line count: 1234 -> ~1K, 56789 -> ~57K."""
    if n is None:
        return "—"
    if n < 500:
        return f"~{n}"
    elif n < 1000:
        return f"~{round(n / 100) * 100}"
    else:
        k = round(n / 1000)
        return f"~{k}K"


def discover_repos():
    """Fetch all non-fork repos and merge with curated PROJECTS list."""
    known = {p["repo"].lower(): p for p in PROJECTS}
    merged = list(PROJECTS)  # start with curated order

    # Fetch all public repos from GitHub
    page = 1
    while True:
        data = gh_api(f"users/{USERNAME}/repos?per_page=100&page={page}&type=owner")
        if not data:
            break
        for r in data:
            name = r["name"]
            if r.get("fork") or name in IGNORE_REPOS or name.lower() in IGNORE_REPOS:
                continue
            if name.lower() not in known:
                # Auto-discover: derive stack from GitHub language
                lang = r.get("language") or ""
                stack = [LANG_MAP[lang]] if lang in LANG_MAP else [lang] if lang else ["—"]
                desc = (r.get("description") or "").strip() or name
                merged.append({
                    "repo": name,
                    "emoji": "📦",
                    "desc": desc[:60],
                    "stack": stack,
                })
                print(f"  [auto-discovered] {name} ({lang})")
        if len(data) < 100:
            break
        page += 1

    return merged


def build_projects_table(projects_data):
    """Build markdown table with emojis."""
    lines = ["| Project | Description | Stack | Lines |", "|---|---|---|---|"]
    for p in projects_data:
        stack_str = " ".join(f"`{s}`" for s in p["stack"])
        emoji = p.get("emoji", "📦")
        lines.append(f'| {emoji} **{p["repo"]}** | {p["desc"]} | {stack_str} | {p["lines_fmt"]} |')
    total = sum(p.get("lines_raw", 0) for p in projects_data)
    total_fmt = format_lines(total)
    lines.append(f'| | | **Total** | **{total_fmt}** |')
    return "\n".join(lines)


def update_readme(projects_data):
    """Replace projects table in README.md."""
    readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
    with open(readme_path, "r") as f:
        content = f.read()

    # Replace the projects table (between "### Projects" and the next --- or end)
    new_table = build_projects_table(projects_data)
    pattern = r"(\| Project \| Description \|.*?\n(?:\|.*\n)*)"
    content = re.sub(pattern, new_table + "\n", content)

    with open(readme_path, "w") as f:
        f.write(content)
    print(f"Updated {readme_path}")


def main():
    print(f"Updating projects for {USERNAME}...")
    all_projects = discover_repos()
    projects_data = []

    for p in all_projects:
        print(f"  {p['repo']}...", end=" ", flush=True)
        lines = count_lines(p["repo"])
        fmt = format_lines(lines)
        print(f"{fmt} lines")
        projects_data.append({
            "repo": p["repo"],
            "emoji": p.get("emoji", "📦"),
            "desc": p["desc"],
            "stack": p["stack"],
            "lines_fmt": fmt,
            "lines_raw": lines or 0,
        })

    update_readme(projects_data)
    print("Done.")


if __name__ == "__main__":
    main()
