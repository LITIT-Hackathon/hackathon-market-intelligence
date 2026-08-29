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
        # English "training" in a company name (WBS TRAINING SE was landing in
        # end_client without it -- Research.txt 9.3)
        r"|berufsfoerderungswerk|qualifizierungs|training",
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
        r"|materna|cancom|\bgisa\b|\bcapita\b|\bsopra\b"
        # Own group (LITIT = NTT Data x Reiz Tech). Token-bounded "ntt" catches
        # NTT Germany / NTT Global Data Centers, which "ntt data" missed --
        # a bare substring would also match Diama-ntt-echnik (Research.txt 9.3).
        r"|(?<![a-z0-9])ntt(?![a-z0-9])|reiz tech|\blitit\b",
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
# IT role and training role detection (ALGORITHM.md interface contract)
#
# is_it_role is TITLE-PRIMARY: the title decides whether a posting is an IT job;
# the KldB code (`is_it_core`) is corroboration feeding Confidence, never a gate.
# Rationale, measured on this dataset (ALGORITHM.md 4.2, independently verified
# in Research.txt 9.1): ~1/3 of KldB-43 postings have no IT signal in the title
# ("Kaufmaennischer Mitarbeiter" coded 43), while ~2,100 real IT jobs sit under
# broken codes ("Junior Java Entwickler" -> 83113 social work, "DevOps Engineer"
# -> 28102 textiles). The two error types are not symmetric: a title is direct
# evidence, a code is an annotation.
#
# THIS IS THE SINGLE SOURCE for the lexicon (ALGORITHM.md rule 5). The scorer
# must consume the columns, never re-implement the pattern: two private
# implementations drifted 4% apart during verification.
#
# Matched against title_fold (lowercased, umlauts expanded), like TECH_PATTERNS.
# Known deliberate calls:
#   - bare "administrator" only when the title STARTS a compound with it
#     (left boundary blocks "Personaladministrator" = HR);
#   - "web" is token-bounded, never prefix-matched ("Weber" is a weaver);
#   - "digitalisierung" is included: digitalisation officers are IT-adjacent
#     buyers, which is the customer this product serves;
#   - pure hardware roles (Hardwareentwickler) are excluded; embedded/firmware
#     are included because embedded is one of the 12 tech categories.
# ---------------------------------------------------------------------------

IT_ROLE_PATTERN = re.compile(
    rf"{_B}it{_E}|{_B}edv{_E}|informatik|software|entwickler|developer|programmier"
    rf"|{_B}devops{_E}|sysadmin|systemadministr|netzwerkadministr|datenbankadministr"
    rf"|{_B}administrator|systemintegration|fachinformatik|wirtschaftsinformatik"
    rf"|anwendungsbetreu|applikation|application (?:manager|engineer|operations)"
    rf"|{_B}sap{_E}|{_B}erp{_E}|{_B}crm{_E}|{_B}cloud{_E}"
    rf"|frontend|backend|fullstack|full.stack|webentwick|{_B}web{_E}"
    rf"|{_B}java{_E}|{_B}python{_E}|{_B}c#|{_B}c\+\+|\.net{_E}|{_B}php{_E}|{_B}sql{_E}"
    rf"|{_B}linux{_E}|{_B}citrix{_E}|{_B}vmware{_E}|sharepoint|servicenow|salesforce"
    # it.sicherheit needs the left boundary or it matches inside
    # "arbe-its-sicherheit" (occupational safety) -- same trap as the Security
    # tech pattern
    rf"|{_B}datev{_E}|cyber|informationssicherheit|{_B}it.sicherheit|netzwerksicherheit"
    rf"|{_B}siem{_E}|{_B}soc{_E}|pentest|data (?:engineer|scientist|analyst|architect)"
    rf"|datenanalyst|dateningenieur|machine learning|{_B}ki{_E}|{_B}ai{_E}"
    rf"|kuenstliche intelligenz|business intelligence|{_B}bi{_E}|{_B}etl{_E}|big data"
    rf"|kubernetes|docker|terraform|ansible|{_B}aws{_E}|{_B}azure{_E}|{_B}gcp{_E}"
    rf"|softwaretest|testautomat|qa engineer|scrum|solution architect|software.?architekt"
    rf"|it.architekt|helpdesk|service.?desk|digitalisierung|embedded"
    rf"|firmware|mikrocontroller",
    re.IGNORECASE,
)

