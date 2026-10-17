# Veröffentlichen und Installieren

Anleitung für den Auftraggeber. Veröffentlicht wird immer von Hand, nie aus einer Claude-Sitzung (D-001, D-016).

## 1. pipx auf dem eigenen Rechner

```
sudo dnf install pipx bubblewrap        # Fedora; Debian/Ubuntu: sudo apt install pipx bubblewrap
pipx ensurepath                         # ~/.local/bin in PATH; danach Terminal neu öffnen
```

| Befehl | Wirkung |
|---|---|
| `pipx install whattheshell` | von PyPI installieren (sobald veröffentlicht) |
| `pipx install ./dist/whattheshell-X.Y.Z-py3-none-any.whl` | aus dem lokalen Wheel |
| `pipx list` | installierte Tools |
| `pipx upgrade whattheshell` | aktualisieren (vorher `wts gui stop`) |
| `pipx uninstall whattheshell` | entfernen; Nutzerdaten bleiben (siehe Abschnitt 5) |

pipx legt je Tool eine eigene virtuelle Umgebung unter `~/.local/share/pipx/venvs/whattheshell` an
(ältere pipx: `~/.local/pipx/venvs`) und verlinkt nur den Befehl `wts` nach `~/.local/bin`.

**Nicht** `pipx install git+https://github.com/…` verwenden: Das Frontend liegt nicht im Git, sondern
entsteht beim Bauen. Ohne Build fehlt der GUI der Inhalt. Immer Wheel oder PyPI.

## 2. Vor dem ersten Release

