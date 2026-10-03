"""
Step 5: Measure what worked. This produces the numbers for your CV and write-up.

As replies come in, update the "status" column in data/personalised.csv to one of:
  not_contacted, sent, replied_negative, replied_positive, meeting_booked
(or export the same from HubSpot).

Run:  python 5_results_report.py
"""
import csv
import os
from collections import defaultdict

import config

SENT = {"sent", "replied_negative", "replied_positive", "meeting_booked"}
REPLIED = {"replied_negative", "replied_positive", "meeting_booked"}
POSITIVE = {"replied_positive", "meeting_booked"}


def rates(rows):
    sent = [r for r in rows if r["status"] in SENT]
    n = len(sent)
    if n == 0:
        return n, 0, 0, 0
    pct = lambda s: 100 * sum(r["status"] in s for r in sent) / n
    return n, pct(REPLIED), pct(POSITIVE), sum(r["status"] == "meeting_booked" for r in sent)


def line(label, rows):
    n, reply, pos, mtg = rates(rows)
    print(f"{label:<32} sent={n:<4} reply={reply:5.1f}%  positive={pos:5.1f}%  meetings={mtg}")


def main():
    with open(os.path.join(config.DATA_DIR, "personalised.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print("=== Overall ===")
    line("All sent", rows)

    print("\n=== By AI fit rating (did the LLM's judgement predict replies?) ===")
    by_fit = defaultdict(list)
    for r in rows:
        by_fit[r["fit"] or "unrated"].append(r)
    for k in ["strong", "medium", "weak", "unrated"]:
        if k in by_fit:
            line(f"fit = {k}", by_fit[k])

    print("\n=== By signal (which signals actually predict interest?) ===")
    by_sig = defaultdict(list)
    for r in rows:
        for s in (r["signals"] or "none").split(";"):
            by_sig[s].append(r)
    for k, v in sorted(by_sig.items()):
        line(k, v)

    print("\n=== By score band ===")
    for lo, hi in [(0, 50), (50, 70), (70, 999)]:
        line(f"score {lo}-{hi if hi < 999 else '+'}", [r for r in rows if lo <= int(r["score"] or 0) < hi])


if __name__ == "__main__":
    main()
