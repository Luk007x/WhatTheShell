# Projektauftrag für Claude Code: Grafischer Baukasten für Terminal-Workflows

> Status: **Version 2.** Annahmen (Abschnitt 13) bestätigt, Entscheidungen des Auftraggebers in Abschnitt 14 verbindlich festgehalten. Offen sind nur die Verfügbarkeitsprüfung des Namens und Lizenzdetails (Abschnitt 18).
> Projektname: **WhatTheShell** (Abschnitt 18). Python-Paket und Importname: `whattheshell`. CLI-Befehl: `whattheshell` mit Kurzalias `wts`. Der Name steht an genau einer Stelle (`pyproject.toml` plus eine Konstante), damit eine spätere Umbenennung leicht bleibt.

---

## 1. Ziel in einem Satz

Ein Linux-Programm mit grafischer Oberfläche, in dem man Kommandozeilen-Tools wie Bausteine (ähnlich Scratch) zu Workflows zusammenklickt, diese ausführt, die Ausgaben auswertet und anhand der Ergebnisse den weiteren Ablauf steuert. Die Bausteine werden **automatisch aus der `--help`-Ausgabe (und Man-Pages) der auf dem System installierten Tools erzeugt** und lassen sich über **dateibasierte Module (YAML/JSON)** per Hand oder durch eine KI verfeinern.

## 2. Hintergrund und Motivation

- Terminal-Tools sind mächtig, aber schwer zu entdecken: Optionen, Reihenfolge und Syntax muss man kennen oder nachschlagen.
- Skripte (Bash) sind für Einsteiger fehleranfällig (Quoting, Pipes, Exit-Codes).
- Visuelle Baukästen (Scratch, Node-RED, n8n) senken die Hürde, kennen aber keine beliebigen lokalen CLI-Tools.
- Dieses Projekt schließt die Lücke: **jedes installierte CLI-Tool wird automatisch zum Baustein**, mit Erklärung und Live-Beispiel.

## 3. Zielgruppe und Kernszenarien

| Nutzer | Szenario |
|---|---|
| Einsteiger | Will `ffmpeg`, `grep`, `find`, `git` verstehen und nutzen, ohne Syntax auswendig zu lernen. |
| Fortgeschrittene | Baut wiederholbare Workflows (Backup, Medienkonvertierung, Log-Analyse) grafisch und teilt sie als Datei. |
| Autoren/KI | Erzeugen und verbessern Module (Beschreibungen, Beispiele, Vorlagen) rein als YAML/JSON-Dateien. |

Beispiel-Workflow: *„Finde alle `.log`-Dateien (`find`), durchsuche sie nach „ERROR" (`grep`), zähle Treffer (`wc`). Wenn Anzahl > 0, schreibe eine Zusammenfassung in eine Datei, sonst gib „alles gut" aus."*

## 4. Abgrenzung (Nicht-Ziele der ersten Versionen)

- Kein Ersatz für eine vollständige Shell oder ein CI-System.
- Keine Windows-/macOS-Unterstützung (nur Linux).
- Kein Cloud-/Mehrbenutzerbetrieb, keine Remote-Ausführung (spätere Option).
- Keine interaktiven Programme (`vim`, `top`, `ssh`) in den ersten Phasen. Ein eingebettetes Terminal ist für Phase 7 geplant.
- KI-Funktionen sind **optional und standardmäßig aus** (siehe 6.6). Die Dateiformate müssen unabhängig davon so gestaltet sein, dass eine KI Module erzeugen kann (siehe 8).
- Kein eigener Shell-Interpreter. Es wird nie ein Shell-String zusammengebaut (siehe 10).

## 5. Kernkonzepte (Glossar)

- **Tool**: Ein ausführbares Programm auf dem System (z. B. `grep`).
- **Befehl (Command)**: Ein Tool oder Subtool (z. B. `git commit`).
- **Katalog**: Die automatisch erzeugte Sammlung aller erkannten Tools und ihrer Optionen, gecacht auf der Platte.
- **Baustein (Block)**: Visuelle Darstellung eines Befehls oder einer Kontrollstruktur, mit Eingabefeldern für Optionen und Argumente.
- **Modul**: Eine Datei (YAML/JSON), die Bausteine für ein Tool **überschreibt oder ergänzt**: bessere Texte, Beispiele, Gruppierung, Standardwerte, Vorlagen. Module haben Vorrang vor automatisch Erkanntem.
- **Workflow**: Eine Datei, die eine Abfolge/einen Graphen aus Bausteinen beschreibt.
- **Evaluator (Auswerter)**: Regel, die Ausgabe/Exit-Code eines Schritts prüft und ein Ergebnis (Wahr/Falsch, Wert) liefert.
- **Vorschau (Beispiel)**: Live-Ausführung des aktuellen Bausteins in einer sicheren Umgebung mit Beispieldaten, sodass man sofort sieht, was er tut.

## 6. Funktionale Anforderungen

