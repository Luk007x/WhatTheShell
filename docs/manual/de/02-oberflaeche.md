# Oberfläche

Die Oberfläche besteht aus Kopfzeile, Modusleiste, drei Spalten (Katalog, Mitte, Details) und einem Fußbereich mit Statuszeile und Ausgabe. Die Spaltenbreiten lassen sich an den Trennern mit der Maus ziehen oder per Tastatur ändern (Trenner fokussieren, Pfeil links/rechts, mit Umschalt in großen Schritten, Pos1/Ende). Die Breiten werden gemerkt.

## Kopfzeile

Von links nach rechts:

| Element | Wirkung |
|---|---|
| Name „WhatTheShell“ | Titel der Anwendung |
| Datei (nur in „Erstellen“) | „Neu“, „Öffnen“, „Speichern“, „Speichern unter“, „Löschen“; zeigt den Workflow-Namen und „ungespeichert“, wenn es Änderungen gibt |
| Rückgängig / Wiederholen (nur in „Erstellen“) | Macht Änderungen am Workflow rückgängig oder stellt sie wieder her |
| Sandbox-Status | „Sandbox bereit“, „Sandbox nicht verfügbar“ oder „Sandbox-Status unbekannt“. Ohne Sandbox gibt es keine Vorschau und keine Terminal-Schritte |
| Handbuch (Buch-Symbol) | Öffnet dieses Handbuch. In der Kopfzeile erscheint dann „← Zurück“, das zur Oberfläche zurückführt |
| Hilfe (Fragezeichen) | Öffnet den Hilfedialog mit den Abschnitten „Erste Schritte“, „Workflow bauen“, „Ausführen und Sicherheit“, „Module“, „Terminal“, „KI-Funktionen“, „Tastenkürzel“ |
| Darstellung (Symbol) | Jeder Klick wechselt zwischen „System“, „Hell“ und „Dunkel“; der Hinweistext lautet „Darstellung: System (klicken für Hell)“ o. ä. „System“ folgt der Einstellung des Betriebssystems |
| Zahnrad | Öffnet die „Einstellungen“ |

Beim allerersten Start öffnet sich die Hilfe automatisch. Kleine Fragezeichen-Knöpfe in den Kopfzeilen von Katalog, Arbeitsfläche, Variablen, Ausführen und Modulen springen direkt zum passenden Hilfeabschnitt.

## Modusleiste

| Element | Wirkung |
|---|---|
| Erstellen | Workflows bauen |
| Ausführen | Gespeicherte Workflows starten |
| Module | Module ansehen und bearbeiten |
| Graph / Blöcke | Nur im Modus „Erstellen“: zwei Ansichten desselben Workflows |

Der zuletzt gewählte Modus und die Ansicht werden gemerkt. Welche Ansicht beim Öffnen der App erscheint, lässt sich in den Einstellungen festlegen („Startansicht beim Öffnen“).

## Katalog (links)

Der Katalog listet die Werkzeuge auf dem Rechner.

- **Suche:** Das Feld „Werkzeuge suchen“ filtert nach dem Namen.
- **Favoriten:** Der Stern neben einem Werkzeug merkt es als Favorit. Favoriten stehen oben unter „Favoriten“, alle anderen unter „Weitere“.
- **Kategorie:** Eine farbige Kopfzeile am Schritt zeigt die Kategorie des Werkzeugs (z. B. Text, Dateien, Netzwerk), sofern ein Modul sie angibt. Bedingung, Schleife und Hilfsschritte haben eigene Farben.
- **Farbpunkte:** Der Punkt vor dem Namen zeigt die Sicherheitsklasse: „sicher“, „Vorsicht“ oder „gefährlich“.
- **Badge „Terminal“:** Das Werkzeug ist interaktiv (z. B. `vim`, `less`, `top`, `ssh`) und läuft als Terminal-Schritt im Terminal.

Ein Werkzeug wird per Ziehen auf die Arbeitsfläche oder mit Strg+Eingabe im Katalog hinzugefügt. Eingabe oder Klick wählt es nur aus.

## Arbeitsfläche (Mitte)

Zeigt den Workflow. Im Graph sind Schritte Knoten, im Block-Ansicht verschachtelte Karten (siehe Kapitel „Workflow bauen“).

Oberhalb der Fläche steht die Werkzeugleiste mit „Neu“, dem Feld „Name“, dem Knopf „Hinzufügen: NAME“ (fügt das im Katalog gewählte Werkzeug ein), den Kontrollbausteinen (Bedingung, Schleife, Variable setzen, Warten, Meldung, Abfrage, Abbrechen), dem Auswahlfeld „Ziel“ („ans Ende“, „in Dann“, „in Sonst“, „in Schleife“) und „Löschen“. Die „Legende“ auf der Fläche erklärt Kanten, Anschlüsse und Farben.

Ist die Fläche leer, steht dort: „Werkzeug aus dem Katalog hierher ziehen oder dort mit Strg+Eingabe einfügen.“

## Details (rechts)

- **Ohne Auswahl:** Die Variablen des Workflows („Variablen“).
- **Mit gewähltem Schritt:** Das Formular dieses Schritts (Befehl, Optionen, Standardeingabe, Fehlerbehandlung, Vorschau). Darunter steht der fertige Befehl zum Kopieren („Kopieren“) mit seiner „Sicherheitsklasse“.

Details zu allen Feldern: Kapitel „Workflow bauen“.

## Ausgabe (unten)

