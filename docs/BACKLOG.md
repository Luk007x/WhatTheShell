# Backlog

Punkte, die bewusst zurückgestellt sind. Jeder Eintrag nennt Auslöser und Bedingung, unter der er angegangen wird.

| Thema | Stand | Angehen, wenn … |
|---|---|---|
| **AppImage** als zweiter Verteilweg (Python gebündelt, Host-Tools und bwrap vom System) | zurückgestellt 2026-10-13 (D-016) | Nutzer ohne Python/pipx erreicht werden sollen. Build aus demselben Wheel (python-appimage), Job in `release.yml`, Größe ca. 40–60 MB, Updates per AppImageUpdate. |
| Fedora-RPM über COPR | Idee | ein Paketbetreuer da ist; `pyproject.toml` ist dafür ausreichend. |
| systemd-User-Unit (`wts gui --install-service`) | Idee | jemand den Server dauerhaft laufen lassen will; bis dahin `wts gui start|stop`. |
| Echter DNS-/ssh-Test für Terminal-Schritte mit `network: true` | offen | eine CI mit Netz verfügbar ist; heute wird nur die Lesbarkeit von `resolv.conf` geprüft. |
| Bestätigung je `foreach`-Durchlauf | offen | Nutzer Klassen-Änderungen innerhalb einer Schleife erleben. |
| Kombinierte Kurzoptionen wie `-rf` in `extra_args` für die Gefahrenklasse zerlegen | offen | ein Modul Gefahr an einer Einzeloption festmacht. |
| LLM-Labels für Communities im graphify-Graphen | offen | der Graph für Außenstehende lesbar sein soll. |
| Typtreue der Hilfe-Heuristik bei BusyBox (Metavariablen nur in Beschreibung) | offen | BusyBox-Nutzer Optionen mit falschem Typ melden. |

## Nach D-017 (2026-10-16)

- **Versionshinweis in den Einstellungen:** PyPI-JSON nur auf Klick lesen, neuere Version und den passenden Update-Befehl anzeigen; kein Installieren aus der App (D-017).
- **Persistenter Lauf-Verlauf:** Workflow, Start, Dauer, Ergebnis, Exit-Code je Lauf in `cache_dir()`; ohne Ausgaben und Secrets; Ansicht im Ausführen-Modus.
- **Oberflächeneinstellungen serverseitig:** Sprache, Schrift, Theme, Startansicht in `settings.yaml` statt `localStorage`, damit sie Browserwechsel überleben.

## Nach D-020 (2026-10-16)

- **Server- und CLI-Meldungen auf Englisch:** Meldungen aus `cli.py`, Runner und API sind deutsch; für die englische Oberfläche fehlt eine Übersetzungsschicht im Backend.
- **Codex ohne Shell-Werkzeug:** sobald die Codex-CLI eine Option bietet, das Shell-Werkzeug abzuschalten, als Pflichtflag in die Allowlist aufnehmen.

## Nach D-021 (2026-10-16)

- **Engine-Komfort:** `~`-Auflösung in Pfad-Variablen, `basename`/`dirname` als Vorlagenfilter, `not`-Operator in Bedingungen, Variablenpfad als `tool` (für `--appimage-extract`).
- **Playwright-Fixture:** `gui/e2e/server.ts` soll `XDG_CONFIG_HOME` herausgeben, damit Import/Integrität end-to-end testbar werden.