### 6.1 Tool-Erkennung und Katalog
- **F-1** Die App durchsucht `PATH` nach ausführbaren Dateien und bietet sie in einer durchsuchbaren Liste an (nach Kategorie, Name, Kurzbeschreibung).
- **F-2** Für jedes Tool wird die Hilfe **bei Bedarf (lazy)** abgefragt, nicht für alle Tools beim Start. Quellen in dieser Reihenfolge: Modul-Datei → `tool --help` → `tool -h` → `man tool` (nur lesen) → `tldr`-Seiten falls installiert (nur für Beispiele).
- **F-3** Subbefehle (`git commit`, `docker run`, `ip addr`) werden rekursiv erkannt (`tool sub --help`), mit Tiefenlimit.
- **F-4** Ergebnis wird als strukturierte Beschreibung **gecacht** (Schlüssel: Pfad + Version + Hash der Hilfe). Bei Tool-Update wird neu geparst.
- **F-5** Das Parsen der Hilfe liefert **pro Option eine Konfidenz** (hoch/mittel/niedrig). Unsichere Stellen werden in der GUI markiert, und der Nutzer kann sie per Modul korrigieren.
- **F-6** Fallback: Wenn die Hilfe nicht parsbar ist, wird ein generischer Baustein „Freie Argumente" mit dem Rohtext der Hilfe angeboten. Nie abbrechen.

### 6.2 Bausteine
- **F-7** Jede Option wird zu einem Eingabefeld passenden Typs: Schalter (Flag), Text, Zahl, Datei/Ordner (mit Dateiauswahl), Auswahlliste (Enum), Mehrfachwert, Pflicht/Optional, Standardwert.
- **F-8** Zu jeder Option wird der Hilfetext direkt am Feld angezeigt (Tooltip/Seitenpanel), Kurz- und Langform (`-r`/`--recursive`) werden zusammengeführt.
- **F-9** Optionen sind gruppiert und durchsuchbar. Häufige Optionen stehen oben, seltene eingeklappt (Gruppierung aus Modul oder Heuristik).
- **F-10** Der Baustein zeigt jederzeit den **resultierenden Befehl als Text** (korrekt gequotet) und lässt ihn kopieren.
- **F-11** Es gibt Kontroll-Bausteine: Reihenfolge, Pipe (`|`), Bedingung (wenn/sonst), Schleife (für jede Zeile/Datei), Variable setzen/lesen, Warten, Meldung anzeigen, Abbrechen.

### 6.3 Live-Vorschau („sehe direkt, was der Befehl macht")
- **F-12** Neben jedem Baustein: Button **„Beispiel ausführen"**. Führt den Befehl in einer **isolierten Sandbox mit mitgelieferten Beispieldaten** aus und zeigt Eingabe → Befehl → Ausgabe.
- **F-13** Beispieldaten und -aufrufe kommen aus dem Modul (Feld `examples`). Gibt es keins, wird nur der Befehl angezeigt, es wird nichts automatisch ausgeführt.
- **F-14** Die Vorschau aktualisiert sich nach Änderung eines Feldes (mit Verzögerung/Debounce) nur bei Befehlen, die als **sicher** eingestuft sind (siehe 10).
- **F-15** Vorschau unterscheidet stdout, stderr, Exit-Code und Laufzeit farblich.

### 6.4 Workflow-Ausführung und Auswertung
- **F-16** Workflows laufen schrittweise mit Live-Ausgabe pro Schritt, Pause/Abbruch/Einzelschritt.
- **F-17** Pro Schritt wird gespeichert: Befehl, Start/Ende, Exit-Code, stdout, stderr (mit Größenlimit).
- **F-18** **Evaluatoren** werten Ergebnisse aus: Exit-Code gleich/ungleich, stdout enthält/Regex/leer, Zeilenanzahl, Zahlenvergleich, JSON-Pfad (`jq`-artig), Dateiexistenz. Ergebnis steuert Bedingungen, Schleifen und Fehlerbehandlung.
- **F-19** Ausgaben können in Variablen übernommen und in späteren Schritten verwendet werden (`{{ schritt1.stdout }}`, `{{ var.name }}`).
- **F-20** Fehlerbehandlung pro Schritt: abbrechen / weitermachen / wiederholen (n-mal) / Alternativzweig.
- **F-21** Trockenlauf (Dry-Run): zeigt alle Befehle, die ausgeführt würden, ohne etwas auszuführen.

### 6.5 Module und Dateien
- **F-22** Module und Workflows sind **reine Textdateien** (YAML, alternativ JSON), in einem Nutzerverzeichnis (`~/.config/whattheshell/`) und optional projektlokal.
- **F-23** Beim Start und per „Neu laden" werden Dateien eingelesen, validiert (JSON-Schema) und Fehler mit Datei/Zeile angezeigt. Fehlerhafte Module deaktivieren **nur sich selbst**.
- **F-24** Datei-Änderungen im Dateisystem werden live erkannt (Hot-Reload).
- **F-25** Ein **In-App-Editor** (Formular + Rohtext) für Module, mit Export/Import und „Aus erkanntem Baustein ein Modul erzeugen" als Startpunkt.
- **F-26** Veröffentlichte JSON-Schemas für Modul und Workflow, damit Editoren und KIs validieren können (siehe 8.3).

