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
4. **Verbinden**: Ablaufkante vom unteren Anschluss „weiter" (setzt die Reihenfolge) oder „dann/sonst/Rumpf/bei Fehler" (Teilfolge) auf den oberen Eingang „Ablauf"; Datenkante von „stdout" (rechts) nach „stdin" (links, nur Befehle). Andere Kombinationen werden abgelehnt, die Statuszeile sagt warum. Entf löscht Knoten oder Pipe-Kanten. Strg+Z / Strg+Umschalt+Z: Rückgängig/Wiederholen.
5. **Formular** (rechts): Schritt anklicken; Eingaben, Optionen, „Freie Argumente", stdin, Fehlerbehandlung. Darunter der fertige Befehl (kopierbar) mit Sicherheitsklasse.
6. **Vorschau**: Beispiel wählen, „Beispiel ausführen" (nur in der Sandbox; bei sicheren Befehlen mit Beispiel automatisch).
7. **Trockenlauf**: zeigt den Plan, führt nichts aus.
8. **Ausführen**: Dialog mit Plan, höchster Sicherheitsklasse, Arbeitsordner und Variablen-Überschreibungen; danach Live-Ausgabe pro Schritt, Pause, Einzelschritt, Abbrechen. Gefährliche Schritte fragen einzeln nach. Bei beendeten Schritten: „Als Variable übernehmen" und „Hier auswerten".
9. **Speichern**: Kopfzeile „Speichern" / „Speichern unter" (id wird aus dem Namen vorgeschlagen), „Öffnen" listet mitgelieferte und eigene Workflows. Ungespeicherte Änderungen sind markiert.

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

Grid: Kopfzeile (Datei, Rückgängig, Sandbox, Einstellungen) / Modusleiste (Erstellen, Module; Graph/Blöcke) / Katalog | Mitte | Details / Fuss (Statuszeile, Ausgabe). Die Spaltenbreiten lassen sich an den Trennern ziehen oder per Tastatur ändern (Trenner fokussieren, ←/→, Umschalt für große Schritte, Pos1/Ende), gespeichert in `localStorage("wts.cols")`. Design-Tokens (Abstände, Farben hell/dunkel per `prefers-color-scheme`, Radien, Schatten) stehen am Anfang von `src/app.css`; Icons in `src/icons.tsx`. `e2e/design.spec.ts` prüft bei 1280×720 (auch Schrift „groß" und dunkel), dass sich Bereiche und Knöpfe nicht überlappen, und legt `e2e-results/design-*.png` ab.

## Ansichten

Modusleiste „Graph" / „Blöcke" schaltet die Darstellung um (gespeichert in `localStorage("wts.view")`, Standard Graph). Beide Ansichten zeigen dasselbe Dokument und teilen Auswahl, Rückgängig, Formular und Laufpanel; `layout` bleibt unverändert (D-010).

Block-Ansicht: verschachtelte Karten, Slots „dann / sonst / für jede Zeile / bei Fehler". Klick wählt aus. Verschieben per Drag & Drop auf Zwischenräume und Slots oder per Tastatur auf dem fokussierten Block: Alt+↑/↓ (hoch/runter), Alt+→ (in den vorhergehenden Container), Alt+← (hinter den Container), Entf (löschen, mit Rückfrage), Enter (auswählen). Das Menü „⋯" bietet dieselben Aktionen, „+" am Ende jeder Folge fügt einen Kontrollbaustein oder das im Katalog gewählte Werkzeug genau dort ein. Eine `aria-live`-Region meldet Verschiebungen.

## Barrierefreiheit

- Skip-Link „Zum Hauptbereich springen" ist das erste fokussierbare Element; Dialoge sind native `<dialog>` (Fokusfalle, Fokus-Rückgabe, Escape).
- Block-Ansicht: Tastaturbedienung (Alt+Pfeile, Entf, Enter), Escape schließt „+"-Liste und Menü, Verschiebungen werden per `aria-live` gemeldet.
- Schriftgröße (Einstellungen: klein/normal/groß) skaliert über `--font-scale` auf `html`; alle Größen in `rem`. `prefers-reduced-motion` schaltet Animationen ab.
- `e2e/a11y.spec.ts` prüft mit axe (WCAG 2.1 A/AA, 0 Verstöße, keine deaktivierten Regeln) Start, Formular, Block-Ansicht (mit „+"-Liste), Laufpanel, Modul-Editor (Rohtext und Formular) und Einstellungen; dazu ein Tastatur-Durchgang ohne Maus. Der Audit dauert ca. 35 s, weil der Katalog alle Programme im PATH listet.

## E2E (Playwright)

`npm run e2e` baut die GUI und startet `wts gui` auf freiem Port mit temporärem `XDG_CONFIG_HOME` (`e2e/server.ts`); Test: `e2e/smoke.spec.ts` (headless Chromium, 1400×900, Sprache de). Einmalig `npx playwright install chromium`. Screenshots bei Fehlschlag: `e2e-results/`. Benötigt `uv`, `bwrap` (Vorschau) und die Systembibliotheken von Chromium.