- [ ] Version in `pyproject.toml` setzen (z. B. `0.1.0`). Eine Version ist auf PyPI nie überschreibbar.
- [ ] `docs/DECISIONS.md` D-001: Domain/Markenprüfung nachholen, wenn gewünscht.
- [ ] Alle Prüfungen grün: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`
      und `cd gui && npm ci && npm run typecheck && npm test && npm run build`.
- [ ] `scripts/build_wheel.sh` lokal laufen lassen, `dist/` enthält Wheel und sdist, das Wheel enthält `api/static/`.
- [ ] Frische Installation testen: `pipx install ./dist/*.whl && wts --version && wts sandbox && wts gui start`.

## 3. Erster Upload auf PyPI (einmalig von Hand)

1. pypi.org → Account settings → API tokens → Token anlegen. Scope beim ersten Mal: **Entire account**
   (das Projekt existiert noch nicht). Nach dem Upload dieses Token löschen und ein auf `whattheshell`
   beschränktes Token anlegen.
2. Bauen und hochladen (Token nicht in die Shell-History, deshalb Umgebungsvariable):

```
scripts/build_wheel.sh
export UV_PUBLISH_TOKEN=pypi-…
env -u VIRTUAL_ENV uv publish dist/*
unset UV_PUBLISH_TOKEN
```

3. Prüfen: `pipx install whattheshell && wts --version`.
4. Git-Tag: `git tag v0.1.0 && git push --tags`. Der Workflow `.github/workflows/release.yml` baut das
   Wheel und hängt es an das GitHub-Release.

Optional vorher auf TestPyPI üben (eigener Account und eigenes Token auf test.pypi.org):

```
env -u VIRTUAL_ENV uv publish --publish-url https://test.pypi.org/legacy/ dist/*
pipx install --index-url https://test.pypi.org/simple/ --pip-args="--extra-index-url https://pypi.org/simple/" whattheshell
```

## 4. Spätere Releases: Trusted Publishing

Ohne Token im Repo: PyPI vertraut dem GitHub-Workflow direkt. Der Job `publish` in
`.github/workflows/release.yml` ist eingebaut (`needs: release`, `environment: pypi`,
`id-token: write`). Er lädt `dist/` aus dem Job `release`, kopiert nur `*.whl` und `*.tar.gz` nach
`dist/pypi/` (die SBOM geht nur ans GitHub-Release, nicht nach PyPI) und lädt mit `skip-existing` hoch.

Einmalige Einrichtung:

1. GitHub → Repo → Settings → Environments → New environment `pypi` (optional mit Required reviewers:
   dann wartet der Job vor dem Upload auf eine Freigabe).
2. pypi.org → Publishing → Add a new pending publisher (solange das Projekt noch nicht existiert) bzw.
   Projekt `whattheshell` → Publishing: Owner `Luk007x`, Repo `WhatTheShell`, Workflow `release.yml`,
   Environment `pypi`.

Ablauf danach: Version in `pyproject.toml` anheben, committen, `git tag vX.Y.Z && git push --tags`.
Der Tag-Push bleibt beim Auftraggeber (D-001, D-016).

## 5. Wo liegt was

| Was | Ort |
|---|---|
| Programm (pipx) | `~/.local/share/pipx/venvs/whattheshell`, Befehl `~/.local/bin/wts` |
| Einstellungen (`settings.yaml`, nur KI-Block) | `~/.config/whattheshell/` |
| Eigene Module | `~/.config/whattheshell/modules/` |
| Eigene Workflows | `~/.config/whattheshell/workflows/` |
| Projektlokale Module/Workflows | `<Projekt>/.whattheshell/{modules,workflows}/` (nur wenn `wts` dort gestartet wird) |
| Cache, Hintergrund-Log, Terminal-Transkripte | `~/.cache/whattheshell/` (`gui.log`, `terminal/`) |
| Laufzeitzustand (`gui.json`, Sperre) | `$XDG_RUNTIME_DIR/whattheshell/` (Fallback `~/.cache/whattheshell/run/`) |
| Oberflächeneinstellungen (Sprache, Theme, Startansicht, Laufwerte) | `localStorage` des Browsers |

`XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_RUNTIME_DIR` werden respektiert. Ein `pipx uninstall` lässt alle
diese Daten liegen; zum vollständigen Entfernen `rm -r ~/.config/whattheshell ~/.cache/whattheshell`.

## 6. PyPI-Seite

Die Projektseite auf pypi.org wird vollständig aus den Paket-Metadaten erzeugt; es gibt nichts, was man dort von Hand pflegt.

| PyPI zeigt | Quelle in `pyproject.toml` |
|---|---|
| Name, Version | `name`, `version` |
| Kurzbeschreibung (Titelzeile, Suche) | `description` |
| Hauptinhalt der Seite (long description) | `readme = "README.md"` (Markdown wird gerendert) |
| Filter und Badges links | `classifiers` (Status, Zielgruppe, Sprache, Python-Versionen, Linux) |
| Schlagwörter | `keywords` |
| Links in der Seitenleiste | `[project.urls]` (Homepage, Repository, Issues, Changelog) |
| Lizenz | `license` (SPDX `AGPL-3.0-or-later`), Datei über `license-files` |
| Python-Anforderung | `requires-python` |
| Autor | `authors` (derzeit nicht gesetzt) |

Die Seite ändert sich nur mit einem neuen Upload: Metadaten nachträglich ändern geht nicht, dafür braucht es eine neue Version.

README-Darstellung vorab lokal prüfen (Fehler melden, bevor PyPI den Upload ablehnt):

```
env -u VIRTUAL_ENV uv run --with readme-renderer python -m readme_renderer README.md -o /tmp/readme.html
```

Logo oder Screenshot sind optional. PyPI zeigt nur Bilder mit absoluter `https://`-URL, relative Pfade bleiben leer.
Also Bild ins Repo legen (z. B. `docs/images/screenshot.png`) und im README mit
`![Screenshot](https://raw.githubusercontent.com/Luk007x/WhatTheShell/main/docs/images/screenshot.png)` einbinden.

Noch vom Auftraggeber zu liefern:

- [ ] Optional: Screenshot oder Logo (siehe oben).
- [ ] Entscheidung über die Projekt-URLs (derzeit `https://github.com/Luk007x/WhatTheShell`, Changelog = Releases-Seite).
- [ ] Autor mit E-Mail in `authors` (z. B. `authors = [{ name = "…", email = "…" }]`); die Adresse wird öffentlich angezeigt.

## 7. SBOM

Jede Veröffentlichung enthält eine CycloneDX-SBOM (JSON, Spec 1.5) der Python-Laufzeitabhängigkeiten
(aus `uv.lock`, ohne Dev-Gruppe) und der gebündelten npm-Pakete (aus `gui/package-lock.json`, ohne Dev).

- Erzeugt von `scripts/sbom.sh` (ruft `scripts/sbom_merge.py`), automatisch aus `scripts/build_wheel.sh`.
  Voraussetzung: `npm ci` in `gui/` (macht `build_wheel.sh` vorher).
- Ablage: `dist/sbom.cdx.json` (Anhang des GitHub-Releases) und `src/whattheshell/sbom.cdx.json`
  (gitignored, liegt im Wheel und sdist). Auf PyPI wird nur Wheel und sdist hochgeladen.
- Prüfen: `wts --sbom` gibt die mitgelieferte Datei aus, z. B. `wts --sbom | python3 -m json.tool | head`.
  Im Entwicklungs-Checkout ohne Build meldet es „Keine SBOM im Paket“ (Exit 1).
- Grenze: Für Python-Pakete enthält die SBOM keine Abhängigkeitskanten untereinander; alle hängen direkt an
  der Wurzel `whattheshell`.
