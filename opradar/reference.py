"""Static reference data: taxonomies, legal forms, classification patterns, tech dictionary.

Everything here is lookup data with no logic. Keep it that way -- it is the part
non-Python people on the team need to be able to read and edit.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# KldB 2010 -- Klassifikation der Berufe (Bundesagentur fuer Arbeit)
#
# A code is 5 digits:
#   digit 1     Berufsbereich        (10 sectors)
#   digits 1-2  Berufshauptgruppe    (37 groups)
#   digits 1-3  Berufsgruppe         (144)
#   digits 1-4  Berufsuntergruppe    (702)
#   digit 5     Anforderungsniveau   (skill level 1-4)
#
# The 5th digit is the most useful classification field in the dataset: it is clean
# and always present, unlike the `seniority` column which is ~88% unknown. But it is
# a QUALIFICATION level, not a career level -- a fresh university graduate is a "4".
# Keep it as its own field; do not map it to seniority.
# ---------------------------------------------------------------------------

KLDB_SECTOR = {
    "0": "Militaer",
    "1": "Land-, Forst- und Tierwirtschaft und Gartenbau",
    "2": "Rohstoffgewinnung, Produktion und Fertigung",
    "3": "Bau, Architektur, Vermessung und Gebaeudetechnik",
    "4": "Naturwissenschaft, Geografie und Informatik",
    "5": "Verkehr, Logistik, Schutz und Sicherheit",
    "6": "Kaufmaennische Dienstleistungen, Warenhandel, Vertrieb, Hotel und Tourismus",
    "7": "Unternehmensorganisation, Buchhaltung, Recht und Verwaltung",
    "8": "Gesundheit, Soziales, Lehre und Erziehung",
    "9": "Geistes-/Gesellschaftswissenschaften, Medien, Kunst, Kultur und Gestaltung",
}

KLDB_GROUP = {
    "01": "Angehoerige der regulaeren Streitkraefte",
    "11": "Land-, Tier- und Forstwirtschaftsberufe",
    "12": "Gartenbauberufe und Floristik",
    "21": "Rohstoffgewinnung und -aufbereitung, Glas und Keramik",
    "22": "Kunststoff- und Holzherstellung und -verarbeitung",
    "23": "Papier- und Druckberufe, technische Mediengestaltung",
    "24": "Metallerzeugung und -bearbeitung, Metallbauberufe",
    "25": "Maschinen- und Fahrzeugtechnikberufe",
    "26": "Mechatronik-, Energie- und Elektroberufe",
    "27": "Technische Forschung, Entwicklung, Konstruktion und Produktionssteuerung",
    "28": "Textil- und Lederberufe",
    "29": "Lebensmittelherstellung und -verarbeitung",
    "31": "Bauplanungs-, Architektur- und Vermessungsberufe",
    "32": "Hoch- und Tiefbauberufe",
    "33": "(Innen-)Ausbauberufe",
    "34": "Gebaeude- und versorgungstechnische Berufe",
    "41": "Mathematik-, Biologie-, Chemie- und Physikberufe",
    "42": "Geologie-, Geografie- und Umweltschutzberufe",
    "43": "Informatik-, Informations- und Kommunikationstechnologieberufe",
    "51": "Verkehrs- und Logistikberufe (ohne Fahrzeugfuehrung)",
    "52": "Fuehrer/innen von Fahrzeug- und Transportgeraeten",
    "53": "Schutz-, Sicherheits- und Ueberwachungsberufe",
    "54": "Reinigungsberufe",
    "61": "Einkaufs-, Vertriebs- und Handelsberufe",
    "62": "Verkaufsberufe",
    "63": "Tourismus-, Hotel- und Gaststaettenberufe",
    "71": "Berufe in Unternehmensfuehrung und -organisation",
    "72": "Finanzdienstleistungs-, Rechnungswesen- und Steuerberatungsberufe",
    "73": "Berufe in Recht und Verwaltung",
    "81": "Medizinische Gesundheitsberufe",
    "82": "Nichtmedizinische Gesundheits-, Koerperpflege- und Wellnessberufe",
    "83": "Erziehung, soziale und hauswirtschaftliche Berufe, Theologie",
    "84": "Lehrende und ausbildende Berufe",
    "91": "Sprach-, Literatur-, Geistes-, Gesellschafts- und Wirtschaftswissenschaften",
    "92": "Werbung, Marketing, kaufmaennische und redaktionelle Medienberufe",
    "93": "Produktdesign, Kunsthandwerk, bildende Kunst, Musikinstrumentenbau",
    "94": "Darstellende und unterhaltende Berufe",
}

# 5th digit -> requirement level
KLDB_LEVEL = {
    "1": ("helper", "Helfer- und Anlerntaetigkeiten"),
    "2": ("skilled", "Fachlich ausgerichtete Taetigkeiten"),
    "3": ("specialist", "Komplexe Spezialistentaetigkeiten"),
    "4": ("expert", "Hoch komplexe Taetigkeiten"),
}

# Which KldB groups count as "IT" for this product.
# 43 is the core IT group. The extended set adds adjacent engineering/R&D groups
# that regularly carry software work (embedded, automation, technical R&D).
KLDB_IT_CORE = ("43",)
KLDB_IT_EXTENDED = ("43", "41", "27", "25")


# ---------------------------------------------------------------------------
# Company name normalisation
# ---------------------------------------------------------------------------

# German legal forms, in the *canonicalised* token spelling produced by
# text.canonicalise() ("GmbH & Co. KG" -> "gmbh und co kg").
# Order matters: longest first, so multi-token forms win.
LEGAL_FORMS = [
    "ug haftungsbeschraenkt und co kg",
    "gmbh und co kgaa",
    "gmbh und co ohg",
    "gmbh und co kg",
    "ag und co kg",
    "se und co kg",
    "kg und co kg",
    "ug haftungsbeschraenkt",
    "partg mbb",
    "gmbh",
    "ggmbh",
    "mbh",
    "kgaa",
    "ohg",
    "gbr",
    "kdoer",
    "aoer",
    "partg",
    "gag",
    "ag",
    "se",
    "kg",
    "ev",
    "ek",
    "inc",
    "ltd",
    "llc",
    "plc",
    "bv",
    "nv",
]

# Branch / division markers. Everything from the marker onward is dropped,
# e.g. "FERCHAU GmbH Niederlassung Bremen City" -> "ferchau".
BRANCH_MARKERS = [
    "zweigniederlassung",
    "niederlassung",
    "geschaeftsstelle",
    "betriebsstaette",
    "standort",
    "filiale",
    "abteilung",
    "bereich",
    "vertrieb",
    "werk",
    "unit",
    "nl",
    "fb",
]

# Stripped only for the *loose* match key -- these genuinely do merge entities
# sometimes and wrongly merge them other times, so they stay opt-in.
LOOSE_SUFFIXES = [
    "deutschland",
    "germany",
    "international",
    "europe",
    "europa",
    "holding",
    "group",
    "gruppe",
    "global",
]


# ---------------------------------------------------------------------------
# Company classification
#
# Two orthogonal outputs:
#   company_class  -- what kind of organisation it is
#   is_competitor  -- does it compete with us for the same placements
#
# For a staffing-side product, agencies are NOT noise: they are the competitive
# intelligence layer. We classify them precisely so we can count them.
# ---------------------------------------------------------------------------

CLASS_TRAINING = "training_provider"
CLASS_STAFFING = "staffing_agency"
CLASS_IT_SERVICES = "it_service_provider"
CLASS_PUBLIC = "public_sector"
CLASS_INDIVIDUAL = "individual"
CLASS_END_CLIENT = "end_client"

# Evaluated in this order; first hit wins.
CLASS_PATTERNS: list[tuple[str, str]] = [
    (
        CLASS_TRAINING,
        r"bildungszentrum|bildungswerk|bildungsinstitut|bildungsakademie|akademie"
        r"|weiterbildung|umschulung|schulungs|lehrinstitut|kolleg\b|volkshochschule"
        r"|berufsfoerderungswerk|qualifizierungs",
    ),
    (
        CLASS_STAFFING,
        r"personaldienst|personalservice|personalmanagement|personalvermittlung"
        r"|personalberatung|personalleasing|personalloesung|arbeitsvermittlung"
        r"|zeitarbeit|leiharbeit|arbeitnehmerueberlassung|temporaer"
        r"|\bpersonal\b|recruit|staffing|headhunt|interim|\btemp\b|jobvermittlung"
        r"|hays|randstad|adecco|manpower|michael page|robert half|amadeus fire"
        r"|\bdis ag\b|orizon|piening|tempton|synergie|hofmann|jobtimum|arbitex"
        r"|perzukunft|\barwa\b|timepartner|time partner|neo temp|hanfried"
        r"|rocket match|pflegia|simplecon|avivar|guldberg|constaff|\bgulp\b"
        # note: canonicalise() rewrites "&" as "und", so match the "und" spelling
        r"|job und karriere|jobaktivisten"
        # Engineering / IT firms that sell people rather than products. Their names
        # carry no agency keyword, so they have to be named explicitly.
        r"|\bbrunel\b|bertrandt|\bedag\b|expleo|invenio|\barrk\b|mbtech|\bmodis\b"
        r"|trenkwalder|zeitkraft|univativ|zenjob|studitemps|actief|\bruntime\b"
        r"|gi group|persona service|unique personal|dekra arbeit|start nrw"
        r"|alphaconsult|engineering people",
    ),
    (
        CLASS_PUBLIC,
        r"^bundes|^landes|^stadt\b|stadtverwaltung|^gemeinde|landkreis|kreisverwaltung"
        r"|ministerium|behoerde|^polizei|justiz|finanzamt|jobcenter|agentur fuer arbeit"
        r"|universitaet|hochschule|fachhochschule|kdoer|aoer"
        r"|koerperschaft des oeffentlichen rechts|anstalt des oeffentlichen rechts"
        r"|eigenbetrieb|deutsche rentenversicherung|bundeswehr|^bwi\b"
        r"|studierendenwerk|studentenwerk|bezirksamt|kreisstadt",
    ),
    (
        CLASS_IT_SERVICES,
        # Deliberately narrow. Generic tech words -- software, informatik, digital,
        # systems, data, technologies -- describe PRODUCT companies just as often as
        # service companies, and a product company is an end client, not a competitor.
        # Only terms that actually denote selling services belong here.
        r"systemhaus|it dienstleist|it service|itservice|edv service|softwarehaus"
        r"|unternehmensberatung|\bconsulting\b|\bconsultants\b|ingenieurbuero"
        r"|engineering services|managed services|\bit beratung\b"
        r"|akkodis|ferchau|\balten\b|bechtle|computacenter|adesso|msg systems"
        r"|capgemini|accenture|\batos\b|sopra steria|\bcgi\b|infosys|wipro|cognizant"
        r"|deloitte|\bkpmg\b|\bpwc\b|ernst und young|mckinsey|bridgingit|scalian"
        r"|materna|cancom|\bgisa\b|ntt data|\bcapita\b|\bsopra\b",
    ),
]

# "Lastname, Firstname" with no company-ish token -> a private individual, not a firm.
INDIVIDUAL_PATTERN = re.compile(r"^[A-Za-zÀ-ÿ'\-]+,\s*[A-Za-zÀ-ÿ'\-]+\.?$")


# ---------------------------------------------------------------------------
# Technology / skill dictionary
#
# Applied to job titles. Coverage from titles alone is low (~5-8% of postings);
# the same dictionary is reused on job descriptions once those are fetched.
#
# Patterns are matched case-insensitively against the raw title. Use explicit
# boundaries -- naive substring matching finds "AI" and "KI" inside hundreds of
# German words and invents an AI boom that is not there.
# ---------------------------------------------------------------------------

_B = r"(?<![A-Za-z0-9])"   # left boundary that also works before "." and "#"
_E = r"(?![A-Za-z0-9])"    # right boundary

TECH_PATTERNS: dict[str, tuple[str, str]] = {
    # canonical name            (category,      regex)
    "Java":            ("language", rf"{_B}java{_E}(?!script)"),
    "JavaScript":      ("language", rf"{_B}javascript{_E}|{_B}js{_E}"),
    "TypeScript":      ("language", rf"{_B}typescript{_E}"),
    "Python":          ("language", rf"{_B}python{_E}"),
    "C#":              ("language", rf"{_B}c#"),
    "C/C++":           ("language", rf"{_B}c\+\+|{_B}c\s?/\s?c\+\+|{_B}embedded c{_E}"),
    ".NET":            ("language", rf"\.net{_E}|{_B}dotnet{_E}"),
    "PHP":             ("language", rf"{_B}php{_E}"),
    "Ruby":            ("language", rf"{_B}ruby{_E}"),
    "Go":              ("language", rf"{_B}golang{_E}"),
    "Rust":            ("language", rf"{_B}rust{_E}"),
    "Kotlin":          ("language", rf"{_B}kotlin{_E}"),
    "Swift":           ("language", rf"{_B}swift{_E}"),
    "Scala":           ("language", rf"{_B}scala{_E}"),
    "ABAP":            ("language", rf"{_B}abap{_E}"),
    "COBOL":           ("language", rf"{_B}cobol{_E}"),

    "SAP":             ("erp",      rf"{_B}sap{_E}"),
    "S/4HANA":         ("erp",      rf"{_B}s/?4\s?hana{_E}|{_B}hana{_E}"),
    "Dynamics":        ("erp",      rf"{_B}dynamics{_E}|{_B}navision{_E}|{_B}business central{_E}"),
    "Salesforce":      ("erp",      rf"{_B}salesforce{_E}"),
    "ServiceNow":      ("erp",      rf"{_B}servicenow{_E}"),
    "DATEV":           ("erp",      rf"{_B}datev{_E}"),
    "Oracle":          ("erp",      rf"{_B}oracle{_E}"),

    "Azure":           ("cloud",    rf"{_B}azure{_E}"),
    "AWS":             ("cloud",    rf"{_B}aws{_E}|amazon web services"),
    "GCP":             ("cloud",    rf"{_B}gcp{_E}|google cloud"),
    "Cloud":           ("cloud",    rf"{_B}cloud{_E}"),
    "Kubernetes":      ("devops",   rf"{_B}kubernetes{_E}|{_B}k8s{_E}"),
    "Docker":          ("devops",   rf"{_B}docker{_E}|{_B}podman{_E}"),
    "Terraform":       ("devops",   rf"{_B}terraform{_E}"),
    "DevOps":          ("devops",   rf"{_B}devops{_E}"),
    "SRE":             ("devops",   rf"{_B}sre{_E}|site reliability"),
    "CI/CD":           ("devops",   rf"{_B}ci/cd{_E}|{_B}jenkins{_E}|{_B}gitlab{_E}"),
    "Linux":           ("platform", rf"{_B}linux{_E}|{_B}unix{_E}"),
    "Windows":         ("platform", rf"{_B}windows{_E}"),
    "Citrix":          ("platform", rf"{_B}citrix{_E}"),
    "VMware":          ("platform", rf"{_B}vmware{_E}"),
    "Microsoft 365":   ("platform", rf"{_B}m365{_E}|{_B}o365{_E}|office 365|microsoft 365"),

    "SQL":             ("data",     rf"{_B}sql{_E}(?!server)"),
    "Data Engineering":("data",     rf"data engineer|dateningenieur|datenarchitekt"),
    "Data Science":    ("data",     rf"data scien|datenanalys|data analyst"),
    "Power BI":        ("data",     rf"power\s?bi{_E}"),
    "Snowflake":       ("data",     rf"{_B}snowflake{_E}"),
    "Databricks":      ("data",     rf"{_B}databricks{_E}"),
    "Big Data":        ("data",     rf"big data|{_B}hadoop{_E}|{_B}spark{_E}|{_B}kafka{_E}"),
    "AI/ML":           ("data",     rf"{_B}ki{_E}|{_B}ai{_E}|kuenstliche intelligenz"
                                    rf"|machine learning|maschinelles lernen|{_B}ml{_E}|{_B}llm{_E}"),

    "React":           ("frontend", rf"{_B}react{_E}"),
    "Angular":         ("frontend", rf"{_B}angular{_E}"),
    "Vue":             ("frontend", rf"{_B}vue{_E}|vue\.js"),
    "Frontend":        ("frontend", rf"{_B}frontend{_E}|front-end"),
    "Backend":         ("backend",  rf"{_B}backend{_E}|back-end"),
    "Fullstack":       ("backend",  rf"{_B}fullstack{_E}|full-stack|full stack"),
    "Spring":          ("backend",  rf"{_B}spring{_E}"),
    "Node.js":         ("backend",  rf"node\.?js{_E}"),

    "Security":        ("security", rf"{_B}security{_E}|{_B}it.sicherheit|{_B}informationssicherheit"
                                    rf"|{_B}cybersicherheit|{_B}datensicherheit|{_B}netzwerksicherheit"
                                    rf"|{_B}soc{_E}|{_B}siem{_E}|{_B}pentest|{_B}penetrationstest"),
    "Network":         ("network",  rf"{_B}netzwerk|{_B}network|{_B}cisco{_E}"
                                    rf"|{_B}lan{_E}|{_B}firewall"),
    "Embedded":        ("embedded", rf"{_B}embedded{_E}|{_B}firmware{_E}|mikrocontroller"
                                    rf"|steuergeraet|{_B}autosar{_E}|{_B}plc{_E}|{_B}sps{_E}"),
    "Mobile":          ("mobile",   rf"{_B}android{_E}|{_B}ios{_E}|mobile app|app-entwickl"),
    "Testing/QA":      ("quality",  rf"{_B}qa{_E}|{_B}test{_E}|{_B}tester|{_B}testautomat"
                                    rf"|{_B}testmanag|quality assurance|{_B}softwaretest"),
    "SharePoint":      ("platform", rf"{_B}sharepoint{_E}"),
    "Atlassian":       ("devops",   rf"{_B}jira{_E}|confluence|atlassian"),
}

# Market domains. These are NOT technologies -- they describe the client's sector,
# which matters enormously for placement fit ("we have three people with banking
# experience") and would otherwise pollute the technology ranking.
DOMAIN_PATTERNS: dict[str, str] = {
    "Automotive":   rf"{_B}automotive|{_B}fahrzeug|{_B}kfz{_E}|{_B}oem{_E}|{_B}e.mobilitaet"
                    rf"|{_B}powertrain|{_B}autonomes fahren",
    "Banking":      rf"{_B}bank|{_B}kreditinstitut|{_B}zahlungsverkehr|{_B}wertpapier"
                    rf"|{_B}fintech|{_B}core.banking|{_B}sparkasse",
    "Insurance":    rf"{_B}versicherung|{_B}insurtech|{_B}schaden{_E}|{_B}aktuar",
    "Healthcare":   rf"{_B}klinik|{_B}medizin|{_B}gesundheitswesen|{_B}pharma|{_B}healthcare"
                    rf"|{_B}medtech|{_B}krankenhaus|{_B}pflege",
    "Public":       rf"{_B}behoerde|{_B}oeffentliche verwaltung|{_B}kommunal|{_B}ministerium"
                    rf"|{_B}bundeswehr|{_B}verteidigung|{_B}defence|{_B}defense",
    "Energy":       rf"{_B}energie|{_B}netzbetreib|{_B}erneuerbare|{_B}photovoltaik"
                    rf"|{_B}windkraft|{_B}smart grid|{_B}stromnetz",
    "Logistics":    rf"{_B}logistik|{_B}supply chain|{_B}spedition|{_B}intralogistik"
                    rf"|{_B}warehouse|{_B}lagerverwaltung",
    "Telecom":      rf"{_B}telekommunikation|{_B}telco{_E}|{_B}mobilfunk|{_B}5g{_E}"
                    rf"|{_B}glasfaser|{_B}breitband",
    "Aerospace":    rf"{_B}luftfahrt|{_B}raumfahrt|{_B}aviation|{_B}aerospace|{_B}satellit",
    "Manufacturing":rf"{_B}produktion|{_B}fertigung|{_B}industrie 4|{_B}maschinenbau"
                    rf"|{_B}anlagenbau|{_B}mes{_E}",
    "Retail":       rf"{_B}handel{_E}|{_B}e.commerce|{_B}retail|{_B}einzelhandel|{_B}webshop",
}

DOMAIN_COMPILED = {
    name: re.compile(pattern, re.IGNORECASE) for name, pattern in DOMAIN_PATTERNS.items()
}


TECH_COMPILED = {
    name: (category, re.compile(pattern, re.IGNORECASE))
    for name, (category, pattern) in TECH_PATTERNS.items()
}


# ---------------------------------------------------------------------------
# Seniority
#
# Priority: explicit title keyword > dataset column > KldB requirement level.
# ---------------------------------------------------------------------------

SENIORITY_ORDER = ["intern", "entry", "junior", "mid", "senior", "lead", "unknown"]

SENIORITY_TITLE_PATTERNS: list[tuple[str, str]] = [
    ("intern", r"praktik|werkstudent|working student|intern|hospitan|schnupper"),
    ("entry",  r"ausbildung|auszubildend|azubi|trainee|duales studium|dualer student"
               r"|berufseinsteiger|quereinsteig|aushilfe|helfer|studentische"),
    ("lead",   r"lead|leiter|leitung|head of|principal|chief|cto|cio"
               r"|teamlead|team lead|gruppenleit|abteilungsleit|bereichsleit|director"
               r"|geschaeftsfuehr|vorstand|staff engineer"),
    ("senior", r"senior|sr\.?|erfahren|expert|experte|architekt|architect"),
    ("junior", r"junior|jr\.?|nachwuchs|einsteiger"),
]

# Deliberately NOT derived from the KldB requirement level. Anforderungsniveau 4
# means "requires a degree", which is true of every graduate hire; mapping it to
# "senior" labelled ~45% of the market senior, which is nonsense. Better to leave
# seniority unknown and expose kldb_level separately than to publish a wrong number.
SENIORITY_FROM_KLDB_LEVEL: dict[str, str] = {}

# Dataset `seniority` column -> our vocabulary
SENIORITY_FROM_DATASET = {
    "entry": "entry",
    "junior": "junior",
    "mid": "mid",
    "senior": "senior",
    "lead": "lead",
    "unknown": None,
}


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------

AUSTRIAN_REGIONS = {
    "Wien", "Niederoesterreich", "Oberoesterreich", "Steiermark", "Tirol",
    "Salzburg", "Kaernten", "Vorarlberg", "Burgenland",
    "Niederösterreich", "Oberösterreich", "Kärnten",
}

SWISS_REGIONS = {
    "Zuerich", "Zürich", "Nordwestschweiz (mit Basel)", "Genferseeregion",
    "Ostschweiz", "Zentralschweiz", "Espace Mittelland", "Tessin",
}

# NUTS-1 -> Bundesland, for filling gaps in `region`.
NUTS_TO_REGION = {
    "DE1": "Baden-Wuerttemberg",
    "DE2": "Bayern",
    "DE3": "Berlin",
    "DE4": "Brandenburg",
    "DE5": "Bremen",
    "DE6": "Hamburg",
    "DE7": "Hessen",
    "DE8": "Mecklenburg-Vorpommern",
    "DE9": "Niedersachsen",
    "DEA": "Nordrhein-Westfalen",
    "DEB": "Rheinland-Pfalz",
    "DEC": "Saarland",
    "DED": "Sachsen",
    "DEE": "Sachsen-Anhalt",
    "DEF": "Schleswig-Holstein",
    "DEG": "Thueringen",
}

# 2022 population, millions -- for normalising regional counts. Crawl coverage is
# uneven by region, so raw regional heatmaps are artefacts, not market facts.
REGION_POPULATION_M = {
    "Nordrhein-Westfalen": 18.14,
    "Bayern": 13.37,
    "Baden-Wuerttemberg": 11.28,
    "Niedersachsen": 8.14,
    "Hessen": 6.39,
    "Rheinland-Pfalz": 4.16,
    "Sachsen": 4.09,
    "Berlin": 3.76,
    "Schleswig-Holstein": 2.95,
    "Brandenburg": 2.57,
    "Sachsen-Anhalt": 2.17,
    "Thueringen": 2.11,
    "Hamburg": 1.89,
    "Mecklenburg-Vorpommern": 1.63,
    "Saarland": 0.99,
    "Bremen": 0.68,
}


# ---------------------------------------------------------------------------
# Title cleaning
# ---------------------------------------------------------------------------

GENDER_MARKERS = re.compile(
    r"\(\s*[mwdfxa](\s*[/|,]\s*[mwdfxa])+\s*\)"          # (m/w/d), (w/m/d), (m/f/x)
    r"|\(\s*all\s+genders?\s*\)"
    r"|\(\s*divers\s*\)"
    r"|\bm\s*/\s*w\s*/\s*[dx]\b"
    r"|\(\s*gn\s*\)"
    r"|\*in(nen)?\b|:in(nen)?\b",
    re.IGNORECASE,
)

# Leading internal reference codes: "355/B - ", "E349/B - ", "B110-C05 "
REF_CODE_PREFIX = re.compile(r"^\s*[A-Z0-9][A-Z0-9\-/_.]{2,14}\s*[-–:]\s*")

# Trailing "in Dresden", "- Standort Muenchen", "| Vollzeit"
TITLE_TAIL_NOISE = re.compile(
    r"\s*[-–|/]\s*(vollzeit|teilzeit|remote|homeoffice|befristet|unbefristet)\b.*$",
    re.IGNORECASE,
)
