import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


YEARS_QUERY = """
query ($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionYears
    }
  }
}
"""

COUNTS_QUERY = """
query ($login: String!, $start: DateTime!, $end: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $start, to: $end) {
      totalPullRequestReviewContributions
      totalIssueContributions
      totalPullRequestContributions
      totalCommitContributions
    }
  }
}
"""

# The order of the labels follows the polygon clockwise from the top.
# Each entry gives the GraphQL field, label, axis direction, and text position.
AXES = (
    ("totalPullRequestReviewContributions", "Code reviews", 0, -1, 140, 54),
    ("totalIssueContributions", "Issues", 1, 0, 238, 119),
    ("totalPullRequestContributions", "Pull requests", 0, 1, 140, 185),
    ("totalCommitContributions", "Commits", -1, 0, 42, 119),
)


def query_contributions(query, **variables):
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({
            "query": query,
            "variables": {"login": os.environ["GITHUB_REPOSITORY_OWNER"], **variables},
        }).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL query failed: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]


def fetch_contributions():
    years = query_contributions(YEARS_QUERY)["contributionYears"]
    totals = {field: 0 for field, *_ in AXES}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for year in years:
        counts = query_contributions(
            COUNTS_QUERY,
            start=f"{year}-01-01T00:00:00Z",
            end=min(f"{year}-12-31T23:59:59Z", now),
        )
        for field in totals:
            totals[field] += counts[field]
    return totals


def render_chart(contributions):
    counts = [contributions[field] for field, *_ in AXES]
    total = sum(counts)
    highest = max(counts) or 1
    points = []
    labels = []
    summary = []
    for (_, label, dx, dy, label_x, label_y), count in zip(AXES, counts):
        share = f"{count / total:.0%}" if total else "0%"
        x = 140 + 49 * dx * count / highest
        y = 124 + 49 * dy * count / highest
        points.append(f"{x:.2f},{y:.2f}")
        labels.append(
            f'<text x="{label_x}" y="{label_y}" font-weight="600">{share}</text>'
            f'<text x="{label_x}" y="{label_y + 15}">{label}</text>'
        )
        summary.append(f"{label}: {share} ({count})")

    dots = []
    for point in points:
        x, y = point.split(",")
        dots.append(f'<circle cx="{x}" cy="{y}" r="2.7" fill="#9ece6a"/>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="280" height="211" viewBox="0 0 280 211" role="img" aria-labelledby="title description">
  <title id="title">GitHub contributions across all years</title>
  <desc id="description">{'; '.join(summary)}</desc>
  <rect width="280" height="211" rx="8" fill="#1a1b27"/>
  <path d="M91 124h98 M140 75v98" stroke="#565f89"/>
  <polygon points="{' '.join(points)}" fill="#9ece6a" fill-opacity="0.28" stroke="#9ece6a" stroke-width="1.5"/>
  {''.join(dots)}
  <g fill="#c0caf5" font-family="system-ui, sans-serif" text-anchor="middle" font-size="12">
    <text x="140" y="25" fill="#7aa2f7" font-size="15" font-weight="600">Contributions · All time</text>
    {''.join(labels)}
  </g>
</svg>
'''


if __name__ == "__main__":
    Path("assets/github-activity.svg").write_text(
        render_chart(fetch_contributions()), encoding="utf-8"
    )
