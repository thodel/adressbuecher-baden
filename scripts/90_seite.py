"""90_seite.py — die Einträge als durchsuchbare statische Seite (GitHub Pages).

    python scripts/90_seite.py --out web/index.html

Liest data/csv/04_entries.csv und 04_berufe.csv sowie data/review/flags.csv (falls vorhanden) und
bettet alles als JSON in eine Seite mit Reitern, Volltextsuche, Band-, Gemeinde-, Konfidenz- und
Hinweisfilter und **Flagging je Zeile** ein (wie die Kontrollseiten von Aarau und Basel):

- Ein Flag (Grund + Notiz) wird im Browser gespeichert (localStorage) und als CSV exportiert;
  `scripts/91_merge_flags.py` mischt den Export nach `data/review/flags.csv`, die Seite zeigt diese
  Flags beim nächsten Bau als «gemeldet».
- Je Zeile ein Link, der ein vorausgefülltes GitHub-Issue öffnet.

Kein Server, keine externen Daten. Seitenbilder gibt es keine: die Scans sind nicht öffentlich und
ihre Herkunft ist ungeklärt, darum werden sie weder eingebettet noch verlinkt.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
norm_street = importlib.import_module("10_geo").norm_street
import site_nav  # noqa: E402  gemeinsame Navigation und Feldsuche aller Adressbuch-Seiten

CSV_DIR = Path("data/csv")
REVIEW = Path("data/review/flags.csv")
TELEFON = Path("web/telefon.csv")  # aus scripts/80_telefon.py
REPO_URL = "https://github.com/thodel/adressbuecher-baden"

TABS = [
    ("einwohner", "Einwohner", ["04_entries.csv"],
     ["entry_id", "volume", "page", "municipality", "surname", "alliance_name", "forename", "title",
      "civil_status", "occupation_raw", "street_raw", "building_no", "phone_flag", "telefon", "other_volume", "authority", "zeitreise", "entry_type",
      "parse_confidence", "qa_flags", "text", "street_key"]),
    ("berufe", "Berufsregister", ["04_berufe.csv"],
     ["entry_id", "volume", "page", "municipality", "heading", "surname", "alliance_name", "forename", "title",
      "civil_status", "occupation_raw", "origin_raw", "street_raw", "building_no", "phone_flag", "telefon", "other_volume", "authority", "zeitreise", "entry_type",
      "parse_confidence", "qa_flags", "text", "street_key"]),
]

LABELS = {"entry_id": "ID", "volume": "Band", "page": "PDF-S.", "municipality": "Gemeinde", "surname": "Name",
          "alliance_name": "Allianz", "forename": "Vorname", "title": "Titel", "civil_status": "Stand",
          "occupation_raw": "Beruf", "origin_raw": "Ort/Zusatz", "street_raw": "Strasse", "building_no": "Nr.",
          "phone_flag": "Tel.", "entry_type": "Typ", "parse_confidence": "Konfidenz", "qa_flags": "Hinweise",
          "heading": "Rubrik", "text": "Gelesene Zeile", "telefon": "Telefonbuch",
          "other_volume": "Anderer Band", "authority": "Normdaten (ungeprüft)", "zeitreise": "Karte damals"}

QA = {"surname_split": "Familienname vom Allianznamen getrennt",
      "street_rare": "Strasse nur einmal im Band",
      "alliance_from_forename": "Allianzname stand im Vornamen",
      "alliance_from_text": "Allianzname aus dem Text ergänzt",
      "dehyphen": "Zeilenend-Trennung zusammengezogen",
      "hyphen": "Trennstrich mitten im Wort",
      "triple": "dreifacher Buchstabe gekürzt",
      "unreadable": "unleserliche Stelle [?]"}

REASONS = ["Lesefehler", "Feld falsch", "Eintrag falsch getrennt", "Gemeinde falsch", "Rubrik falsch",
           "Quelle: Druckfehler", "Dublette", "Anderes"]


def load_phone() -> dict[str, str]:
    """entry_id → «Stufe|Jahr|Name|Strasse|Nummer|Einheit|Bild» aus web/telefon.csv."""
    if not TELEFON.exists():
        return {}
    with TELEFON.open(encoding="utf-8") as fh:
        return {r["entry_id"]: "|".join(r[k].replace("|", "/") for k in ("how", "ptt_year", "ptt_name", "ptt_street",
                                                                        "ptt_phone", "entity_id", "image"))
                for r in csv.DictReader(fh)}


PHONE = load_phone()


def load_simple(path: str, fields: tuple[str, ...]) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as fh:
        return {r["entry_id"]: "|".join(r[k].replace("|", "/") for k in fields) for r in csv.DictReader(fh)}


OTHER = load_simple("web/baende.csv", ("tier", "other_volume", "other_id", "other_text", "evidence"))  # 81_baende.py
AUTH = load_simple("web/normdaten.csv", ("tier", "label", "life", "hls_id", "qid", "gnd", "field", "note"))  # 82_normdaten.py


def lv95(lat: float, lon: float) -> tuple[int, int]:
    """WGS84 → LV95 (Näherung von swisstopo, auf ~1 m genau)."""
    p, l = (lat * 3600 - 169028.66) / 10000, (lon * 3600 - 26782.5) / 10000
    e = 2600072.37 + 211455.93 * l - 10938.51 * l * p - 0.36 * l * p * p - 44.54 * l ** 3
    n = 1200147.07 + 308807.95 * p + 3745.25 * l * l + 76.63 * p * p - 194.56 * l * l * p + 119.79 * p ** 3
    return round(e), round(n)


def load_geo() -> dict[str, list[int]]:
    """«Gemeinde|Strassenschlüssel» bzw. «Gemeinde|» → [E, N] für den Link auf die Zeitreise von swisstopo."""
    out = {}
    for name, key in (("municipalities.csv", lambda r: r["municipality"] + "|"),
                      ("streets.csv", lambda r: r["municipality"] + "|" + r["street_norm"]),
                      ("streets_manual.csv", lambda r: r["municipality"] + "|" + r["street_norm"])):
        p = Path("web/geo") / name
        if p.exists():
            for r in csv.DictReader(p.open(encoding="utf-8")):
                if r["lat"]:
                    out[key(r)] = list(lv95(float(r["lat"]), float(r["lon"])))
    return out


GEO = load_geo()


def tel_stat() -> str:
    n_flag = sum(1 for f in ("04_entries.csv", "04_berufe.csv")
                 for r in csv.DictReader((CSV_DIR / f).open(encoding="utf-8")) if r["phone_flag"] == "1")
    return f"{len(PHONE):,} von {n_flag:,} Einträgen mit ☏ haben einen Treffer.".replace(",", "\u202f")


def load(files: list[str], cols: list[str]) -> list[list[str]]:
    """Zeilen in der Reihenfolge von cols; weitere CSV-Spalten werden an cols angehängt (nur für die Feldsuche)."""
    rows, csv_rows, fieldnames = [], [], []
    for f in files:
        p = CSV_DIR / f
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            csv_rows += list(reader)
            fieldnames += [c for c in reader.fieldnames if c not in fieldnames]
    cols += site_nav.extra_columns(csv_rows, fieldnames, cols)
    for r in csv_rows:
        r["qa_flags"] = " ".join(x for x in r.get("qa_flags", "").replace(";", " ").split())
        r["telefon"] = PHONE.get(r["entry_id"], "")
        r["street_key"] = norm_street(r["street_raw"]) if r.get("street_raw") else ""
        r["other_volume"] = OTHER.get(r["entry_id"], "")
        r["authority"] = AUTH.get(r["entry_id"], "")
        r["zeitreise"] = ""  # im Browser aus GEO
        rows.append([r.get(c, "") for c in cols])
    return rows


def load_flags() -> list[dict]:
    if not REVIEW.exists():
        return []
    with REVIEW.open(encoding="utf-8") as fh:
        return [{"table": r["table"], "id": r["id"], "reason": r["reason"], "note": r["note"],
                 "by": r.get("by", ""), "date": r.get("date", "")}
                for r in csv.DictReader(fh) if r.get("status", "open") != "fixed"]


TEMPLATE = r"""<!doctype html>
<html lang="de">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Adressbücher Baden 1900/1910</title>
<meta name="description" content="Einträge der Adressbücher von Baden (Aargau) 1900 und 1910, maschinell gelesen mit qwen3.8, durchsuchbar nach Name, Beruf, Strasse und Gemeinde.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Source+Code+Pro:wght@400;600&display=swap">
<style>
/* Layout: Werkzeug wie Aarau/Basel — Kopf mit Hinweis und Filtern, darunter eine Tabelle, die den Rest füllt. */
:root {
  --bg: #f6f5f1; --paper: #ffffff; --fg: #1d2129; --muted: #5c6370; --line: #d9d7cf;
  --accent: #7a2e2e; --accent-soft: #f1e3e1; --ok: #2f6f4e; --warn: #9a6b11; --bad: #a33a2a; --flag: #fff3c4;
  --note-bg: #fbf4e2; --note-line: #e2cf9c;
  --font-body: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  --font-data: "Source Code Pro", ui-monospace, Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #15171b; --paper: #1d2026; --fg: #e8e6df; --muted: #a39f94; --line: #353942;
  --accent: #d08a84; --accent-soft: #3a2626; --ok: #7fc39d; --warn: #d9b35a; --bad: #e08a79; --flag: #3b3418;
  --note-bg: #2a2619; --note-line: #5a4d2a; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #15171b; --paper: #1d2026; --fg: #e8e6df; --muted: #a39f94; --line: #353942;
  --accent: #d08a84; --accent-soft: #3a2626; --ok: #7fc39d; --warn: #d9b35a; --bad: #e08a79; --flag: #3b3418;
  --note-bg: #2a2619; --note-line: #5a4d2a; color-scheme: dark }
[hidden] { display: none !important; }
html, body { height: 100%; }
body { background: var(--bg); color: var(--fg); font-family: var(--font-body); font-size: 15px; line-height: 1.4;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 16px; display: flex; flex-direction: column; gap: 10px; box-sizing: border-box; margin: 0; }
header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 20px; }
.nav { font-size: 0.9rem; color: var(--muted); }
.nav a, td a, .note a, .sub a { color: var(--accent); }
.nav a { font-weight: 600; text-decoration: none; }
.nav a:hover, .nav a:focus-visible { text-decoration: underline; }
h1 { font-size: 1.3rem; margin: 0; font-weight: 700; letter-spacing: -0.01em; text-wrap: balance; }
.sub { color: var(--muted); font-size: 0.88rem; margin: 0; }
.note { background: var(--note-bg); border: 1px solid var(--note-line); border-radius: 8px; padding: 8px 12px; font-size: 0.9rem; }
.note p { margin: 0; }
.note details { margin-top: 4px; }
.note summary { cursor: pointer; color: var(--accent); font-weight: 600; }
.note .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 4px 24px; margin-top: 6px; }
.note h2 { font-size: 0.95rem; margin: 6px 0 2px; }
.note ul { margin: 0; padding-left: 1.2em; }
.note li { margin: 2px 0; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; }
.tabs { display: flex; gap: 4px; flex-wrap: wrap; }
button { font: inherit; cursor: pointer; }
.tabs button { font-weight: 600; background: transparent; color: var(--muted); border: 1px solid var(--line); border-radius: 999px; padding: 4px 12px; }
.tabs button[aria-selected="true"] { background: var(--accent); border-color: var(--accent); color: #fff; }
button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
input[type="search"], select, input[type="text"] { font: inherit; padding: 5px 9px; border: 1px solid var(--line); border-radius: 6px; background: var(--paper); color: var(--fg); min-width: 0; max-width: 100%; }
input[type="search"] { flex: 1 1 220px; }
.chip { display: inline-flex; gap: 6px; align-items: center; background: var(--accent-soft); border: 1px solid var(--accent); border-radius: 999px; padding: 2px 4px 2px 10px; font-size: 0.88rem; }
.chip button { border: 0; background: transparent; color: var(--accent); font-weight: 700; padding: 0 6px; }
.count { color: var(--muted); font-variant-numeric: tabular-nums; font-size: 0.9rem; }
.flagbar { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; padding: 8px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); font-size: 0.9rem; }
.flagbar .n { font-weight: 700; color: var(--accent); font-variant-numeric: tabular-nums; }
.btn { border: 1px solid var(--line); background: var(--paper); color: var(--fg); border-radius: 6px; padding: 4px 10px; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.wrap { flex: 1 1 auto; min-height: 320px; overflow: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); }
table { border-collapse: collapse; width: max-content; min-width: 100%; font-size: 13.5px; }
th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); vertical-align: top; white-space: nowrap; max-width: 32ch; overflow: hidden; text-overflow: ellipsis; }
td.wide { white-space: normal; max-width: 48ch; }
th { position: sticky; top: 0; background: var(--paper); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); z-index: 1; }
td.num, td.id { font-family: var(--font-data); font-variant-numeric: tabular-nums; font-size: 12.5px; }
td button.gem { border: 0; background: none; padding: 0; color: var(--accent); text-decoration: underline dotted; text-underline-offset: 2px; }
tr.flagged td { background: var(--flag); }
tr.reported td:first-child::before { content: "✓ "; color: var(--ok); font-weight: 700; }
.pill { display: inline-block; border-radius: 999px; padding: 0 8px; font-size: 0.74rem; font-weight: 600; line-height: 1.5; }
.pill.high { background: color-mix(in srgb, var(--ok) 18%, transparent); color: var(--ok); }
.pill.medium { background: color-mix(in srgb, var(--warn) 18%, transparent); color: var(--warn); }
.pill.review { background: color-mix(in srgb, var(--bad) 18%, transparent); color: var(--bad); }
.qa { display: inline-block; border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; margin-right: 3px; font-size: 0.74rem; color: var(--muted); }
.star { color: var(--accent); font-weight: 700; }
td.act { white-space: nowrap; }
td.act select, td.act input { font-size: 12.5px; padding: 2px 5px; }
td.act input[type="text"] { width: 14ch; }
td.act a { color: var(--muted); font-size: 12px; margin-left: 6px; }
.more { display: block; width: 100%; padding: 8px; background: var(--accent-soft); color: var(--fg); border: 0; }
.legend { color: var(--muted); font-size: 0.84rem; margin: 0; }
.legend b { color: var(--fg); }
footer { color: var(--muted); font-size: 0.8rem; }
footer a { color: var(--accent); }
#toast { position: fixed; bottom: calc(12px + env(safe-area-inset-bottom, 0px)); right: calc(12px + env(safe-area-inset-right, 0px)); background: var(--fg); color: var(--bg); padding: 8px 14px; border-radius: 8px; font-size: 0.9rem; }
@media (max-width: 600px) { body { font-size: 14px; } th, td { max-width: 22ch; } td.act input[type="text"] { width: 9ch; } .flagbar .sub { display: none; } .wrap { min-height: 70vh; } }
__NAVCSS__
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
__CITYBAR__
<header>
  __CITYNAV__
  <h1>Adressbücher Baden 1900 und 1910</h1>
  <p class="sub">Stand __DATE__ · Einwohnerverzeichnisse und Berufsregister der Stadt Baden (1900, mit Ennetbaden) und des Bezirks Baden (1910, 29 Gemeinden).</p>