### 6.6 Optionale KI-Funktionen (standardmäßig AUS)
- **F-27** Ein-/Ausschalter in den Einstellungen, Standard: aus. Solange er aus ist, wird kein KI-Code-Pfad ausgeführt, es entstehen keine Netzwerkverbindungen und keine Fremdprozesse.
- **F-28** Provider-Abstraktion (`ai/providers`) mit drei Arten:
  - **Lokal:** OpenAI-kompatible lokale Endpunkte (Ollama, llama.cpp, LM Studio).
  - **API:** Cloud-APIs (z. B. Anthropic, OpenAI-kompatible), API-Key aus Umgebungsvariable oder Schlüsselbund, nie im Klartext in Dateien.
  - **Agenten-CLIs:** Claude Code (nicht-interaktiv, z. B. `claude -p`) und Codex CLI (z. B. `codex exec`) als Subprozess. Die Aufrufzeilen sind konfigurierbar, weil sich CLIs ändern. **Prüfe die aktuelle Aufrufsyntax in der offiziellen Dokumentation, bevor du sie implementierst.**
- **F-29** Funktionen: Modul verbessern (Beschreibungen, Gruppierung, Standardwerte), Beispiele und Beispieldaten (`fixtures`) erzeugen, Workflow aus einer Textbeschreibung entwerfen, bei einem fehlgeschlagenen Schritt Ursachen und Korrekturvorschläge liefern (nur Vorschläge).
- **F-30** Sicherheitsregeln:
  - KI liefert ausschließlich **Dateien** (Modul/Workflow). Diese werden gegen das Schema validiert und als **Diff zur Freigabe** angezeigt.
  - **Nie automatische Ausführung** von KI-Ergebnissen. KI-Ausgaben gelten als untrusted (Abschnitt 10, Punkt 6).
  - Vor dem Senden zeigt die App, welche Daten gesendet werden. Befehlsausgaben werden nur auf ausdrücklichen Wunsch mitgesendet, Secrets sind maskiert.
  - Agenten-CLIs laufen mit eingeschränktem Arbeitsverzeichnis und Schreibzugriff nur auf den Modul-/Workflow-Ordner.
- **F-31** Alle KI-Funktionen sind auch per CLI nutzbar (z. B. `wts ai improve-module grep`). Damit können externe Agenten wie Claude Code oder Codex direkt Dateien erzeugen. `docs/MODULE_AUTHORING.md` plus die JSON-Schemas müssen dafür ausreichen.

### 6.7 Ansichten (Knoten-Graph und Block-Ansicht)
- **F-32** Derselbe Workflow ist in zwei Darstellungen sichtbar: **Knoten-Graph** (Standard) und **Block-Ansicht** (Scratch-artig, einrastende Bausteine). Umschalten ist jederzeit und ohne Datenverlust möglich; die Wahl wird als Nutzereinstellung gespeichert.
- **F-33** Der Zustand lebt im **kanonischen Modell des Kerns**. Beide Ansichten sind reine Darstellungsschichten (Renderer + Editieroperationen über die Kern-API), ohne eigene Logik.
- **F-34** Positionsdaten (Layout) liegen in einem getrennten, optionalen Abschnitt der Workflow-Datei. Fehlt er, wird automatisch angeordnet.
- **F-35** Jede Struktur muss in beiden Ansichten darstellbar und bearbeitbar sein, auch wenn sie nicht überall gleich elegant aussieht.

### 6.8 Später: Eingebettetes Terminal (Phase 7)
- **F-36** Interaktive Programme laufen in einem eingebetteten Terminal (z. B. xterm.js im Browser, PTY im Backend) und können als Schritt in einem Workflow vorkommen. Vor der Umsetzung ist ein eigener Sicherheitsabschnitt zu schreiben (Rechte, Sitzungsisolation, Eingabeprotokollierung).

## 7. Nicht-funktionale Anforderungen

- **Plattform:** Linux (Debian/Ubuntu, Fedora, Arch). Distribution zuerst lokal (Entwicklungsinstallation), danach per `pip`/`pipx` (PyPI-Paket mit eingebettetem, vorgebautem Frontend, Python ≥ 3.11, **kein Node nötig zur Laufzeit**). Systemvoraussetzung für die Vorschau: `bubblewrap` (`bwrap`).
- **Performance:** Start < 2 s; Hilfe-Parsing eines Tools < 1 s (gecacht < 50 ms); GUI bleibt flüssig bei Workflows mit 200 Bausteinen.
- **Robustheit:** Nie ein Absturz durch merkwürdige Hilfetexte. Parser laufen in eigenem Prozess/Timeout.
- **Offline:** Vollständig offline nutzbar (KI-Funktionen optional, mit lokalen Modellen ebenfalls offline möglich).
- **Lokalisierung:** UI Deutsch und Englisch (i18n von Anfang an), Hilfetexte der Tools bleiben im Original, Module können Übersetzungen enthalten.
- **Barrierefreiheit:** Tastaturbedienung, ausreichende Kontraste, skalierbare Schrift.
- **Datenschutz:** Keine Telemetrie. Netzwerkzugriffe durch die App nur, wenn der Nutzer KI-Funktionen mit einem Cloud-Provider aktiviert hat.

