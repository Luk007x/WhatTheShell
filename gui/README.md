# WhatTheShell GUI

React + Vite + TypeScript (strict). Types in `src/types/` are generated from `../schemas/` (`npm run gen:types`, also run by `npm run build`).

## Use the built GUI

```
npm ci && npm run build      # writes ../src/whattheshell/api/static
uv run wts gui --no-browser  # prints a URL like http://127.0.0.1:PORT/#token=...
```

Open the URL with the token. Without the token the page shows an error.

## Development with `vite dev`

```
VITE_WTS_PORT=PORT npm run dev
```

Start the backend first (`uv run wts gui --no-browser`), then open `http://localhost:5173/#token=...` using the token from the console.
`/api` and `/ws` are proxied to `http://127.0.0.1:PORT` (`changeOrigin: false`). The backend rejects non-GET requests and WebSockets whose
`Origin` is not `http://127.0.0.1:PORT` or `http://localhost:PORT`; the dev origin is `http://localhost:5173`, so the proxy rewrites the
`Origin` header to `http://127.0.0.1:PORT`.

## Checks

`npm run typecheck`, `npm test`.

## Ablauf

1. **Starten**: `uv run wts gui --no-browser`, die URL mit `#token=...` aus der Konsole öffnen.
2. **Katalog** (links): Werkzeug suchen und auswählen. Der Stern merkt Favoriten.
3. **Hinzufügen**: Toolbar „Hinzufügen: <Werkzeug>" fügt einen Befehlsschritt ein; Kontrollbausteine (Bedingung, Schleife, Variable, Warten, Meldung, Abfrage, Abbrechen) daneben. Ist ein `if`/`foreach` gewählt, wählt das Ziel-Select „ans Ende / in Dann / in Sonst / in Schleife".
4. **Verbinden**: Ablaufkante vom unteren Anschluss „weiter" (setzt die Reihenfolge) oder „dann/sonst/Rumpf/bei Fehler" (Teilfolge) auf den oberen Eingang „Ablauf"; Datenkante von „stdout" (rechts) nach „stdin" (links, nur Befehle). Andere Kombinationen werden abgelehnt, die Statuszeile sagt warum. Entf löscht Knoten oder Pipe-Kanten. Katalog-Einträge und Kontrollbausteine lassen sich auf die Fläche ziehen. Tastenkürzel: siehe „Tastenkürzel“ (`?` öffnet die Übersicht).
5. **Formular** (rechts): Schritt anklicken; Eingaben, Optionen, „Freie Argumente", stdin, Fehlerbehandlung. Darunter der fertige Befehl (kopierbar) mit Sicherheitsklasse.
6. **Vorschau**: Beispiel wählen, „Beispiel ausführen" (nur in der Sandbox; bei sicheren Befehlen mit Beispiel automatisch).
7. **Trockenlauf**: zeigt den Plan, führt nichts aus.
8. **Ausführen**: Dialog mit Plan, höchster Sicherheitsklasse, Arbeitsordner und Variablen-Überschreibungen; danach Live-Ausgabe pro Schritt, Pause, Einzelschritt, Abbrechen. Gefährliche Schritte fragen einzeln nach. Bei beendeten Schritten: „Als Variable übernehmen" und „Hier auswerten".
9. **Speichern**: Kopfzeile „Speichern" / „Speichern unter" (id wird aus dem Namen vorgeschlagen), „Öffnen" zeigt die Workflow-Bibliothek (Suche, Quellen-Badges). Gespeichert wird in den Nutzerordner; der Workflow erscheint damit sofort im Modus „Ausführen". Ungespeicherte Änderungen sind markiert.

## Tastenkürzel

Im Modus „Erstellen“; nicht in Formularfeldern und offenen Dialogen (dort gilt die Browser-Bearbeitung). Strg gilt auch als Cmd. `?` zeigt dieselbe Tabelle in der App.

