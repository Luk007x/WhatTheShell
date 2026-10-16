# Einführung

WhatTheShell ist ein grafischer Baukasten für Terminal-Workflows. Kommandozeilen-Werkzeuge wie `grep`, `find`, `nmcli` oder `rsync` werden in einer Oberfläche im Browser zu Bausteinen. Diese lassen sich zu Abläufen zusammenklicken, ausführen und in ihrer Ausgabe auswerten. Der fertige Workflow ist eine YAML-Datei, die sich speichern, wiederverwenden und mit anderen teilen lässt.

Das Programm läuft lokal auf dem eigenen Rechner. Die Oberfläche wird von einem kleinen Server auf `127.0.0.1` ausgeliefert und im normalen Browser geöffnet (siehe Kapitel „Installation und Start“).

## Was WhatTheShell kann

- Werkzeuge auf dem Rechner finden (alle Programme im `PATH`) und ihre Optionen als Formular anzeigen. Die Optionen werden aus der Hilfe des Werkzeugs (`--help`) gelesen. Mitgelieferte und eigene Module verbessern diese Erkennung.
- Workflows als Graph (Knoten und Kanten) oder als verschachtelte Blöcke bauen. Beide Ansichten zeigen denselben Workflow.
- Die Ausgabe eines Schritts an den nächsten weiterreichen, mit Bedingungen verzweigen und über Zeilen einer Ausgabe wiederholen.
- Befehle vor dem Ausführen ansehen, als Trockenlauf prüfen und bei riskanten Schritten ausdrücklich bestätigen.
- Interaktive Programme wie `vim`, `less` oder `top` als Terminal-Schritt im Browser laufen lassen, immer in einer Sandbox.
- Optional (standardmäßig aus): KI-Funktionen, die Module oder Workflows vorschlagen.

## Grundbegriffe

| Begriff | Bedeutung |
|---|---|
| Werkzeug | Ein Programm auf dem Rechner, z. B. `grep`. Im Katalog links aufgelistet. |
| Modul | Eine YAML-Datei, die ein Werkzeug beschreibt: deutsche Beschriftungen, Gruppen, Beispiele, Sicherheitsklasse. Ohne Modul kommt alles aus der Hilfe des Werkzeugs. |
| Workflow | Eine Folge von Schritten, gespeichert als `*.workflow.yaml`. |
| Schritt | Ein Baustein des Workflows: ein Befehl, ein Terminal-Schritt oder ein Kontrollbaustein (Bedingung, Schleife, Variable setzen, Warten, Meldung, Abfrage, Abbrechen). |
| Variable | Ein benannter Wert, der beim Start des Workflows abgefragt wird und in Feldern als `{{ var.name }}` verwendet wird. |
| Lauf | Eine Ausführung eines Workflows mit konkreten Werten. Läufe sind nach dem Beenden des Servers weg. |
| Sandbox | Eine abgeschottete Umgebung (`bwrap`, bubblewrap) für Vorschau, Modul-Beispiele und Terminal-Schritte: kein Netz, nur ein beschreibbarer Ordner. |
| Sicherheitsklasse | Einstufung eines Befehls: sicher, Vorsicht oder gefährlich. Sie bestimmt, ob vor dem Start nachgefragt wird. |

## Die drei Modi

| Modus | Zweck |
|---|---|
| Erstellen | Workflows bauen und bearbeiten (Graph oder Blöcke). |
| Ausführen | Gespeicherte Workflows aus der Bibliothek starten, ohne den Editor. |
| Module | Die Beschreibung der Werkzeuge ansehen und bearbeiten. |

## Ein kurzes Beispiel

Aufgabe: In allen Logdateien eines Ordners Zeilen mit `ERROR` finden und einen Bericht schreiben, falls es Treffer gibt.

1. Im Modus „Erstellen“ im Katalog `find` suchen und auf die Arbeitsfläche ziehen.
2. Danach `grep` und `wc` hinzufügen. Zwischen `grep` und `wc` eine Datenkante (stdout → stdin) ziehen.
3. Eine Bedingung anlegen, die prüft, ob die Zeilenzahl größer als 0 ist.
4. Mit Strg+S speichern. Der Workflow erscheint im Modus „Ausführen“.

Ein ähnlicher Workflow wird mit WhatTheShell mitgeliefert: „Fehler in Logs zählen“ (`log_errors`).

## Was WhatTheShell nicht ist

- Keine Shell und kein Skript-Interpreter: Befehle werden nie als Shell-Zeile ausgeführt, sondern als Liste von Argumenten. Sonderzeichen in Werten sind wirkungslos.
- Kein Server für andere Rechner: Die Oberfläche ist nur über `127.0.0.1` erreichbar, nicht aus dem Netzwerk.
- Kein Ersatz für ein Terminal: Die Terminal-Schritte laufen in der Sandbox, es gibt kein Terminal mit vollen Rechten des Benutzerkontos.
- Kein Schutz vor allem: Ein bestätigter Befehl läuft mit den Rechten des Benutzers. Die Einstufung in Sicherheitsklassen ist eine Heuristik auf Namen und Optionen (Kapitel „Sicherheit“).
- Kein Programm für root: Ein Start als root wird verweigert.
- Kein Mehrbenutzer- oder Cloud-Dienst; Workflows und Einstellungen liegen als Dateien im Benutzerordner.
- Kein automatischer Updater: Aktualisiert wird mit dem Paketwerkzeug (Kapitel „Installation und Start“).

## Aufbau dieses Handbuchs

| Kapitel | Inhalt |
|---|---|
| Installation und Start | Voraussetzungen, Installation, Start, Beenden, Aktualisieren, Deinstallieren |
| Oberfläche | Kopfzeile, Katalog, Arbeitsfläche, Details, Ausgabe, Tastenkürzel, Einstellungen |
| Workflow bauen | Schritte, Datenfluss, Vorlagen, Variablen, Kontrollbausteine, Speichern |
| Ausführen | Startformular, Bestätigung, Trockenlauf, `wts run`, Terminal-Schritte |
| Module | Modul-Editor, eigene Module, `wts scaffold` |
| KI-Funktionen | Optionale Vorschläge durch ein Modell |
| Sicherheit | Was geschützt ist und was nicht |
| Dateien und Orte | Speicherorte und Dateiformate |
| Fehlerbehebung | Typische Meldungen und Lösungen |
