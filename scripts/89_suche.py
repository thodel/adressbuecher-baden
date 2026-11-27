"""89_suche.py — Startseite mit Suche über alle Bände und Eintragsseiten (scripts/site_search.py).

    python scripts/89_suche.py --out _site

Nimmt die Tabellen der Kontrollseite (scripts/90_seite.py: TABS und load(), mit Telefon, anderen Bänden und
Normdaten) und die Strassen- und Gemeindepunkte aus web/geo/ (WGS84, wie 10_geo.py sie schreibt). Die Kontrollseite
selbst liegt unter korrektur/.

Die Zellformate von Baden weichen von site_search.std_links() ab (other_volume «Stufe|Band|entry_id|…», authority
«Stufe|Label|Lebensdaten|HLS|QID|GND|…»); Links und andere Bände baut darum dieses Skript.
Gebiet ist die Gemeinde (1910 der ganze Bezirk, 1900 Baden und Ennetbaden). Strassen ausserhalb der Stadt Baden tragen
die Gemeinde im Namen («Bahnhofstrasse (Wettingen)»), damit gleichnamige Strassen verschiedener Gemeinden nicht
zusammenfallen; ohne Strasse liegt ein Eintrag auf dem Punkt der Gemeinde, ausserhalb Badens auch mit nicht verorteter
Strasse. Seitenbilder gibt es keine (die Scans sind nicht öffentlich, Herkunft ungeklärt).
"""
from __future__ import annotations

import argparse
import csv
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import site_nav  # noqa: E402
import site_search  # noqa: E402

K = importlib.import_module("90_seite")
HOME = "Baden"

CITY = {
    "key": "baden", "name": "Baden", "span": "1900–1910", "lang": "de",
    "title": "Adressbücher Baden 1900 und 1910",
    "lead": "Einwohner und Berufsregister aus den Adressbüchern von Baden 1900 (mit Ennetbaden) und 1910 (Stadt und "
            "Bezirk Baden, 29 Gemeinden), maschinell gelesen und in Felder zerlegt. Gesucht wird über alle Bände.",
    "tagline": "Adressbücher · Einwohner · Berufe · Gemeinden",
    "repo": K.REPO_URL, "center": [47.4733, 8.3080],
    "korr": "korrektur/?tab={part}&vol={vol}&q={id}",
    "nav": [["karte.html", "Karte: Gemeinden und Strassen"]],
    "note": "Quellen: Adressbuch Baden 1900 inkl. Ennetbaden und Adressbuch für Stadt und Bezirk Baden 1910. Gelesen "
            "mit qwen3.8 (Universität Bern), nicht von Hand korrigiert. Im Scan von 1910 fehlen Blätter: die Stadt "
            "Baden ab «Rü…», Bellikon (nur im Berufsregister) und Bergdietikon bis «P».",
    "page_note": "Seitenbilder werden weder gezeigt noch verlinkt: die Scans sind nicht öffentlich und ihre Herkunft ist "
                 "ungeklärt. «Seite» ist die Seite im PDF, nicht die gedruckte Seitenzahl.",
    "parts": {k: label for k, label, *_ in K.TABS},
    "volumes": {"1900": "1900", "1910": "1910"},  # kurz: das Jahr (die Titel stehen in der Kontrollseite)
    "ui": {"area": "Gemeinde", "area_l": "Gemeinde", "filters": "Filter: Band, Teil, Gemeinde, Strasse, Beruf"},
}
CORE = {"entry_id", "volume", "page", "surname", "forename", "alliance_name", "maiden_name", "occupation_raw",
        "street_raw", "building_no", "text", "telefon", "other_volume", "authority", "zeitreise", "street_key",
        "municipality", "title", "heading", "origin_raw", "qa_flags", "phone_flag"}


