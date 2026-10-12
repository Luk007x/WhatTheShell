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
3. **Hinzufügen**: Toolbar „Hinzufügen: <Werkzeug>" fügt einen Befehlsschritt ein; Kontrollbausteine (Bedingung, Schleife, Variable, Warten, Meldung, Abbrechen) daneben. Ist ein `if`/`foreach` gewählt, wählt das Ziel-Select „ans Ende / in Dann / in Sonst / in Schleife".
4. **Verbinden**: Ablaufkante vom unteren Anschluss „next" (setzt die Reihenfolge), von „Dann/Sonst/Schleife" (Teilfolge), Datenkante von „stdout" nach „stdin" (Pipe). Entf löscht Knoten oder Pipe-Kanten. Strg+Z / Strg+Umschalt+Z: Rückgängig/Wiederholen.
5. **Formular** (rechts): Schritt anklicken; Eingaben, Optionen, „Freie Argumente", stdin, Fehlerbehandlung. Darunter der fertige Befehl (kopierbar) mit Sicherheitsklasse.
6. **Vorschau**: Beispiel wählen, „Beispiel ausführen" (nur in der Sandbox; bei sicheren Befehlen mit Beispiel automatisch).
7. **Trockenlauf**: zeigt den Plan, führt nichts aus.
8. **Ausführen**: Dialog mit Plan, höchster Sicherheitsklasse, Arbeitsordner und Variablen-Überschreibungen; danach Live-Ausgabe pro Schritt, Pause, Einzelschritt, Abbrechen. Gefährliche Schritte fragen einzeln nach. Bei beendeten Schritten: „Als Variable übernehmen" und „Hier auswerten".
9. **Speichern**: Kopfzeile „Speichern" / „Speichern unter" (id wird aus dem Namen vorgeschlagen), „Öffnen" listet mitgelieferte und eigene Workflows. Ungespeicherte Änderungen sind markiert.

## Ansichten

Kopfzeile „Graph" / „Blöcke" schaltet die Darstellung um (gespeichert in `localStorage("wts.view")`, Standard Graph). Beide Ansichten zeigen dasselbe Dokument und teilen Auswahl, Rückgängig, Formular und Laufpanel; `layout` bleibt unverändert (D-010).

Block-Ansicht: verschachtelte Karten, Slots „dann / sonst / für jede Zeile / bei Fehler". Klick wählt aus. Verschieben per Drag & Drop auf Zwischenräume und Slots oder per Tastatur auf dem fokussierten Block: Alt+↑/↓ (hoch/runter), Alt+→ (in den vorhergehenden Container), Alt+← (hinter den Container), Entf (löschen, mit Rückfrage), Enter (auswählen). Das Menü „⋯" bietet dieselben Aktionen, „+" am Ende jeder Folge fügt einen Kontrollbaustein oder das im Katalog gewählte Werkzeug genau dort ein. Eine `aria-live`-Region meldet Verschiebungen.

## E2E (Playwright)

`npm run e2e` baut die GUI und startet `wts gui` auf freiem Port mit temporärem `XDG_CONFIG_HOME` (`e2e/server.ts`); Test: `e2e/smoke.spec.ts` (headless Chromium, 1400×900, Sprache de). Einmalig `npx playwright install chromium`. Screenshots bei Fehlschlag: `e2e-results/`. Benötigt `uv`, `bwrap` (Vorschau) und die Systembibliotheken von Chromium.
