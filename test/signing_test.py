"""
The signing test for HTE's copy of Documenso: one CSR, signed the way csr.htepr.com has it signed.

  1. (with --setup) a test account: sign up, mark the e-mail verified (--sql), sign in, make an API token;
  2. the CSR app's own client (csrapp/documenso.py) creates the envelope - the technician, then the
     customer - with a sample CSR and its five fields, and opens it without e-mail;
  3. a headless browser signs as the technician, then as the customer;
  4. the envelope must reach COMPLETED, and the signed PDF and the signing certificate must download;
  5. HTE's own pieces must be there (sign-in card, logo, "Powered by Documenso", light/dark switch);
  6. screenshots of each screen, light and dark, for the update e-mail.

    python test/signing_test.py --base http://localhost:3000 --out results --setup \
        --sql "docker exec -i pg psql -U documenso -d documenso"      # sign-ups on, once
    python test/signing_test.py --base http://localhost:3000 --out results --account results/account.json

Writes results/results.json and results/*.png; exits non-zero if any check failed.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import shlex
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from csrapp.csrpdf import Field  # noqa: E402
from csrapp.documenso import Documenso, DocumensoError  # noqa: E402
from playwright.sync_api import Page, sync_playwright  # noqa: E402

CHECKS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail[:500]})
    print(("ok   " if ok else "FAIL ") + name + (f"  ({detail[:200]})" if detail and not ok else ""), flush=True)
    return ok


def draw_signature(pg: Page) -> None:
    pad = pg.locator("[role=dialog] canvas").first
    box = pad.bounding_box()
    x, y = box["x"], box["y"]
    pg.mouse.move(x + 60, y + 100)
    pg.mouse.down()
    for i in range(1, 28):
        pg.mouse.move(x + 60 + i * 11, y + 100 - (i % 4) * 14, steps=2)
    pg.mouse.up()
    pg.wait_for_timeout(300)


def press_dialog(pg: Page, *names: str) -> bool:
    for name in names:
        btn = pg.locator("[role=dialog]").get_by_role("button", name=name, exact=True)
        if btn.count() and btn.first.is_enabled():
            btn.first.click()
            return True
    return False


def settle(pg: Page, ms: int = 2000) -> None:
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(ms)


# ---------------------------------------------------------------- the test account
def setup_account(browser, base: str, sql: str, out: Path) -> tuple[str, str, str]:
    email = f"signing.test.{secrets.token_hex(3)}@htepr.test"
    password = "St-" + secrets.token_urlsafe(14) + "9!"
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.goto(base + "/signup")
    settle(pg)
    pg.fill("input[name=name]", "Signing Test")
    pg.fill("input[name=email]", email)
    pg.fill("input[name=password]", password)
    pg.get_by_text("Sign Here").locator("xpath=following::*[1]").click()
    pg.wait_for_timeout(800)
    draw_signature(pg)
    press_dialog(pg, "Next", "Save", "Sign")
    pg.wait_for_timeout(600)
    pg.get_by_role("button", name="Create account").click()
    pg.wait_for_timeout(5000)
    statement = f"UPDATE \"User\" SET \"emailVerified\" = now() WHERE email = '{email}';"
    run = subprocess.run(shlex.split(sql), input=statement, capture_output=True, text=True, timeout=60)
    if not check("test account created and verified", run.returncode == 0 and "UPDATE 1" in run.stdout,
                 run.stdout + run.stderr):
        raise SystemExit(1)
    pg.goto(base + "/signin")
    settle(pg)
    other = pg.get_by_role("button", name="Sign in with e-mail and password")
    if other.count():
        other.click()
    pg.fill("input[name=email]", email)
    pg.fill("input[name=password]", password)
    pg.get_by_role("button", name="Sign In", exact=True).click()
    pg.wait_for_timeout(6000)
    team = re.search(r"/t/([^/]+)/", pg.url)
    if not check("signed in to the test account", bool(team), pg.url):
        raise SystemExit(1)
    pg.goto(f"{base}/t/{team.group(1)}/settings/tokens")
    settle(pg)
    pg.get_by_role("button", name="Create token").last.click()
    pg.wait_for_timeout(1200)
    pg.locator("[role=dialog] input").first.fill("signing-test")
    pg.locator("[role=dialog] button[type=submit]").click()
    pg.wait_for_timeout(3000)
    token = re.search(r"api_[A-Za-z0-9_]+", pg.content())
    if not check("API token made", bool(token)):
        raise SystemExit(1)
    ctx.storage_state(path=str(out / "state.json"))
    ctx.close()
    return token.group(0), team.group(1), str(out / "state.json")


# ---------------------------------------------------------------- signing, as a person would
def sign_as(browser, url: str, label: str, out: Path) -> bool:
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    try:
        pg.goto(url)
        settle(pg)
        for _ in range(8):
            nxt = pg.get_by_role("button", name="Next Field").first
            if not nxt.is_visible():
                break
            nxt.click()
            pg.wait_for_timeout(1200)
            tip = pg.get_by_text("Click to insert field").first
            if not tip.is_visible():
                break
            box = tip.bounding_box()
            pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] + 22)
            pg.wait_for_timeout(1500)
            if pg.locator("[role=dialog] canvas").count():
                draw_signature(pg)
                press_dialog(pg, "Sign", "Next", "Save", "Continue")
                pg.wait_for_timeout(1500)
        done = pg.get_by_role("button", name="Complete")
        if not done.count():
            pg.screenshot(path=str(out / f"failed-{label}.png"))
            return check(f"{label} could fill every field", False, "no Complete button")
        done.first.click()
        pg.wait_for_timeout(1500)
        pg.locator("[role=dialog]").get_by_role("button", name="Sign").first.click()
        pg.wait_for_timeout(5000)
        return check(f"{label} signed", True)
    except Exception as exc:  # noqa: BLE001 - every failure is a failed check, with a picture
        pg.screenshot(path=str(out / f"failed-{label}.png"))
        return check(f"{label} signed", False, repr(exc))
    finally:
        ctx.close()


# ---------------------------------------------------------------- HTE's own pieces and the pictures
def pictures(browser, base: str, state: str, team: str, envelope_id: str, customer_url: str, out: Path) -> None:
    for scheme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme=scheme)
        pg = ctx.new_page()
        pg.goto(base + "/signin")
        settle(pg)
        if scheme == "light":
            body = pg.inner_text("body")
            check("sign-in page is HTE's card", "HTE Document Signing" in body, body[:200])
            check("Powered by Documenso line, with its source link",
                  "Powered by" in body and pg.locator(".hte-powered a[href*='github.com']").count() == 1)
            logo_ok = pg.evaluate("() => [...document.querySelectorAll('img.hte-logo')].every(i => i.naturalWidth > 0)")
            check("HTE logo loads", bool(logo_ok) and pg.locator("img.hte-logo").count() > 0)
            check("page title is HTE's", "HTE Document Signing" in pg.title(), pg.title())
        check(f"follows the device ({scheme})", pg.evaluate("document.documentElement.className") == scheme,
              pg.evaluate("document.documentElement.className"))
        pg.screenshot(path=str(out / f"{scheme}-signin.png"))
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme=scheme, storage_state=state)
        pg = ctx.new_page()
        pg.goto(f"{base}/t/{team}/documents?status=ALL")
        settle(pg)
        pg.screenshot(path=str(out / f"{scheme}-documents.png"))
        if scheme == "light":
            other = "Dark"
            pg.get_by_role("button", name=other).first.click()
            pg.wait_for_timeout(1500)
            check("the switch turns dark on", pg.evaluate("document.documentElement.className") == "dark")
            pg.get_by_role("button", name="Light").first.click()
            pg.wait_for_timeout(1500)
            check("and light again", pg.evaluate("document.documentElement.className") == "light")
        pg.goto(f"{base}/t/{team}/documents/{envelope_id}")
        settle(pg)
        pg.screenshot(path=str(out / f"{scheme}-document.png"))
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme=scheme)
        pg = ctx.new_page()
        pg.goto(customer_url + "/complete")
        settle(pg, 3000)
        pg.screenshot(path=str(out / f"{scheme}-signed.png"))
        if scheme == "light":
            body = pg.inner_text("body")
            check("no 'create your account' panel after signing", "Need to sign documents" not in body)
        ctx.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="the Documenso to test, e.g. http://localhost:3000")
    ap.add_argument("--out", default="results")
    ap.add_argument("--setup", action="store_true",
                    help="only make a test account (needs --sql and sign-ups on); writes <out>/account.json")
    ap.add_argument("--account", default="", help="an account.json from --setup")
    ap.add_argument("--sql", default="", help="a command that runs SQL from stdin against Documenso's database")
    ap.add_argument("--token", default="", help="an API token (without --setup)")
    ap.add_argument("--team", default="", help="the team's url part (without --setup)")
    ap.add_argument("--state", default="", help="a signed-in browser state file (without --setup)")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            if args.setup:
                token, team, state = setup_account(browser, base, args.sql, out)
                (out / "account.json").write_text(json.dumps({"token": token, "team": team, "state": state}))
                raise SystemExit(0)
            if args.account:
                acct = json.loads(Path(args.account).read_text())
                token, team, state = acct["token"], acct["team"], acct["state"]
            else:
                token, team, state = args.token, args.team, args.state

            client = Documenso(base, token)
            fields = {k: Field(**v) for k, v in json.loads((HERE / "sample-fields.json").read_text()).items()}
            stamp = time.strftime("%H%M%S")
            envelope_id = client.create(
                title=f"CSR-40999 - Test Customer Inc. ({stamp})", external_id=f"signing-test-{stamp}",
                pdf=(HERE / "sample-csr.pdf").read_bytes(), file_name="CSR-40999-Test Customer Inc.pdf",
                technician={"email": "technician@htepr.test", "name": "Test Technician"},
                customer={"email": "customer@example.test", "name": "Test Customer"},
                fields=fields, redirect_url=base + "/")
            check("the CSR app's client created the envelope", bool(envelope_id), envelope_id)
            recipients = client.distribute(envelope_id)
            links = [r.get("signingUrl") or "" for r in recipients]
            links = [base + "/" + u.split("/", 3)[3] for u in links if u]
            if not check("opened for signing without e-mail, two signing links", len(links) == 2, str(recipients)[:300]):
                raise SystemExit(1)

            sign_as(browser, links[0], "the technician", out)
            sign_as(browser, links[1], "the customer", out)

            status, envelope = "", {}
            for _ in range(60):
                envelope = client.get(envelope_id)
                status = envelope.get("status", "")
                if status == "COMPLETED":
                    break
                time.sleep(5)
            check("the envelope completed", status == "COMPLETED", status)
            if status == "COMPLETED":
                try:
                    signed = client.signed_pdf(envelope)
                    check("signed PDF downloads", signed.startswith(b"%PDF") and len(signed) > 10_000, f"{len(signed)} bytes")
                    (out / "signed.pdf").write_bytes(signed)
                    cert = client.certificate(envelope_id)
                    check("signing certificate downloads", cert.startswith(b"%PDF") and len(cert) > 5_000, f"{len(cert)} bytes")
                    (out / "certificate.pdf").write_bytes(cert)
                except DocumensoError as exc:
                    check("signed PDF and certificate download", False, str(exc))

            pictures(browser, base, state, team, envelope_id, links[1], out)
        except SystemExit:
            pass
        except Exception:  # noqa: BLE001
            check("the test ran to the end", False, traceback.format_exc())
        finally:
            browser.close()

    ok = bool(CHECKS) and all(c["ok"] for c in CHECKS)
    (out / "results.json").write_text(json.dumps({"ok": ok, "checks": CHECKS}, indent=1))
    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
