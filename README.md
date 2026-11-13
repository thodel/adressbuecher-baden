# Adressbücher Baden 1900 und 1910

Einträge der Adressbücher von Baden (Aargau), maschinell gelesen. Quelle für
[Vernetzte Schweiz 1860–1914](https://thodel.github.io/vernetzte-schweiz/), wo sie mit den
Telefonbüchern und den anderen Adressbüchern verknüpft werden.

| Band | Seiten | Einwohner | Berufsregister | Gemeinden |
|---|---:|---:|---:|---|
| Adressbuch Baden 1900 inkl. Ennetbaden | 62 | 1 136 | 743 | Baden, Ennetbaden |
| Adressbuch für Stadt und Bezirk Baden 1910 | 212 | 6 534 | 1 754 | Bezirk Baden, 29 Gemeinden |

## Dateien

Schema wie [adressbuecher-aarau](https://github.com/thodel/adressbuecher-aarau), dazu die
Spalten `municipality` (Gemeinde zum Stand 1914) und `qa_flags`.

- `data/csv/04_entries.csv`: Einwohnerverzeichnisse.
- `data/csv/04_berufe.csv`: Berufsregister; der Beruf steht in `heading`.
- `data/csv/03_sections.csv`: welche Seiten in welchen Teil gehen, und ab welcher Stelle welche
  Gemeinde gilt.
- `data/csv/00_volumes.csv`: die Bände mit Prüfsumme des PDFs.
- `data/csv/10_authority_links.csv`: leer. Normdaten (Wikidata, HLS, GND) verknüpft «Vernetzte
  Schweiz» über die Personen, nicht dieses Repo.
- `data/qwen/<Jahr>/`: die Lesung, wie sie vom Modell kam (`entries.csv`, je Seite `pages.csv`).

`python scripts/convert.py` erzeugt `data/csv/` aus `data/qwen/`; `python -m unittest discover -s tests`
prüft Ort- und Gemeindezuordnung.

## Wie gelesen

- **Modell:** `qwen3.8-27b` auf GPUStack der Universität Bern, Seitenbild 2× vergrössert,
  Ausgabe als JSON-Zeilen (Familienname, Allianzname, Vorname, Beruf, Strasse, Hausnummer,
  Telefon). Alle Seiten endeten sauber.
- **Stichprobe, von Hand am Seitenbild:** Baden 1900 154 von 161 Einträgen voll korrekt (96 %),
  Baden 1910 127 von 136 (93 %). «Voll korrekt» heisst: Text zeichengenau und Felder richtig getrennt.
- Keine Nachkorrektur. `qa_flags` markiert Verdachtsfälle (seltene Strasse, Trennstrich,
  zusammengesetzter Name); solche Einträge haben `parse_confidence = medium`.

## Gemeinden

- **1900:** Einwohner und Berufsregister der Stadt (S. 19–56), dann Ennetbaden (S. 57–59, nach
  Berufen geordnet).
- **1910:** Einwohner der Stadt (S. 33–64), dann die Gemeinden des Bezirks bis S. 116. Jede beginnt
  mit einem Kopf «… m über Meer. — … Einwohner»; daran ist die Gemeinde festgemacht. Ortsteile
  gehören zu ihrer Gemeinde von 1914 (Rütihof → Dättwil, Vogelsang → Gebenstorf,
  Staretschwil → Oberrohrdorf).
- **Berufsregister 1910:** gilt für den ganzen Bezirk; die Gemeinde kommt aus dem Ende des Eintrags
  («…, Haselstr. 27, Baden»). 22 von 1 754 Einträgen nennen keinen erkennbaren Ort und bleiben ohne
  Gemeinde.

## Lücken

- **Im Scan von 1910 fehlen Blätter** zwischen S. 64 und 65: die Stadt Baden ab «Rü…», Bellikon
  ganz und Bergdietikon bis «P». Bellikon erscheint darum nur im Berufsregister.
- **1910, S. 69 und 70** liegen im Scan vor S. 71–74; S. 69 gehört zu Ennetbaden, S. 70 zu Fislisbach.
- **Nicht übernommen:** Inserate, Vorspann, Behörden-, Vereins- und Reglementsseiten.

## Lizenz

Die Bücher sind vor 1914 erschienen; ihr Inhalt ist gemeinfrei (URG Art. 2 Abs. 1, Art. 29 Abs. 2).
Die Daten in `data/` stehen unter [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/),
der Code unter MIT. Die Scans selbst liegen nicht in diesem Repo.