Die Ausgabe zeigt Live-Ausgabe, Meldungen und Plan eines Laufs je Schritt. „Ausgabe anzeigen“ und „Ausgabe ausblenden“ klappen den Bereich auf und zu. Bis zum ersten Lauf steht dort „Noch keine Ausgabe.“ Die Statuszeile meldet Fehler beim Verbinden und Hinweise („Workflow gültig“ oder „n Fehler im Workflow“).

## Tastenkürzel

Gelten im Modus „Erstellen“, nicht in Formularfeldern und offenen Dialogen. Strg gilt auch als Cmd. Strg+S wird in allen Modi abgefangen (speichert aber nur in „Erstellen“), `?` gilt in allen Modi und zeigt dieselbe Tabelle in der App.

| Taste | Wirkung |
|---|---|
| Entf / Rücktaste | Ausgewählten Schritt löschen (Strg+Z macht es rückgängig) |
| Strg+Z | Rückgängig |
| Strg+Umschalt+Z / Strg+Y | Wiederholen |
| Strg+S | Speichern (öffnet den Speichern-Dialog, ohne Datei „Speichern unter“) |
| Esc | Auswahl aufheben, Hinweis löschen |
| Strg+Eingabe (im Katalog) | Werkzeug am gewählten Ziel anhängen |
| ? | Hilfe öffnen (Tastenkürzel) |
| Ziehen | Katalog-Eintrag oder Kontrollbaustein auf die Fläche: Schritt entsteht an der Drop-Stelle |

In der Block-Ansicht gelten zusätzlich auf dem fokussierten Block: Alt+Pfeil hoch/runter (verschieben), Alt+Pfeil rechts (in den vorhergehenden Container), Alt+Pfeil links (hinter den Container), Entf/Rücktaste (löschen, ohne Rückfrage), Eingabe (auswählen). Im Terminal-Schritt verlässt man das Terminal mit Esc, dann Tab.

Es gibt einen Link „Zum Hauptbereich springen“ als erstes fokussierbares Element, alle Dialoge lassen sich mit Esc schließen.

## Einstellungen

Das Zahnrad öffnet die Einstellungen.

### Allgemein

| Feld | Werte | Wirkung |
|---|---|---|
| Sprache | Deutsch, English | Sprache der Oberfläche. Dieselbe Wahl gilt für Meldungen von Server und Kommandozeile `wts` (gespeichert als `language` in `settings.yaml`; `wts --lang` und `WTS_LANG` haben Vorrang) |
| Schriftgröße | klein, normal, groß | Skaliert alle Texte |
| Startansicht beim Öffnen | Zuletzt verwendet, Bauen: Graph, Bauen: Blöcke, Ausführen, Module | Wirkt beim nächsten Öffnen der App |
| Vorschau automatisch ausführen | an/aus | Nur für Befehle der Klasse „sicher“ und nur mit gewähltem Beispiel; läuft immer in der Sandbox |

### Programm

Der Knopf „WhatTheShell beenden“ beendet den Server (nach Rückfrage). Laufende Workflows werden abgebrochen.

### KI-Funktionen (optional)

Standardmäßig aus. Solange „KI-Funktionen aktivieren“ nicht angehakt ist, gibt es keine Netzwerkverbindungen und keine Fremdprozesse. Ausführlich im Kapitel „KI-Funktionen“.

| Feld | Bedeutung |
|---|---|
| KI-Funktionen aktivieren | Schaltet die Funktionen ein oder aus |
| Anbieter | Lokales Modell (Ollama, llama.cpp, LM Studio, OpenAI-kompatibel), Cloud-API (Anthropic oder OpenAI-kompatibel) oder Installiertes Agentenprogramm (Claude Code oder Codex) |
| Endpunkt (Lokales Modell) | Adresse des Modellservers; Standard `http://127.0.0.1:11434/v1` ist Ollama |
| Modell | Name des Modells, wie ihn der Endpunkt listet (lokal), bzw. Pflichtfeld bei der Cloud-API |
| Protokoll (Cloud-API) | `anthropic` oder `openai`; `openai` gilt auch für kompatible Anbieter |
| Endpunkt (optional) | Leer = Standard des Anbieters |
| Umgebungsvariable des Schlüssels | Name der Variable, nie der Schlüssel selbst. Der Server braucht sie in seiner Umgebung: vor `wts gui start` exportieren |
| Schlüsselstatus | „gesetzt“ oder „fehlt“ |
| Schlüsselquelle | Umgebungsvariable oder Systemschlüsselbund (braucht das Extra `whattheshell[keyring]`) |
| Programm (bei „Installiertes Agentenprogramm“) | `claude` oder `codex`, mit Anzeige „gefunden“ (Pfad) oder „nicht installiert“ |
| Aufrufzeile (optional) | Leer = eingebauter Aufruf. Eine Zeile je Argument; Platzhalter `{system}` und `{tmp}` |
| Zeitlimit (Sekunden) | Wartezeit auf die Antwort |
| Befehlsausgaben an die KI senden | Aus = nur Hilfetexte und Modul-/Workflow-Dateien werden gesendet. An = auch stdout/stderr aus Läufen |

Der Knopf „Speichern“ in diesem Abschnitt schreibt die KI-Einstellungen in `~/.config/whattheshell/settings.yaml`.

Sprache, Schriftgröße, Darstellung, Startansicht, Vorschau-Option und Favoriten liegen nicht in dieser Datei, sondern im Browser (Kapitel „Dateien und Orte“).