| Taste | Wirkung |
|---|---|
| Entf / Rücktaste | ausgewählten Schritt löschen (Strg+Z macht es rückgängig) |
| Strg+Z | Rückgängig |
| Strg+Umschalt+Z / Strg+Y | Wiederholen |
| Strg+S | Speichern (öffnet den Speichern-Dialog, ohne Datei „Speichern unter“) |
| Esc | Auswahl aufheben, Hinweis löschen |
| Strg+Eingabe im Katalog | Werkzeug am gewählten Ziel anhängen (Eingabe/Klick wählt nur aus) |
| ? | Hilfe öffnen (Tastenkürzel) |
| Ziehen | Katalog-Eintrag oder Kontrollbaustein auf die Fläche: Schritt entsteht an der Drop-Stelle |

## Ausführen

Modus „Ausführen" (Modusleiste; der zuletzt gewählte Modus steht in `localStorage("wts.mode")`, Standard „Erstellen") führt fertige Workflows aus, ohne den Editor:

- **Bibliothek** (links): `GET /api/workflows`, gruppiert nach mitgeliefert / eigene / Projekt (`~/.config/whattheshell/workflows`, `.whattheshell/workflows` im Startordner), mit Suche, Schrittzahl, Quellen-Badge und Hinweis „überdeckt: …". Projektdateien sind als „hier nicht änderbar" markiert (Speichern/Löschen derselben id antwortet 409 mit Hinweis). Kaputte Dateien sind ausgegraut und zeigen `Pfad:Zeile: Meldung`. Der Server beobachtet die Ordner; die Liste lädt beim Moduswechsel, bei Fensterfokus und über „Aktualisieren" neu.
- **Eingaben** (rechts): ein Feld je Variable (Text, Zahl mit `min`/`max`, Auswahl aus `choices` bei `enum`, Checkbox, Passwort für `secret`, Pfad mit Hinweis), Pflichtfelder mit `*`, Defaults vorbelegt, dazu der Arbeitsordner. Werte werden je Workflow in `localStorage("wts.runvalues.<id>")` gemerkt, Secrets nie.
- **Trockenlauf** zeigt den Plan unten. **Ausführen** prüft die Eingaben, holt den Plan und zeigt den Bestätigungsdialog (Plan, höchste Sicherheitsklasse, Arbeitsordner); erst „Workflow ausführen" startet den Lauf. Live-Ausgabe, Schritt-Bestätigungen, Pause, Einzelschritt und Abbrechen kommen aus denselben Hooks wie im Editor (`useRun`, `usePlanThenRun` in `src/run/useRun.ts`). Weicht der Plan der echten Anfrage vom bestätigten ab, startet nichts; der Dialog zeigt den neuen Plan zur erneuten Bestätigung. Die Ansicht bleibt beim Moduswechsel gemountet: ein laufender Lauf behält seine Verbindung, Schritt-Bestätigungen erscheinen auch im Editor.
- Nach dem Ende: „Erneut ausführen" und „Im Editor öffnen" (fragt bei ungespeicherten Änderungen nach). **Letzte Läufe** (`GET /api/runs`) zeigt Status, Startzeit und Exitcode; ein Klick lädt den Verlauf schreibgeschützt in die Ausgabe.

## Terminal-Schritt

Werkzeuge, die der Katalog als interaktiv meldet (Badge „Terminal“), werden als Terminal-Schritt angelegt; im Schritt-Panel
lässt sich das per Checkbox umschalten. Er hat nur die Ports Ablauf/weiter (kein stdin/stdout), sein Output geht nicht an
Folgeschritte, und `network` (Netzzugang) hebt die Sicherheitsklasse auf Vorsicht. Das eingebettete Terminal selbst folgt später.

## Wie Daten fließen

Schritte laufen nacheinander (Ablaufkante). Ein Befehl schreibt seine Ausgabe (stdout) in den Lauf-Verlauf. Eine Datenkante stdout → stdin übergibt diese Ausgabe als Text an den nächsten Befehl (wie `|` in der Shell, nur nacheinander). Alles andere holt man per `{{ schritt.stdout }}`, `{{ schritt.exit_code }}` oder `{{ var.name }}` in ein Feld; Bedingungen und Schleifen lesen so ebenfalls.

Anschlüsse am Knoten (D-012), nur nach Schrittart:

