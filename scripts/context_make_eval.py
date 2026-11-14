#!/usr/bin/env python3
"""Write results/samples/historic_eval.jsonl: hand-labelled questions over historic drawings (habs, finna,
europeana, wikimedia). Drawings were drawn at random (seed 2026, scripts/context_build candidates); 3 non-drawings
(blank sheet, book cover, unreadable blueprint) were skipped.

Each row: path, question, accept (list of alternatives; an alternative = list of lowercase substrings that must ALL
appear in the normalized prediction), qtype, origin ("record" = checkable in the archive record, "image" = judged by
looking at the drawing, "record+reasoning" = needs translation / inference from the record), needs_human_check
(true for image-judged answers), split (dev/test by drawing hash). The context "bucket" (answer verbatim in the
context or not) is computed at evaluation time from the actual context block.
"""
import hashlib, json, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
A = lambda *alts: [[w.lower() for w in (a if isinstance(a, (list, tuple)) else [a])] for a in alts]

Q = [
    # ---------------- HABS (Library of Congress) ----------------
    ("habs/co0298_sheet_00001.jpg", "Which farm is documented on this sheet?", A("felderman"), "name", "record"),
    ("habs/co0298_sheet_00001.jpg", "In which US state is this farm located? Give the full state name.", A("colorado"), "place", "record"),
    ("habs/co0298_sheet_00001.jpg", "What kind of drawing is the main drawing on this sheet: floor plan, section, elevation or site plan?", A("site plan", "site"), "drawing_type", "image"),
    ("habs/ma0578_sheet_00002.jpg", "Which compass direction does the elevation drawn on this sheet face?", A("north"), "other", "image"),
    ("habs/ma0578_sheet_00002.jpg", "In which decade was this mill originally built?", A("1820"), "year", "record+reasoning"),
    ("habs/ma0578_sheet_00002.jpg", "What is the name of the mill shown?", A(["crown", "eagle"]), "name", "record"),
    ("habs/de0044_sheet_00001.jpg", "What type of structure is shown on this sheet?", A("lighthouse", "range light", "light tower", "beacon"), "function", "record+reasoning"),
    ("habs/de0044_sheet_00001.jpg", "What metal is this tower built from?", A("wrought iron"), "other", "record"),
    ("habs/de0044_sheet_00001.jpg", "In which year was this structure first built?", A("1876"), "year", "record"),
    ("habs/de0323_sheet_00002.jpg", "What was this small building originally used for?", A("smoke"), "function", "record"),
    ("habs/de0323_sheet_00002.jpg", "Which two levels are shown in plan on this sheet?", A(["first", "cellar"], ["ground", "cellar"], ["first", "basement"]), "floor", "image"),
    ("habs/de0323_sheet_00002.jpg", "In what year was this building constructed?", A("1845"), "year", "record"),
    ("habs/nj0479_sheet_00016.jpg", "Which architectural element is detailed on this sheet?", A("mantel", "fireplace", "chimney piece", "chimneypiece"), "other", "image"),
    ("habs/nj0479_sheet_00016.jpg", "In which town is this house located?", A("livingston"), "place", "record"),
    ("habs/dc0621_sheet_00002.jpg", "In which city is this bridge?", A("washington"), "place", "record"),
    ("habs/dc0621_sheet_00002.jpg", "In which years was this bridge initially constructed?", A("1908", "1909"), "year", "record"),
    ("habs/dc0621_sheet_00002.jpg", "Which basin does this bridge's gate structure control?", A("tidal basin", "tidal reservoir"), "name", "record"),
    ("habs/hi0700_sheet_00005.jpg", "What is the name of the vessel shown in these deck plans?", A("missouri"), "name", "record"),
    ("habs/hi0700_sheet_00005.jpg", "What type of ship is this?", A("battleship"), "function", "record"),
    ("habs/ne0022_sheet_00004.jpg", "What building is shown?", A(["episcopal", "mission"], ["mission", "church"]), "name", "record"),
    ("habs/ne0022_sheet_00004.jpg", "Which two elevations are drawn on this sheet?", A(["north", "east"]), "other", "image"),
    ("habs/ne0022_sheet_00004.jpg", "In what year was this building originally built?", A("1884"), "year", "record"),
    ("habs/wa0660_sheet_00006.jpg", "Which elevation of the building is drawn here?", A("northeast", "north east", "north-east"), "other", "image"),
    ("habs/wa0660_sheet_00006.jpg", "In which US state is this building? Give the full state name.", A("washington"), "place", "record"),
    ("habs/wa0660_sheet_00006.jpg", "In what year was this building constructed?", A("1927"), "year", "record"),
    ("habs/nj0168_sheet_00002.jpg", "What kinds of drawings are on this sheet?", A(["section", "elevation"]), "drawing_type", "image"),
    ("habs/nj0168_sheet_00002.jpg", "What did the company that owned this shop manufacture?", A("locomotive"), "function", "record+reasoning"),
    ("habs/nj0168_sheet_00002.jpg", "In which city is this building?", A("paterson"), "place", "record"),
    ("habs/nc0046_sheet_00002.jpg", "What type of building is this?", A("jail", "gaol", "prison"), "function", "record"),
    ("habs/nc0046_sheet_00002.jpg", "Which two plans are shown on this sheet?", A(["ceiling", "first floor"], ["ceiling", "floor plan"]), "drawing_type", "image"),
    ("habs/nc0046_sheet_00002.jpg", "In which US state is this building?", A("north carolina"), "place", "record"),
    ("habs/or0016_sheet_00008.jpg", "Apart from the porch section, which building elements are detailed on this sheet?", A("door"), "other", "image"),
    ("habs/or0016_sheet_00008.jpg", "In which US state is this house?", A("oregon"), "place", "record"),
    ("habs/mt0046_sheet_00004.jpg", "How many elevations are drawn on this sheet?", A("4", "four"), "count", "image"),
    ("habs/mt0046_sheet_00004.jpg", "What construction method are these buildings?", A("log"), "other", "image"),
    ("habs/mt0046_sheet_00004.jpg", "In which US state is this ranch?", A("montana"), "place", "record"),
    # ---------------- Finna (Helsinki City Archives / Architecture & Design Museum) ----------------
    ("finna/hka.139878141203200_167699166535000.jpg", "What kind of object is drawn here? Answer in English.", A("coupling", "pipe joint", "pipe fitting", "sleeve", "muff", "flange", "pipe connector", "joint"), "function", "record+reasoning"),
    ("finna/hka.139878141203200_167699166535000.jpg", "What is the nominal size of this part in millimetres?", A("305"), "other", "record"),
    ("finna/hka.139878141203200_167699166535000.jpg", "In what year was this drawing made?", A("1909"), "year", "record"),
    ("finna/hka.139879309684900_166937160999000.jpg", "What is the street address of the property in this drawing?", A("kaasutehtaankatu 3", "gasverksgatan 3", "kaasutehtaankatu"), "place", "record"),
    ("finna/hka.139879309684900_166937160999000.jpg", "In which language is the handwritten text on this drawing?", A("swedish"), "language", "image"),
    ("finna/hka.139879309684900_166937160999000.jpg", "In what year was this drawing made?", A("1882"), "year", "record"),
    ("finna/hka.139878174949000_145250875435500.jpg", "What type of facility is this drawing for? Answer in English.", A("fire"), "function", "record+reasoning"),
    ("finna/hka.139878174949000_145250875435500.jpg", "In what year was this drawing made?", A("1926"), "year", "record"),
    ("finna/hka.139879309684900_154961546225500.jpg", "What kind of drawing is this: floor plan, section, elevation or site plan?", A("site plan", "site", "location plan"), "drawing_type", "record"),
    ("finna/hka.139879309684900_154961546225500.jpg", "In which city is this property?", A("helsinki", "helsingfors"), "place", "record"),
    ("finna/hka.139879309684900_161226020881500.jpg", "What buildings are drawn on this sheet? Answer in English.", A("cafe", "café", "coffee"), "function", "record+reasoning"),
    ("finna/hka.139879309684900_161226020881500.jpg", "In what year was this drawing made?", A("1924"), "year", "record"),
    ("finna/hka.139879309684900_167144338158600.jpg", "What kind of drawing is this: floor plan, section, elevation or site plan?", A("floor plan", "ground plan"), "drawing_type", "record"),
    ("finna/hka.139879309684900_167144338158600.jpg", "What is the Finnish name of the island district this property is on?", A("siltasaari"), "place", "record"),
    ("finna/hka.139879309684900_166878548098200.jpg", "What is the present-day Finnish name of the street on which this property stands?", A("mannerheimintie"), "place", "record+reasoning"),
    ("finna/hka.139879309684900_166878548098200.jpg", "In which city is this property?", A("helsinki", "helsingfors"), "place", "record"),
    ("finna/hka.139879309684900_166878548098200.jpg", "In what year was this drawing made?", A("1932"), "year", "record"),
    ("finna/hka.139880068219800_169323282696500.jpg", "What is the street address of this building?", A("kulmavuorenkatu 8", "kulmavuorenkatu"), "place", "record"),
    ("finna/hka.139880068219800_169323282696500.jpg", "In what year was this drawing made?", A("1913"), "year", "record"),
    ("finna/hka.139879309684900_154961506634300.jpg", "What kind of drawing is this: floor plan, section, elevation or site plan?", A("elevation", "facade"), "drawing_type", "record"),
    ("finna/hka.139879309684900_154961506634300.jpg", "What type of building is being extended in this drawing?", A("villa"), "function", "image"),
    ("finna/mfa.de93ed0e-f4f8-430e-9d5b-6133fe2358ed.jpg", "What structure is depicted?", A("water tower"), "function", "record"),
    ("finna/mfa.de93ed0e-f4f8-430e-9d5b-6133fe2358ed.jpg", "Who was the architect?", A("lumme"), "author", "record"),
    ("finna/mfa.de93ed0e-f4f8-430e-9d5b-6133fe2358ed.jpg", "In which city is this structure?", A("helsinki"), "place", "record"),
    ("finna/mfa.e16a8cc1-e971-40d6-b0e4-22d9d2d78800.jpg", "Which villa's garden is planned in this drawing?", A("kultaranta"), "name", "record"),
    ("finna/mfa.e16a8cc1-e971-40d6-b0e4-22d9d2d78800.jpg", "Who designed this garden plan?", A("olsson"), "author", "record"),
    ("finna/mfa.e16a8cc1-e971-40d6-b0e4-22d9d2d78800.jpg", "This villa is today the official summer residence of which office-holder?", A("president"), "other", "record+reasoning"),
    ("finna/mfa.2e7597a2-1124-461d-a65f-32854d69d5e3.jpg", "At what scale is this drawing?", A("1:50", "1/50"), "scale", "record"),
    ("finna/mfa.2e7597a2-1124-461d-a65f-32854d69d5e3.jpg", "In which Finnish town is this site?", A("kauniainen", "grankulla"), "place", "record"),
    ("finna/mfa.2e7597a2-1124-461d-a65f-32854d69d5e3.jpg", "In what year was this drawing made?", A("1943"), "year", "record"),
    ("finna/mfa.ca9d34a4-0fd7-4e99-9cab-a1316e9ba24e.jpg", "Which architecture firm designed this house?", A(["gesellius", "saarinen"]), "author", "record"),
    ("finna/mfa.ca9d34a4-0fd7-4e99-9cab-a1316e9ba24e.jpg", "Which level of the house does this plan show?", A("basement", "cellar"), "floor", "record"),
    ("finna/mfa.ca9d34a4-0fd7-4e99-9cab-a1316e9ba24e.jpg", "In which country is this house?", A("germany"), "place", "record"),
    ("finna/mfa.4a7b0a5f-3429-43b9-9013-687afce16773.jpg", "Which architecture firm made this plan?", A(["gesellius", "lindgren", "saarinen"]), "author", "record"),
    ("finna/mfa.4a7b0a5f-3429-43b9-9013-687afce16773.jpg", "In which Helsinki district is this building?", A("katajanokka", "skatudden"), "place", "record"),
    ("finna/mfa.f4d8c7a8-9173-46f7-9fa8-161ec5032db9.jpg", "What type of building is this? Answer in English.", A("day care", "daycare", "kindergarten", "nursery", "children", "child care", "childcare"), "function", "record"),
    ("finna/mfa.f4d8c7a8-9173-46f7-9fa8-161ec5032db9.jpg", "In which city is this building?", A("turku", "åbo"), "place", "record"),
    ("finna/mfa.f4d8c7a8-9173-46f7-9fa8-161ec5032db9.jpg", "What kind of drawing is this: floor plan, section, elevation or site plan?", A("elevation", "facade"), "drawing_type", "record"),
    ("finna/mfa.499c47d2-307d-4f28-b270-56efb250920d.jpg", "In what year was this garden plan signed?", A("1915"), "year", "record"),
    ("finna/mfa.499c47d2-307d-4f28-b270-56efb250920d.jpg", "What kind of garden is planned here?", A("terrace"), "function", "record"),
    # ---------------- Europeana ----------------
    ("europeana/283_4796_DS.jpg", "What kind of structure is drawn?", A("triumphal arch", "triumphal arc", "arch"), "function", "record"),
    ("europeana/283_4796_DS.jpg", "In which century was this drawing made?", A("18th", "xviii", "eighteenth", "1700s"), "year", "record+reasoning"),
    ("europeana/91676_arkm_object_ARKM1970_18_270_002.jpg", "Which city does this plan show?", A("berlin"), "place", "record"),
    ("europeana/91676_arkm_object_ARKM1970_18_270_002.jpg", "Which district of that city is shown?", A("charlottenburg"), "place", "record"),
    ("europeana/08535_item_227MGO6YEPEBMMWO6AGJPHLSAT4AK4QU.jpg", "Which theatre is shown in these drawings?", A("grillo", ["stadttheater", "essen"], ["city theatre", "essen"], ["municipal theatre", "essen"]), "name", "record"),
    ("europeana/08535_item_227MGO6YEPEBMMWO6AGJPHLSAT4AK4QU.jpg", "Which architect designed this theatre?", A("seeling"), "author", "record"),
    ("europeana/08535_item_227MGO6YEPEBMMWO6AGJPHLSAT4AK4QU.jpg", "What two kinds of drawing are on this sheet?", A(["plan", "section"]), "drawing_type", "record"),
    ("europeana/126_https___www_searchculture_gr_aggregator_edm_travelogues_000116_48056.jpg", "Which ancient monument is depicted? Answer in English.", A("lysicrates", "lysikrates", "lantern of diogenes"), "name", "record+reasoning"),
    ("europeana/126_https___www_searchculture_gr_aggregator_edm_travelogues_000116_48056.jpg", "In which city is this monument?", A("athens"), "place", "record"),
    ("europeana/285_gam13330.jpg", "Which building is this drawing for?", A("mole antonelliana", "antonelliana"), "name", "record"),
    ("europeana/285_gam13330.jpg", "Which part of the building is drawn?", A("stair"), "other", "record"),
    ("europeana/285_gam13330.jpg", "Who was the architect?", A("antonelli"), "author", "record"),
    ("europeana/10501_bib_rnod_221767.jpg", "What kind of structure is designed in this drawing? Answer in English.", A("bridge"), "function", "record+reasoning"),
    ("europeana/10501_bib_rnod_221767.jpg", "In which country are the places named in this drawing?", A("portugal"), "place", "record+reasoning"),
    ("europeana/401_item_Q2H7K452JZWXZWZC3NTRKTES4IZAFQMX.jpg", "What kind of building is this the plan of?", A("school"), "function", "record"),
    ("europeana/401_item_Q2H7K452JZWXZWZC3NTRKTES4IZAFQMX.jpg", "Which floor does this plan show?", A("ground", "first floor"), "floor", "record"),
    ("europeana/401_item_Q2H7K452JZWXZWZC3NTRKTES4IZAFQMX.jpg", "In which language is the room schedule written?", A("estonian"), "language", "image"),
    ("europeana/332_BVE0831516.jpg", "Which monument is shown?", A("trajan", "traiana"), "name", "record"),
    ("europeana/332_BVE0831516.jpg", "In which city does this monument stand?", A("rome", "roma"), "place", "record+reasoning"),
    ("europeana/91659_sk_photo_SKARIT10501_005.jpg", "What is the name of the building in this measured drawing?", A("apoteket", "petissan"), "name", "record"),
    ("europeana/91659_sk_photo_SKARIT10501_005.jpg", "In which country is this building?", A("sweden"), "place", "record"),
    ("europeana/463_item_S7E2D7PFDMFW26A53GHVV5IFOSQRZHWV.jpg", "Which building is shown?", A("zeughaus", "albertinum", "arsenal", "armoury", "armory"), "name", "record"),
    ("europeana/463_item_S7E2D7PFDMFW26A53GHVV5IFOSQRZHWV.jpg", "In which city is this building?", A("dresden"), "place", "record"),
    ("europeana/463_item_S7E2D7PFDMFW26A53GHVV5IFOSQRZHWV.jpg", "In which century was this drawing made?", A("18th", "xviii", "eighteenth", "1700s"), "year", "record+reasoning"),
    ("europeana/10501_bib_rnod_222012.jpg", "How many floors does the building in this study have?", A("3", "three"), "count", "record+reasoning"),
    ("europeana/10501_bib_rnod_221768.jpg", "Which castle is shown? Answer with its location.", A("castro laboreiro"), "name", "record"),
    ("europeana/10501_bib_rnod_221768.jpg", "In which century was this drawing made?", A("17th", "xvii", "seventeenth", "1600s"), "year", "record+reasoning"),
    ("europeana/150__REB01_000190990.jpg", "What type of building is shown?", A("synagogue"), "function", "record"),
    ("europeana/150__REB01_000190990.jpg", "What kind of drawing is this: floor plan, section, elevation or site plan?", A("section"), "drawing_type", "record"),
    # ---------------- Wikimedia Commons ----------------
    ("wikimedia/116817466.jpg", "Which château does this outbuilding belong to?", A("ettevaux"), "name", "record"),
    ("wikimedia/116817466.jpg", "In what year was this design made?", A("1911"), "year", "record"),
    ("wikimedia/116817466.jpg", "What was this building used for? Answer in English.", A("stable", "carriage", "coach house", "horse"), "function", "record+reasoning"),
    ("wikimedia/9975897.jpg", "In which present-day country are these ruins?", A("turkey", "türkiye", "turkiye"), "place", "record"),
    ("wikimedia/9975897.jpg", "What type of complex is shown?", A("bath", "therm"), "function", "record"),
    ("wikimedia/9975897.jpg", "What is the room labelled I called?", A("caldarium"), "other", "image"),
    ("wikimedia/45733769.jpg", "Which architect drew this?", A("lequeu", "le queu"), "author", "record"),
    ("wikimedia/45733769.jpg", "Which city's gate is this?", A("rouen", "roüen"), "place", "record"),
    ("wikimedia/66072221.jpg", "Which church is this the plan of?", A(["peter", "basilica"], "st. peter", "saint peter", "st peter", "san pietro"), "name", "record"),
    ("wikimedia/66072221.jpg", "In which city is this church?", A("rome", "vatican"), "place", "record+reasoning"),
    ("wikimedia/86583721.jpg", "Which temple is shown?", A("olympieion", "olympian zeus", "zeus"), "name", "record"),
    ("wikimedia/86583721.jpg", "Whose architecture history book is this plan from?", A("fletcher"), "author", "record"),
    ("wikimedia/11770863.jpg", "Which architect made this drawing?", A("klein"), "author", "record"),
    ("wikimedia/11770863.jpg", "In what year was this drawing made?", A("1874"), "year", "record"),
    ("wikimedia/11770863.jpg", "In which country is this building?", A("denmark"), "place", "record"),
    ("wikimedia/73836773.jpg", "What kind of building complex is this? Answer in English.", A("monastery", "abbey", "cloister", "convent", "priory"), "function", "record+reasoning"),
    ("wikimedia/73836773.jpg", "In which city is this site?", A("oslo"), "place", "record"),
    ("wikimedia/50602369.jpg", "Who designed this house type?", A("stryje"), "author", "record"),
    ("wikimedia/50602369.jpg", "In what year was this design published?", A("1915"), "year", "record"),
    ("wikimedia/50602369.jpg", "What kind of building is this? Answer in English.", A("house", "cottage", "hut", "farm", "dwelling"), "function", "record+reasoning"),
    ("wikimedia/53028310.jpg", "Which archaeological site is shown?", A("roman agora"), "name", "record"),
    ("wikimedia/53028310.jpg", "How many numbered features are marked on the plan?", A("8", "eight"), "count", "image"),
    ("wikimedia/31296291.jpg", "For which event was this stadium built?", A("olympic"), "other", "record"),
    ("wikimedia/31296291.jpg", "In which city is this stadium?", A("london"), "place", "record+reasoning"),
    ("wikimedia/61577576.jpg", "In which town is this church?", A("elvas"), "place", "record"),
    ("wikimedia/61577576.jpg", "In which country is this church?", A("portugal"), "place", "record"),
    ("wikimedia/852781.jpg", "Which church is this the plan of?", A("barbara"), "name", "record"),
    ("wikimedia/852781.jpg", "What is the Czech name of the town labelled Kuttenberg?", A("kutná hora", "kutna hora"), "place", "record"),
    ("wikimedia/66136614.jpg", "Which cathedral is shown?", A("wells"), "name", "record"),
    ("wikimedia/66136614.jpg", "In which country is this cathedral?", A("england", "united kingdom", "uk", "britain"), "place", "record+reasoning"),
    ("wikimedia/11765168.jpg", "Who designed this house?", A("doesburg"), "author", "record"),
    ("wikimedia/11765168.jpg", "What kind of projection is this drawing?", A("axonometr", "isometr"), "drawing_type", "record"),
    ("wikimedia/11765168.jpg", "In which town is this house?", A("meudon"), "place", "record"),
    ("wikimedia/18968700.jpg", "In which city is this monastery?", A("hrodna", "grodno", "harodnia", "gardinas"), "place", "record"),
    ("wikimedia/18968700.jpg", "In which country is this monastery?", A("belarus"), "place", "record"),
    # ---------------- interpretation questions (answer should NOT be verbatim in the context) ----------------
    ("finna/hka.139879309684900_166937160999000.jpg", "In which century was this drawing made?", A("19th", "nineteenth", "1800s", "xix"), "year", "record+reasoning"),
    ("finna/hka.139880068219800_169323282696500.jpg", "In which century was this drawing made?", A("20th", "twentieth", "1900s", "xx"), "year", "record+reasoning"),
    ("habs/ma0578_sheet_00002.jpg", "In which century was this mill first built?", A("19th", "nineteenth", "1800s", "xix"), "year", "record+reasoning"),
    ("habs/nc0046_sheet_00002.jpg", "In which century was this jail first built?", A("18th", "eighteenth", "1700s", "xviii"), "year", "record+reasoning"),
    ("habs/hi0700_sheet_00005.jpg", "In which ocean is the harbour where this ship is moored?", A("pacific"), "place", "record+reasoning"),
    ("habs/ne0022_sheet_00004.jpg", "Which Native American people's reservation is this mission on?", A("sioux", "dakota", "santee"), "other", "record+reasoning"),
    ("europeana/08535_item_227MGO6YEPEBMMWO6AGJPHLSAT4AK4QU.jpg", "In which country is this theatre?", A("germany"), "place", "record+reasoning"),
    ("europeana/285_gam13330.jpg", "In which country is this building?", A("italy"), "place", "record+reasoning"),
    ("europeana/463_item_S7E2D7PFDMFW26A53GHVV5IFOSQRZHWV.jpg", "In which country is this building?", A("germany"), "place", "record+reasoning"),
    ("europeana/332_BVE0831516.jpg", "In which century was this engraving published?", A("16th", "sixteenth", "1500s", "xvi"), "year", "record+reasoning"),
    ("wikimedia/11765168.jpg", "In which country is this house?", A("france"), "place", "record+reasoning"),
    ("wikimedia/45733769.jpg", "In which country is this city gate?", A("france"), "place", "record+reasoning"),
    ("wikimedia/11770863.jpg", "In which city is this building?", A("copenhagen", "kobenhavn", "københavn"), "place", "record+reasoning"),
    ("wikimedia/86583721.jpg", "In which country is this temple?", A("greece"), "place", "record+reasoning"),
    ("wikimedia/73836773.jpg", "On what kind of land feature is this monastery located?", A("island"), "other", "record+reasoning"),
    ("finna/mfa.de93ed0e-f4f8-430e-9d5b-6133fe2358ed.jpg", "In which decade was this water tower completed?", A("1970"), "year", "record+reasoning"),
    ("finna/mfa.ca9d34a4-0fd7-4e99-9cab-a1316e9ba24e.jpg", "Which of this firm's partners later emigrated to the United States?", A("eliel", "saarinen"), "author", "record+reasoning"),
    ("wikimedia/31296291.jpg", "In which year were the Olympic Games held for which this stadium was built?", A("1908"), "year", "record+reasoning"),
]


def split_of(path):
    return "dev" if int(hashlib.sha256(("hist-split:" + path).encode()).hexdigest()[:8], 16) % 2 == 0 else "test"


def main():
    out = os.path.join(ROOT, "results/samples/historic_eval.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        for i, (p, q, acc, qt, origin) in enumerate(Q):
            src = p.split("/")[0]
            f.write(json.dumps({"id": f"h{i:03d}", "path": f"data/{p}", "source": src, "question": q, "accept": acc,
                                "answer": " | ".join(" + ".join(a) for a in acc), "qtype": qt, "origin": origin,
                                "needs_human_check": origin == "image", "split": split_of(p)}, ensure_ascii=False) + "\n")
    import collections
    print(out, len(Q), "questions,", len({q[0] for q in Q}), "drawings")
    print(collections.Counter(q[0].split("/")[0] for q in Q), collections.Counter(q[4] for q in Q))


if __name__ == "__main__":
    main()
