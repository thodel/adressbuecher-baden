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
import json
from collections import Counter
from datetime import date
from pathlib import Path

CSV_DIR = Path("data/csv")
REVIEW = Path("data/review/flags.csv")
REPO_URL = "https://github.com/thodel/adressbuecher-baden"

TABS = [
    ("einwohner", "Einwohner", ["04_entries.csv"],
     ["entry_id", "volume", "page", "municipality", "surname", "alliance_name", "forename", "title",
      "civil_status", "occupation_raw", "street_raw", "building_no", "phone_flag", "entry_type",
      "parse_confidence", "qa_flags", "text"]),
    ("berufe", "Berufsregister", ["04_berufe.csv"],
     ["entry_id", "volume", "page", "municipality", "heading", "surname", "alliance_name", "forename", "title",
      "civil_status", "occupation_raw", "origin_raw", "street_raw", "building_no", "phone_flag", "entry_type",
      "parse_confidence", "qa_flags", "text"]),
]

LABELS = {"entry_id": "ID", "volume": "Band", "page": "PDF-S.", "municipality": "Gemeinde", "surname": "Name",
          "alliance_name": "Allianz", "forename": "Vorname", "title": "Titel", "civil_status": "Stand",
          "occupation_raw": "Beruf", "origin_raw": "Ort/Zusatz", "street_raw": "Strasse", "building_no": "Nr.",
          "phone_flag": "Tel.", "entry_type": "Typ", "parse_confidence": "Konfidenz", "qa_flags": "Hinweise",
          "heading": "Rubrik", "text": "Gelesene Zeile"}

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


def load(files: list[str], cols: list[str]) -> list[list[str]]:
    rows = []
    for f in files:
        p = CSV_DIR / f
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["qa_flags"] = " ".join(x for x in r.get("qa_flags", "").replace(";", " ").split())
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
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
<header>
  <nav class="nav"><a href="./">Baden</a> · <a href="https://thodel.github.io/adressbuecher-aarau/">Adressbücher Aarau</a> · <a href="https://thodel.github.io/adressbuecher-basel/">Adressbücher Basel</a> · <a href="https://thodel.github.io/vernetzte-schweiz/">Vernetzte Schweiz</a> · <a href="__REPO__">Repo</a></nav>
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
  <label><input type="checkbox" id="onlyflag"> nur markierte</label>
  <input id="q" type="search" placeholder="Suchen: Name, Beruf, Strasse, Rubrik, ID …" aria-label="Suchen">
  <span class="count" id="count" aria-live="polite"></span>
</div>
<div class="flagbar">
  <span><span class="n" id="nflags">0</span> Flags in diesem Browser · <span id="nreported">0</span> bereits im Repo gemeldet</span>
  <button class="btn primary" id="dl">Flags als CSV herunterladen</button>
  <button class="btn" id="copy">CSV in die Zwischenablage</button>
  <button class="btn" id="clear">Flags löschen</button>
  <span class="sub">Danach: <code>python scripts/91_merge_flags.py &lt;datei.csv&gt;</code> und committen.</span>