## 8. Dateiformate (verbindlich zu entwerfen, Entwurf unten)

Ziel: **menschenlesbar, diff-bar, von KI zuverlässig erzeugbar, per JSON-Schema validierbar.** Jede Datei hat `schema_version`.

### 8.1 Modul (Beispiel `grep.module.yaml`)

```yaml
schema_version: 1
tool: grep
display_name: "grep – Text durchsuchen"
category: Text
summary: "Durchsucht Dateien oder Eingaben nach Mustern."
description: |
  Gibt alle Zeilen aus, die zu einem Muster passen.
override_mode: merge        # merge | replace  (Verhältnis zur Auto-Erkennung)

inputs:                     # Positionsargumente
  - id: pattern
    label: Suchmuster
    type: string
    required: true
    help: "Regulärer Ausdruck oder fester Text."
  - id: files
    label: Dateien
    type: path[]
    required: false

options:
  - id: ignore_case
    flags: ["-i", "--ignore-case"]
    label: Groß-/Kleinschreibung ignorieren
    type: bool
    group: Suche
    importance: common      # common | normal | rare
    help: "Unterscheidet nicht zwischen Groß- und Kleinbuchstaben."
  - id: recursive
    flags: ["-r", "--recursive"]
    type: bool
    group: Dateien
  - id: context
    flags: ["-C", "--context"]
    type: int
    min: 0
    default: 2
    group: Ausgabe

output:
  stdout:
    kind: lines             # lines | text | json | csv | bytes
  exit_codes:
    0: "Treffer gefunden"
    1: "Keine Treffer"
    2: "Fehler"
safety: safe                # safe | caution | dangerous  (siehe 10)

examples:
  - title: "Fehlerzeilen finden"
    description: "Sucht ERROR ohne Rücksicht auf Groß-/Kleinschreibung."
    fixtures:               # Dateien, die in der Sandbox angelegt werden
      - path: app.log
        content: |
          INFO start
          ERROR disk full
          error timeout
    args:
      ignore_case: true
      pattern: "error"
      files: ["app.log"]
    expect:
      exit_code: 0
      stdout_contains: "disk full"

templates:                  # vorgefertigte Mini-Workflows
  - title: "Treffer zählen"
    workflow: grep_count.workflow.yaml
```

### 8.2 Workflow (Beispiel)

```yaml
schema_version: 1
name: "Fehler in Logs zählen"
variables:
  logdir: { type: path, default: "./logs" }
steps:
  - id: finde
    tool: find
    args: { path: "{{ var.logdir }}", name: "*.log", type: f }
  - id: suche
    tool: grep
    args: { pattern: "ERROR", recursive: true, count: true }
    stdin: "{{ finde.stdout }}"        # oder pipe: finde
    on_error: continue
  - id: pruefe
    if:
      eval: { source: suche.stdout, number_gt: 0 }
    then:
      - id: bericht
        tool: tee
        args: { file: "bericht.txt" }
    else:
      - id: ok
        action: message
        text: "Alles in Ordnung."
```

### 8.3 Anforderungen an die Formate
- Spezifikation als **JSON-Schema** (`schemas/module.schema.json`, `schemas/workflow.schema.json`), automatisch aus den Typen im Code erzeugt oder umgekehrt, damit sie nie auseinanderlaufen.
- Genau **eine** Quelle der Wahrheit für die Datenmodelle (z. B. Pydantic-Modelle, daraus Schema-Export).
- Fehlermeldungen beim Validieren müssen für Menschen **und KI** brauchbar sein (Pfad zum Feld, erwarteter Typ, Vorschlag).
- Ein Dokument `docs/MODULE_AUTHORING.md` erklärt das Format mit Beispielen so, dass eine KI damit zuverlässig Module erzeugen kann (inkl. Prompt-Vorlage).
- Abwärtskompatibilität über `schema_version` plus Migrationsfunktionen.
- **Das Workflow-Format muss ohne Informationsverlust sowohl als Knoten-Graph als auch als Block-Folge darstellbar sein (siehe 6.7).** Der Entwurf in 8.2 ist nur ein Startpunkt. Überarbeite ihn in Phase 0 (z. B. Knoten mit `id`, Ports und Verbindungen, Kontrollstrukturen als Knoten, optionaler getrennter `layout`-Abschnitt) und lege den Vorschlag zur Abnahme vor, bevor du die Engine baust.
- Ein CLI-Befehl `wts validate <datei>` und `wts scaffold <tool>` (erzeugt aus der Auto-Erkennung ein Modul-Gerüst zum Verfeinern).

## 9. Hilfe-Parser (Herzstück, besondere Sorgfalt)

**Ziel:** Aus unstrukturiertem Hilfetext eine strukturierte Optionsliste ableiten.

