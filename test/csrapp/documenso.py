"""
The self-hosted Documenso at sign.htepr.com, through its v2 API.

A CSR is one envelope with two signers in order: the technician, then the
customer. It is always created without Documenso sending anything
(distribution NONE): the technician signs straight away on the device in
hand. What happens next depends on how the customer signs:

  in person   the page hands the device over and opens the customer's link;
  by e-mail   once the technician has signed, the envelope is switched to
              e-mail and the customer is sent the request (redistribute).

Either way Documenso e-mails the signed PDF to both when the customer signs,
and the service fetches it to file (see service.py).
"""
from __future__ import annotations

import json

import httpx

from .csrpdf import Field


class DocumensoError(RuntimeError):
    pass


class Documenso:
    def __init__(self, base_url: str, token: str, timeout: float = 60.0):
        self.base = base_url.rstrip("/") + "/api/v2"
        self.token = token
        self.timeout = timeout

    @property
    def ready(self) -> bool:
        return bool(self.token)

    def _call(self, method: str, path: str, **kw):
        if not self.token:
            raise DocumensoError("Documenso is not set up: no API token on the server.")
        headers = {"Authorization": self.token, "Accept": "application/json"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.request(method, self.base + path, headers=headers, **kw)
        except httpx.HTTPError as exc:
            raise DocumensoError(f"Documenso could not be reached ({exc.__class__.__name__}).") from exc
        if r.status_code >= 400:
            try:
                msg = r.json().get("message") or r.text
            except ValueError:
                msg = r.text
            raise DocumensoError(f"Documenso said {r.status_code}: {str(msg)[:300]}")
        return r

    def create(self, *, title: str, external_id: str, pdf: bytes, file_name: str, technician: dict,
               customer: dict, fields: dict[str, Field], redirect_url: str, language: str = "en",
               timezone: str = "America/Puerto_Rico") -> str:
        """The envelope, not yet sent to anyone. Returns its id."""
        def f(kind: str, key: str, **meta) -> dict:
            out = {"type": kind, **fields[key].percent()}
            if meta:
                out["fieldMeta"] = meta
            return out

        payload = {
            "title": title,
            "type": "DOCUMENT",
            "externalId": external_id,
            "recipients": [
                {"email": technician["email"], "name": technician["name"], "role": "SIGNER", "signingOrder": 1,
                 "fields": [f("SIGNATURE", "tech_signature", type="signature", required=True),
                            f("DATE", "tech_date")]},
                {"email": customer.get("email") or "", "name": customer["name"], "role": "SIGNER", "signingOrder": 2,
                 "fields": [f("SIGNATURE", "cust_signature", type="signature", required=True),
                            f("NAME", "cust_name"), f("DATE", "cust_date")]},
            ],
            "meta": {
                "signingOrder": "SEQUENTIAL", "distributionMethod": "NONE", "redirectUrl": redirect_url,
                "language": language, "timezone": timezone, "dateFormat": "MM/dd/yyyy",
                "typedSignatureEnabled": True, "drawSignatureEnabled": True, "uploadSignatureEnabled": False,
                # The owner is the service's own account: it needs none of these.
                "emailSettings": {"recipientSigningRequest": True, "recipientRemoved": False, "recipientSigned": False,
                                  "documentPending": False, "documentCompleted": True, "documentDeleted": False,
                                  "ownerDocumentCompleted": False, "ownerRecipientExpired": False,
                                  "ownerDocumentCreated": False},
            },
        }
        r = self._call("POST", "/envelope/create",
                       data={"payload": json.dumps(payload)},
                       files={"files": (file_name, pdf, "application/pdf")})
        return r.json()["id"]

    def distribute(self, envelope_id: str, method: str = "NONE", subject: str = "", message: str = "",
                   language: str = "en") -> list[dict]:
        """Opens the envelope for signing; returns the recipients with their signing links."""
        meta = {"distributionMethod": method, "language": language}
        if subject:
            meta["subject"] = subject
        if message:
            meta["message"] = message
        r = self._call("POST", "/envelope/distribute", json={"envelopeId": envelope_id, "meta": meta})
        return r.json().get("recipients", [])

    def switch_to_email(self, envelope_id: str, subject: str, message: str, language: str = "en") -> None:
        self._call("POST", "/envelope/update", json={"envelopeId": envelope_id, "meta": {
            "distributionMethod": "EMAIL", "subject": subject, "message": message, "language": language}})

    def redistribute(self, envelope_id: str, recipient_ids: list[int]) -> None:
        self._call("POST", "/envelope/redistribute", json={"envelopeId": envelope_id, "recipients": recipient_ids})

    def get(self, envelope_id: str) -> dict:
        return self._call("GET", f"/envelope/{envelope_id}").json()

    def cancel(self, envelope_id: str, reason: str = "") -> None:
        body = {"envelopeId": envelope_id}
        if reason:
            body["reason"] = reason
        self._call("POST", "/envelope/cancel", json=body)

    def signed_pdf(self, envelope: dict) -> bytes:
        items = envelope.get("envelopeItems") or []
        if not items:
            raise DocumensoError("The envelope has no document.")
        return self._download(f"/envelope/item/{items[0]['id']}/download?version=signed")

    def certificate(self, envelope_id: str) -> bytes:
        return self._download(f"/envelope/{envelope_id}/certificate/download")

    def _download(self, path: str) -> bytes:
        r = self._call("GET", path)
        if "json" in r.headers.get("content-type", ""):
            info = r.json()
            url = info.get("downloadUrl") or info.get("url")
            if not url:
                raise DocumensoError("Documenso gave no file for " + path)
            try:                                   # its own errors as Documenso's too (2026-10-05)
                with httpx.Client(timeout=self.timeout) as client:
                    got = client.get(url)
                    got.raise_for_status()
                    return got.content
            except httpx.HTTPError as exc:
                raise DocumensoError(f"Documenso's file could not be fetched ({exc.__class__.__name__}).") from exc
        return r.content

    def ping(self) -> dict:
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(self.base.rsplit("/api/v2", 1)[0] + "/api/health")
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {"status": "unreachable", "error": exc.__class__.__name__}