</header>
<section class="note" aria-label="Hinweis zu den Daten">
  <p><b>Maschinell gelesen, nicht von Hand korrigiert.</b> Der Text stammt vom Sprachmodell qwen3.8 (Universität Bern) und wurde nicht nachkorrigiert. In einer Stichprobe waren 96&nbsp;% (1900) bzw. 93&nbsp;% (1910) der Einträge zeichengenau und richtig in Felder getrennt. <b>Seitenbilder gibt es hier keine.</b></p>
  <details id="about">
    <summary>Über die Daten: Lücken, Gemeinden, Lizenz</summary>
    <div class="cols">
      <div>
        <h2>Bände</h2>
        <ul>
          <li><b>1900</b> · Adressbuch Baden inkl. Ennetbaden: __N1900__ Einwohner, __B1900__ Einträge im Berufsregister.</li>
          <li><b>1910</b> · Adressbuch für Stadt und Bezirk Baden: __N1910__ Einwohner, __B1910__ Einträge im Berufsregister, 29 Gemeinden.</li>
        </ul>
        <h2>Lücken</h2>
        <ul>
          <li>Im Scan von 1910 fehlen Blätter zwischen PDF-S. 64 und 65: die Stadt Baden ab «Rü…», Bellikon ganz und Bergdietikon bis «P». Bellikon erscheint darum nur im Berufsregister.</li>
          <li>1910, PDF-S. 69 und 70 liegen im Scan vor S. 71–74; S. 69 gehört zu Ennetbaden, S. 70 zu Fislisbach.</li>
          <li>Nicht übernommen: Inserate, Vorspann, Behörden-, Vereins- und Reglementsseiten.</li>
        </ul>
      </div>
      <div>
        <h2>Gemeinden</h2>
        <ul>
          <li>Die Gemeinde gilt zum Stand 1914. Ortsteile gehören zu ihrer Gemeinde (Rütihof → Dättwil, Vogelsang → Gebenstorf, Staretschwil → Oberrohrdorf).</li>
          <li>Im Berufsregister 1910 kommt die Gemeinde aus dem Ende des Eintrags; __NOGEM__ Einträge nennen keinen erkennbaren Ort.</li>
        </ul>
        <h2>Telefonbuch</h2>
        <ul><li>Einträge mit ☏ sind, wo möglich, mit dem PTT-Telefonbuch verbunden: zuerst über die gedruckte Nummer und den Familiennamen (höchstens 5 Jahre Abstand), sonst über die Verknüpfung von <a href="https://thodel.github.io/vernetzte-schweiz/">Vernetzte Schweiz</a>, sonst wenn im Telefonbuch der Gemeinde genau eine Person mit diesem Namen und Vornamen steht. __TELSTAT__</li></ul>
        <h2>Verknüpfungen</h2>
        <ul>
          <li><b>Anderer Band:</b> __NOTHER__ Einträge sind automatisch mit derselben Person im anderen Band verbunden (gleicher Familienname, passender Vorname, dazu Beruf, Strasse, Allianzname); mehrdeutige Fälle bleiben offen.</li>
          <li><b>Normdaten:</b> __NAUTH__ Einträge haben einen <b>ungeprüften</b> Kandidaten aus dem HLS bzw. Wikidata (Person mit Bezug zur Gemeinde, lebte im Jahr des Bandes, Name und Vorname passen, Beruf passt zum Feld oder der Name ist selten).</li>
          <li><b>Karte damals:</b> Link auf die Siegfriedkarte des Jahres (swisstopo Zeitreise) an der Strasse, sonst an der Gemeinde. Dazu die <a href="karte.html">Karte</a> aller Einträge.</li>
        </ul>
        <h2>Seitenbilder</h2>
        <ul><li>Die Scans sind nicht öffentlich und ihre Herkunft ist ungeklärt; sie werden weder gezeigt noch verlinkt. «PDF-S.» ist die Seite im Scan, nicht die gedruckte Seitenzahl.</li></ul>
        <h2>Lizenz</h2>
        <ul><li>Die Bücher erschienen vor 1914, ihr Inhalt ist gemeinfrei. Daten <a href="__REPO__/blob/main/data/LICENSE.md">CC0 1.0</a>, Code <a href="__REPO__/blob/main/LICENSE">MIT</a>. CSV im <a href="__REPO__/tree/main/data/csv">Repo</a>.</li></ul>
      </div>
    </div>
  </details>