Vorgehen:
1. Hilfetext holen (`--help`, `-h`, `man -P cat`), mit Timeout, ohne Terminalsteuerzeichen, mit gesetzter Umgebung `LC_ALL=C` (stabile Formatierung) plus Option für Nutzersprache.
2. Abschnitte erkennen (Usage, Options, Commands, Examples).
3. Optionszeilen per mehrstufigen Heuristiken parsen: `-x, --long=ARG`, `-x ARG`, `--long[=ARG]`, `--[no-]flag`, eingerückte Beschreibungen über mehrere Zeilen, Standardwerte („default: 5"), Wertelisten („one of: a, b, c"), Metavariablen (`FILE`, `NUM`, `DIR`) → Typ ableiten.
4. Subbefehle erkennen (Abschnitt `Commands:`/`Available commands`), rekursiv, mit Limit.
5. Ergebnis pro Option mit **Konfidenz**.
6. Bekannte Hilfeformate (GNU, argparse, click/cobra/clap, BusyBox) mit **Testkorpus** abdecken.

**Pflicht:** Ein Test-Korpus (`tests/corpus/`) mit gespeicherten Hilfetexten echter Tools (grep, find, ls, tar, curl, git, ffmpeg, rsync, docker, ip, systemctl, jq, sed, awk, BusyBox-Varianten) und erwarteten Parser-Ergebnissen (Golden Files). Neue Parsing-Fehler werden zuerst als Testfall angelegt.

Optional später: Shell-Completion-Skripte (`_tool`, bash-completion) als zusätzliche, oft genauere Quelle.

## 10. Sicherheit (nicht verhandelbar)

Die App führt beliebige Befehle aus. Deshalb:

1. **Kein `shell=True`, keine String-Konkatenation.** Befehle werden immer als **Argument-Liste** (`argv`) gestartet. Pipes werden vom Programm selbst verdrahtet. Der angezeigte Befehlstext wird nur zur Anzeige gequotet (`shlex.quote`).
2. **Sicherheitsklassen** pro Tool/Option (`safe`, `caution`, `dangerous`), erkannt über Heuristiken und überschreibbar im Modul (z. B. `rm`, `dd`, `mkfs`, `chmod -R`, `sudo` = dangerous).
3. **Vorschau nur in einer `bwrap`-Sandbox (Bubblewrap), ohne Ausnahme:** temporäres Verzeichnis als einziges beschreibbares Arbeitsverzeichnis, übriges Dateisystem schreibgeschützt oder unsichtbar, kein Netzwerk (`--unshare-net`), `--unshare-pid`, `--die-with-parent`, bereinigte Umgebungsvariablen, Zeit-, Speicher- und Ausgabelimit.
   - Beim Start läuft ein **Selbsttest der Sandbox**. Ist `bwrap` nicht installiert oder funktionsunfähig (z. B. gesperrte User-Namespaces), ist die Vorschau **deaktiviert**. Die App zeigt eine einsteigerfreundliche Meldung mit dem passenden Installationsbefehl für die erkannte Distribution und einem Button „Erneut testen".
   - Es gibt **keinen ungeschützten Ersatzmodus**.
   - Automatische Vorschau nur für `safe`.
   - Optional (Phase 3): Schalter „Geschützter Lauf", der ganze Workflows ebenfalls in `bwrap` ausführt. Normale Läufe passieren auf dem Host mit Bestätigung nach Punkt 4.
4. **Bestätigung:** `caution`/`dangerous` verlangt vor echter Ausführung eine Bestätigung mit Klartext-Befehl. Dry-Run immer verfügbar.
5. **Kein stilles Sudo.** Rechteerhöhung nur bewusst und sichtbar.
6. **Workflow-Dateien sind untrusted:** Beim Öffnen einer fremden Datei wird nichts ausgeführt. Vor dem ersten Lauf zeigt die App eine Zusammenfassung aller Befehle und der Gefahrenklassen.
7. **Template-Ausdrücke** (`{{ ... }}`) in einer eingeschränkten, sicheren Sprache (keine Codeausführung).
8. Logs enthalten keine Geheimnisse: Felder vom Typ `secret` werden maskiert.

## 11. GUI-Konzept

- **Drei Bereiche:** links *Katalog* (Suche, Kategorien, Favoriten), Mitte *Arbeitsfläche* (Bausteine zusammenstecken), rechts *Detail/Hilfe/Vorschau* des gewählten Bausteins. Unten *Ausgabe-/Verlaufspanel*.
- Standardansicht ist der **Knoten-Graph** (Knoten = Befehle und Kontrollstrukturen, Kanten = Datenfluss, Pipes, Ablauf). Umschaltbar auf die **Block-Ansicht** (Scratch-artig, einrastend), siehe 6.7.
- Farbcodierung nach Kategorie und Sicherheitsklasse.
- Jedes Eingabefeld zeigt Hilfetext, Typ und Standardwert; Pflichtfelder sind markiert.
- Ausgaben sind klickbar: „Als Variable übernehmen", „Hier auswerten" (erzeugt Evaluator).
- Rückgängig/Wiederholen, Speichern/Laden, Zoom, Suchen im Workflow.
- Erste Fassung: funktional und übersichtlich, **kein Pixelperfektionismus**.