| Anschluss | Lage | Schrittarten | Bedeutung |
|---|---|---|---|
| Ablauf (`in`) | oben | alle | Eingang der Reihenfolge |
| weiter (`next`) | unten Mitte | alle | nächster Schritt derselben Folge |
| dann / sonst (`then`/`else`) | unten links/rechts | Bedingung | erster Schritt der Teilfolge |
| Rumpf (`body`) | unten links | Schleife | läuft je Zeile der Quelle |
| bei Fehler (`fallback`) | unten rechts | Befehl mit `on_error.action: fallback` | Ersatzschritte |
| stdin / stdout | links / rechts | nur Befehl | Datenkante, gestrichelt, „stdout → stdin" |

Ablaufkanten sind durchgezogen mit Pfeil, Datenkanten gestrichelt in zweiter Farbe. Die „Legende" auf der Fläche und der „?"-Knopf in der Werkzeugleiste erklären dasselbe in der App. In der Block-Ansicht zeigt ein Abzeichen „Eingabe: stdout von <id>".

## Oberfläche

Grid: Kopfzeile (Datei, Rückgängig, Sandbox, Einstellungen) / Modusleiste (Erstellen, Ausführen, Module; Graph/Blöcke) / Katalog | Mitte | Details / Fuss (Statuszeile, Ausgabe). Die Spaltenbreiten lassen sich an den Trennern ziehen oder per Tastatur ändern (Trenner fokussieren, ←/→, Umschalt für große Schritte, Pos1/Ende), gespeichert in `localStorage("wts.cols")`. Design-Tokens (Abstände, Farben hell/dunkel über `data-theme` am `<html>`, Radien, Schatten) stehen am Anfang von `src/app.css`; Icons in `src/icons.tsx`. Der Knopf links vom Zahnrad schaltet Darstellung System → Hell → Dunkel (gespeichert in `localStorage("wts.theme")`, „System" folgt `prefers-color-scheme`; Logik in `src/theme.ts`). `e2e/design.spec.ts` prüft bei 1280×720 (auch Schrift „groß" und dunkel), dass sich Bereiche und Knöpfe nicht überlappen, und legt `e2e-results/design-*.png` ab.

## Ansichten

Modusleiste „Graph" / „Blöcke" schaltet die Darstellung um (gespeichert in `localStorage("wts.view")`, Standard Graph). Beide Ansichten zeigen dasselbe Dokument und teilen Auswahl, Rückgängig, Formular und Laufpanel; `layout` bleibt unverändert (D-010).

Block-Ansicht: verschachtelte Karten, Slots „dann / sonst / für jede Zeile / bei Fehler". Klick wählt aus. Verschieben per Drag & Drop auf Zwischenräume und Slots; Werkzeuge aus dem Katalog lassen sich ebenfalls dorthin ziehen und werden an der Stelle eingefügt. Per Tastatur per Tastatur auf dem fokussierten Block: Alt+↑/↓ (hoch/runter), Alt+→ (in den vorhergehenden Container), Alt+← (hinter den Container), Entf/Rücktaste (löschen, ohne Rückfrage), Enter (auswählen). Das Menü „⋯" bietet dieselben Aktionen, „+" am Ende jeder Folge fügt einen Kontrollbaustein oder das im Katalog gewählte Werkzeug genau dort ein. Eine `aria-live`-Region meldet Verschiebungen.

## Terminal-Schritte

Schritte mit `kind: terminal` öffnen im Laufpanel ein xterm.js-Terminal (`src/run/Terminal.tsx`), verbunden über den Binär-WebSocket `/ws/runs/{id}/terminal/{step}` (Ausgabe und Tastatur als Bytes, `open`/`resize` als JSON). Escape-Sequenzen für Zwischenablage (OSC 52), Fenstertitel und Hyperlinks (OSC 8) werden verworfen, es gibt keine Link-/Image-Addons; Tastatureingaben werden nirgends gespeichert. Tastaturflucht: Esc, dann Tab. Das Transkript (nur Ausgabe, Opt-in im Ausführen-Dialog, nur sichtbar bei Workflows mit Terminal-Schritt) meldet der Server als Dateiname; „Löschen“ ruft `DELETE /api/terminal/transcripts/{name}`. Nach dem Ende bleibt der Terminalinhalt schreibgeschützt sichtbar (Knopf „Schließen“, der nächste Terminal-Schritt ersetzt ihn). Trennen der Seite beendet den Prozess, es gibt kein Reattach. Test: `e2e/terminal.spec.ts` (überspringt sich ohne bwrap).