</section>
<div class="toolbar">
  <div class="tabs" role="tablist" id="tabs"></div>
  <select id="vol" aria-label="Band"><option value="">alle Bände</option></select>
  <select id="gem" aria-label="Gemeinde"><option value="">alle Gemeinden</option></select>
  <select id="conf" aria-label="Konfidenz"><option value="">alle Konfidenzen</option><option value="high">high</option><option value="medium">medium</option></select>
  <select id="qa" aria-label="Hinweis"><option value="">alle Hinweise</option><option value="-">ohne Hinweis</option></select>
  <select id="tel" aria-label="Telefon"><option value="">Telefon: alle</option><option value="1">mit ☏</option><option value="link">mit Telefonbuch-Eintrag</option><option value="none">☏, kein Eintrag gefunden</option></select>
  <span class="chip" id="strchip" hidden>Strasse = <b id="strlabel"></b><button type="button" id="strclear" aria-label="Strassenfilter entfernen">✕</button></span>
  <label><input type="checkbox" id="onlyflag"> nur markierte</label>
  <input id="q" type="search" placeholder="Suchen: Name, Beruf, Strasse, Rubrik, ID …" aria-label="Suchen">
  <span class="count" id="count" aria-live="polite"></span>
</div>
__FSPANEL__
<div class="flagbar">
  <span><span class="n" id="nflags">0</span> Flags in diesem Browser · <span id="nreported">0</span> bereits im Repo gemeldet</span>
  <button class="btn primary" id="dl">Flags als CSV herunterladen</button>
  <button class="btn" id="copy">CSV in die Zwischenablage</button>
  <button class="btn" id="clear">Flags löschen</button>
  <span class="sub">Danach: <code>python scripts/91_merge_flags.py &lt;datei.csv&gt;</code> und committen.</span>