### Technologie (entschieden)
- **Kern:** Python ≥ 3.11, eigenständige Bibliothek **ohne GUI-Abhängigkeit**, mit CLI (`whattheshell`, Alias `wts`). Pydantic für Modelle und Schema-Export.
- **GUI:** Lokale **Web-UI**. Backend FastAPI mit WebSocket für Live-Ausgaben, Frontend in TypeScript. Der Befehl `wts` startet den lokalen Server und öffnet den Browser.
- **Sicherheit der Web-UI (kritisch, da die API Befehle ausführen kann):** Server bindet nur an `127.0.0.1`, zufälliges Sitzungstoken, Origin-/Host-Prüfung gegen DNS-Rebinding und CSRF, keine offenen CORS-Regeln, kein Start als root.
- **Auslieferung:** Das Frontend wird vorgebaut ins Python-Paket kopiert, damit `pip`/`pipx` ohne Node funktioniert.
- **Knoten-Graph-Bibliothek:** Wähle eine etablierte Bibliothek (z. B. React Flow / Svelte Flow oder Rete.js) und begründe die Wahl in `docs/DECISIONS.md`. **Blockly** ist für die Block-Ansicht (Phase 5) vorgesehen und nicht mehr die Hauptansicht.
- **Strikte Trennung:** Kern bietet eine klar definierte API/Events. Ansichten sind austauschbare Renderer (siehe 6.7). Der Kern bleibt ohne GUI testbar.

## 12. Architektur und Projektstruktur (Vorschlag)

```
whattheshell/
├─ CLAUDE.md                  # Regeln für Claude Code (aus Abschnitt 15 ableiten)
├─ pyproject.toml
├─ src/whattheshell/
│  ├─ catalog/                # Tool-Suche, Cache, Versionierung
│  ├─ helpparse/              # Hilfe-Parser (Herzstück), Heuristiken, Konfidenz
│  ├─ models/                 # Pydantic-Modelle: Tool, Option, Modul, Workflow
│  ├─ modules/                # Laden, Validieren, Mergen, Hot-Reload
│  ├─ engine/                 # Ausführung, Pipes, Variablen, Evaluatoren, Fehlerbehandlung
│  ├─ sandbox/                # Isolierte Vorschau, Limits
│  ├─ safety/                 # Gefahrenklassen, Bestätigungslogik
│  ├─ api/                    # HTTP/WebSocket-Schnittstelle zur Web-UI (nur localhost)
│  ├─ ai/                     # optionale KI-Provider (lokal, API, Agenten-CLI)
│  ├─ terminal/               # später: eingebettetes Terminal (Phase 7)
│  └─ cli.py                  # validate, scaffold, run, dry-run
├─ gui/                       # Web-Frontend (TypeScript); Build wird ins Paket kopiert
├─ modules/                   # Mitgelieferte Beispielmodule (grep, find, ls, tar, ...)
├─ workflows/                 # Mitgelieferte Beispiel-Workflows
├─ schemas/                   # Exportierte JSON-Schemas
├─ docs/                      # MODULE_AUTHORING.md, ARCHITECTURE.md, SECURITY.md
└─ tests/                     # unit, corpus (Golden Files), e2e
```

Datenfluss: `Tool auf PATH → helpparse → Roh-Katalog → (+ Modul-Overrides) → fertiger Baustein → GUI → Workflow-Datei → Engine → Ergebnis/Evaluator`.

## 13. Annahmen (vom Auftraggeber bestätigt)

1. Linux-Desktop mit installiertem `man`, Standard-GNU-Tools; GUI-Toolkit-Entscheidung liegt bei dir.
2. Primäre Sprache der UI ist Deutsch, Code und Dateischlüssel sind Englisch.
3. Open Source mit Copyleft, Details siehe Abschnitt 18.
4. Ein einzelner Entwickler plus Claude Code; Priorität liegt auf einem funktionierenden, stabilen Kern vor GUI-Politur.
5. Sandboxing basiert ausschließlich auf `bwrap` (Abschnitt 10, Punkt 3).
6. Nur nicht-interaktive Tools sind bis Phase 6 unterstützt. Interaktive Programme (`vim`, `top`, `less`) werden erkannt und mit Hinweis ausgeklammert; das eingebettete Terminal folgt in Phase 7.

## 14. Entscheidungen des Auftraggebers (verbindlich)

| # | Thema | Entscheidung |
|---|---|---|
| 1 | GUI | Web-UI (lokal), siehe Abschnitt 11 |
| 2 | Kernsprache | Python |
| 3 | Verteilung | Erst lokal, danach `pip`/`pipx` |
| 4 | Interaktive Tools | Später eingebettetes Terminal (Phase 7) |
| 5 | Sandbox | Vorschau **nur mit `bwrap`**, sonst deaktiviert mit Installationshilfe (einsteigerfreundlich) |
| 6 | Darstellung | Knoten-Graph, umschaltbar auf Block-Ansicht; nur Darstellungsschicht (6.7) |
| 7 | KI-Funktionen | Ja, optional aktivierbar: lokal, per API und über Agenten-CLIs wie Claude Code/Codex (6.6) |
| 8 | Lizenz / Name | Open Source mit Copyleft, Name noch offen (Abschnitt 18) |

