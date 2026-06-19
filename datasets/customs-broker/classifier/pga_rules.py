"""
Deterministic HTS-chapter -> Partner Government Agency (PGA) mapping.

This is the rules layer. It must NEVER depend on the LLM: admissibility is a
legal question, so the agencies that gate a commodity are derived from the HTS
chapter and a few keyword overlays, not guessed by a model. The classifier asks
Claude for the HTS code, then this module attaches the PGA flags deterministically
so the same input always yields the same agency set.

Derived from datasets/customs-broker/regulated-imports.csv.
"""

# 2-digit HTS chapter -> list of agencies that commonly control admissibility.
# Representative, not exhaustive; many goods are regulated by more than one agency.
CHAPTER_PGA = {
    "01": ["USDA APHIS"],                       # live animals
    "02": ["USDA FSIS"],                        # meat
    "03": ["FDA", "NOAA/NMFS (SIMP)"],          # fish & seafood
    "04": ["FDA", "USDA FSIS (eggs)"],          # dairy, eggs, honey
    "05": ["USDA APHIS", "FDA"],                # animal products
    "06": ["USDA APHIS PPQ"],                   # live plants
    "07": ["FDA", "USDA APHIS PPQ"],            # vegetables
    "08": ["FDA", "USDA APHIS PPQ"],            # fruit
    "09": ["FDA"],                              # coffee, tea, spices
    "10": ["FDA", "USDA APHIS PPQ"],            # cereals/grain
    "11": ["FDA"],                              # milling products
    "12": ["USDA APHIS PPQ", "FDA"],            # seeds, oil seeds
    "15": ["FDA"],                              # fats & oils
    "16": ["FDA", "USDA FSIS"],                 # prepared meat/fish
    "17": ["FDA"],                              # sugars
    "18": ["FDA"],                              # cocoa
    "19": ["FDA"],                              # cereal/bakery prep
    "20": ["FDA"],                              # prepared vegetables/fruit
    "21": ["FDA"],                              # misc edible prep
    "22": ["TTB", "FDA"],                       # beverages, spirits
    "23": ["FDA", "USDA APHIS"],                # animal feed
    "24": ["TTB", "FDA (CTP)"],                 # tobacco & nicotine
    "28": ["EPA (TSCA)"],                       # inorganic chemicals
    "29": ["EPA (TSCA)", "DEA"],                # organic chemicals / precursors
    "30": ["FDA"],                              # pharmaceuticals
    "31": ["EPA"],                              # fertilizers
    "32": ["EPA (TSCA)"],                       # dyes, paints
    "33": ["FDA"],                              # cosmetics, perfumery
    "34": ["EPA (FIFRA)", "FDA"],               # soaps, antimicrobials
    "36": ["ATF", "CPSC", "DOT"],               # explosives, fireworks
    "38": ["EPA (FIFRA/TSCA)"],                 # pesticides, misc chemicals
    "39": ["CPSC", "FDA (food-contact)"],       # plastics
    "40": ["CPSC", "DOT/NHTSA (tires)"],        # rubber
    "41": ["USDA APHIS", "US FWS"],             # hides & skins
    "42": ["US FWS"],                           # leather goods (CITES species)
    "43": ["US FWS"],                           # furs
    "44": ["USDA APHIS PPQ"],                   # wood
    "50": ["CBP (UFLPA, marking)"],             # silk
    "51": ["CBP (UFLPA, marking)"],             # wool
    "52": ["CBP (UFLPA, marking)"],             # cotton
    "53": ["CBP (UFLPA, marking)"],             # other vegetable textile
    "54": ["CBP (UFLPA, marking)"],             # man-made filaments
    "55": ["CBP (UFLPA, marking)"],             # man-made staple fibers
    "56": ["CBP (UFLPA, marking)"],             # wadding, nonwovens
    "57": ["CBP (UFLPA, marking)"],             # carpets
    "58": ["CBP (UFLPA, marking)"],             # special woven fabrics
    "59": ["CBP (UFLPA, marking)"],             # coated textiles
    "60": ["CBP (UFLPA, marking)"],             # knitted fabrics
    "61": ["CBP (UFLPA, marking)", "CPSC (children)"],  # apparel, knit
    "62": ["CBP (UFLPA, marking)", "CPSC (children)"],  # apparel, woven
    "63": ["CBP (UFLPA, marking)"],             # other made-up textiles
    "64": ["CBP (marking)", "CPSC"],            # footwear
    "71": ["CBP", "US FWS (coral/shell)"],      # precious stones, jewelry
    "84": ["EPA (engines)", "DOE", "CPSC"],     # machinery
    "85": ["FCC", "DOE", "CPSC", "FDA (CDRH)"], # electrical/electronics
    "87": ["DOT/NHTSA", "EPA"],                 # vehicles
    "88": ["FAA", "DDTC"],                      # aircraft
    "89": ["USCG", "EPA"],                      # ships
    "90": ["FDA (CDRH)", "FCC"],                # optical, medical instruments
    "93": ["ATF", "State DDTC"],                # arms & ammunition
    "94": ["CPSC", "DOE"],                      # furniture, lighting
    "95": ["CPSC"],                             # toys, games
    "97": ["CBP", "State (cultural property)"], # works of art, antiques
}

# Keyword overlays add agencies regardless of chapter (catch cross-cutting controls).
KEYWORD_PGA = [
    (("laser", "x-ray", "x ray", "ultraviolet", "uv lamp", "sunlamp",
      "microwave oven", "radiation", "sterilizer lamp"), "FDA (CDRH radiation, Form 2877)"),
    (("wifi", "wi-fi", "bluetooth", "transmitter", "radio frequency", "rf module",
      "wireless", "cellular", "router", "drone", "transceiver"), "FCC (equipment authorization)"),
    (("vape", "e-cigarette", "e-cig", "nicotine", "tobacco"), "FDA (CTP) + TTB"),
    (("pesticide", "insecticide", "herbicide", "fungicide", "antimicrobial",
      "disinfectant", "sanitizer"), "EPA (FIFRA, Notice of Arrival)"),
    (("refrigerant", "hcfc", "hfc", "ozone"), "EPA (Clean Air Act / AIM Act)"),
    (("firearm", "rifle", "pistol", "shotgun", "ammunition", "silencer",
      "suppressor"), "ATF (Form 6 import permit)"),
    (("dietary supplement", "vitamin", "supplement"), "FDA (dietary supplement)"),
    (("medical device", "diagnostic", "implant", "surgical", "thermometer",
      "syringe", "catheter"), "FDA (CDRH device)"),
    (("endangered", "ivory", "coral", "python", "crocodile", "tortoise shell",
      "wildlife", "fur", "feather"), "US FWS (Form 3-177 / CITES)"),
    (("controlled substance", "narcotic", "ketamine", "ephedrine",
      "pseudoephedrine"), "DEA (import permit)"),
    (("seafood", "shrimp", "tuna", "crab", "abalone", "swordfish"),
     "NOAA/NMFS (Seafood Import Monitoring Program)"),
]


def agencies_for(hts_code: str, description: str = "") -> list[str]:
    """Return the deduplicated, ordered list of likely PGAs for an HTS code."""
    flags: list[str] = []
    chapter = (hts_code or "").replace(".", "").strip()[:2]
    for agency in CHAPTER_PGA.get(chapter, []):
        if agency not in flags:
            flags.append(agency)
    blob = (description or "").lower()
    for keys, agency in KEYWORD_PGA:
        if any(k in blob for k in keys) and agency not in flags:
            flags.append(agency)
    return flags
