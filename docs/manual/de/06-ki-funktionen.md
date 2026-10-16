# KI-Funktionen

Die KI-Funktionen sind optional und **standardmäßig ausgeschaltet**. Solange sie aus sind, gibt es keine Netzwerkverbindungen, keine fremden Prozesse und keinen KI-Code, der überhaupt geladen wird. Die Knöpfe „Mit KI verbessern“ und Co. zeigen dann nur „KI aus“ („KI-Funktionen sind ausgeschaltet. Einschalten unter Einstellungen.“).

Eine KI kann Vorschläge machen. Sie führt nie etwas aus: Jede Antwort kommt als Diff zur Freigabe, und der Vorschlag wird erst gespeichert, wenn man ihn übernimmt.

## Einschalten

- In der Oberfläche: Zahnrad, Abschnitt „KI-Funktionen (optional)“, „KI-Funktionen aktivieren“, Quelle einstellen, „Speichern“.
- Auf der Kommandozeile: `wts ai enable`; ausschalten mit `wts ai disable`; Einstellungen ansehen mit `wts ai status` (ohne Schlüssel).

Die Einstellungen liegen in `~/.config/whattheshell/settings.yaml` (nur für den Benutzer lesbar). Schlüssel stehen **nie** in dieser Datei.

## Quellen

Der „Anbieter“ legt fest, wohin die Anfrage geht.

### Lokales Modell

Ein Modellserver auf dem eigenen Rechner (Ollama, llama.cpp, LM Studio oder ein anderer OpenAI-kompatibler Server).

| Feld | Bedeutung |
|---|---|
| Endpunkt | Adresse des Modellservers. Standard `http://127.0.0.1:11434/v1` ist Ollama |
| Modell | Name, wie ihn der Endpunkt listet, z. B. `llama3` |
| Zeitlimit (Sekunden) | Standard 120 |

### Cloud-API

| Feld | Bedeutung |
|---|---|
| Protokoll | `anthropic` oder `openai` (`openai` gilt auch für kompatible Anbieter) |
| Endpunkt (optional) | Leer = Standard des Anbieters |
| Modell | Pflichtfeld, z. B. `claude-sonnet-5-5`. Die Prüfung meldet einen leeren Wert |
| Umgebungsvariable des Schlüssels | Name der Variable, nie der Schlüssel selbst. Standard `ANTHROPIC_API_KEY` |
| Schlüsselstatus | „gesetzt“ oder „fehlt“ |
| Schlüsselquelle | „Umgebungsvariable“ oder „Systemschlüsselbund“ (braucht das Extra `whattheshell[keyring]`) |
| Zeitlimit (Sekunden) | Standard 120 |

### Installiertes Agentenprogramm

Ruft ein auf dem Rechner installiertes Programm auf: Claude Code (`claude`) oder Codex (`codex`).

| Feld | Bedeutung |
|---|---|
| Programm | `claude` oder `codex`; daneben „gefunden“ (mit Pfad) oder „nicht installiert“ |
| Aufrufzeile (optional) | Leer = eingebauter Aufruf. Eine Zeile je Argument. Platzhalter `{system}` = Systemanweisung, `{tmp}` = leerer Arbeitsordner. Beispiel für ein anderes Modell: `claude`, `-p`, `--model`, `sonnet`, … |
| Zeitlimit (Sekunden) | Standard 300 |

Ist das Programm nicht im `PATH`, steht: „Programm nicht im PATH. Installation siehe `wts ai check`.“

### Befehlsausgaben

„Befehlsausgaben an die KI senden“: Aus (Standard) = nur Hilfetexte sowie Modul- und Workflow-Dateien werden gesendet. An = auch stdout und stderr aus Läufen, die Dateinamen oder Daten enthalten können.

## Schlüssel

Schlüssel werden nie in Dateien gespeichert. Es gibt zwei Quellen:

- **Umgebungsvariable:** Der Name steht in den Einstellungen. Die Variable muss in der Umgebung des Servers gesetzt sein, also **vor** `wts gui start` exportiert werden:

```
export ANTHROPIC_API_KEY=…
wts gui start
```

