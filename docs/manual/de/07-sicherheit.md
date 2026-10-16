# Sicherheit

WhatTheShell führt Befehle auf dem eigenen Rechner aus. Dieses Kapitel beschreibt, was das Programm dagegen tut, dass dabei etwas schiefgeht, und wo die Grenzen liegen.

## Keine Shell, nur Argumentlisten

- Jeder Befehl wird als Liste von Argumenten gestartet, nie als Shell-Zeile. Sonderzeichen wie `;`, `$()`, Backticks, Leerzeichen oder Anführungszeichen in Werten sind damit wirkungslos.
- Der angezeigte Befehl wird nur zur Anzeige mit Anführungszeichen versehen; gestartet wird die Liste.
- Ein Wert, der mit `-` beginnt, kann vom Werkzeug als Option gelesen werden. Das Programm fügt kein `--` ein, weil nicht jedes Werkzeug es kennt.
- Ein Werkzeug, das selbst eine Shell startet (`sh -c`, `xargs`), wird dadurch nicht entschärft. Solche Werkzeuge sind mindestens „Vorsicht“.

## Workflow- und Moduldateien sind nicht vertrauenswürdig

Dateien aus fremder Quelle gelten als fremder Input.

- Beim Öffnen oder Laden wird **nichts ausgeführt**. Die Datei wird nur gelesen und geprüft.
- Vor dem ersten Lauf zeigt das Programm alle Befehle mit Sicherheitsklasse (Plan).
- Dateien über 1 MiB, YAML-Aliase und -Anker (Schutz vor YAML-Bomben) sowie extrem tiefe Verschachtelung werden abgelehnt. Eine fehlerhafte Datei deaktiviert nur sich selbst.
- Vorlagen `{{ … }}` kennen nur Verweise auf Werte; es gibt keine Ausdrücke, Aufrufe oder Filter.
- Ein Terminal-Schritt hat keine vorbelegten Tastatureingaben; solche Felder lehnt das Programm ab.

Grenzen:

- Es gibt keine Herkunftsmarkierung („fremde Datei, noch nie bestätigt“).
- Projektmodule und Projektworkflows aus `./.whattheshell/` werden ohne Rückfrage geladen.
- Das Auflösen eines Werkzeugs liest dessen Hilfe (`--help`); das startet das Werkzeug. Für unbekannte Unterbefehle geschieht das nie. Werkzeuge wie `shutdown`, `reboot`, `halt`, `poweroff`, `init`, `telinit` und `kexec` werden dabei nie abgefragt. Weitere gefährliche Werkzeuge sind nicht erfasst. Der Abruf läuft in der Sandbox, sobald sie verfügbar ist; Werkzeuge unter `/home`, `/root`, `/tmp`, `/var/tmp` und `/run` laufen zusätzlich auf dem Host.
- Ein bösartiges Modul kann irreführende Beschreibungen oder Beispiele enthalten. Der angezeigte Befehl ist dennoch der, der läuft.

## Sicherheitsklassen und Bestätigungen

| Klasse | Verhalten |
|---|---|
| sicher (`safe`) | Läuft ohne Rückfrage |
| Vorsicht (`caution`) | Rückfrage mit Klartextbefehl |
| gefährlich (`dangerous`) | Rückfrage mit Klartextbefehl und rotem Bestätigungsknopf |

- Die höchste zutreffende Regel gewinnt. Module dürfen höher einstufen, nicht niedriger als die eingebauten Listen.
- Die Klasse wird vor dem Lauf und noch einmal zur Laufzeit mit den eingesetzten Werten bestimmt; die höhere gilt.
- Der Trockenlauf ist immer verfügbar und startet nichts.
- `sudo`, `su`, `doas`, `pkexec`, `chroot` sind „gefährlich“. Es gibt kein stilles `sudo`. `sudo` braucht ein Terminal für das Passwort, und die Engine reicht kein Passwort durch.
- Auf der Kommandozeile bestätigt `--yes` alles ohne Rückfrage. Das ist beabsichtigt für Skripte.

