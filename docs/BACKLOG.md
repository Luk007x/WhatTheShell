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
