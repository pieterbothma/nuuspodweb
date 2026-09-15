"""Read Verkiesing Supabase credentials from ~/nuuspod/.env.local.

Values in that file may be wrapped in double quotes; this module strips
them. Error messages never include the values themselves.
"""

from __future__ import annotations

from pathlib import Path

STANDAARD_PAD = Path.home() / "nuuspod" / ".env.local"

_VERPLIGTE_SLEUTELS = ("VERKIESING_SUPABASE_URL", "VERKIESING_SUPABASE_SECRET_KEY")


class OmgewingFout(Exception):
    """Raised when a required environment value is missing or unreadable."""


def _ontsyfer_reël(reël: str) -> tuple[str, str] | None:
    if "=" not in reël:
        return None
    sleutel, _, waarde = reël.partition("=")
    sleutel = sleutel.strip()
    waarde = waarde.strip()
    if len(waarde) >= 2 and waarde[0] == waarde[-1] == '"':
        waarde = waarde[1:-1]
    return sleutel, waarde


def lees(pad: Path | str | None = None) -> dict[str, str]:
    """Read {url, sleutel} from an .env.local-style file.

    Defaults to ~/nuuspod/.env.local. Raises OmgewingFout (naming only the
    missing key names, never any value) if either required key is absent.
    """
    bestand = Path(pad) if pad is not None else STANDAARD_PAD

    if not bestand.exists():
        raise OmgewingFout(f"omgewingslêer nie gevind nie: {bestand}")

    waardes: dict[str, str] = {}
    for reël in bestand.read_text().splitlines():
        reël = reël.strip()
        if not reël or reël.startswith("#"):
            continue
        ontsyfer = _ontsyfer_reël(reël)
        if ontsyfer is None:
            continue
        sleutel, waarde = ontsyfer
        if sleutel in _VERPLIGTE_SLEUTELS:
            waardes[sleutel] = waarde

    ontbrekend = [naam for naam in _VERPLIGTE_SLEUTELS if not waardes.get(naam)]
    if ontbrekend:
        raise OmgewingFout(
            f"ontbrekende omgewingveranderlike(s) in {bestand}: {', '.join(ontbrekend)}"
        )

    return {
        "url": waardes["VERKIESING_SUPABASE_URL"],
        "sleutel": waardes["VERKIESING_SUPABASE_SECRET_KEY"],
    }