- **Systemschlüsselbund:** Dafür das Extra `whattheshell[keyring]` installieren und „Systemschlüsselbund“ als Quelle wählen.

Die Einstellungsdatei lehnt Felder mit „key“ im Namen und Werte ab, die wie ein Schlüssel aussehen. Ein Schlüssel aus der Umgebung wird in Vorschau, Fehlermeldungen und Antworten maskiert; ein Schlüssel aus dem Schlüsselbund wird nicht maskiert und steht nur in einer Fehlermeldung, wenn der Anbieter ihn selbst zurückspiegelt.

## Aufgaben

| Aufgabe | In der Oberfläche | Kommandozeile |
|---|---|---|
| Modul verbessern | Modul-Editor: „Mit KI verbessern“ | `wts ai improve-module TOOL` |
| Beispiele ergänzen | Modul-Editor: „Beispiele mit KI erzeugen“ | `wts ai examples TOOL` |
| Workflow-Entwurf aus einer Beschreibung | Datei-Menü: „Entwurf aus Beschreibung (KI)“, Felder „Beschreibung“ und „Dateiname (optional)“ | `wts ai draft-workflow "BESCHREIBUNG" [--name NAME]` |
| Diagnose eines fehlgeschlagenen Schritts | Am fehlgeschlagenen Schritt in der Ausgabe des Laufs: „Ursache analysieren (KI)“ | `wts ai diagnose LAUF.json SCHRITT_ID` (Datei = Ausgabe von `wts run --json`) |

Grundlage für „Modul verbessern“ und „Beispiele“ ist die eigene Moduldatei, sonst ein Gerüst aus der erkannten Hilfe.

## Was gesendet wird

Jede Aufgabe läuft in zwei Schritten.

1. **Vorschau:** Ein Dialog zeigt den System- und den Nutzertext **vollständig** mit Zeichenzahl („n Zeichen“). Es steht: „Diese Daten werden an die KI gesendet. Es wird nichts gesendet, bevor Sie „Senden“ wählen.“ Bei der Diagnose lässt sich „Befehlsausgaben mitsenden“ ankreuzen.
2. **Senden:** Erst „Senden“ schickt die Anfrage. „Abbrechen“ verwirft sie.

Ohne Befehlsausgaben gehen bei der Diagnose nur Befehl, Exitcode, Dauer und Status hinaus, keine Ausgabezeile. Mit Ausgaben werden diese gekürzt. Der Wert der Schlüsselvariable ist in der Vorschau maskiert.

Die Vorschau zeigt, was WhatTheShell sendet. Was ein Agentenprogramm selbst nachlädt oder an seinen Anbieter schickt, zeigt sie nicht.

Auf der Kommandozeile zeigt jede Aufgabe die Vorschau und fragt vor dem Senden nach; `--yes` bestätigt das Senden, `--preview-file DATEI` schreibt die Vorschau in eine Datei statt auf die Standardausgabe. Ohne Terminal und ohne `--yes` wird abgebrochen. Mit `--include-output` (nur Diagnose) gehen Ausgaben mit.

## Antwort: Diff, nie ausgeführt

- Die Antwort wird aus dem Text gezogen und mit denselben Regeln geprüft wie jede Modul- oder Workflow-Datei. „Gültig: ja“ oder „Gültig: nein“ zeigt das Ergebnis.
- Der Dialog zeigt die „Änderungen“ als Diff („hinzugefügt“, „entfernt“).
- Senkt ein Vorschlag die Sicherheitsklasse eines Befehls oder einer Option, steht vor dem Diff „ACHTUNG: Sicherheitsklasse … gesenkt“.
- „Übernehmen“ lädt einen Entwurf in den Editor; er ist dann noch nicht gespeichert. „Verwerfen“ wirft ihn weg.
- Auf der Kommandozeile: `--apply` schreibt das Ergebnis ohne Rückfrage in den Benutzerordner; ohne `--apply` steht „Nichts gespeichert“. `--yes` erlaubt nur das Senden, nicht das Schreiben.
- Geschrieben wird nur in den eigenen Ordner `~/.config/whattheshell/modules` bzw. `workflows`, mit einfachem Dateinamen, nie in Unterordner. Die Datei ist nur für den Benutzer lesbar.
- Die Diagnose liefert reinen Text. Er wird nicht ausgeführt.

