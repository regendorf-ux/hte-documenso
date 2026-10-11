"""The release notes for a build: what changed in Documenso since the version we last built, then the
signing test's results.  python tools/notes.py <upstream tag> <last upstream tag or ""> <results.json> <image>"""
import json
import sys
import urllib.request

tag, last, results, image = sys.argv[1:5]


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "hte-documenso"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


releases = get("https://api.github.com/repos/documenso/documenso/releases?per_page=40")
names = [r["tag_name"] for r in releases]
start = names.index(tag) if tag in names else 0
stop = names.index(last) if last in names else start + 1
covered = [r for r in releases[start:stop] if not r.get("draft")]
security = any("security" in (r.get("body") or "").lower() or "security" in r["name"].lower() for r in covered)

out = []
checks = json.load(open(results))
out.append(f"HTE's copy of Documenso {tag}. Image: `{image}`")
out.append("")
out.append("**Security fixes in this update: " + ("YES**" if security else "none mentioned**"))
out.append("")
out.append("## Signing test: " + ("passed" if checks["ok"] else "FAILED"))
for c in checks["checks"]:
    out.append(f"- {'✅' if c['ok'] else '❌'} {c['check']}")
out.append("")
for r in covered:
    out.append(f"## Documenso {r['tag_name']} ({r['published_at'][:10]})")
    out.append("")
    out.append((r.get("body") or "(no notes)").strip())
    out.append("")
print("\n".join(out))
print(json.dumps({"security": security, "covers": [r["tag_name"] for r in covered]}), file=sys.stderr)