</div>
<p class="legend"><b>Konfidenz</b>: high = keine Auffälligkeit, medium = ein Hinweis spricht für Prüfung (seltene Strasse, Trennstrich, unleserlich, getrennter Familienname) · <b>Hinweise</b>: automatische Markierungen, keine Korrekturen (Maus darüber für Erklärung) · <b>Gemeinde</b> anklicken filtert · <b>☏</b> = Telefonnummer genannt · <b>✓</b> = Flag schon im Repo</p>
<div class="wrap"><table id="t"><thead></thead><tbody></tbody></table><button class="more" id="more" hidden>weitere Zeilen zeigen</button></div>
<footer>Daten CC0 1.0 · Code MIT · Quelle für <a href="https://thodel.github.io/vernetzte-schweiz/">Vernetzte Schweiz 1860–1914</a></footer>
<div id="toast" hidden></div>
<script>
const DATA = __DATA__;
const LABELS = __LABELS__;
const QA = __QA__;
const REASONS = __REASONS__;
const REPORTED = __REPORTED__;
const REPO = "__REPO__";
const PAGE = 300;
const KEY = 'baden.flags.v1';
const P = new URLSearchParams(location.search);
let tab = P.get('tab') && DATA[P.get('tab')] ? P.get('tab') : ((location.hash.replace('#','') in DATA) ? location.hash.replace('#','') : Object.keys(DATA)[0]);
let shown = PAGE;
let flags = {};
try { flags = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { flags = {}; }
const reported = {}; for (const f of REPORTED) reported[f.table + '|' + f.id] = f;
const $ = id => document.getElementById(id);
const tabsEl = $('tabs'), q = $('q'), vol = $('vol'), gem = $('gem'), conf = $('conf'), qa = $('qa'), onlyflag = $('onlyflag');
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
function cell(k, col, v) {
  if (col === 'parse_confidence') return `<td><span class="pill ${esc(v)}">${esc(v)}</span></td>`;
  if (col === 'phone_flag') return `<td class="num">${v === '1' ? '<span class="star" title="Telefon">☏</span>' : ''}</td>`;
  if (col === 'municipality') return `<td>${v ? `<button type="button" class="gem" data-g="${esc(v)}" title="nach ${esc(v)} filtern">${esc(v)}</button>` : '<span class="sub">–</span>'}</td>`;
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
  if (conf.value) p.set('conf', conf.value); if (qa.value) p.set('qa', qa.value);
  if (q.value.trim()) p.set('q', q.value.trim());
  history.replaceState(null, '', location.pathname + '?' + p.toString());
}
function render() {
  for (const b of tabsEl.children) b.setAttribute('aria-selected', b.dataset.k === tab);
  gemOptions();
  const d = DATA[tab], needle = q.value.trim().toLowerCase(), v = vol.value, g = gem.value, c = conf.value, h = qa.value;
  const ci = d.cols.indexOf('parse_confidence'), gi = d.cols.indexOf('municipality'), hi = d.cols.indexOf('qa_flags');
  const rows = d.rows.filter(r => (!v || r[1] === v)
    && (!g || (g === '–' ? !r[gi] : r[gi] === g))
    && (!c || r[ci] === c)
    && (!h || (h === '-' ? !r[hi] : (' ' + r[hi] + ' ').includes(' ' + h + ' ')))
    && (!onlyflag.checked || flags[tab + '|' + r[0]] || reported[tab + '|' + r[0]])
    && (!needle || r.join(' ').toLowerCase().includes(needle)));
  thead.innerHTML = '<tr><th>Flag</th>' + d.cols.map(cc => `<th>${esc(LABELS[cc] || cc)}</th>`).join('') + '</tr>';
  tbody.innerHTML = rows.slice(0, shown).map(r => {
    const key = tab + '|' + r[0];
    const cls = (flags[key] && flags[key].reason ? 'flagged ' : '') + (reported[key] ? 'reported' : '');
    return `<tr class="${cls}" title="${reported[key] ? esc('gemeldet: ' + reported[key].reason + ' ' + reported[key].note) : ''}">${actCell(tab, r)}${r.map((vv, i) => cell(tab, d.cols[i], vv)).join('')}</tr>`;
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
for (const el of [q, vol, gem, conf, qa, onlyflag]) el.addEventListener(el === q ? 'input' : 'change', () => { shown = PAGE; render(); });
if (P.get('vol')) vol.value = P.get('vol');
if (P.get('conf')) conf.value = P.get('conf');
if (P.get('qa')) qa.value = P.get('qa');
if (P.get('q')) q.value = P.get('q');
if (P.get('gem')) { gemOptions(); const o = document.createElement('option'); o.value = P.get('gem'); gem.appendChild(o); gem.value = P.get('gem'); }
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
            data[key] = {"label": label, "cols": cols, "rows": rows}
            print(f"{label}: {len(rows)} Zeilen")
    n_ein = Counter(r[1] for r in data["einwohner"]["rows"])
    n_ber = Counter(r[1] for r in data["berufe"]["rows"])
    gi = data["berufe"]["cols"].index("municipality")
    no_gem = sum(1 for r in data["berufe"]["rows"] if r[1] == "1910" and not r[gi])
    fmt = lambda n: f"{n:,}".replace(",", "\u202f")
    reported = load_flags()
    html = (TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            .replace("__LABELS__", json.dumps(LABELS, ensure_ascii=False))
            .replace("__QA__", json.dumps(QA, ensure_ascii=False))
            .replace("__REASONS__", json.dumps(REASONS, ensure_ascii=False))
            .replace("__REPORTED__", json.dumps(reported, ensure_ascii=False))
            .replace("__N1900__", fmt(n_ein["1900"])).replace("__N1910__", fmt(n_ein["1910"]))
            .replace("__B1900__", fmt(n_ber["1900"])).replace("__B1910__", fmt(n_ber["1910"]))
            .replace("__NOGEM__", str(no_gem))
            .replace("__REPO__", REPO_URL)
            .replace("__DATE__", date.today().strftime("%d.%m.%Y")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"{len(reported)} gemeldete Flags → {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
