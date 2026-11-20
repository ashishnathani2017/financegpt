"""Download the most relevant RBI and SEBI documents listed in IndiaFinBench metadata.

Usage (project root, venv active):
    python scripts/download_regulatory.py            # up to 20 documents
    python scripts/download_regulatory.py --max 30

Writes:
    data/raw/regulatory/<source>/<file>.pdf
    data/regulatory_log.csv   (source, title, date, url, status, size_kb)
"""
import argparse
import csv
import hashlib
import pathlib
import re

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
META = ROOT / "data" / "raw" / "indiafinbench" / "data"
OUT = ROOT / "data" / "raw" / "regulatory"
LOG = ROOT / "data" / "regulatory_log.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (academic research project)"}

# Keywords for documents most useful to a retail-finance RAG index.
KEYWORDS = [
    "monetary policy", "financial stability", "master circular", "master direction",
    "mutual fund", "investment adviser", "investment advis", "research analyst",
    "disclosure", "risk", "fraud", "digital lending", "kyc", "credit",
]


def wanted(title):
    t = title.lower()
    return any(k in t for k in KEYWORDS)


def safe(name):
    # Keep a readable prefix and append a short hash so long titles cannot collide.
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:100]
    tag = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{base}_{tag}"


def main(max_docs):
    rows = []
    for fname in ("metadata_rbi.csv", "metadata_sebi.csv"):
        with open(META / fname, encoding="utf-8", newline="") as f:
            rows += list(csv.DictReader(f))
    picked = [r for r in rows if wanted(r.get("title", "")) and r.get("url")][:max_docs]
    print(f"Matched {len(picked)} documents (limit {max_docs}).")

    log = []
    session = requests.Session()
    session.headers.update(HEADERS)
    for r in picked:
        src = r["source"].lower()
        dest_dir = OUT / src
        dest_dir.mkdir(parents=True, exist_ok=True)
        name = safe(f"{src}_{r['date']}_{r['title']}") + ".pdf"
        if (dest_dir / name).exists():
            print(f"[skip] already downloaded: {name}")
            continue
        status, size = "", 0
        try:
            resp = session.get(r["url"], timeout=60)
            if resp.status_code == 200 and resp.content[:4] == b"%PDF":
                (dest_dir / name).write_bytes(resp.content)
                status, size = "ok", len(resp.content)
            else:
                status = f"http {resp.status_code} or not a PDF"
        except Exception as e:
            status = f"error: {e.__class__.__name__}"
        print(f"[{status}] {r['title'][:70]}")
        log.append({"source": r["source"], "title": r["title"], "date": r["date"],
                    "url": r["url"], "status": status, "size_kb": round(size / 1024, 1)})

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w", encoding="utf-8", newline="") as f:
        fields = list(log[0].keys()) if log else ["source"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(log)
    ok = sum(1 for x in log if x["status"] == "ok")
    print(f"\nDownloaded {ok} of {len(log)}. Log: {LOG}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=20)
    main(ap.parse_args().max)