## Beenden

Einstellungen, Abschnitt „Programm“: „WhatTheShell beenden“ ruft `POST /api/shutdown` und zeigt danach eine Abschlussansicht; Tabs schließen beendet den Server nicht.

## Barrierefreiheit

- Skip-Link „Zum Hauptbereich springen" ist das erste fokussierbare Element; Dialoge sind native `<dialog>` (Fokusfalle, Fokus-Rückgabe, Escape).
- Block-Ansicht: Tastaturbedienung (Alt+Pfeile, Entf/Rücktaste, Enter), Escape schließt „+"-Liste und Menü, Verschiebungen werden per `aria-live` gemeldet.
- Schriftgröße (Einstellungen: klein/normal/groß) skaliert über `--font-scale` auf `html`; alle Größen in `rem`. `prefers-reduced-motion` schaltet Animationen ab.
- `e2e/a11y.spec.ts` prüft mit axe (WCAG 2.1 A/AA, 0 Verstöße, keine deaktivierten Regeln) Start, Formular, Block-Ansicht (mit „+"-Liste), Laufpanel, Modul-Editor (Rohtext und Formular) und Einstellungen; dazu ein Tastatur-Durchgang ohne Maus. Der Audit dauert ca. 35 s, weil der Katalog alle Programme im PATH listet.

## E2E (Playwright)

`npm run e2e` baut die GUI und startet `wts gui` auf freiem Port mit temporärem `XDG_CONFIG_HOME` (`e2e/server.ts`); Tests: `e2e/smoke.spec.ts`, `e2e/run.spec.ts` (Modus „Ausführen"), `e2e/terminal.spec.ts`, `e2e/design.spec.ts`, `e2e/a11y.spec.ts`, `e2e/ai.spec.ts` (headless Chromium, 1400×900, Sprache de). Einmalig `npx playwright install chromium`. Screenshots bei Fehlschlag: `e2e-results/`. Benötigt `uv`, `bwrap` (Vorschau) und die Systembibliotheken von Chromium.

## Hilfe in der App

- Der Knopf mit dem Fragezeichen in der Kopfzeile (und die Taste `?`) öffnet den Hilfedialog; links stehen die Abschnitte (Erste Schritte, Workflow bauen, Ausführen und Sicherheit, Module, Terminal, KI-Funktionen, Tastenkürzel), rechts der Inhalt.
- Kleine `?`-Knöpfe in den Kopfzeilen von Katalog, Arbeitsfläche, Variablen, Ausführen und Modulen springen direkt zum passenden Abschnitt.
- Beim ersten Start öffnet sich die Hilfe automatisch; danach merkt sich `localStorage` (`wts.helpseen`), dass sie gesehen wurde.
- Texte stehen in `src/i18n.ts` unter `help.<abschnitt>.*`; neue Abschnitte in `src/Help.tsx` (`SECTIONS`) eintragen.

## Handbuch

- Kapitel liegen als Markdown unter `../docs/manual/NN-slug.md` (Dateiname sortiert die Reihenfolge, `slug` wird die Kapitel-ID, die erste `# `-Überschrift der Titel).
- Neues Kapitel: Datei anlegen, fertig. Der Vite-Build (`vite.config.ts`, virtuelles Modul `virtual:manual`) wandelt alle Kapitel mit `marked` in HTML um und bettet sie ins Bundle ein; `vite dev` lädt bei Änderungen neu. Ohne Kapitel zeigt die Ansicht „Noch keine Kapitel“.
- Interne Links: `[Text](#kapitel-id)` oder `[Text](#kapitel-id/ueberschrift-id)`; Überschrift-IDs sind der Slug des Textes (`ä`→`ae`, Leerzeichen→`-`).
- Einstieg: Buch-Symbol in der Kopfzeile und „Ausführlich im Handbuch“ im Hilfedialog (springt zum Kapitel mit der ID des Hilfeabschnitts, z. B. `build`, sonst zum ersten).
