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

## 4. Spätere Releases: Trusted Publishing (empfohlen)

Ohne Token im Repo: PyPI vertraut dem GitHub-Workflow direkt.

1. pypi.org → Projekt `whattheshell` → Publishing → GitHub: Owner `Luk007x`, Repo `WhatTheShell`,
   Workflow `release.yml`, Environment `pypi`.
2. In `release.yml` einen Job `publish` ergänzen (`needs: release`, `environment: pypi`,
   `permissions: id-token: write`, Schritt `pypa/gh-action-pypi-publish` mit `dist/`).
3. Ab dann genügt: Version anheben, committen, `git tag vX.Y.Z && git push --tags`.

Der Job ist noch nicht eingebaut; auf Zuruf baut ihn die Claude-Sitzung ein, der Tag-Push bleibt beim Auftraggeber.

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
