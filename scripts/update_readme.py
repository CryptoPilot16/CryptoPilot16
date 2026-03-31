#!/usr/bin/env python3
"""Auto-update the projects table and tech stack in README.md using GitHub API."""

import json
import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request

TOKEN = os.environ.get("GH_TOKEN", "")
USERNAME = os.environ.get("GITHUB_USERNAME", "CryptoPilot16")

# Project registry — emoji, description, and stack are manually curated; lines auto-counted.
# New repos not listed here are auto-discovered and appended with defaults.
PROJECTS = [
    {"repo": "pm-relay",          "emoji": "📊", "desc": "Multi-venue spread tracking and execution",         "stack": ["Python", "Node.js", "Express", "React", "Playwright", "Polygon", "Claude API"]},
    {"repo": "Tailwinds",         "emoji": "✈️",  "desc": "Flight data aggregation and alerting",              "stack": ["TypeScript", "Next.js", "React", "Tailwind CSS", "Node.js", "Express", "PostgreSQL", "Stripe", "Twilio", "SendGrid"]},
    {"repo": "f1_analytics",      "emoji": "🏎️",  "desc": "F1 telemetry analysis and fantasy optimization",    "stack": ["JavaScript", "React", "Vite", "Node.js", "Express", "Puppeteer", "Claude API"]},
    {"repo": "skybuddy",          "emoji": "🌍", "desc": "3D social flight tracker",                          "stack": ["JavaScript", "Cesium.js", "Node.js", "Express", "PostgreSQL", "Playwright", "Claude API"]},
    {"repo": "TradingOdds",       "emoji": "🎯", "desc": "Prediction market execution layer",                 "stack": ["TypeScript", "Next.js", "React", "Tailwind CSS", "Node.js", "ethers.js", "Polygon", "Playwright", "Vitest"]},
    {"repo": "smartmoney-radar",  "emoji": "🔍", "desc": "On-chain wallet profiling and flow monitoring",     "stack": ["TypeScript", "Next.js", "React", "Tailwind CSS", "Node.js", "PostgreSQL", "ethers.js", "Solana", "Telegram"]},
    {"repo": "clawnux-v3",        "emoji": "🤖", "desc": "Multi-model coding agent",                          "stack": ["Shell", "Next.js", "PostgreSQL", "Claude Code", "Vercel", "Telegram"]},
    {"repo": "govdeals-platform", "emoji": "🏛️",  "desc": "Gov surplus property scraper with Zillow valuations", "stack": ["TypeScript", "Python", "Next.js", "React", "Tailwind CSS", "Node.js", "Express", "PostgreSQL", "Playwright", "Leaflet"]},
    {"repo": "codex-control",     "emoji": "🖥️",  "desc": "Server provisioning and deployment toolkit",        "stack": ["Shell", "Python", "tmux", "Tailscale", "Vercel", "Telegram"]},
    {"repo": "echoes",            "emoji": "👻", "desc": "Eternal Conversational Hologram Of Embedded Souls", "stack": ["TypeScript", "Python", "Next.js", "Tailwind CSS", "Three.js", "Node.js", "FastAPI", "PostgreSQL", "Ollama", "Whisper", "RunPod"]},
]

# Repos to never include (profile repo, forks, etc.)
IGNORE_REPOS = {USERNAME, USERNAME.lower(), ".github", "dotfiles"}

# Language → stack label mapping for auto-discovered repos
LANG_MAP = {
    "Python": "Python", "JavaScript": "JavaScript", "TypeScript": "TypeScript",
    "Shell": "Shell", "Go": "Go", "Rust": "Rust", "Java": "Java",
    "HTML": "HTML", "CSS": "CSS", "Vue": "Vue", "Svelte": "Svelte",
}

TECH_ROW_ORDER = ["Languages", "Frontend", "Backend", "Infra", "Web3", "AI", "Other"]

# Baseline badges we always show, plus dynamic additions from project stacks.
BASE_TECH_STACK = {
    "Languages": ["Python", "TypeScript", "JavaScript"],
    "Frontend": ["React", "Next.js", "Cesium.js"],
    "Backend": ["Node.js", "PostgreSQL"],
    "Infra": ["Linux", "Caddy", "PM2", "Playwright"],
    "Web3": ["Polygon", "ethers.js"],
    "AI": ["Claude API", "Claude Code", "Codex"],
}

