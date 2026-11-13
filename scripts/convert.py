"""Lesungen von qwen3.8 (data/qwen/<Jahr>/entries.csv) → Eintragsdateien im Schema von adressbuecher-aarau.

    python scripts/convert.py

Schreibt data/csv/04_entries.csv (Einwohner), 04_berufe.csv (Berufsregister), 03_sections.csv
(welche Seiten in welchen Teil und welche Gemeinde gehen) und 10_authority_links.csv (leer:
Normdaten verknüpft «Vernetzte Schweiz» über die Einheiten, nicht dieses Repo).

Nicht übernommen: Inserate, Vorspann, Behörden-, Vereins- und Reglementsseiten.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QWEN = ROOT / "data" / "qwen"
CSV = ROOT / "data" / "csv"

FIELDS = [
    "entry_id", "volume", "page", "section", "line_from", "line_to", "entry_type", "citizen_flag",
    "dash_prefix", "surname", "surname_inherited", "alliance_name", "maiden_name", "forename", "title",
    "civil_status", "relation", "occupation_raw", "origin_raw", "origin_canton", "address_seq",
    "address_role", "street_raw", "building_no", "phone_flag", "heading", "parse_method",
    "parse_confidence", "residual", "text", "municipality", "qa_flags",
]
AUTH_FIELDS = [
    "entry_id", "kind", "volume", "surname", "forename", "occupation", "origin", "qid", "label", "birth",
    "death", "hls_id", "gnd", "wd_description", "wd_occupations", "evidence", "score", "n_candidates",
    "tier", "hls_origins", "hls_head", "hls_check",
]
METHOD = "qwen3.8-27b, Bild 2x"

# ── Aufbau der Bände ─────────────────────────────────────────────────────
# Seite = Seite im PDF (= Bildnummer der Lesung). Geprüft an den Seitenbildern, 13.11.2026.
#
# 1900: Einwohner der Stadt S. 19–44, Berufsregister der Stadt S. 45–56, Ennetbaden S. 57–59
# (nach Berufen geordnet, mit «Diverse» als Einwohnerliste).
# 1910: Einwohner der Stadt S. 33–64, dann die Gemeinden des Bezirks bis S. 116, Berufsregister
# des ganzen Bezirks S. 123–162 (Ort steht im Eintrag). Im Scan fehlen Blätter zwischen S. 64 und
# 65 (Stadt Baden ab «Rü…», Bellikon, Bergdietikon bis «P»), und S. 69/70 stehen vor S. 71–74.
SECTIONS = {
    "1900": [("einwohner", 19, 44), ("berufe", 45, 59)],
    "1910": [("einwohner", 33, 116), ("berufe", 123, 162)],
}
# Gemeinde je Abschnitt: ab (Seite, Laufnummer) gilt die Gemeinde bis zum nächsten Wechsel.
# Die Wechsel stehen im Band als Kopf «… m über Meer. — … Einwohner».
MUNI_STARTS = {
    "1900": [((19, 1), "Baden"), ((57, 1), "Ennetbaden")],
    "1910": [
        ((33, 1), "Baden"), ((65, 1), "Bergdietikon"), ((65, 30), "Birmenstorf (AG)"),
        ((67, 87), "Dättwil"), ((69, 1), "Ennetbaden"), ((70, 1), "Fislisbach"), ((71, 1), "Ennetbaden"),
        ((75, 1), "Fislisbach"), ((75, 72), "Freienwil"), ((76, 32), "Gebenstorf"), ((79, 33), "Killwangen"),
        ((80, 8), "Künten"), ((81, 33), "Mägenwil"), ((82, 45), "Mellingen"), ((85, 71), "Neuenhof"),
        ((87, 20), "Niederrohrdorf"), ((88, 69), "Oberehrendingen"), ((89, 75), "Oberrohrdorf"),
        ((90, 76), "Obersiggenthal"), ((95, 13), "Remetschwil"), ((96, 41), "Spreitenbach"),
        ((98, 41), "Stetten (AG)"), ((99, 52), "Turgi"), ((102, 36), "Unterehrendingen"),
        ((103, 1), "Untersiggenthal"), ((105, 37), "Wettingen"), ((111, 73), "Wohlenschwil"),
        ((113, 21), "Würenlingen"), ((114, 97), "Würenlos"),
    ],
}
# Berufsregister 1910: Ort aus dem Ende des Eintrags. Gemeinden und ihre Ortsteile.
MUNIS_1910 = [m for _, m in MUNI_STARTS["1910"]] + ["Bellikon"]
PLACE_ALIASES = {
    "birmenstorf": "Birmenstorf (AG)", "stetten": "Stetten (AG)",
    "wettingendorf": "Wettingen", "wettingenkloster": "Wettingen", "langenstein": "Wettingen",
    "langensteinwettingen": "Wettingen", "klosterwettingen": "Wettingen",
    "nussbaumen": "Obersiggenthal", "unternussbaumen": "Obersiggenthal", "obernussbaumen": "Obersiggenthal",
    "kirchdorf": "Obersiggenthal", "rieden": "Obersiggenthal", "obersiggental": "Obersiggenthal",
    "untersiggental": "Untersiggenthal", "ennetturgi": "Untersiggenthal", "ennetlurgi": "Untersiggenthal",
    "vogelsang": "Gebenstorf", "reuss": "Gebenstorf", "vogelsangturgi": "Gebenstorf",
    "rutihof": "Dättwil", "munzlishausen": "Dättwil",
    "bellikonhausen": "Bellikon", "hausen": "Bellikon",
    "baltenschwil": "Bergdietikon", "kindhausen": "Bergdietikon",
    "staretschwil": "Oberrohrdorf", "busslingen": "Remetschwil", "bublikon": "Wohlenschwil",
    "sulz": "Künten", "wilturgi": "Turgi", "turgivogelsang": "Turgi",
    # Schreibungen der Lesung
    "bueblikon": "Wohlenschwil", "fislibach": "Fislisbach", "berg": "Wettingen",
    "untersiggingen": "Untersiggenthal", "obersiggingen": "Untersiggenthal", "siggingen": "Untersiggenthal",
    "datwil": "Dättwil", "thurgi": "Turgi", "gebeinstorf": "Gebenstorf",
}
# Zwischenköpfe, die keine Einträge tragen (Ennetbaden 1900, Gemeindeköpfe 1910)
SKIP_HEADINGS = re.compile(r"^(Behörden|Lehrerschaft|Vereine)", re.I)
NOT_ENTRY = re.compile(r"über Meer|ü\. ?M\.|\d+ Einwohner|^mit [A-ZÄÖÜ]|^Auch die kleinen Bäder")
FIRM = re.compile(r"&|\bCie\b|\bGebr(?:\.|üder)|A\.-?G\.|\bAG\b|Aktiengesellschaft|Genossenschaft|"
                  r"Verein\b|Gesellschaft|Fabrik\b|Kasse\b|Bank\b|Werke?\b|Erben\b", re.I)
WIDOW = re.compile(r"\bWwe\.?|\bWitwe\b", re.I)
DASH = re.compile(r"^\s*[—–-]")


def key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s)


PLACES = {key(m.split(" (")[0]): m for m in MUNIS_1910} | PLACE_ALIASES


def place_of(text: str) -> str:
    """Gemeinde aus dem Ende eines Eintrags im Berufsregister 1910 («…, Haselstr. 27, Baden ☎»)."""
    for part in reversed(text.split(",")):
        p = re.sub(r"☎|\bH\.|\bR\.|\d+[a-z]?\b|\(.*?\)", " ", part)
        p = re.sub(r"\s*[—–]\s*", "-", re.sub(r"(\w)-\s+(\w)", r"\1-\2", p))
        k = key(p)
        if k in PLACES:
            return PLACES[k]
        # «Bahnhofstrasse in Wettingen», «Vogelsang-Gebenstorf», «Staretschwil-Ober-Rohrdorf»
        words = [w for w in re.split(r"[\s/]+", p) if key(w)]
        for w in reversed(words):
            pieces = w.split("-")
            # längste Endung zuerst («Ober-Rohrdorf» vor «Rohrdorf»), dann der Anfang («Stetten-Oberdorf»)
            tries = ["".join(pieces[i:]) for i in range(len(pieces))] + \
                    ["".join(pieces[:j]) for j in range(len(pieces) - 1, 0, -1)]
            for t in tries:
                k = key(t)
                if len(k) > 3 and k in PLACES:
                    return PLACES[k]
    return ""


def clean_street(street: str, number: str) -> str:
    """Strasse ohne Ortsnamen und ohne doppelte Hausnummer: «Bruggerstrasse 25, Baden H.» → «Bruggerstrasse».

    Ein Ortsname allein ist keine Strasse («Brunner, Wilhelm, Würenlos»)."""
    parts = []
    for part in street.split(","):
        part = re.sub(r"\s*(?:\bH\.|☎.*)$", "", part).strip()
        if not part or key(part) in PLACES:
            continue
        if number:
            part = re.sub(rf"\s+{re.escape(number)}\s*$", "", part)
        parts.append(part)
    return ", ".join(parts)


def muni_at(volume: str, page: int, seq: int) -> str:
    cur = ""
    for (p, s), m in MUNI_STARTS[volume]:
        if (page, seq) >= (p, s):
            cur = m
    return cur


def section_of(volume: str, page: int) -> str:
    for name, a, b in SECTIONS[volume]:
        if a <= page <= b:
            return name
    return ""


def own_surname(r: dict) -> str:
    """Familienname; ein vom Vorgänger geerbter Name, der zum Text nicht passt, wird ersetzt."""
    sn = r["surname"].strip()
    if r["dash_prefix"] == "1" and not DASH.match(r["text"]) and sn and sn not in r["text"]:
        return r["text"].split(",")[0].strip(" .")
    return sn


def convert(volume: str) -> tuple[list[dict], Counter]:
    rows = list(csv.DictReader(open(QWEN / volume / "entries.csv", encoding="utf-8")))
    pages = Counter(int(r["page"]) for r in rows)
    out, stats = [], Counter()
    for r in rows:
        page, seq = int(r["page"]), int(r["seq"])
        sec = section_of(volume, page)
        if not sec:
            stats["ausserhalb der Verzeichnisse"] += 1
            continue
        if volume == "1910" and sec == "berufe" and pages[page] < 10:
            stats["Inseratseite im Berufsregister"] += 1
            continue
        if NOT_ENTRY.search(r["text"]) or SKIP_HEADINGS.match(r["heading"]):
            stats["Kopf oder Behörde"] += 1
            continue
        surname = own_surname(r)
        if not surname:
            stats["ohne Familienname"] += 1
            continue
        if volume == "1910" and sec == "berufe":
            muni = place_of(r["text"])
        else:
            muni = muni_at(volume, page, seq)
        street, number = clean_street(r["street"], r["building_no"]), r["building_no"].strip()
        m = re.match(r"^(.*\D)\s+(\d+\s?[a-z]?)$", street)
        if m and not number:  # «Bruggerstrasse 25» ohne Nummernfeld
            street, number = m.group(1).strip(), m.group(2).replace(" ", "")
        flags = [f for f in r["qa_flags"].split(";") if f]
        firm = bool(FIRM.search(f"{surname} {r['forename']} {r['text'][:60]}")) and not WIDOW.search(r["text"])
        out.append({
            "entry_id": f"{volume}-{sec}-{page:03d}-{seq:03d}", "volume": volume, "page": page,
            "section": sec, "line_from": seq, "line_to": seq,
            "entry_type": "firma" if firm else "person", "citizen_flag": "",
            "dash_prefix": r["dash_prefix"], "surname": surname,
            "surname_inherited": "1" if r["dash_prefix"] == "1" and DASH.match(r["text"]) else "",
            "alliance_name": r["alliance_name"], "maiden_name": "", "forename": r["forename"].strip(" ."),
            "title": r["title"], "civil_status": r["civil_status"], "relation": "",
            "occupation_raw": r["occupation"], "origin_raw": r["origin"], "origin_canton": "",
            "address_seq": "1", "address_role": "", "street_raw": street, "building_no": number,
            "phone_flag": "1" if r["phone"].strip() else "", "heading": r["heading"],
            "parse_method": METHOD,
            "parse_confidence": "medium" if {"street_rare", "hyphen", "unreadable", "surname_split"} & set(flags)
            else "high",
            "residual": "", "text": r["text"], "municipality": muni, "qa_flags": ";".join(flags),
        })
        stats[f"{sec}" + ("" if muni else " ohne Gemeinde")] += 1
    return out, stats


def main() -> None:
    entries, berufe, sections = [], [], []
    for volume in ("1900", "1910"):
        rows, stats = convert(volume)
        entries += [r for r in rows if r["section"] == "einwohner"]
        berufe += [r for r in rows if r["section"] == "berufe"]
        for name, a, b in SECTIONS[volume]:
            sections.append({"volume": volume, "section": name, "page_from": a, "page_to": b,
                             "municipality": "", "from_seq": ""})
        for (p, s), m in MUNI_STARTS[volume]:
            sections.append({"volume": volume, "section": "gemeinde", "page_from": p, "page_to": "",
                             "municipality": m, "from_seq": s})
        print(volume, dict(sorted(stats.items())))
        print("  Gemeinden:", dict(Counter(r["municipality"] for r in rows).most_common()))
    CSV.mkdir(parents=True, exist_ok=True)
    for name, rows, fields in (("04_entries.csv", entries, FIELDS), ("04_berufe.csv", berufe, FIELDS),
                               ("03_sections.csv", sections,
                                ["volume", "section", "page_from", "page_to", "municipality", "from_seq"]),
                               ("10_authority_links.csv", [], AUTH_FIELDS)):
        with open(CSV / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
