"""Der Update-Public-Key muss im gebauten Host wirklich ankommen.

Warum es das braucht: Der Bau materialisierte den Schluessel nur fuer die
Module, nie fuer den Host selbst - und ``LifePlanner.spec`` nimmt die Datei nur
mit, *falls* es sie gibt. Beides schwieg. Der ausgelieferte Host hatte damit
keinen Vertrauensanker und lehnte fail-closed jedes Update ab; sichtbar wurde
das erst dem Nutzer als "kein Key hinterlegt".

Geprueft wird der Weg, nicht der Wortlaut: dass der Bau den Schluessel anlegt,
dass die Spec ihn dann auch einpackt, und dass die Ausnahme des einen Moduls
ohne eigenen Updater eine Deklaration ist statt einer fehlenden Datei.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.module_sources import load_lock

WURZEL = Path(__file__).resolve().parents[1]
KEY = WURZEL / "lifeplanner_core" / "resources" / "lifeplanner_update_public_key.b64"
BAUSKRIPTE = ("tools/build_release.py", "tools/build_linux_release.py")


def _spec_datas() -> list[tuple[str, str]]:
    """Die ``datas``-Liste aus LifePlanner.spec, wirklich ausgewertet."""
    spec = (WURZEL / "LifePlanner.spec").read_text(encoding="utf-8")
    kopf = spec.split("a = Analysis(", 1)[0]
    raum: dict[str, object] = {"SPECPATH": str(WURZEL)}
    exec(compile(kopf, "LifePlanner.spec", "exec"), raum)
    return list(raum["datas"])  # type: ignore[arg-type]


def test_die_spec_packt_den_schluessel_ein_sobald_es_ihn_gibt():
    """Die Gegenprobe zum stillen ``if ... .is_file()``.

    Im Quellbaum liegt der Schluessel nicht - er entsteht erst im Release-Bau.
    Also wird er hier angelegt und danach wieder entfernt.
    """
    vorhanden = KEY.is_file()
    if not vorhanden:
        KEY.parent.mkdir(parents=True, exist_ok=True)
        KEY.write_text("A" * 43 + "=\n", encoding="ascii")
    try:
        ziele = [ordner for quelle, ordner in _spec_datas() if Path(quelle) == KEY]
        assert ziele == ["resources"], "Update-Public-Key fehlt in den datas"
    finally:
        if not vorhanden:
            KEY.unlink(missing_ok=True)


@pytest.mark.parametrize("skript", BAUSKRIPTE)
def test_der_bau_legt_den_eigenen_schluessel_vor_dem_einfrieren_an(skript):
    """Er kam nie vor: materialisiert wurden nur die Schluessel der Module."""
    text = (WURZEL / skript).read_text(encoding="utf-8")
    # Beide Skripte benennen ihre Helfer verschieden (einmal mit fuehrendem
    # Unterstrich), gemeint ist derselbe Aufruf.
    aufruf = "materialize_host_public_key(signing=signing)"
    assert aufruf in text, f"{skript} materialisiert den eigenen Update-Public-Key nicht"
    assert text.index(aufruf) < text.index('"-m", "PyInstaller"'), (
        f"{skript}: der Schluessel entsteht erst nach dem Einfrieren"
    )


@pytest.mark.parametrize("skript", BAUSKRIPTE)
def test_ein_fehlender_helfer_bricht_den_bau_statt_zu_schweigen(skript):
    text = (WURZEL / skript).read_text(encoding="utf-8")
    assert "raise SystemExit(" in text.split("materialize_update_public_key.py")[1][:400]


def test_die_ausnahme_steht_in_der_lockdatei_statt_in_einer_fehlenden_datei():
    """Der FreizeitManager hat keinen eigenen Updater - das ist erklaert, nicht geraten."""
    ohne = {spec.module_id for spec in load_lock() if not spec.eigener_updater}
    assert ohne == {"freizeitmanager"}, ohne
