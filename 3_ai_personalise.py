"""
Step 3: Use an LLM to sanity-check each qualified account and write a personalised opener.

Get a key: https://console.anthropic.com  ->  export ANTHROPIC_API_KEY=your_key
Run:   python 3_ai_personalise.py
Without a key it falls back to a template, so you can still test the flow.

Output: data/personalised.csv  <- review this by hand before anything is sent
"""
import csv
import json
import os

import config

PROMPT = """You are a GTM researcher. We are reaching out to {target}.

What we offer: {offer}

Company: {name} ({locality})
Companies House accounts type: {accounts}
Most recent share allotment (SH01) filing: {sh01}
Signals our rules detected: {signals}
Text from their website (truncated):
\"\"\"{excerpt}\"\"\"

Return ONLY a JSON object with these keys:
- "fit": "strong", "medium" or "weak"
- "fit_reason": one sentence, grounded only in the evidence above
- "likely_pain": the specific go-to-market problem this company probably has right now, one sentence
- "first_line": a cold email opening line (max 25 words) that references something SPECIFIC
  and true (from their website or the filing). No flattery, no "I hope this finds you well",
  no made-up facts. Never state a funding amount or investor name: we don't know them.
  Refer to funding only loosely (e.g. "the recent raise"), since an SH01 can also be option exercises.
If the evidence is thin, say so in fit_reason and set fit to "weak"."""


def ask_llm(row):
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": PROMPT.format(
            target=config.TARGET_DESCRIPTION,
            offer=config.OFFER,
            sh01=(f"{row.get('last_sh01_date')} ({row.get('sh01_count_12m')} in last 12 months)"
                  if row.get("last_sh01_date") else "none found"),
            name=row["company_name"],
            locality=row["locality"],
            accounts=row["accounts_type"] or "unknown",
            signals=row["signals"] or "none",
            excerpt=row["site_excerpt"][:1500],
        )}],
    )
    text = msg.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def clean_name(name):
    """'NORTHGATE CARGO SOLUTIONS LTD' -> 'Northgate Cargo Solutions'"""
    words = name.title().split()
    while words and words[-1].rstrip(".") in {"Ltd", "Limited", "Plc", "Llp"}:
        words.pop()
    return " ".join(words)


def template_fallback(row):
    """Used when there's no API key. Shows the shape of the output."""
    s, name = row["signals"], clean_name(row["company_name"])
    if "hiring_first_sales" in s:
        line = f"Saw {name} is hiring its first sales reps after the recent raise. New reps usually spend month one building lists instead of selling."
    elif "hiring_sales_leader" in s:
        line = f"Saw {name} is bringing in a sales leader. The first thing they'll ask for is a repeatable source of pipeline."
    else:
        line = f"Congrats on the recent raise at {name}. Founder-led sales usually hits a ceiling right around now."
    return {"fit": "medium", "fit_reason": "Template mode (no API key)",
            "likely_pain": "No repeatable outbound pipeline for a new sales team", "first_line": line}


def main():
    with open(os.path.join(config.DATA_DIR, "scored.csv"), encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["qualified"] == "yes"]

    use_llm = bool(config.ANTHROPIC_API_KEY)
    print(f"Personalising {len(rows)} qualified accounts ({'LLM' if use_llm else 'template mode'})\n")

    out = []
    for r in rows:
        try:
            ai = ask_llm(r) if use_llm else template_fallback(r)
        except Exception as e:  # keep going if one call fails
            print(f"  failed on {r['company_name']}: {e}")
            continue
        out.append({
            "company_number": r["company_number"],
            "company_name": r["company_name"],
            "website": r["website"],
            "director": r["director"],
            "score": r["score"],
            "signals": r["signals"],
            "fit": ai.get("fit", ""),
            "fit_reason": ai.get("fit_reason", ""),
            "likely_pain": ai.get("likely_pain", ""),
            "first_line": ai.get("first_line", ""),
            "approved": "",          # you fill this: yes/no after reading each one
            "contact_email": "",     # from Apollo/Hunter/Clay
            "status": "not_contacted",
        })
        print(f"[{ai.get('fit','?'):>6}] {r['company_name'][:40]:<40} {ai.get('first_line','')}")

    path = os.path.join(config.DATA_DIR, "personalised.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()) if out else ["company_number"])
        w.writeheader()
        w.writerows(out)
    print(f"\nSaved -> {path}\nNext: read every row, set approved=yes/no, add contact_email.")


if __name__ == "__main__":
    main()
