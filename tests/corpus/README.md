# Hilfe-Korpus (Golden Files)

Je Tool ein Ordner mit `stdout.txt`, `stderr.txt`, `meta.json` (Aufruf und Exit-Code, erfasst mit `LC_ALL=C COLUMNS=80 TERM=dumb`, stdin geschlossen) und `expected.json` (per Hand erstellt, Wahrheit für den Parser).

`expected.json`:

```json
{
  "summary_contains": "optionaler Teilstring der Kurzbeschreibung",
  "subcommands": ["commit", "push"],
  "options": [
    {"flags": ["-i", "--ignore-case"], "takes_value": false, "type": "bool"},
    {"flags": ["-C", "--context"], "takes_value": true, "type": "int"},
    {"flags": ["--color"], "takes_value": true, "type": "enum", "choices": ["always", "never", "auto"]}
  ]
}
```

Regeln für Autoren:
- Jede Option aus den Options-Abschnitten (bzw. aus der Usage-Zeile, wenn es keinen gibt) ist ein Eintrag. Kurz- und Langform in einem Eintrag.
- `--[no-]foo` wird ein Eintrag mit `["--foo", "--no-foo"]`, Typ `bool`.
- `type`: `bool` ohne Wert; mit Wert nach Metavariable: `FILE`, `DIR`, `PATH`, `DIRECTORY` → `path`; `NUM`, `N`, `COUNT`, `LINES`, `SECONDS`, `PORT` → `int`; feste Werteliste → `enum` mit `choices`; sonst `string`. Optionales Argument (`[=WHEN]`) zählt als `takes_value: true`.
- Neue Parser-Fehler werden zuerst hier als Testfall angelegt (Projektauftrag Abschnitt 9).

Die Messung in `tests/unit/test_corpus.py` prüft Options-Recall (Treffer über eine gemeinsame Flag), Typtreue der Treffer und Subbefehl-Recall. Schwelle: 90 % Options-Recall über den gesamten Korpus, 75 % je Tool.