TECH_BADGES = {
    "Python": {"category": "Languages", "color": "3776AB", "logo": "python", "logoColor": "white"},
    "TypeScript": {"category": "Languages", "color": "3178C6", "logo": "typescript", "logoColor": "white"},
    "JavaScript": {"category": "Languages", "color": "F7DF1E", "logo": "javascript", "logoColor": "black"},
    "Shell": {"category": "Languages", "color": "4EAA25", "logo": "gnubash", "logoColor": "white"},
    "Go": {"category": "Languages", "color": "00ADD8", "logo": "go", "logoColor": "white"},
    "Rust": {"category": "Languages", "color": "000000", "logo": "rust", "logoColor": "white"},
    "Java": {"category": "Languages", "color": "007396", "logo": "openjdk", "logoColor": "white"},
    "HTML": {"category": "Languages", "color": "E34F26", "logo": "html5", "logoColor": "white"},
    "CSS": {"category": "Languages", "color": "1572B6", "logo": "css3", "logoColor": "white"},
    "React": {"category": "Frontend", "color": "61DAFB", "logo": "react", "logoColor": "black"},
    "Next.js": {"category": "Frontend", "color": "000000", "logo": "nextdotjs", "logoColor": "white"},
    "Tailwind CSS": {"category": "Frontend", "color": "06B6D4", "logo": "tailwindcss", "logoColor": "white"},
    "Three.js": {"category": "Frontend", "color": "000000", "logo": "threedotjs", "logoColor": "white"},
    "Cesium.js": {"category": "Frontend", "color": "6CADDF", "logo": "cesium", "logoColor": "white"},
    "Leaflet": {"category": "Frontend", "color": "199900", "logo": "leaflet", "logoColor": "white"},
    "Vite": {"category": "Frontend", "color": "646CFF", "logo": "vite", "logoColor": "white"},
    "Vue": {"category": "Frontend", "color": "4FC08D", "logo": "vuedotjs", "logoColor": "white"},
    "Svelte": {"category": "Frontend", "color": "FF3E00", "logo": "svelte", "logoColor": "white"},
    "Node.js": {"category": "Backend", "color": "339933", "logo": "nodedotjs", "logoColor": "white"},
    "FastAPI": {"category": "Backend", "color": "009688", "logo": "fastapi", "logoColor": "white"},
    "PostgreSQL": {"category": "Backend", "color": "4169E1", "logo": "postgresql", "logoColor": "white"},
    "Express": {"category": "Backend", "color": "000000", "logo": "express", "logoColor": "white"},
    "Stripe": {"category": "Backend", "color": "635BFF", "logo": "stripe", "logoColor": "white"},
    "Twilio": {"category": "Backend", "color": "F22F46", "logo": "twilio", "logoColor": "white"},
    "SendGrid": {"category": "Backend", "color": "51A9E3", "logo": "sendgrid", "logoColor": "white"},
    "Linux": {"category": "Infra", "color": "FCC624", "logo": "linux", "logoColor": "black"},
    "Caddy": {"category": "Infra", "color": "1F88C0", "logo": "caddy", "logoColor": "white"},
    "PM2": {"category": "Infra", "color": "2B037A", "logo": "pm2", "logoColor": "white"},
    "Playwright": {"category": "Infra", "color": "2EAD33", "logo": "playwright", "logoColor": "white"},
    "Puppeteer": {"category": "Infra", "color": "40B5A4", "logo": "puppeteer", "logoColor": "white"},
    "Vitest": {"category": "Infra", "color": "6E9F18", "logo": "vitest", "logoColor": "white"},
    "Vercel": {"category": "Infra", "color": "000000", "logo": "vercel", "logoColor": "white"},
    "tmux": {"category": "Infra", "color": "1BB91F"},
    "Tailscale": {"category": "Infra", "color": "242424", "logo": "tailscale", "logoColor": "white"},
    "Telegram": {"category": "Infra", "color": "26A5E4", "logo": "telegram", "logoColor": "white"},
    "Docker": {"category": "Infra", "color": "2496ED", "logo": "docker", "logoColor": "white"},
    "GitHub Actions": {"category": "Infra", "color": "2088FF", "logo": "githubactions", "logoColor": "white"},
    "RunPod": {"category": "Infra", "color": "FF6A00", "logo": "kubernetes", "logoColor": "white"},
    "Polygon": {"category": "Web3", "color": "8247E5", "logo": "polygon", "logoColor": "white"},
    "ethers.js": {"category": "Web3", "color": "2535A0", "logo": "ethereum", "logoColor": "white"},
    "Solana": {"category": "Web3", "color": "14F195", "logo": "solana", "logoColor": "black"},
    "Claude API": {"category": "AI", "color": "CC785C", "logo": "anthropic", "logoColor": "white", "badge": "Claude_API"},
    "Claude Code": {"category": "AI", "color": "CC785C", "logo": "anthropic", "logoColor": "white", "badge": "Claude_Code"},
    "Codex": {"category": "AI", "color": "000000", "logo": "openai", "logoColor": "white"},
    "OpenAI": {"category": "AI", "color": "000000", "logo": "openai", "logoColor": "white"},
    "Anthropic": {"category": "AI", "color": "CC785C", "logo": "anthropic", "logoColor": "white"},
    "Ollama": {"category": "AI", "color": "111111", "logo": "ollama", "logoColor": "white"},
    "Whisper": {"category": "AI", "color": "111111", "logo": "openai", "logoColor": "white"},
}

