"""Zeitstempel fuer Dateinamen - an einer Stelle, mit der Begruendung dabei.

Der Host stempelt an mehreren Stellen die Uhrzeit in einen Namen: Profil-
Sicherungen, Rollback-Ordner, Update-Plaene, verworfene settings.json. Diese
Namen liest ein Mensch, der wissen will, welche Sicherung von heute Mittag
stammt - deshalb ist hier ausdruecklich die lokale Zeit richtig und nicht UTC.

Ohne diesen Ort stuende die Entscheidung fuenfmal als nackter
``datetime.now()`` im Code, jede fuer sich unbegruendet, und der Linter haette
fuenfmal recht damit, sie anzumahnen (DTZ005).

Fuer alles, was zwischen Programmen ausgetauscht oder verglichen wird - Events,
Manifeste, Bridge-Datensaetze -, gilt das Gegenteil: dort gehoert eine
zeitzonenbewusste UTC-Angabe hin. ``jetzt_utc`` steht dafuer daneben.
"""

from __future__ import annotations

from datetime import UTC, datetime

DATEI_FORMAT = "%Y%m%d-%H%M%S"


def dateimarke(zeitpunkt: datetime | None = None) -> str:
    """Lokale Zeit als ``20260822-174500`` - sortierbar und ohne Sonderzeichen.

    Der Wert landet in Dateinamen; die Zeichenauswahl ist damit nicht nur
    Geschmack, sondern muss auf allen drei Betriebssystemen zulaessig sein.
    """
    return (zeitpunkt or datetime.now()).strftime(DATEI_FORMAT)  # noqa: DTZ005


def jetzt_utc() -> datetime:
    """Zeitzonenbewusste Gegenwart fuer alles, was das Programm verlaesst."""
    return datetime.now(UTC)
