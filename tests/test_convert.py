"""Ort und Gemeinde der Einträge (scripts/convert.py)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from convert import clean_street, muni_at, own_surname, place_of  # noqa: E402


class PlaceOf(unittest.TestCase):
    def test_end_of_entry(self):
        self.assertEqual(place_of("Egolf, J. H., Haselstr. 27, Baden ☎"), "Baden")
        self.assertEqual(place_of("Brunner, Wilhelm, Würenlos"), "Würenlos")
        self.assertEqual(place_of("Zweifel & Cie., Baumwollspinnerei, Wettingen H. ☎"), "Wettingen")

    def test_compounds_and_hamlets(self):
        self.assertEqual(place_of("Baumann, Samuel, Vogelsang-Gebenstorf H."), "Gebenstorf")
        self.assertEqual(place_of("— S., Staretschwil-Ober-Rohrdorf"), "Oberrohrdorf")
        self.assertEqual(place_of("Fischer, Joseph, Stetten-Oberdorf"), "Stetten (AG)")
        self.assertEqual(place_of("Brunner, G., Langenstein-Wettingen"), "Wettingen")

    def test_ennetbaden_is_not_baden(self):
        self.assertEqual(place_of("Wegmann & Cie., Kasinostrasse, Ennetbaden H. ☎ 65"), "Ennetbaden")

    def test_unknown(self):
        self.assertEqual(place_of("Meier, Robert, Badstrasse 14 ☎ 338"), "")


class MuniAt(unittest.TestCase):
    def test_sections_1910(self):
        self.assertEqual(muni_at("1910", 64, 61), "Baden")
        self.assertEqual(muni_at("1910", 65, 29), "Bergdietikon")
        self.assertEqual(muni_at("1910", 65, 30), "Birmenstorf (AG)")
        self.assertEqual(muni_at("1910", 69, 5), "Ennetbaden")  # Blatt im Scan vor Fislisbach
        self.assertEqual(muni_at("1910", 75, 10), "Fislisbach")
        self.assertEqual(muni_at("1910", 116, 80), "Würenlos")

    def test_1900(self):
        self.assertEqual(muni_at("1900", 44, 1), "Baden")
        self.assertEqual(muni_at("1900", 58, 4), "Ennetbaden")


class Street(unittest.TestCase):
    def test_place_and_number_are_dropped(self):
        self.assertEqual(clean_street("Bruggerstrasse 25, Baden H.", "25"), "Bruggerstrasse")
        self.assertEqual(clean_street("Römerstrasse, Baden", "9"), "Römerstrasse")
        self.assertEqual(clean_street("Würenlos", ""), "")
        self.assertEqual(clean_street("Hasel, Bruggerstraße", "802"), "Hasel, Bruggerstraße")


class Surname(unittest.TestCase):
    def test_wrong_inheritance_is_replaced(self):
        r = {"surname": "Hegner", "dash_prefix": "1", "text": "Grüter, Alfred."}
        self.assertEqual(own_surname(r), "Grüter")
        r = {"surname": "Ackermann", "dash_prefix": "1", "text": "-Weber, Aug., Obere Halde 24"}
        self.assertEqual(own_surname(r), "Ackermann")


if __name__ == "__main__":
    unittest.main()