## 15. Arbeitsanweisungen für Claude Code

**Lies zuerst diese Datei komplett. Die Entscheidungen in Abschnitt 14 und die Annahmen in Abschnitt 13 sind verbindlich. Offen sind nur die Namensprüfung und Lizenzdetails (Abschnitt 18): Starte Phase 0 mit dem Namen `whattheshell` (Verfügbarkeitsprüfung siehe 18.1) und der Lizenz-Vorgabe aus Abschnitt 18. Bei jeder anderen Unklarheit frage nach, statt zu raten.**

### Vorgehen
- Arbeite **in kleinen, überprüfbaren Schritten**. Jede Phase (Abschnitt 16) wird abgeschlossen und vom Auftraggeber abgenommen, bevor die nächste beginnt.
- Lege zu Beginn eine `docs/ARCHITECTURE.md` und ein `CLAUDE.md` an (Konventionen, Befehle zum Testen/Linten, Verzeichnisstruktur) und halte sie aktuell.
- **Tests zuerst für den Parser:** Baue den Golden-File-Korpus (Abschnitt 9), bevor du Heuristiken schreibst.
- Fasse nach jeder Phase kurz zusammen: Was funktioniert, was nicht, was ist offen, wie probiert man es aus.

### Regeln
- Halte dich an Abschnitt 10 (Sicherheit) ohne Ausnahme. Insbesondere: nie `shell=True`, nie Befehle aus Dateien beim Laden ausführen.
- Eine Quelle der Wahrheit für Datenmodelle, Schemas werden generiert.
- Kern ohne GUI-Abhängigkeit, testbar über CLI.
- Typisierter Code (Type Hints), Linting (ruff), Typprüfung (mypy/pyright), Tests (pytest). CI-Konfiguration anlegen.
- Fehler nie verschlucken: klare, nutzerlesbare Meldungen mit Ursache und Lösungshinweis.
- Keine unnötigen Abhängigkeiten, bewährte Bibliotheken vor Eigenbau (Pydantic, ruamel.yaml/PyYAML, watchfiles, jsonschema).
- Dokumentiere jede Entscheidung, die vom Auftrag abweicht, in `docs/DECISIONS.md` mit Begründung.
- Wenn eine Anforderung unklar oder widersprüchlich ist: **stoppe und frage.**

## 16. Phasenplan mit Abnahmekriterien

**Phase 0: Fundament**
Projektgerüst, `CLAUDE.md`, Tooling, Datenmodelle, JSON-Schema-Export.
*Abnahme:* `pytest` und Linter laufen grün; Schemas werden erzeugt.

**Phase 1: Katalog und Hilfe-Parser (CLI)**
`catalog`, `helpparse`, Cache, Test-Korpus mit mind. 15 echten Tools.
*Abnahme:* `wts inspect grep` gibt strukturierte Optionen mit Typ, Hilfetext und Konfidenz aus; ≥ 90 % der Optionen im Korpus korrekt erkannt; Fehlschläge fallen auf „Freie Argumente" zurück.

**Phase 2: Module**
Laden, Validieren, Mergen, Hot-Reload, `validate`/`scaffold`, `MODULE_AUTHORING.md`, 10 Beispielmodule.
*Abnahme:* Ein per Hand geschriebenes Modul überschreibt Auto-Erkennung sichtbar; fehlerhafte Datei erzeugt verständliche Meldung und blockiert nichts anderes.

**Phase 3: Engine und Evaluatoren (CLI)**
Workflows ausführen, Pipes, Variablen, Bedingungen, Schleifen, Fehlerbehandlung, Dry-Run, Sicherheitsklassen, Sandbox.
*Abnahme:* Beispiel-Workflow aus Abschnitt 3 läuft per `wts run`; gefährliche Befehle verlangen Bestätigung; Injektionstest (`;`, `$()`, Leerzeichen, Sonderzeichen in Argumenten) besteht.

**Phase 4: GUI-Prototyp (Knoten-Graph)**
Katalog, Arbeitsfläche, Baustein-Formulare mit Hilfetexten, Befehlsanzeige, Live-Vorschau, Workflow speichern/laden/ausführen mit Live-Ausgabe.
*Abnahme:* Der Beispiel-Workflow lässt sich komplett grafisch bauen, speichern und ausführen.

**Phase 5: Block-Ansicht, Komfort und Paketierung**
Block-Ansicht (Blockly o. ä.) mit verlustfreiem Umschalten (6.7), In-App-Modul-Editor, Vorlagen, Rückgängig/Wiederholen, Lokalisierung, Barrierefreiheit, Paketierung für `pip`/`pipx` (Frontend eingebettet).
*Abnahme:* Ein Workflow lässt sich in beiden Ansichten bearbeiten, ohne dass sich die Datei inhaltlich ändert (nur `layout`); `pipx install` auf einem frischen System funktioniert ohne Node; die UI ist nur über localhost mit Token erreichbar.

