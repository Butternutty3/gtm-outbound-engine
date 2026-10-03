"""
Step 1: Find recently funded UK tech startups from Companies House (free, official data).

How it works:
  1. Advanced search: active companies in tech SIC codes, incorporated in our window
  2. For each one, check filing history for SH01 filings (new shares allotted = likely funding round)
  3. Only for companies with a recent SH01: pull profile (size) + a current director

Get a free API key: https://developer.company-information.service.gov.uk/
Then (Windows PowerShell):  $env:COMPANIES_HOUSE_API_KEY="your_key"
     (Mac/Linux):           export COMPANIES_HOUSE_API_KEY="your_key"

Run:   python 1_pull_companies.py --scan 300
       (--scan = how many companies to check for funding; only funded ones are saved)
Demo (no key needed):  python 1_pull_companies.py --demo

Output: data/companies.csv
"""
import argparse
import csv
import json
import os
import time
from datetime import date, datetime

import requests

import config

BASE = "https://api.company-information.service.gov.uk"
FIELDS = [
    "company_number", "company_name", "incorporated", "postcode", "locality", "sic_codes",
    "last_sh01_date", "days_since_sh01", "sh01_count_12m", "accounts_type", "director", "website",
]


def ch_get(path, params=None):
    """GET from Companies House. The API key is the username, password is blank."""
    for attempt in range(5):
        try:
            r = requests.get(BASE + path, params=params,
                             auth=(config.COMPANIES_HOUSE_API_KEY, ""), timeout=30)
        except (requests.ConnectionError, requests.Timeout):
            # wifi blip or DNS hiccup: wait and try again rather than crashing
            wait = 10 * (attempt + 1)
            print(f"  connection problem, retrying in {wait}s...")
            time.sleep(wait)
            continue
        if r.status_code == 429:  # rate limit: 600 requests per 5 minutes
            print("  rate limited, waiting 60s...")
            time.sleep(60)
            continue
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()
    raise requests.ConnectionError("Could not reach Companies House after several tries")


def search_companies(limit):
    """Advanced search: active tech companies incorporated in our window."""
    results, start = [], 0
    while len(results) < limit:
        page = ch_get("/advanced-search/companies", {
            "sic_codes": ",".join(config.SIC_CODES),
            "company_status": "active",
            "company_type": "ltd",
            "incorporated_from": config.INCORPORATED_FROM,
            "incorporated_to": config.INCORPORATED_TO,
            "size": min(500, limit - len(results)),
            "start_index": start,
        })
        items = page.get("items", [])
        if not items:
            break
        results.extend(items)
        start += len(items)
    return results[:limit]


def funding_signal(number):
    """Look for SH01 (allotment of shares) filings in the lookback window."""
    hist = ch_get(f"/company/{number}/filing-history", {"category": "capital", "items_per_page": 50})
    today = date.today()
    dates = []
    for f in hist.get("items", []):
        if f.get("type") == "SH01" and f.get("date"):
            d = datetime.strptime(f["date"], "%Y-%m-%d").date()
            if (today - d).days <= config.FUNDING_LOOKBACK_DAYS:
                dates.append(d)
    if not dates:
        return None
    last = max(dates)
    return {"last_sh01_date": last.isoformat(), "days_since_sh01": (today - last).days,
            "sh01_count_12m": len(dates)}


def details(number):
    """Accounts type (size proxy) and one current director."""
    profile = ch_get(f"/company/{number}")
    accounts_type = (profile.get("accounts", {}).get("last_accounts", {}) or {}).get("type", "")
    director = ""
    officers = ch_get(f"/company/{number}/officers", {"items_per_page": 20})
    for o in officers.get("items", []):
        if o.get("officer_role") == "director" and not o.get("resigned_on"):
            director = o.get("name", "")
            break
    return accounts_type, director


def save(rows, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", type=int, default=300, help="how many companies to check for funding")
    ap.add_argument("--demo", action="store_true", help="use sample data, no API key needed")
    args = ap.parse_args()

    os.makedirs(config.DATA_DIR, exist_ok=True)
    out_path = os.path.join(config.DATA_DIR, "companies.csv")

    if args.demo:
        with open(os.path.join(os.path.dirname(__file__), "sample_data", "companies_sample.json")) as f:
            rows = json.load(f)
    else:
        if not config.COMPANIES_HOUSE_API_KEY:
            raise SystemExit("Set COMPANIES_HOUSE_API_KEY first (or run with --demo).")
        items = search_companies(args.scan)
        print(f"Checking {len(items)} tech companies for recent share allotments (SH01)...")
        rows = []
        for i, item in enumerate(items, 1):
            number = item["company_number"]
            try:
                fund = funding_signal(number)
                time.sleep(0.5)
                if fund:
                    accounts_type, director = details(number)
                    time.sleep(1.0)
                    addr = item.get("registered_office_address", {}) or {}
                    rows.append({
                        "company_number": number,
                        "company_name": item.get("company_name", ""),
                        "incorporated": item.get("date_of_creation", ""),
                        "postcode": addr.get("postal_code", ""),
                        "locality": addr.get("locality", ""),
                        "sic_codes": ";".join(item.get("sic_codes", [])),
                        **fund,
                        "accounts_type": accounts_type,
                        "director": director,
                        "website": "",  # not in Companies House: fill via Clay/Apollo/Google (see README)
                    })
                    print(f"  FUNDED  {item.get('company_name','')[:45]:<45} last SH01 {fund['last_sh01_date']}")
                    save(rows, out_path)  # save as we go, so a crash never loses results
            except requests.RequestException as e:
                print(f"  skip {number}: {type(e).__name__}")
            if i % 25 == 0:
                print(f"  ...checked {i}/{len(items)}, {len(rows)} with recent funding")

    save(rows, out_path)
    print(f"Saved {len(rows)} recently funded companies -> {out_path}")


if __name__ == "__main__":
    main()
