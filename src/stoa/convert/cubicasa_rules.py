"""How each cubicasa question template counts annotated elements (rules chosen on TRAIN, see
scripts/calibrate_cubicasa_svg.py). The same element classes are what the detector is trained to find."""
import re

TEMPLATES = {  # key -> regex over the (English) question; Finnish variants are matched by the router separately
    "windows": r"How many windows",
    "floors": r"How many floors",
    "toilets": r"How many toilet bowls",
    "sinks": r"How many sinks and wash basins",
    "showers_baths": r"How many showers and bathtubs",
    "doors": r"How many doors",
    "saunas": r"How many saunas",
    "kitchens": r"How many kitchens",
    "bedrooms": r"How many bedrooms",
    "bathrooms": r"How many bathrooms or washrooms",
    "wc_rooms": r"How many separate WC rooms",
    "balconies": r"How many balconies",
}


def template_of(q):
    for k, p in TEMPLATES.items():
        if re.match(p, q):
            return k
    return None


def _n(items, pred):
    return sum(1 for x in items if pred(x["cls"].split()))


SINKS = {"Sink", "DoubleSink", "RoundSink", "DoubleSinkRight", "SideSink", "CornerSink", "DoubleSinkLeft"}
RULES = {
    "windows": {"all": lambda A: len(A["windows"])},
    "floors": {"floorplans": lambda A: len(A["floors"])},
    "doors": {"all": lambda A: len(A["doors"]),
              "not_None": lambda A: _n(A["doors"], lambda c: "None" not in c)},
    "toilets": {"Toilet": lambda A: _n(A["fixtures"], lambda c: "Toilet" in c)},
    "sinks": {"sinks": lambda A: _n(A["fixtures"], lambda c: bool(SINKS & set(c))),
              "Sink_only": lambda A: _n(A["fixtures"], lambda c: "Sink" in c)},
    "showers_baths": {"Shower+Bathtub": lambda A: _n(A["fixtures"], lambda c: "Shower" in c or "Bathtub" in c),
                      "+Cab+Jacuzzi": lambda A: _n(A["fixtures"], lambda c: bool({"Shower", "Bathtub", "ShowerCab", "Jacuzzi"} & set(c)))},
    "saunas": {"Space Sauna": lambda A: _n(A["rooms"], lambda c: "Sauna" in c),
               "SaunaStove": lambda A: _n(A["fixtures"], lambda c: any(x.startswith("SaunaStove") for x in c)),
               "SaunaBench": lambda A: _n(A["fixtures"], lambda c: "SaunaBench" in c),
               "room_or_stove": lambda A: max(_n(A["rooms"], lambda c: "Sauna" in c), _n(A["fixtures"], lambda c: any(x.startswith("SaunaStove") for x in c))),
               "stove_any": lambda A: _n(A["fixtures"], lambda c: any("Sauna" in x and "Bench" not in x for x in c))},
    "kitchens": {"Space Kitchen": lambda A: _n(A["rooms"], lambda c: "Kitchen" in c)},
    "bedrooms": {"Space Bedroom": lambda A: _n(A["rooms"], lambda c: "Bedroom" in c)},
    "bathrooms": {"Space Bath": lambda A: _n(A["rooms"], lambda c: "Bath" in c),
                  "Bath_not_WC": lambda A: sum(1 for r in A["rooms"] if "Bath" in r["cls"].split() and (r["label"] or "").upper() != "WC"),
                  "Bath_noWCsub": lambda A: sum(1 for r in A["rooms"] if "Bath" in r["cls"].split() and "WC" not in (r["label"] or "").upper())},
    "wc_rooms": {"Bath_WC": lambda A: sum(1 for r in A["rooms"] if "Bath" in r["cls"].split() and (r["label"] or "").upper() == "WC"),
                 "Bath_WCsub": lambda A: sum(1 for r in A["rooms"] if "Bath" in r["cls"].split() and "WC" in (r["label"] or "").upper())},
    "balconies": {"Space Balcony": lambda A: _n(A["rooms"], lambda c: "Balcony" in c),
                  "Outdoor Balcony+Glazed": lambda A: _n(A["rooms"], lambda c: "Outdoor" in c and "Balcony" in c)},
}