Die Einstufung ist eine Heuristik auf Namen und Optionen. Sie erkennt nicht:

- Werkzeuge unter anderem Namen (Symlink, Skript),
- Gefahr, die erst in Werten steckt (z. B. `dd of=/dev/sda`, Zielpfade),
- gebündelte Kurzoptionen wie `-rf` (Ausnahme `sed -i…`),
- Werkzeuge, die intern `sudo` oder eine Shell aufrufen.

Unbekannte Werkzeuge bleiben „sicher“. Wer ein Werkzeug genauer einstufen will, schreibt ein Modul (Kapitel „Module“). Im Zweifel die höhere Klasse wählen.

Reale Läufe erben die volle Umgebung des Benutzers (`HOME`, `PATH` …). Secrets in Umgebungsvariablen sind für jedes gestartete Programm sichtbar. Speicher- und Prozesslimits der Sandbox gelten nicht für Läufe auf dem Host.

## Sandbox

Vorschau eines Schritts, Modul-Beispiele und Terminal-Schritte laufen in `bwrap` (bubblewrap).

| Eigenschaft | Wirkung |
|---|---|
| Dateisystem | Schreibgeschützt eingebunden; `/tmp`, `/var/tmp`, `/home`, `/root`, `/run` sind leer. Beschreibbar ist nur der Arbeitsordner (in der Sandbox unter `/tmp/work`) |
| Netz | Kein Netz. Nur ein Terminal-Schritt mit `network: true` bekommt eines |
| Prozesse | Eigener Prozess-Namensraum; endet mit dem Programm |
| Umgebung | Bereinigt; fester `PATH` |
| Limits | Vorschau: 10 s und 1 MiB Ausgabe; Speicher und Prozesse über `prlimit` (512 MiB Adressraum, 256 Prozesse) |

**Es gibt keinen Ersatzmodus.** Ohne `bwrap` gibt es keine Vorschau, keine Beispiele und keine Terminal-Schritte, statt sie ungeschützt auszuführen. `wts sandbox` zeigt den Zustand und, falls etwas fehlt, den Installationsbefehl.

Grenzen der Sandbox:

- `bwrap` braucht unprivilegierte User-Namespaces; wo diese gesperrt sind, entfällt die Sandbox.
- Das Dateisystem ist **lesbar**: `/home` ist verdeckt, aber `/etc`, `/usr` und Daten außerhalb von `/home` sind lesbar.
- Fehlt `prlimit`, läuft die Sandbox ohne Speicher- und Prozesslimit (mit Warnung).
- Die normale Ausführung eines Workflows (Modus „Ausführen“, `wts run`) läuft **nicht** in der Sandbox, sondern mit den Rechten des Benutzers. Dafür gibt es die Bestätigungen.

## Secrets

Variablen vom Typ `secret` werden in Befehlsanzeige, Ausgabe, Meldungen und Ergebnis als `***` ersetzt, außerdem in Protokollen und KI-Vorschauen. Ein Secret darf keinen Standardwert haben und wird nicht im Browser gemerkt.

Grenzen:

- Maskiert wird der exakte Wert. Abgewandelte Formen (Base64, URL-kodiert, gekürzt) bleiben sichtbar.
- Ein Secret mit Zeilenumbruch, verteilt ausgegeben, kann der Maskierung entgehen. Die Maskierung arbeitet zeilenweise.
- Ein Secret steht in der Argumentliste des Programms und ist für andere Prozesse desselben Benutzers sichtbar (`/proc/PID/cmdline`). Besser über Umgebung oder Standardeingabe übergeben.
- Im Terminal-Transkript wird nach bestem Bemühen maskiert; Neuzeichnungen mit Cursorsprüngen können durchrutschen. Getippte Zeichen erscheinen als Echo.
- Fehlermeldungen wegen eines falschen Variablentyps können den Wert enthalten; das wurde nicht lückenlos geprüft.

## Lokale Oberfläche und API

