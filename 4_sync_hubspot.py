"""
Step 4: Push approved accounts into HubSpot (free CRM) so you can run sequences and track replies.

Setup: HubSpot (free) -> Settings -> Integrations -> Private Apps -> Create
  scopes: crm.objects.companies.write, crm.objects.contacts.write, crm.schemas.companies.write
  export HUBSPOT_TOKEN=pat-...

Run:   python 4_sync_hubspot.py            (dry run: prints what it would send)
       python 4_sync_hubspot.py --send     (actually creates records)
"""
import argparse
import csv
import os

import requests

import config

API = "https://api.hubapi.com"

CUSTOM_PROPS = [
    ("gtm_score", "GTM score", "number", "number"),
    ("gtm_signals", "GTM signals", "string", "textarea"),
    ("gtm_first_line", "GTM first line", "string", "textarea"),
    ("gtm_likely_pain", "GTM likely pain", "string", "textarea"),
]


def hs(method, path, **kw):
    r = requests.request(method, API + path, timeout=30,
                         headers={"Authorization": f"Bearer {config.HUBSPOT_TOKEN}"}, **kw)
    if r.status_code == 409:  # already exists
        return r.json()
    r.raise_for_status()
    return r.json()


def ensure_properties():
    """Create the custom company fields once, so scores show up in HubSpot views."""
    for name, label, type_, field in CUSTOM_PROPS:
        hs("POST", "/crm/v3/properties/companies", json={
            "name": name, "label": label, "type": type_, "fieldType": field,
            "groupName": "companyinformation",
        })


def split_director(name):
    """Companies House format is 'SURNAME, Firstname Middle' -> ('Firstname', 'Surname')."""
    if "," not in name:
        return name.title(), ""
    surname, given = name.split(",", 1)
    return given.strip().split(" ")[0].title(), surname.strip().title()


def domain_of(url):
    return url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(config.DATA_DIR, "personalised.csv"), encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["approved"].strip().lower() == "yes"]

    if not rows:
        raise SystemExit("No rows with approved=yes in data/personalised.csv. Review them first.")

    if args.send:
        if not config.HUBSPOT_TOKEN:
            raise SystemExit("Set HUBSPOT_TOKEN first.")
        ensure_properties()

    for r in rows:
        company = {"properties": {
            "name": r["company_name"].title(),
            "domain": domain_of(r["website"]),
            "gtm_score": r["score"],
            "gtm_signals": r["signals"],
            "gtm_first_line": r["first_line"],
            "gtm_likely_pain": r["likely_pain"],
        }}
        if not args.send:
            print(f"[dry run] company: {company['properties']['name']}  score={r['score']}")
            continue

        c = hs("POST", "/crm/v3/objects/companies", json=company)
        if r["contact_email"]:
            first, last = split_director(r["director"])
            contact = hs("POST", "/crm/v3/objects/contacts", json={"properties": {
                "email": r["contact_email"], "firstname": first, "lastname": last,
            }})
            if "id" in c and "id" in contact:
                hs("PUT", f"/crm/v4/objects/companies/{c['id']}/associations/default/contacts/{contact['id']}")
        print(f"synced: {r['company_name']}")

    print(f"\n{'Synced' if args.send else 'Would sync'} {len(rows)} accounts.")


if __name__ == "__main__":
    main()