# is_training_role: Ausbildung / duales Studium / Werkstudent / Praktikum
# (the four categories named in ALGORITHM.md 1). A company hiring apprentices is
# building capability in-house -- the opposite of an outsourcing trigger --
# and `seniority_derived` cannot express this: the same postings split across
# `entry` (~4,000) and `intern` (~1,700).
#
# "praktikum|praktikant" is deliberate, NOT the bare stem "praktik": the stem
# also matches "Heilpraktiker" (a naturopath, neither IT nor training).
# "trainee" is deliberately absent -- trainee programmes are paid employment,
# and the contract's list does not include them. Raise with the scorer if that
# call should change; do not widen silently.
TRAINING_ROLE_PATTERN = re.compile(
    rf"ausbildung|auszubildend|{_B}azubi{_E}|duale[sm]? stud|dualstudium"
    rf"|werkstudent|praktikum|praktikant|studentische",
    re.IGNORECASE,
)


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


# ---------------------------------------------------------------------------
# Candidate dataset (michaelozon/candidate-matching-synthetic)
#
# A SYNTHETIC supply-side fixture: 10,000 resumes, 2,500 openings, 2,500 match
# records. Generated by an LLM with a 73-skill vocabulary and 24 role titles.
#
# Read this before wiring it to the German posting data: the two vocabularies
# barely intersect. Only 7 of its 73 skills have an equivalent in our German
# extraction, and those 7 appear in 3.3% of German IT postings. It carries no
# SAP, Azure, C#, .NET or embedded work -- which is most of the German market.
# Treat it as a standalone supply-side fixture for building and demoing the
# matcher, not as data that joins to German demand.
# ---------------------------------------------------------------------------

CANDIDATE_SENIORITY = {"Junior": "junior", "Mid": "mid", "Senior": "senior"}

CANDIDATE_EDUCATION_RANK = {
    "High School": 1, "BA": 2, "BSc": 2, "MSc": 3, "MBA": 3,
}

# Synthetic industries -> our market domains. Half have no equivalent; left as
# None rather than forced into a bucket they do not belong in.
CANDIDATE_INDUSTRY_TO_DOMAIN = {
    "FinTech": "Banking",
    "E-commerce": "Retail",
    "Retail": "Retail",
    "Healthcare": "Healthcare",
    "Logistics": "Logistics",
    "Cybersecurity": None,
    "EdTech": None,
    "Gaming": None,
    "SaaS": None,
    "Travel": None,
}

ROLE_FAMILIES = {
    "engineering": ["Backend Engineer", "Software Engineer", "Full Stack Engineer"],
    "data": ["BI Analyst", "Data Analyst"],
    "product": ["Product Manager", "Associate Product Manager", "Technical Product Manager"],
    "analysis": ["Business Analyst"],
    "finance": ["Financial Analyst", "FP&A Analyst", "Junior Accountant"],
    "marketing": ["Marketing Manager", "Content Marketer", "Performance Marketer"],
    "sales": ["Sales Representative", "Account Executive", "Business Development Manager"],
    "support": ["Technical Support Specialist", "Customer Support Specialist",
                "Customer Success Associate"],
    "delivery": ["Project Manager", "Program Coordinator", "Operations Manager"],
}
ROLE_TO_FAMILY = {r: fam for fam, roles in ROLE_FAMILIES.items() for r in roles}

TECH_ROLE_FAMILIES = {"engineering", "data"}
TECH_ROLES_EXTRA = {"Technical Product Manager", "Technical Support Specialist"}

SKILL_FAMILIES = {
    "engineering": ["OOP", "Databases", "Git", "Docker", "Python", "Unit Testing", "Java",
                    "JavaScript", "REST APIs", "CI/CD"],
    "data": ["SQL", "ETL", "Pandas", "Power BI", "Tableau", "Data Visualization", "Statistics",
             "Analytics", "Reporting", "KPIs", "Forecasting", "A/B Testing", "Excel"],
    "product": ["Product Strategy", "Roadmap", "PRD", "User Research", "Prioritization",
                "Agile", "Scrum", "Jira", "Asana"],
    "marketing": ["Content Marketing", "SEO", "Email Marketing", "Google Ads", "Meta Ads",
                  "Landing Pages", "Conversion Optimization", "Copywriting", "Lead Generation",
                  "Marketing Analytics"],
    "sales": ["Prospecting", "Closing", "Negotiation", "Account Management",
              "Pipeline Management", "Outbound Outreach", "CRM", "Discovery Calls"],
    "finance": ["Accounting", "Budgeting", "Cash Flow", "Financial Modeling", "Valuation",
                "Variance Analysis", "Risk Management"],
    "support": ["Ticketing", "Zendesk", "Intercom", "Escalations", "SLA", "Troubleshooting",
                "Customer Satisfaction", "Root Cause Analysis"],
    "delivery": ["Project Planning", "Timeline Management", "Process Improvement",
                 "Stakeholder Communication", "Stakeholder Management",
                 "Cross-functional Coordination", "Documentation", "Communication"],
}
SKILL_TO_FAMILY = {s: fam for fam, skills in SKILL_FAMILIES.items() for s in skills}