| Schutz | Wirkung |
|---|---|
| Nur `127.0.0.1` | Der Server ist aus dem Netzwerk nicht erreichbar. Kein `0.0.0.0`, kein IPv6 |
| Sitzungstoken | 32 zufällige Bytes je Start; jede Anfrage braucht es, sonst wird sie abgewiesen. Das Token steht im Teil nach `#` der Adresse und geht nicht an den Server |
| Host-Prüfung | Nur `127.0.0.1:PORT` und `localhost:PORT` werden angenommen (Schutz gegen DNS-Rebinding) |
| Herkunftsprüfung | Anfragen anderer Webseiten werden abgewiesen (Schutz gegen Cross-Site-Anfragen) |
| Kein CORS | Andere Webseiten dürfen die API nicht lesen |
| Kein root | Der Start als root wird verweigert |
| Kein Zugriffslog | Das Token landet nicht in einem Log |
| Größenlimits | Anfragen bis 1 MiB |
| Laufgrenzen | höchstens 4 gleichzeitige Läufe, höchstens 2 gleichzeitige Vorschauen |

Nicht Teil des Schutzes:

- **Andere Prozesse desselben Benutzers.** Sie erreichen den Port und können die Zustandsdatei mit dem Token lesen. Schutz vor lokalen Angreifern mit den Rechten des Benutzers gehört nicht zum Modell. Ebenso ein bereits kompromittiertes Benutzerkonto.
- Jeder Browser-Tab mit gültigem Token kann Rückfragen beantworten; das ist derselbe Benutzer.
- Die erste Adresse mit `#token=…` steht im Browserverlauf und in der Terminalausgabe. Das Token gilt nur für diese Sitzung. Wird der Server hart beendet (`SIGKILL`), bleibt die Weiterleitungsdatei mit dem Token liegen; sie ist nur für den Benutzer lesbar und das Token ist dann wertlos.
- Es gibt keine Content-Security-Policy. Die Oberfläche zeigt Ausgaben als Text an und nutzt kein `innerHTML`.

## Terminal-Schritte

- Nur in der Oberfläche, nur als normaler Benutzer, immer in der Sandbox, höchstens 4 gleichzeitig, eine Verbindung je Terminal. Kein Terminal ohne Sandbox.
- Kein Netz, außer `network: true`; dann mindestens „Vorsicht“ und der Bestätigungstext nennt „Netzzugang“.
- Der Arbeitsordner muss im Laufordner liegen, damit eine fremde Workflow-Datei nicht z. B. `$HOME` beschreibbar einbindet.
- Keine setuid-Programme: `sudo`, `su`, `pkexec` funktionieren in der Sandbox nicht.
- Tastatureingaben werden nie gespeichert oder protokolliert. Ein Transkript speichert nur die Ausgabe, nur auf Wunsch, nur für den Benutzer lesbar.
- Escape-Sequenzen für Zwischenablage (OSC 52), Fenstertitel und Hyperlinks werden verworfen.
- Trennen der Verbindung beendet das Programm. Es gibt kein Wiederverbinden.
- Zeitlimits: das des Schritts, 15 Minuten ohne Ein- oder Ausgabe.
- Die Ausgabe eines Terminal-Schritts geht nicht an Folgeschritte.

## KI aus heißt kein Netz

Solange die KI-Funktionen ausgeschaltet sind (Standard), wird kein KI-Code geladen, es gibt keine Netzwerkverbindung und keinen Fremdprozess. Ist sie an, geht nichts hinaus, bevor man in der Vorschau „Senden“ wählt. Antworten werden nie ausgeführt, sondern nur als Diff zur Freigabe angezeigt (Kapitel „KI-Funktionen“).

## Sicherheitsprobleme melden

Bitte als GitHub-Issue mit dem Label `security` melden. Keine Zugangsdaten, Secrets oder ausnutzbaren Details öffentlich posten; die Beschreibung der Art des Problems genügt. Eine Antwortfrist ist nicht zugesagt.