**Phase 6: Optionale KI-Funktionen**
Provider-Abstraktion (lokal, API, Agenten-CLIs), Diff-Freigabe, Datenvorschau, CLI-Befehle `wts ai ...`.
*Abnahme:* Bei ausgeschalteter KI entstehen nachweislich keine Netzwerk- oder Fremdprozess-Aktivitäten (Test); KI-Ergebnisse werden nie ohne Freigabe gespeichert oder ausgeführt; ein erzeugtes Modul besteht die Schema-Validierung.

**Phase 7: Eingebettetes Terminal**
Interaktive Tools in einem Terminal-Schritt (F-36), vorher Sicherheitsabschnitt schreiben und vom Auftraggeber freigeben lassen.
*Abnahme:* Nach Absprache.

## 17. Definition of Done (gesamt, v1)

- Jedes auf dem System installierte, nicht interaktive CLI-Tool ist als Baustein nutzbar (ggf. im Fallback-Modus).
- Mindestens 10 hochwertige mitgelieferte Module mit Beispielen und Vorlagen.
- Module/Workflows sind reine Dateien, validiert per Schema, von einer KI anhand der Dokumentation erzeugbar.
- Sicherheitskonzept (Abschnitt 10) umgesetzt und getestet.
- Dokumentation: README, Architektur, Modulautorenhandbuch, Sicherheitskonzept.

## 18. Projektname und Lizenz

### 18.1 Projektname: WhatTheShell (entschieden)
Der Auftraggeber hat **WhatTheShell** gewählt. Der Name erklärt das Problem, das das Tool löst („Was macht dieser Shell-Befehl eigentlich?"), ist kurz und hat keinen Markenbezug (der früher erwogene Name „WhatsATerminal" spielte auf WhatsApp an und ist verworfen).

| Bezeichner | Wert |
|---|---|
| Anzeigename | WhatTheShell |
| PyPI-Distribution / Importname | `whattheshell` (PyPI normalisiert `what-the-shell` und `whattheshell` zum selben Namen) |
| CLI-Befehl | `whattheshell`, Kurzalias `wts` |
| Konfigurationsverzeichnis | `~/.config/whattheshell/` |

**Verfügbarkeit (Stand dieses Dokuments):** Der Auftraggeber meldet, der Name sei auf PyPI frei. Das ist hier **nicht unabhängig geprüft** (PyPI war aus der Erstellungsumgebung nicht erreichbar).

**Zu erledigen zu Beginn von Phase 0 (Claude Code):**
1. PyPI prüfen: `whattheshell` (und `what-the-shell`) darf nicht belegt sein. Die JSON-Seite `https://pypi.org/pypi/whattheshell/json` liefert bei freiem Namen 404.
2. GitHub-Organisation/Repository, Domain und ggf. Marken-Register (DPMA/EUIPO) prüfen. Ähnliche, bereits bekannte Projekte mit dem Namen „What The Shell" recherchieren und Verwechslungsgefahr einschätzen.
3. Prüfen, ob der Alias `wts` unter gängigen Linux-Distributionen mit einem vorhandenen Befehl kollidiert (z. B. `command -v wts`, Paketsuche). Bei Kollision den Alias weglassen oder ändern.
4. Ergebnis kurz in `docs/DECISIONS.md` festhalten. Ist der Name belegt, **stoppe und lege dem Auftraggeber Alternativen vor** (z. B. `whattheshell-gui`, `wtshell`, `shellbricks`).
5. Wenn der Name frei ist, den Namen früh auf PyPI sichern (leeres Platzhalter-Paket erst nach Rücksprache mit dem Auftraggeber veröffentlichen).

### 18.2 Lizenz (Empfehlung)
Ziel des Auftraggebers: Open Source, und das Tool soll nur in Open-Source-Projekten verwendet werden dürfen.

- **Empfehlung: GNU AGPL-3.0-or-later** für den Code. Das ist starkes Copyleft: Wer den Code verändert, weitergibt oder in ein eigenes Produkt einbaut, muss das Ergebnis unter derselben Lizenz offenlegen. Die AGPL schließt zusätzlich die Lücke, dass man die Software nur als Netzwerkdienst anbietet (relevant wegen der Web-UI).
- **Wichtige Einschränkung:** Eine Klausel „nur in Open-Source-Projekten nutzbar" wäre eine Nutzungsbeschränkung. Sie widerspricht der Open-Source-Definition und ist mit GPL/AGPL unvereinbar. Das Copyleft erreicht das Ziel für Einbau und Weitergabe, kann aber die **reine Nutzung als Programm** nicht verbieten (z. B. nutzt eine Firma das Tool intern, um eigene Workflows zu bauen).
- Offen für den Auftraggeber: Sollen mitgelieferte Module und Workflows (Daten, keine Programme) unter derselben Lizenz stehen oder unter einer freieren (z. B. CC0/MIT), damit sie leicht geteilt werden können? Eigene Dateien der Nutzer gehören den Nutzern.
- Technisch: `LICENSE`-Datei, SPDX-Header in allen Quelldateien, Abhängigkeiten auf Lizenzkompatibilität prüfen (Liste in `docs/DEPENDENCIES.md`).
- Dies ist keine Rechtsberatung. Vor einer Veröffentlichung sollte die Wahl juristisch geprüft werden.