EXPERIENCE_BANDS = [(0, 2, "0-2 yrs"), (3, 5, "3-5 yrs"), (6, 8, "6-8 yrs"), (9, 99, "9+ yrs")]

# The documented ground-truth rule: a resume is "relevant" when it holds at least
# this share of a job's must-have skills.
MATCH_THRESHOLD = 0.6


# ---------------------------------------------------------------------------
# RoleAtom vocabulary (ALGORITHM.md 6 -- the integration contract)
#
# Both pipelines emit the same unit:
#   RoleAtom { role_family, tech_tags (subset of tech categories),
#              seniority, region }
#
# ROLE_FAMILY_PATTERNS is ordered; first hit wins. The fallback for an eligible
# IT posting that matches nothing specific is "dev" -- by construction these
# titles passed IT_ROLE_PATTERN, and unclassified IT work is most often
# development ("Fachinformatiker Anwendungsentwicklung").
# ---------------------------------------------------------------------------

ROLE_FAMILIES_ATOM = ["dev", "ops", "data", "security", "qa", "architect", "analyst", "support"]

ROLE_FAMILY_PATTERNS: list[tuple[str, str]] = [
    ("architect", r"architekt|architect"),
    ("security",  rf"{_B}security|cyber|informationssicherheit|{_B}it.sicherheit"
                  rf"|netzwerksicherheit|pentest|penetrationstest|{_B}siem{_E}|{_B}soc{_E}"),
    ("qa",        r"softwaretest|testautomat|testmanag|qa engineer|quality assurance"
                  r"|test.?(?:engineer|analyst)|{_B}tester"),
    ("data",      rf"data.?(?:engineer|scientist|analyst|architect)|datenanalyst"
                  rf"|dateningenieur|business intelligence|{_B}bi{_E}|machine learning"
                  rf"|{_B}ki{_E}|{_B}ai{_E}|{_B}etl{_E}|big data|datenbankentwickl"),
    ("support",   r"support|helpdesk|service.?desk|servicetechniker|anwenderbetreu"
                  r"|user help|hotline"),
    ("ops",       rf"administrator|{_B}admin{_E}|devops|sysop|systemintegration"
                  rf"|netzwerk|{_B}network|infrastruktur|rechenzentrum|platform engineer"
                  rf"|cloud engineer|site reliability|{_B}sre{_E}|systembetreu"),
    ("analyst",   r"consultant|berater|beratung|analyst|projektmanager|projektleit"
                  r"|product owner|scrum|requirements|prozessmanager|koordinator"
                  r"|projektkoordination|manager"),
    ("dev",       r"."),   # fallback -- see note above
]

ROLE_FAMILY_COMPILED = [(fam, re.compile(pat, re.IGNORECASE)) for fam, pat in ROLE_FAMILY_PATTERNS]

# Seniority ordering used by the match rule "candidate >= demand - 1".
# `entry` folds into junior; unknown stays None and the seniority test passes
# (a posting that states nothing must not auto-fail 70% of the market).
SENIORITY_RANK = {"entry": 0, "junior": 0, "mid": 1, "senior": 2, "lead": 3}


# ---------------------------------------------------------------------------
# Bench profile (ALGORITHM_PEOPLE.md 4, option B3)
#
# The bench is generated in the GERMAN tech vocabulary so Pipeline C is a join
# by construction. The profile is DELIBERATELY different from German demand --
# a bench that mirrored demand would match everything and the product would
# have nothing to say (the "trap in B3"). Shape: a Lithuanian nearshore
# consultancy strong in modern software delivery (language/backend/data/devops/
# cloud/quality), thin in security, nearly absent in SAP/erp, absent in
# embedded and mobile -- which are precisely large German demand categories.
# The gap IS the product's insight, and it shows up honestly in Serviceability.
#
# Family counts sum to the bench size (ALGORITHM_PEOPLE 11/P4: ~100-120
# specialists is LITIT's stated year-one scale).
# ---------------------------------------------------------------------------

BENCH_SIZE = 120
BENCH_SEED = 42          # deterministic: two runs must produce the same bench

