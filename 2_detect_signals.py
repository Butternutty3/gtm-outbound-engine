"""
Step 2: Detect buying signals on each company's website, then score every account.

Needs the "website" column filled in data/companies.csv (see README, step 2).
Run:   python 2_detect_signals.py      (Windows: use "py" instead of "python")
Demo:  python 2_detect_signals.py --demo

Output: data/scored.csv  (sorted best-first, with the reasons for each score)
"""
import argparse
import csv
import json
import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config

# Pages where quoting and hiring signals usually live
SUBPAGES = ["", "careers", "jobs", "join-us", "about", "contact", "pricing", "demo"]
HEADERS = {"User-Agent": "Mozilla/5.0 (research project; contact via LinkedIn)"}


CAREER_WORDS = ["career", "jobs", "join", "hiring", "work-with-us", "vacanc", "open-roles"]
# Many startups host their jobs on these external sites rather than their own domain
JOB_BOARDS = ["workable.com", "ashbyhq.com", "greenhouse.io", "lever.co", "teamtailor.com",
              "breezy.hr", "notion.site", "workatastartup.com", "otta.com", "welcometothejungle.com"]


def page_text(url):
    """Return (visible text, list of absolute links) for one page, or ('', []) if it fails."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if not (r.ok and "text/html" in r.headers.get("Content-Type", "")):
            return "", []
        soup = BeautifulSoup(r.text, "html.parser")
        links = [urljoin(r.url, a.get("href", "")) for a in soup.find_all("a") if a.get("href")]
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(" "), links
    except requests.RequestException:
        return "", []


def fetch_site_text(website):
    """Read the homepage, common subpages, and any careers/job-board links the homepage points to."""
    website = (website or "").strip()
    if not website or website.upper() == "N/A":
        return ""
    if not website.startswith("http"):
        website = "https://" + website
    base = website.rstrip("/") + "/"

    text, seen = [], set()
    home_text, home_links = page_text(base)
    text.append(home_text)
    text.extend(home_links)  # keep hrefs: calendly links, mailto: etc.
    seen.add(base)

    # 1) careers pages the homepage actually links to (including external job boards)
    to_visit = []
    for link in home_links:
        low = link.lower()
        if any(w in low for w in CAREER_WORDS) or any(j in low for j in JOB_BOARDS):
            to_visit.append(link)
    # 2) common paths, in case the homepage menu is built with JavaScript
    to_visit += [urljoin(base, sub) for sub in SUBPAGES if sub]

    for url in to_visit[:12]:
        if url in seen:
            continue
        seen.add(url)
        t, _ = page_text(url)
        text.append(t)
        time.sleep(0.3)  # be polite
    return re.sub(r"\s+", " ", " ".join(text)).lower()


def score(company, site_text):
    """Transparent rules-based score. Every point comes with a reason you can show."""
    points, reasons, signals = 0, [], []

    # Funding signal from Companies House (SH01 filings)
    days = company.get("days_since_sh01", "")
    if days not in ("", None):
        days = int(days)
        for max_days, pts in config.FUNDING_RECENCY_POINTS:
            if days <= max_days:
                points += pts
                signals.append("recent_funding")
                reasons.append(f"New shares allotted {days} days ago, likely a funding round (+{pts})")
                break
        if int(company.get("sh01_count_12m") or 0) >= 2:
            points += config.MULTIPLE_ALLOTMENTS_POINTS
            reasons.append(f"{company['sh01_count_12m']} share allotments in 12 months (+{config.MULTIPLE_ALLOTMENTS_POINTS})")

    acc = company.get("accounts_type", "")
    acc_pts = config.ACCOUNTS_TYPE_POINTS.get(acc, 0)
    if acc_pts:
        points += acc_pts
        reasons.append(f"{acc} accounts ({acc_pts:+d})")

    for name, rule in config.WEBSITE_SIGNALS.items():
        hits = [k for k in rule["keywords"] if k in site_text]
        if hits:
            points += rule["points"]
            signals.append(name)
            reasons.append(f"{rule['why']} [found: {', '.join(hits[:3])}] ({rule['points']:+d})")

    if not site_text:
        reasons.append("No website text found (0)")

    return points, signals, reasons


def has_positive_site_signal(signals):
    return any(config.WEBSITE_SIGNALS.get(s, {}).get("points", 0) > 0 for s in signals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    in_path = os.path.join(config.DATA_DIR, "companies.csv")
    with open(in_path, encoding="utf-8") as f:
        companies = list(csv.DictReader(f))

    demo_text = {}
    if args.demo:
        with open(os.path.join(os.path.dirname(__file__), "sample_data", "companies_sample.json")) as f:
            demo_text = {c["company_number"]: c.get("_demo_site_text", "").lower() for c in json.load(f)}

    out = []
    for c in companies:
        site_text = demo_text.get(c["company_number"], "") if args.demo else fetch_site_text(c["website"])
        pts, signals, reasons = score(c, site_text)
        c.update({
            "score": pts,
            # funding alone isn't enough: we need evidence from the website that they sell B2B / are hiring
            "qualified": "yes" if pts >= config.QUALIFY_THRESHOLD and has_positive_site_signal(signals) else "no",
            "pages_read": "yes" if site_text else "no",
            "signals": ";".join(signals),
            "reasons": " | ".join(reasons),
            "site_excerpt": site_text[:1500],  # passed to the AI step for personalisation
        })
        out.append(c)
        note = "" if site_text else "   (no website text read)"
        print(f"{pts:>4}  {c['company_name'][:45]:<45} {';'.join(signals)}{note}")

    out.sort(key=lambda r: r["score"], reverse=True)
    out_path = os.path.join(config.DATA_DIR, "scored.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    q = sum(r["qualified"] == "yes" for r in out)
    print(f"\n{q}/{len(out)} accounts qualified (score >= {config.QUALIFY_THRESHOLD} and a website signal) -> {out_path}")


if __name__ == "__main__":
    main()
