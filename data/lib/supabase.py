"""Batched, retrying PostgREST writes against the Verkiesing project.

Every request goes through an httpx.Client built from `omgewing.lees()`
(apikey + Bearer auth against .../rest/v1/) unless a client is injected —
tests inject an httpx.MockTransport-backed client so nothing here ever
touches the network.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from . import omgewing

MAKS_HERHALINGS = 3
BASIS_VERTRAGING_S = 0.5
KORT_BOODSKAP_LENGTE = 500


class SupabaseFout(Exception):
    """Raised on any non-recoverable PostgREST failure.

    The message is the response body truncated to KORT_BOODSKAP_LENGTE
    characters; it never includes request/response headers (which may carry
    the secret key).
    """


def _bou_klient() -> httpx.Client:
    omgewing_waardes = omgewing.lees()
    basis_url = omgewing_waardes["url"].rstrip("/") + "/rest/v1/"
    koptekste = {
        "apikey": omgewing_waardes["sleutel"],
        "Authorization": f"Bearer {omgewing_waardes['sleutel']}",
        "Content-Type": "application/json",
    }
    return httpx.Client(base_url=basis_url, headers=koptekste, timeout=30.0)


def _kort_boodskap(resp: httpx.Response) -> str:
    teks = resp.text or f"HTTP {resp.status_code}"
    return teks[:KORT_BOODSKAP_LENGTE]


def _herhaalbaar(status_kode: int) -> bool:
    return status_kode == 429 or status_kode >= 500


def _stuur_met_herhaling(
    klient: httpx.Client, pad: str, liggaam: Any, koptekste: dict[str, str]
) -> httpx.Response:
    resp = klient.post(pad, json=liggaam, headers=koptekste)
    poging = 0
    while _herhaalbaar(resp.status_code) and poging < MAKS_HERHALINGS:
        time.sleep(BASIS_VERTRAGING_S * (2**poging))
        poging += 1
        resp = klient.post(pad, json=liggaam, headers=koptekste)
    return resp


def _plaas_bondel(
    klient: httpx.Client, tabel: str, bondel: list[dict], koptekste: dict[str, str]
) -> None:
    if not bondel:
        return

    resp = _stuur_met_herhaling(klient, tabel, bondel, koptekste)

    if resp.status_code == 413:
        if len(bondel) == 1:
            raise SupabaseFout(_kort_boodskap(resp))
        helfte = len(bondel) // 2
        _plaas_bondel(klient, tabel, bondel[:helfte], koptekste)
        _plaas_bondel(klient, tabel, bondel[helfte:], koptekste)
        return

    if resp.status_code >= 400:
        raise SupabaseFout(_kort_boodskap(resp))


def plaas_bondels(
    tabel: str,
    rye: list[dict],
    grootte: int = 500,
    klient: httpx.Client | None = None,
) -> list[dict]:
    """POST rye to tabel in batches of `grootte`.

    Halves a batch and retries on 413. Retries up to MAKS_HERHALINGS times
    with exponential backoff on 429/5xx. Any other failure raises
    SupabaseFout. Returns rye (the rows sent) on success.
    """
    eie_klient = klient is None
    aktiewe_klient = klient if klient is not None else _bou_klient()
    koptekste = {"Prefer": "return=minimal"}
    try:
        for i in range(0, len(rye), grootte):
            _plaas_bondel(aktiewe_klient, tabel, list(rye[i : i + grootte]), koptekste)
    finally:
        if eie_klient:
            aktiewe_klient.close()
    return rye


def kry_alles(
    pad: str,
    parameters: dict[str, str] | None = None,
    klient: httpx.Client | None = None,
    bladsy_grootte: int = 1000,
) -> list[dict]:
    """GET pad (e.g. "stg_wyke") with optional query `parameters`, paginated via the
    PostgREST `Range` header, returning every row.

    Keeps requesting `[begin, begin+bladsy_grootte)` windows until a page comes back
    shorter than `bladsy_grootte` (the last page). No retry logic — reads are used only
    for verslag diagnostics, so a transient failure should surface immediately as a
    SupabaseFout rather than being silently retried.
    """
    eie_klient = klient is None
    aktiewe_klient = klient if klient is not None else _bou_klient()
    alle_rye: list[dict] = []
    try:
        begin = 0
        while True:
            koptekste = {"Range-Unit": "items", "Range": f"{begin}-{begin + bladsy_grootte - 1}"}
            resp = aktiewe_klient.get(pad, params=parameters, headers=koptekste)
            if resp.status_code >= 400:
                raise SupabaseFout(_kort_boodskap(resp))
            bladsy = resp.json()
            alle_rye.extend(bladsy)
            if len(bladsy) < bladsy_grootte:
                break
            begin += bladsy_grootte
    finally:
        if eie_klient:
            aktiewe_klient.close()
    return alle_rye


def rpc(naam: str, args: dict, klient: httpx.Client | None = None) -> Any:
    """POST rpc/<naam> with args, return the parsed JSON (or None on 204)."""
    eie_klient = klient is None
    aktiewe_klient = klient if klient is not None else _bou_klient()
    try:
        resp = _stuur_met_herhaling(aktiewe_klient, f"rpc/{naam}", args, {})
        if resp.status_code >= 400:
            raise SupabaseFout(_kort_boodskap(resp))
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()
    finally:
        if eie_klient:
            aktiewe_klient.close()