# per family: headcount and P(tech_tag) draws
BENCH_PROFILE: dict[str, dict] = {
    "dev":       {"n": 44, "tech": [("language", 0.95), ("backend", 0.75), ("frontend", 0.45),
                                    ("devops", 0.35), ("cloud", 0.30), ("quality", 0.20)]},
    "data":      {"n": 20, "tech": [("data", 1.00), ("language", 0.60), ("cloud", 0.35),
                                    ("devops", 0.15)]},
    "ops":       {"n": 13, "tech": [("platform", 0.70), ("cloud", 0.60), ("devops", 0.55),
                                    ("network", 0.45)]},
    "qa":        {"n": 12, "tech": [("quality", 1.00), ("language", 0.40), ("devops", 0.25)]},
    "analyst":   {"n": 10, "tech": [("data", 0.60), ("erp", 0.25)]},
    "architect": {"n": 8,  "tech": [("cloud", 0.80), ("backend", 0.70), ("language", 0.60),
                                    ("security", 0.25)]},
    "support":   {"n": 7,  "tech": [("platform", 0.60), ("network", 0.40)]},
    "security":  {"n": 6,  "tech": [("security", 1.00), ("network", 0.50), ("cloud", 0.40)]},
}

BENCH_SENIORITY = [("junior", 0.28), ("mid", 0.40), ("senior", 0.26), ("lead", 0.06)]
BENCH_AVAILABILITY = [("now", 0.25), ("in_30d", 0.35), ("in_90d", 0.25), ("unavailable", 0.15)]
BENCH_GERMAN_RATE = 0.30      # German capability is a hard nearshore constraint
BENCH_REGIONS = [("LT011", 0.7), ("LT021", 0.2), ("remote_eu", 0.1)]   # Vilnius / Kaunas

# ---------------------------------------------------------------------------
# Bench commercials and engineering footprint.
#
# SIMULATED, and named `sim_` downstream so the prefix survives every join: the
# bench is synthetic, so these are properties of invented people. They are
# DISPLAY attributes only -- nothing in people.py or scoring.py reads them,
# because a generated number must never move a ranking.
#
# Coefficients are the ones calibrated for the retired simulation layer
# (simcoeff.py, commit ebcb272), kept rather than re-invented so the observed
# distributions in DATA.md still describe the output.
# ---------------------------------------------------------------------------

# GitHub stands in for a real GitHub user-API pull. It is applied to PEOPLE,
# not companies: for German mid-market employers a public presence is rare and
# uninformative, whereas for an individual consultant it is genuine evidence of
# competence -- but only in the families that actually publish code, which is
# why the rate collapses for analyst and support.
BENCH_GITHUB_PROFILE_RATE = {
    "dev": 0.78, "data": 0.58, "architect": 0.62, "ops": 0.48,
    "security": 0.44, "qa": 0.36, "analyst": 0.16, "support": 0.10,
}
BENCH_GITHUB_PROFILE_RATE_DEFAULT = 0.30
# Families where a public profile is weak evidence either way, so the UI shows
# "not a signal for this role" instead of an empty score that reads as a defect.
BENCH_GITHUB_RELEVANT = {"dev", "data", "architect", "ops", "security", "qa"}

BENCH_GITHUB_REPOS_MEDIAN = {"dev": 14, "data": 9, "architect": 11, "ops": 8,
                             "security": 7, "qa": 5, "analyst": 3, "support": 2}
BENCH_GITHUB_CONTRIB_MEDIAN = {"dev": 210, "data": 130, "architect": 120, "ops": 95,
                               "security": 70, "qa": 55, "analyst": 25, "support": 15}
# Heavy-tailed on purpose: most consultants have almost nothing public and a
# few have a great deal. A uniform draw would make the field useless as a
# discriminator, which is exactly how it behaves in reality.
BENCH_GITHUB_REPOS_SIGMA = 0.75
BENCH_GITHUB_CONTRIB_SIGMA = 0.95
BENCH_GITHUB_STARS_SIGMA = 1.9
BENCH_GITHUB_YEARS_FACTOR = 0.055     # per year of experience, compounding

# Lithuanian nearshore day rate charged to a German client, EUR.
BENCH_DAY_RATE = {"junior": 370, "mid": 490, "senior": 640, "lead": 810}
BENCH_RATE_SIGMA = 0.09
# German capability is chargeable: a consultant who can run client meetings in
# German commands a premium and unlocks work others cannot take.
BENCH_GERMAN_PREMIUM = 1.12
# Billable days in a year, for turning a day rate into an annual cost a client
# can compare against a salary.
BENCH_BILLABLE_DAYS_YEAR = 215

