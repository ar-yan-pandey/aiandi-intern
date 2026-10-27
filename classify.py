#!/usr/bin/env python3
"""Classify forum comments with Cloudflare's Clef decision model.

Reads credentials from cloud-flare.local.sh (git-ignored), classifies each
comment in comments.json as acceptable / toxic / spam, then writes:
  - classifications.json  (machine-readable results)
  - comments.html         (easy-to-scan page, one row per comment)
"""
import json
import re
import time
import html
import urllib.request
import urllib.error

import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", default="comments.json", help="input JSON file with a comments list")
parser.add_argument("--html", default="comments.html", help="HTML report to write")
parser.add_argument("--json", default="classifications.json", help="machine-readable results to write")
parser.add_argument("--model", default="clef-flash", choices=["clef-flash", "clef"],
                    help="clef-flash: faster/cheaper. clef: larger, better on borderline inputs")
args = parser.parse_args()
MODEL = args.model

creds = dict(re.findall(r'export (\w+)="([^"]*)"', open("cloud-flare.local.sh").read()))
ACCOUNT = creds["CLOUDFLARE_ACCOUNT_ID"]
TOKEN = creds["CLOUDFLARE_API_TOKEN"]

QUESTION = {
    "type": "choice",
    "instructions": (
        "Classify `comment`, one post from a college course discussion forum. "
        "The course is CS307 Applied AI Lab; students discuss assignments, share "
        "their work, and ask the instructor questions."
    ),
    "criteria": {
        "acceptable": (
            "A genuine course-related post: a question, answer, opinion, or shared "
            "work from a student. On-topic and civil, even if informal, confused, "
            "off-syllabus, or mildly off-topic chat between classmates."
        ),
        "toxic": (
            "Attacks, insults, harasses, or demeans a person or group; includes "
            "abuse, slurs, threats, or hostile personal remarks, even if wrapped "
            "in a course topic."
        ),
        "spam": (
            "Advertising, self-promotion, scams, or junk: selling services or "
            "products, posting contact details for paid help, irrelevant links, "
            "or repeated/low-effort promotion rather than course discussion."
        ),
    },
}


def classify(comment_text, retries=4):
    payload = {
        "state": {"comment": comment_text},
        "questions": {"label": QUESTION},
    }
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/@cf/cloudflare/{MODEL}"
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
        if not data.get("success"):
            raise RuntimeError(f"API error: {data.get('errors')}")
        return data["result"]["answers"]["label"]
    raise RuntimeError("too many 429s")


def main():
    comments = json.load(open(args.input))["comments"]
    results = []
    for c in comments:
        ans = classify(c["comment"])
        results.append({
            "id": c["id"],
            "author": c["author"],
            "thread": c["thread"],
            "posted_at": c["posted_at"],
            "comment": c["comment"],
            "label": ans["choice"],
            "probabilities": ans["probabilities"],
            "confidence": ans["confidence"],
        })
        print(f"{c['id']:>3}  {ans['choice']:<11} conf={ans['confidence']:.2f}  {c['comment'][:60]!r}", flush=True)
        time.sleep(0.2)  # stay polite on rate limits
    json.dump({"model": MODEL, "input": args.input, "results": results}, open(args.json, "w"), indent=1)
    write_html(results, args.html, MODEL, args.input)
    print(f"\nWrote {args.json} and {args.html} for {len(results)} comments.")


LABEL_ORDER = {"toxic": 0, "spam": 1, "acceptable": 2}
LABEL_COLOR = {"toxic": "#d93025", "spam": "#e8710a", "acceptable": "#188038"}


def write_html(results, path, model, source):
    rows = []
    ordered = sorted(results, key=lambda r: (LABEL_ORDER.get(r["label"], 3), r["confidence"]))
    for r in ordered:
        probs = " &middot; ".join(
            f"{k} {v:.2f}" for k, v in sorted(r["probabilities"].items(), key=lambda kv: -kv[1])
        )
        low = ' <span class="low">low confidence</span>' if r["confidence"] < 0.5 else ""
        rows.append(f"""<tr>
<td class="id">{r['id']}</td>
<td><span class="badge" style="background:{LABEL_COLOR.get(r['label'], '#555')}">{r['label']}</span>{low}<br>
<span class="probs">{probs}</span></td>
<td><b>{html.escape(r['author'])}</b> &middot; {html.escape(r['thread'])} &middot; {html.escape(r['posted_at'])}<br>
{html.escape(r['comment'])}</td>
</tr>""")
    counts = {lab: sum(1 for r in results if r["label"] == lab) for lab in ("acceptable", "toxic", "spam")}
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>CS307 forum comments - Clef classification ({html.escape(source)}, {model})</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #202124; }}
table {{ border-collapse: collapse; width: 100%; }}
td {{ border-bottom: 1px solid #e0e0e0; padding: 8px 10px; vertical-align: top; }}
tr:hover {{ background: #f6f8fc; }}
.badge {{ color: #fff; border-radius: 10px; padding: 1px 10px; font-size: 13px; }}
.id {{ color: #888; width: 3em; }}
.probs {{ font-size: 12px; color: #777; }}
.low {{ font-size: 12px; color: #b3261e; font-weight: 600; }}
.summary span {{ margin-right: 18px; font-weight: 600; }}
</style></head><body>
<h1>Forum comment classification</h1>\n<p>Source: <code>{html.escape(source)}</code> &middot; model: <code>{model}</code></p>
<p class="summary"><span style="color:#188038">acceptable: {counts['acceptable']}</span>
<span style="color:#d93025">toxic: {counts['toxic']}</span>
<span style="color:#e8710a">spam: {counts['spam']}</span>
(sorted so the likely problems are on top; low-confidence rows are marked)</p>
<table>{''.join(rows)}
</table></body></html>"""
    open(path, "w").write(page)


if __name__ == "__main__":
    main()