TECH_ALIAS_MAP = {
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "next": "Next.js",
    "nextjs": "Next.js",
    "reactjs": "React",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "three": "Three.js",
    "three.js": "Three.js",
    "vitejs": "Vite",
    "fastapi": "FastAPI",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "vue.js": "Vue",
    "cesium": "Cesium.js",
    "leaflet.js": "Leaflet",
    "ethers": "ethers.js",
    "ethersjs": "ethers.js",
    "solana web3": "Solana",
    "tmux session": "tmux",
    "anthropic": "Anthropic",
    "claude": "Claude API",
    "claude sonnet": "Claude API",
    "openai api": "OpenAI",
    "telegram bot": "Telegram",
}

TECH_CANONICAL_BY_LOWER = {name.lower(): name for name in TECH_BADGES}

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
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "readme-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(f"https://api.github.com/{path}", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  API error for {path}: {e}")
        return None


def count_lines(repo_name):
    """Clone repo shallow and count lines of code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        if TOKEN:
            clone_url = f"https://x-access-token:{TOKEN}@github.com/{USERNAME}/{repo_name}.git"
        else:
            clone_url = f"https://github.com/{USERNAME}/{repo_name}.git"
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


def normalize_tech_name(name):
    """Normalize stack item labels to canonical tech badge names."""
    raw = (name or "").strip()
    if not raw or raw == "—":
        return ""
    lowered = raw.lower()
    if lowered in TECH_ALIAS_MAP:
        return TECH_ALIAS_MAP[lowered]
    if lowered in TECH_CANONICAL_BY_LOWER:
        return TECH_CANONICAL_BY_LOWER[lowered]
    return raw


def build_badge_url(tech_name):
    """Build shields.io badge URL for a tech label."""
    meta = TECH_BADGES.get(tech_name)
    if not meta:
        label = urllib.parse.quote(tech_name.replace(" ", "_"), safe=".")
        return f"https://img.shields.io/badge/{label}-4B5563?style=flat-square"

    badge_label = meta.get("badge", tech_name).replace(" ", "_")
    label = urllib.parse.quote(badge_label, safe=".")
    url = f"https://img.shields.io/badge/{label}-{meta['color']}?style=flat-square"
    logo = meta.get("logo")
    if logo:
        url += f"&logo={urllib.parse.quote(logo)}"
    logo_color = meta.get("logoColor")
    if logo_color:
        url += f"&logoColor={urllib.parse.quote(logo_color)}"
    return url


def ordered_techs_for_row(row_name, row_values):
    """Keep baseline ordering stable; append new entries alphabetically."""
    base = BASE_TECH_STACK.get(row_name, [])
    ordered = [t for t in base if t in row_values]
    extras = sorted([t for t in row_values if t not in base], key=str.lower)
    return ordered + extras


def build_tech_stack_table(projects_data):
    """Build the HTML tech stack table from baseline + project stacks."""
    rows = {row: set(values) for row, values in BASE_TECH_STACK.items()}
    rows.setdefault("Other", set())

    for p in projects_data:
        for stack_item in p.get("stack", []):
            tech = normalize_tech_name(stack_item)
            if not tech:
                continue
            meta = TECH_BADGES.get(tech)
            row = meta["category"] if meta else "Other"
            rows.setdefault(row, set()).add(tech)

    html = ["<table>"]
    for row in TECH_ROW_ORDER:
        values = rows.get(row, set())
        if not values:
            continue
        ordered_techs = ordered_techs_for_row(row, values)
        html.append("<tr>")
        html.append(f'<td align="center"><b>{row}</b></td>')
        html.append("<td>")
        for tech in ordered_techs:
            html.append(f'<img src="{build_badge_url(tech)}" />')
        html.append("</td>")
        html.append("</tr>")
    html.append("</table>")
    return "\n".join(html)


def update_readme(projects_data):
    """Replace tech stack and projects table in README.md."""
    readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
    with open(readme_path, "r") as f:
        content = f.read()

    new_tech_table = build_tech_stack_table(projects_data)
    tech_pattern = r"(### Tech Stack\s*\n\s*\n)(<table>.*?</table>)"
    content = re.sub(tech_pattern, rf"\1{new_tech_table}", content, flags=re.S, count=1)

    # Replace the projects table (between "### Projects" and the next --- or end)
    new_table = build_projects_table(projects_data)
    projects_pattern = r"(### Projects\s*\n\s*\n)(\| Project \| Description \|.*?\n(?:\|.*\n)+)"
    content = re.sub(projects_pattern, rf"\1{new_table}\n", content, flags=re.S, count=1)

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

    # Auto-commit and push if running outside CI (the GH Actions workflow has its own commit step)
    if not os.environ.get("GITHUB_ACTIONS"):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["git", "-C", repo_root, "diff", "--quiet", "README.md"],
            capture_output=True,
        )
        if result.returncode != 0:
            subprocess.run(["git", "-C", repo_root, "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-m", "Update projects + tech stack (auto-sync)"],
                check=True,
            )
            subprocess.run(["git", "-C", repo_root, "push"], check=True)
            print("Committed and pushed README update.")
        else:
            print("No changes to README.")

    print("Done.")


if __name__ == "__main__":
    main()