def geo() -> tuple[dict[tuple[str, str], tuple[float, float]], dict[str, tuple[float, float]]]:
    """(Gemeinde, Strassenschlüssel) → (lat, lon) und Gemeinde → (lat, lon), wie load_geo() in 90_seite.py, aber WGS84."""
    streets, munis = {}, {}
    for name in ("municipalities.csv", "streets.csv", "streets_manual.csv"):
        p = Path("web/geo") / name
        if p.exists():
            for r in csv.DictReader(p.open(encoding="utf-8")):
                if not r["lat"]:
                    continue
                pt = (float(r["lat"]), float(r["lon"]))
                if name == "municipalities.csv":
                    munis[r["municipality"]] = pt
                else:
                    streets[(r["municipality"], r["street_norm"])] = pt
    return streets, munis


def links_of(r: dict) -> tuple[list, list]:
    """Telefon im gemeinsamen Format (std_links); Normdaten «Stufe|Label|Leben|HLS|QID|GND|Feld|Notiz» und andere
    Bände «Stufe|Band|entry_id|Text|Belege» (Reihenfolge von 90_seite.py, nicht die von std_links)."""
    links, _ = site_search.std_links({"telefon": r.get("telefon", "")})
    if r.get("authority"):
        tier, label, life, hls, qid, gnd, field, note = (r["authority"].split("|") + [""] * 8)[:8]
        what = " · ".join(x for x in (life, field.replace("/", " · "), note, f"{tier}, ungeprüft") if x)
        if qid:
            links.append(["wd", label or qid, f"https://www.wikidata.org/wiki/{qid}", f"{what} · Wikidata"])
        if hls:
            links.append(["hls", f"HLS {hls}", f"https://hls-dhs-dss.ch/de/articles/{hls}/", "Historisches Lexikon der Schweiz"])
        if gnd:
            links.append(["ext", f"GND {gnd}", f"https://d-nb.info/gnd/{gnd}", "Gemeinsame Normdatei"])
    related = []
    if r.get("other_volume"):
        tier, ov, oid = (r["other_volume"].split("|") + [""] * 3)[:3]
        if oid:
            related.append([ov, tier, oid])
    return links, related


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    streets, munis = geo()
    labels = {**site_nav.LABELS["de"], **K.LABELS, "street_raw": "Strasse (gedruckt)", "page": "Seite im PDF"}
    recs = []
    for key, _label, files, cols in K.TABS:
        cols = list(cols)
        for row in K.load(files, cols):  # hängt weitere CSV-Spalten an cols an
            r = dict(zip(cols, row))
            muni, sk = r.get("municipality", ""), r.get("street_key", "")
            g = streets.get((muni, sk)) if sk else None
            street = sk or r.get("street_raw", "")
            if street and muni and muni != HOME:
                street = f"{street} ({muni})"
            if not street or muni != HOME:
                g = g or munis.get(muni)  # Karte: der Punkt der Gemeinde
            links, related = links_of(r)
            fields = [(c, r.get(c, "")) for c in cols if c not in CORE and r.get(c, "")]
            if r.get("street_raw") and r["street_raw"] != sk:
                fields.insert(0, ("street_raw", r["street_raw"]))
            if r.get("origin_raw"):  # «Ort/Zusatz»: im Berufsregister meist der Ort des Geschäfts, keine Herkunft
                fields.insert(0, ("origin_raw", r["origin_raw"]))
            if r.get("qa_flags"):
                fields.append(("qa_flags", "; ".join(K.QA.get(x, x) for x in r["qa_flags"].split())))
            if r.get("phone_flag") == "1":
                fields.append(("phone_flag", "☏ im Adressbuch"))
            recs.append({
                "id": r["entry_id"], "vol": r["volume"], "year": int(r["volume"]), "part": key,
                "name": r.get("surname", ""), "forename": r.get("forename", ""),
                "alliance": r.get("alliance_name", ""), "maiden": r.get("maiden_name", ""),
                "occupation": r.get("occupation_raw", ""), "street": street, "no": r.get("building_no", ""),
                "area": muni, "place": muni,  # ohne Strasse: der Ort für die Karte
                "origin": "", "title": r.get("title", ""), "heading": r.get("heading", ""),
                "text": r.get("text", ""), "page": r.get("page", ""), "page_url": "",
                "lat": g[0] if g else None, "lon": g[1] if g else None,
                "fields": fields, "links": links, "related": related,
            })
    site_search.build(args.out, city=CITY, records=recs, labels=labels)


if __name__ == "__main__":
    main()