Antworten sind nicht vertrauenswürdig: Hilfetexte, Moduldateien oder mitgesendete Ausgaben können den Vorschlag beeinflussen (Prompt-Injection). Deshalb den Diff lesen, bevor man ihn übernimmt. Wer ihn ungelesen mit `--apply` übernimmt, übernimmt das Risiko.

## Isolation der Agentenprogramme

Claude Code und Codex laufen eingeschränkt:

- In einem **Wegwerf-HOME**: ein temporärer, nur für den Benutzer lesbarer Ordner mit eigenem `home/` und `work/`. Die Konfiguration des Benutzers (globale `CLAUDE.md`, Einstellungen, Hooks, Plugins, Skills, Codex-`config.toml`) ist dort nicht vorhanden. Kopiert wird nur die Anmeldedatei (`~/.claude/.credentials.json` bzw. `~/.codex/auth.json`), falls vorhanden.
- **Ohne Schreibzugriff** auf die Dateien des Benutzers. Claude zusätzlich **ohne Werkzeuge**; Codex im Modus `read-only`.
- Der Ordner samt Sitzungsdateien wird nach jedem Aufruf gelöscht, auch bei Zeitlimit und Fehler.
- Der Prompt geht über die Standardeingabe, nicht über die Kommandozeile. Die Umgebung ist bereinigt, ergänzt um die Schlüsselvariable des Agenten und Proxy-Variablen.
- Die Antwort ist auf 2 MiB begrenzt.

Restrisiken:

- Codex im Modus `read-only` kann die ganze Platte lesen; ein eingeschleuster Prompt könnte Daten an den Anbieter senden, die die Vorschau nicht zeigt.
- Die Anmeldedaten sind dem Agenten zugänglich (nötig für den Aufruf). Einstellungen, die der Anbieter am Konto hält, gelten weiterhin.
- Liegen die Anmeldedaten nicht in einer Datei (z. B. in einem Schlüsselbund), ist der Agent im Wegwerf-HOME nicht angemeldet; der Check meldet das. Abhilfe: `ANTHROPIC_API_KEY` bzw. `claude login` / `codex login`.

## Prüfen mit `wts ai check`

```
wts ai check               # prüft die eingestellte Quelle
wts ai check --no-network  # ohne einen Endpunkt zu kontaktieren
```

Der Check prüft je nach Anbieter: Erreichbarkeit des Endpunkts, ob das Modell vorhanden ist, ob der Schlüssel gesetzt ist, ob das Agentenprogramm installiert und angemeldet ist. Jedes Ergebnis steht als Zeile mit einem Hinweis zum nächsten Schritt. Exit-Code 0 bedeutet: alles in Ordnung, 1: etwas fehlt. Ist die KI aus, meldet der Check „KI aus“, ohne etwas zu laden oder zu kontaktieren.

Agentenprogramme werden beim Check immer gestartet (Versions- und Anmeldeprüfung im Wegwerf-HOME), auch mit `--no-network`. Die Anmeldeprüfung gibt die Statusausgabe (mit E-Mail-Adresse) nicht weiter.

Einstellungen lassen sich auch auf der Kommandozeile ändern:

```
wts ai config set provider agent
wts ai config set agent.kind codex
wts ai config set api.model MODELLNAME
wts ai config set api.key_env MEINE_VARIABLE
wts ai config set send_outputs true
```

## Weitere Grenzen

- Pro Zeitpunkt laufen höchstens zwei Anbieteraufrufe gleichzeitig; sonst „KI beschäftigt. Später erneut versuchen.“
- Fehlerantworten des Anbieters werden gekürzt und von Steuerzeichen befreit; Antworten sind auf 2 MiB begrenzt. Weiterleitungen werden nicht verfolgt.
- Fehler beim Anbieter erscheinen als „Anbieterfehler“.