</div>
<p class="legend"><b>Konfidenz</b>: high = keine Auffälligkeit, medium = ein Hinweis spricht für Prüfung (seltene Strasse, Trennstrich, unleserlich, getrennter Familienname) · <b>Hinweise</b>: automatische Markierungen, keine Korrekturen (Maus darüber für Erklärung) · <b>Gemeinde</b> anklicken filtert · <b>☏</b> = Telefon genannt · <b>Telefonbuch</b>: passender Eintrag im PTT-Telefonbuch, Link auf die Person bei Vernetzte Schweiz und aufs Seitenbild; «nummer» = gleiche Nummer und Name, «name» = einzige Person mit Name und Vorname, sonst die Stufe der Verknüpfung von Vernetzte Schweiz · <b>Anderer Band</b>: dieselbe Person im anderen Band (automatisch, Stufe) · <b>Normdaten</b>: ungeprüfte Kandidaten aus HLS und Wikidata · <b>Karte damals</b>: Siegfriedkarte des Jahres bei swisstopo · <b>✓</b> = Flag schon im Repo</p>
<div class="wrap"><table id="t"><thead></thead><tbody></tbody></table><button class="more" id="more" hidden>weitere Zeilen zeigen</button></div>
<footer>Daten CC0 1.0 · Code MIT · Quelle für <a href="https://thodel.github.io/vernetzte-schweiz/">Vernetzte Schweiz 1860–1914</a></footer>
<div id="toast" hidden></div>
<script>
__FSJS__
const FSTX = __FSTX__;
const DATA = __DATA__;
const LABELS = __LABELS__;
const QA = __QA__;
const GEO = __GEO__;
const HOW = {nummer: 'gleiche Telefonnummer und Familienname', sicher: 'Vernetzte Schweiz: sicher', wahrscheinlich: 'Vernetzte Schweiz: wahrscheinlich', möglich: 'Vernetzte Schweiz: möglich (nur Name)', name: 'einzige Person dieses Namens und Vornamens im Telefonbuch der Gemeinde'};
const REASONS = __REASONS__;
const REPORTED = __REPORTED__;
const REPO = "__REPO__";
const PAGE = 300;
const KEY = 'baden.flags.v1';
const P = new URLSearchParams(location.search);
let tab = P.get('tab') && DATA[P.get('tab')] ? P.get('tab') : ((location.hash.replace('#','') in DATA) ? location.hash.replace('#','') : Object.keys(DATA)[0]);
let shown = PAGE;
let strF = P.get('str') || '';
let flags = {};
try { flags = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { flags = {}; }
const reported = {}; for (const f of REPORTED) reported[f.table + '|' + f.id] = f;
const $ = id => document.getElementById(id);
const tabsEl = $('tabs'), q = $('q'), vol = $('vol'), gem = $('gem'), conf = $('conf'), qa = $('qa'), tel = $('tel'), onlyflag = $('onlyflag');
const thead = document.querySelector('#t thead'), tbody = document.querySelector('#t tbody'), more = $('more'), count = $('count');
const vols = new Set(); for (const k in DATA) for (const r of DATA[k].rows) vols.add(r[1]);
[...vols].sort().forEach(v => { const o = document.createElement('option'); o.value = v; o.textContent = v; vol.appendChild(o); });
for (const k in QA) { const o = document.createElement('option'); o.value = k; o.textContent = QA[k]; qa.appendChild(o); }
for (const k in DATA) { const b = document.createElement('button'); b.setAttribute('role', 'tab'); b.textContent = `${DATA[k].label} (${DATA[k].rows.length.toLocaleString('de-CH')})`; b.dataset.k = k; b.onclick = () => { tab = k; shown = PAGE; render(); }; tabsEl.appendChild(b); }
function esc(s) { return String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function save() { try { localStorage.setItem(KEY, JSON.stringify(flags)); } catch (e) {} }
function toast(msg) { const t = $('toast'); t.textContent = msg; t.hidden = false; setTimeout(() => { t.hidden = true; }, 2500); }
function gemOptions() {
  // Gemeinden des aktuellen Reiters und Bands, mit Anzahl; die Auswahl bleibt, auch wenn sie 0 Treffer hat.
  const d = DATA[tab], gi = d.cols.indexOf('municipality'), cur = gem.value, n = {};
  for (const r of d.rows) if (!vol.value || r[1] === vol.value) { const g = r[gi] || '–'; n[g] = (n[g] || 0) + 1; }
  if (cur && !(cur in n)) n[cur] = 0;
  const names = Object.keys(n).sort((a, b) => a === 'Baden' ? -1 : b === 'Baden' ? 1 : a.localeCompare(b, 'de'));
  gem.innerHTML = '<option value="">alle Gemeinden</option>' + names.map(g => `<option value="${esc(g)}">${esc(g === '–' ? 'ohne Gemeinde' : g)} (${n[g].toLocaleString('de-CH')})</option>`).join('');
  gem.value = cur;
}
function issueUrl(k, r) {
  const d = DATA[k], id = r[0];
  const body = `Tabelle: ${d.label}\nID: ${id}\nBand ${r[1]}, PDF-Seite ${r[2]}, Gemeinde ${r[d.cols.indexOf('municipality')] || '–'}\n\nGelesene Zeile:\n${r[d.cols.indexOf('text')] ?? ''}\n\nProblem:\n`;
  return `${REPO}/issues/new?title=${encodeURIComponent('Flag ' + id)}&labels=${encodeURIComponent('review')}&body=${encodeURIComponent(body)}`;
}
function cell(k, col, v, r) {
  const d = DATA[k];
  if (col === 'parse_confidence') return `<td><span class="pill ${esc(v)}">${esc(v)}</span></td>`;
  if (col === 'phone_flag') return `<td class="num">${v === '1' ? '<span class="star" title="Telefon">☏</span>' : ''}</td>`;
  if (col === 'municipality') return `<td>${v ? `<button type="button" class="gem" data-g="${esc(v)}" title="nach ${esc(v)} filtern">${esc(v)}</button>` : '<span class="sub">–</span>'}</td>`;
  if (col === 'telefon') {
    if (!v) return r[d.cols.indexOf('phone_flag')] === '1' ? '<td class="sub">nicht gefunden</td>' : '<td></td>';
    const [how, year, name, street, phone, eid, img] = v.split('|');
    const tip = `Telefonbuch ${year}: ${name}${street ? ', ' + street : ''}${phone ? ', Nr. ' + phone : ''} · Zuordnung: ${HOW[how] || how}`;
    const main = eid ? `<a href="https://thodel.github.io/vernetzte-schweiz/#/e/${esc(eid)}" target="_blank" rel="noopener" title="${esc(tip)}">${esc(year)}${phone ? ' · Nr. ' + esc(phone) : ''}</a>` : `<span title="${esc(tip)}">${esc(year)}</span>`;
    return `<td>${main}${img ? ` · <a href="${esc(img)}" target="_blank" rel="noopener" title="Seite im Telefonbuch (PTT-Archiv)">Bild</a>` : ''} <span class="pill ${how === 'nummer' || how === 'sicher' ? 'high' : 'medium'}" title="${esc(HOW[how] || how)}">${esc(how)}</span></td>`;
  }
  if (col === 'other_volume') {
    if (!v) return '<td></td>';
    const [tier, ov, oid, otext, ev] = v.split('|');
    return `<td><a href="?tab=einwohner&vol=${esc(ov)}&q=${encodeURIComponent(oid)}" title="${esc(otext + ' · ' + ev)}">${esc(ov)} ↗</a> <span class="pill ${tier === 'sicher' ? 'high' : 'medium'}">${esc(tier)}</span></td>`;
  }
  if (col === 'authority') {
    if (!v) return '<td></td>';
    const [tier, label, life, hls, qid, gnd, field, note] = v.split('|');
    const links = [hls ? `<a href="https://hls-dhs-dss.ch/de/articles/${esc(hls)}/" target="_blank" rel="noopener">HLS</a>` : '',
      qid ? `<a href="https://www.wikidata.org/wiki/${esc(qid)}" target="_blank" rel="noopener">Wikidata</a>` : '',
      gnd ? `<a href="https://d-nb.info/gnd/${esc(gnd)}" target="_blank" rel="noopener">GND</a>` : ''].filter(Boolean).join(' · ');
    return `<td class="wide" title="${esc(field + (note ? ' · ' + note : ''))}">${esc(label)} <small>${esc(life)}</small> · ${links} <span class="pill ${tier === 'wahrscheinlich' ? 'high' : 'medium'}" title="ungeprüfter Kandidat">${esc(tier)}</span></td>`;
  }
  if (col === 'zeitreise') {
    const g = GEO[r[d.cols.indexOf('municipality')] + '|' + r[d.cols.indexOf('street_key')]] || GEO[r[d.cols.indexOf('municipality')] + '|'];
    if (!g) return '<td></td>';
    const exact = !!r[d.cols.indexOf('street_key')] && !!GEO[r[d.cols.indexOf('municipality')] + '|' + r[d.cols.indexOf('street_key')]];
    return `<td><a href="https://map.geo.admin.ch/#/map?lang=de&center=${g[0]},${g[1]}&z=${exact ? 11 : 9}&crosshair=marker&bgLayer=void&layers=ch.swisstopo.zeitreihen@year=${esc(r[1])}" target="_blank" rel="noopener" title="${exact ? 'Strasse' : 'Gemeinde'} auf der Siegfriedkarte ${esc(r[1])} (swisstopo Zeitreise)">${exact ? 'Strasse' : 'Ort'} ${esc(r[1])} ↗</a></td>`;
  }
  if (col === 'qa_flags') return `<td>${v ? v.split(' ').map(x => `<span class="qa" title="${esc(QA[x] || x)}">${esc(x)}</span>`).join('') : ''}</td>`;
  if (col === 'entry_id') return `<td class="id">${esc(v)}</td>`;
  if (['page','building_no','volume'].includes(col)) return `<td class="num">${esc(v)}</td>`;
  if (['occupation_raw','text'].includes(col)) return `<td class="wide">${esc(v)}</td>`;
  return `<td>${esc(v)}</td>`;
}
function actCell(k, r) {
  const key = k + '|' + r[0], f = flags[key] || {};
  const opts = ['<option value="">— Flag —</option>'].concat(REASONS.map(x => `<option value="${esc(x)}" ${f.reason === x ? 'selected' : ''}>${esc(x)}</option>`)).join('');
  return `<td class="act"><select data-key="${esc(key)}" data-f="reason" aria-label="Grund">${opts}</select> <input type="text" data-key="${esc(key)}" data-f="note" placeholder="Notiz" value="${esc(f.note || '')}" aria-label="Notiz"><a href="${issueUrl(k, r)}" target="_blank" rel="noopener">Issue</a></td>`;
}
function syncUrl() {
  const p = new URLSearchParams();
  p.set('tab', tab);
  if (vol.value) p.set('vol', vol.value); if (gem.value) p.set('gem', gem.value);
  if (conf.value) p.set('conf', conf.value); if (qa.value) p.set('qa', qa.value); if (tel.value) p.set('tel', tel.value); if (strF) p.set('str', strF);
  if (q.value.trim()) p.set('q', q.value.trim());
  FS.toParams(p);
  history.replaceState(null, '', location.pathname + '?' + p.toString() + (location.hash === '#suche' ? '#suche' : ''));
}
let fsTab = '';
function render() {
  for (const b of tabsEl.children) b.setAttribute('aria-selected', b.dataset.k === tab);
  gemOptions();
  const d = DATA[tab], needle = q.value.trim().toLowerCase(), v = vol.value, g = gem.value, c = conf.value, h = qa.value;
  const oi = d.cols.indexOf('other_volume'), hide = d.hide;
  if (tab !== fsTab) { fsTab = tab; FS.refresh(); }
  const ci = d.cols.indexOf('parse_confidence'), gi = d.cols.indexOf('municipality'), hi = d.cols.indexOf('qa_flags');
  const pi = d.cols.indexOf('phone_flag'), ti = d.cols.indexOf('telefon'), t = tel.value, ki = d.cols.indexOf('street_key');
  $('strchip').hidden = !strF;
  if (strF) $('strlabel').textContent = strF;
  const rows = d.rows.filter(r => (!v || r[1] === v)
    && (!g || (g === '–' ? !r[gi] : r[gi] === g))
    && (!c || r[ci] === c)
    && (!strF || r[ki] === strF)
    && (!t || (t === '1' ? r[pi] === '1' : t === 'link' ? !!r[ti] : r[pi] === '1' && !r[ti]))
    && (!h || (h === '-' ? !r[hi] : (' ' + r[hi] + ' ').includes(' ' + h + ' ')))
    && (!onlyflag.checked || flags[tab + '|' + r[0]] || reported[tab + '|' + r[0]])
    && (!needle || r.filter((_, i) => i !== oi).join(' ').toLowerCase().includes(needle))
    && FS.test(r, d.cols));
  thead.innerHTML = '<tr><th>Flag</th>' + d.cols.filter(cc => !hide.includes(cc)).map(cc => `<th>${esc(LABELS[cc] || cc)}</th>`).join('') + '</tr>';
  tbody.innerHTML = rows.slice(0, shown).map(r => {
    const key = tab + '|' + r[0];
    const cls = (flags[key] && flags[key].reason ? 'flagged ' : '') + (reported[key] ? 'reported' : '');
    return `<tr class="${cls}" title="${reported[key] ? esc('gemeldet: ' + reported[key].reason + ' ' + reported[key].note) : ''}">${actCell(tab, r)}${r.map((vv, i) => hide.includes(d.cols[i]) ? '' : cell(tab, d.cols[i], vv, r)).join('')}</tr>`;
  }).join('');
  more.hidden = rows.length <= shown;
  count.textContent = `${Math.min(shown, rows.length).toLocaleString('de-CH')} von ${rows.length.toLocaleString('de-CH')} Zeilen`;
  $('nflags').textContent = Object.values(flags).filter(f => f.reason).length;
  $('nreported').textContent = REPORTED.length;
  syncUrl();
}
tbody.addEventListener('change', e => {
  const el = e.target, key = el.dataset.key; if (!key) return;
  flags[key] = flags[key] || {}; flags[key][el.dataset.f] = el.value;
  if (!flags[key].reason && !flags[key].note) delete flags[key];
  save(); const tr = el.closest('tr'); tr.classList.toggle('flagged', !!(flags[key] && flags[key].reason)); $('nflags').textContent = Object.values(flags).filter(f => f.reason).length;
});
tbody.addEventListener('click', e => {
  const b = e.target.closest('button.gem'); if (!b) return;
  gemOptions(); gem.value = b.dataset.g; shown = PAGE; render();
});
function flagsCsv() {
  const q2 = s => '"' + String(s ?? '').replace(/"/g, '""') + '"';
  const lines = ['table,id,reason,note,by,date'];
  const today = new Date().toISOString().slice(0, 10);
  for (const key in flags) { const f = flags[key]; if (!f.reason) continue; const [t, id] = key.split('|'); lines.push([t, id, f.reason, f.note || '', '', today].map(q2).join(',')); }
  return lines.join('\n') + '\n';
}
$('dl').onclick = () => {
  const blob = new Blob(['﻿' + flagsCsv()], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `flags_baden_${new Date().toISOString().slice(0, 10)}.csv`; document.body.appendChild(a); a.click(); a.remove();
  toast('CSV wird heruntergeladen (falls gesperrt: Zwischenablage nutzen)');
};
$('copy').onclick = () => {
  const text = flagsCsv();
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(() => toast('CSV kopiert'), () => fallbackCopy(text)); else fallbackCopy(text);
};
function fallbackCopy(text) { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); toast('CSV kopiert'); } catch (e) { toast('Kopieren nicht möglich: Text ist markiert'); } ta.remove(); }
$('clear').onclick = () => { if (!Object.keys(flags).length) return; flags = {}; save(); render(); toast('Flags gelöscht'); };
more.onclick = () => { shown += PAGE; render(); };
for (const el of [q, vol, gem, conf, qa, tel, onlyflag]) el.addEventListener(el === q ? 'input' : 'change', () => { shown = PAGE; render(); });
if (P.get('vol')) vol.value = P.get('vol');
if (P.get('conf')) conf.value = P.get('conf');
if (P.get('qa')) qa.value = P.get('qa');
if (P.get('tel')) tel.value = P.get('tel');
$('strclear').onclick = () => { strF = ''; shown = PAGE; render(); };
if (P.get('q')) q.value = P.get('q');
if (P.get('gem')) { gemOptions(); const o = document.createElement('option'); o.value = P.get('gem'); gem.appendChild(o); gem.value = P.get('gem'); }
FS.init({ cols: () => DATA[tab].cols, skip: ['street_key', 'zeitreise', 'telefon', 'other_volume', 'authority'], labels: LABELS, tx: FSTX, first: 'surname', onChange: () => { shown = PAGE; render(); } });
render();
</script>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    data = {}
    for key, label, files, cols in TABS:
        rows = load(files, cols)
        if rows:
            data[key] = {"label": label, "cols": cols, "rows": rows, "hide": cols[cols.index("street_key"):]}
            print(f"{label}: {len(rows)} Zeilen")
    n_ein = Counter(r[1] for r in data["einwohner"]["rows"])
    n_ber = Counter(r[1] for r in data["berufe"]["rows"])
    gi = data["berufe"]["cols"].index("municipality")
    no_gem = sum(1 for r in data["berufe"]["rows"] if r[1] == "1910" and not r[gi])
    fmt = lambda n: f"{n:,}".replace(",", "\u202f")
    reported = load_flags()
    html = (TEMPLATE.replace("__CITYBAR__", site_nav.city_bar("baden")).replace("__CITYNAV__", site_nav.city_nav("Baden 1900/1910", REPO_URL, "entries"))
            .replace("__NAVCSS__", site_nav.CSS).replace("__FSPANEL__", site_nav.search_panel())
            .replace("__FSJS__", site_nav.FIELD_SEARCH_JS).replace("__FSTX__", json.dumps(site_nav.fs_texts(), ensure_ascii=False))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            .replace("__LABELS__", json.dumps(LABELS, ensure_ascii=False))
            .replace("__QA__", json.dumps(QA, ensure_ascii=False))
            .replace("__GEO__", json.dumps(GEO, ensure_ascii=False, separators=(",", ":")))
            .replace("__REASONS__", json.dumps(REASONS, ensure_ascii=False))
            .replace("__REPORTED__", json.dumps(reported, ensure_ascii=False))
            .replace("__N1900__", fmt(n_ein["1900"])).replace("__N1910__", fmt(n_ein["1910"]))
            .replace("__B1900__", fmt(n_ber["1900"])).replace("__B1910__", fmt(n_ber["1910"]))
            .replace("__NOGEM__", str(no_gem))
            .replace("__TELSTAT__", tel_stat())
            .replace("__NOTHER__", f"{len(OTHER):,}".replace(",", "\u202f"))
            .replace("__NAUTH__", f"{len(AUTH):,}".replace(",", "\u202f"))
            .replace("__REPO__", REPO_URL)
            .replace("__DATE__", date.today().strftime("%d.%m.%Y")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"{len(reported)} gemeldete Flags → {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
