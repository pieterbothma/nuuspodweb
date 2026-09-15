import pytest

from lib import omgewing


def test_lees_strips_quotes(tmp_path):
    pad = tmp_path / ".env.local"
    pad.write_text(
        'VERKIESING_SUPABASE_URL="https://voorbeeld.supabase.co"\n'
        'VERKIESING_SUPABASE_SECRET_KEY="sb_secret_xyz"\n'
    )
    waardes = omgewing.lees(pad)
    assert waardes == {"url": "https://voorbeeld.supabase.co", "sleutel": "sb_secret_xyz"}


def test_lees_without_quotes(tmp_path):
    pad = tmp_path / ".env.local"
    pad.write_text(
        "VERKIESING_SUPABASE_URL=https://voorbeeld.supabase.co\n"
        "VERKIESING_SUPABASE_SECRET_KEY=sb_secret_xyz\n"
    )
    waardes = omgewing.lees(pad)
    assert waardes == {"url": "https://voorbeeld.supabase.co", "sleutel": "sb_secret_xyz"}


def test_lees_ignores_other_lines(tmp_path):
    pad = tmp_path / ".env.local"
    pad.write_text(
        "# 'n kommentaar\n"
        "ANDER_SLEUTEL=iets\n"
        'VERKIESING_SUPABASE_URL="https://voorbeeld.supabase.co"\n'
        'VERKIESING_SUPABASE_SECRET_KEY="sb_secret_xyz"\n'
        "VERKIESING_TELEGRAM_CHAT_ID=12345\n"
    )
    waardes = omgewing.lees(pad)
    assert waardes == {"url": "https://voorbeeld.supabase.co", "sleutel": "sb_secret_xyz"}


def test_lees_raises_clear_error_when_missing(tmp_path):
    pad = tmp_path / ".env.local"
    pad.write_text('VERKIESING_SUPABASE_URL="https://voorbeeld.supabase.co"\n')
    with pytest.raises(omgewing.OmgewingFout) as fout_inligting:
        omgewing.lees(pad)
    boodskap = str(fout_inligting.value)
    assert "VERKIESING_SUPABASE_SECRET_KEY" in boodskap
    # Never leak the value that *was* present into the error.
    assert "voorbeeld.supabase.co" not in boodskap


def test_lees_raises_when_file_missing(tmp_path):
    pad = tmp_path / "geen-so-lêer.env"
    with pytest.raises(omgewing.OmgewingFout):
        omgewing.lees(pad)
