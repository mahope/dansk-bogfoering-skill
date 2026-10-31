"""Genkend leverandør ud fra banktekst eller fakturatekst, og gæt leverandørens momsland.

VENDORS: (banktekst-regex, navn, fakturatekst-regex). Listen er et startpunkt med udbredte leverandører.
Tilføj jeres egne leverandører her, ikke i reglerne, og kør derefter laer.py.
"""
import re

import config

_CFG = config.load()
# Egen CVR (køberen) står på alle fakturaer til jer og må ikke tolkes som sælgers momsnummer.
EGET_CVR = _CFG["virksomhed"]["cvr"]

VENDORS = [
    (r"OPENAI|CHATGPT", "OpenAI", r"openai"),
    (r"ANTHROPIC|CLAUDE\.AI", "Anthropic", r"anthropic"),
    (r"CURSOR", "Cursor", r"cursor|anysphere"),
    (r"OBSIDIAN", "Obsidian", r"obsidian"),
    (r"GOOGLE\*ADS", "Google Ads", r"google ads|google ireland"),
    (r"Google Play|WL\*GOOGLE|GOOGLE \*Google Play", "Google Play", r"google play|google commerce"),
    (r"OPENROUTER", "OpenRouter", r"openrouter"),
    (r"F-SECURE", "F-Secure", r"f-secure"),
    (r"GOOGLE\*CHROME", "Chrome Web Store", r"chrome web"),
    (r"Google CLOUD", "Google Cloud", r"google cloud"),
    (r"Punktum", "Punktum.dk", r"punktum"),
    (r"HETZNER", "Hetzner", r"hetzner"),
    (r"CANVA", "Canva", r"canva"),
    (r"ATLASSIAN", "Atlassian", r"atlassian"),
    (r"ELEVENLABS", "ElevenLabs", r"eleven ?labs"),
    (r"COOKIEYES", "CookieYes", r"cookieyes"),
    (r"PADDLE", "Paddle", r"paddle"),
    (r"ELEMENTOR", "Elementor", r"elementor"),
    (r"SKATTEKONTOEN|^SKAT\b", "SKAT", r"skattestyrelsen"),
    (r"Gldsstyrelsen|Gældsstyrelsen", "Gældsstyrelsen", r"gældsstyrelsen"),
    (r"CLOUDFLARE", "Cloudflare", r"cloudflare"),
    (r"MIDJOURNEY", "Midjourney", r"midjourney"),
    (r"SENTRY", "Sentry", r"sentry|functional software"),
    (r"GITHUB", "GitHub", r"github"),
    (r"CODERABBIT", "CodeRabbit", r"coderabbit"),
    (r"MICROSOFT", "Microsoft", r"microsoft"),
    (r"REMA 1000", "Rema 1000", r"rema 1000"),
    (r"APPLE\.COM", "Apple", r"apple distribution|apple\.com"),
    (r"hostinger", "Hostinger", r"hostinger"),
    (r"RESEND", "Resend", r"resend"),
    (r"WOOCOMMERCE", "WooCommerce", r"woocommerce|automattic"),
    (r"DSB", "DSB", r"dsb\.dk|kvittering fra DSB"),
    (r"REJSEKORT", "Rejsekort", r"rejsekort"),
    (r"ENVATO", "Envato", r"envato"),
    (r"BACKBLAZE", "Backblaze", r"backblaze"),
    (r"MOB\.PAY\*DSB|DSB/7-11", "DSB", r"(?!x)x"),
    (r"MOB\.PAY|MobilePay", "MobilePay-betaling", r"(?!x)x"),
    (r"RESTAURANT", "Restaurant", r"(?!x)x"),
    (r"NETTO|LIDL|FØTEX|FOTEX|BILKA|COOP|7-ELEVEN", "Dagligvarer", r"netto a/s|salling group|lidl danmark|7-eleven"),
]

_B = [(re.compile(b, re.I), n) for b, n, _ in VENDORS]
_T = [(re.compile(t, re.I), n) for _, n, t in VENDORS]

# Bankposter, der ikke er leverandørudgifter. Skal aldrig konteres som regning.
IKKE_REGNING = [
    # Eksempel: en bank, der automatisk fordeler en andel af hver indbetaling til en moms- og skattekonto. Tilpas til jeres bank.
    (re.compile(r"^Income sorter$", re.I), "moms-/skatteoverførsel", "Bankens automatiske fordeling af kundeindbetalinger til moms- og skattekonto. Overførsel mellem egne konti."),
    # OBS: "Transfer" er IKKE med: en bankoverførsel kan være en udgift (fx en bogholders faktura betalt som 'Transfer').
    (re.compile(r"^Udtræk", re.I), "privat hævning", "Hævning til privat — bogføres som privat hævning, ikke som udgift."),
    (re.compile(r"SKATTEKONTOEN|^SKAT\b|Gldsstyrelsen|Gældsstyrelsen", re.I), "skat", "Betaling til skattekontoen (B-skat/restskat/moms). Ikke en driftsudgift."),
    (re.compile(r"^STRIPE [A-Z0-9]{6}$", re.I), "indtægt", "Stripe-udbetaling = indtægt fra salg, ikke regning."),
]


def fra_banktekst(tekst):
    for rx, n in _B:
        if rx.search(tekst or ""):
            return n
    return None


def fra_fakturatekst(tekst):
    """Sælgeren står næsten altid i fakturaens hoved. Søg først i de første 400 tegn,
    derefter i hele teksten; ved flere træf vinder den, der nævnes tidligst."""
    t = tekst or ""
    for vindue in (t[:400], t):
        hits = []
        for rx, n in _T:
            m = rx.search(vindue)
            if m:
                hits.append((m.start(), n))
        if hits:
            return min(hits)[1]
    return None


# Leverandører, der optræder under forskellige navne i bank og faktura (forhandler/Merchant of Record).
# Eksempel: et abonnement købt via Google Play står som Google Play i banken, men som F-Secure på fakturaen.
ALIASER = [{"Google Play", "F-Secure"}, {"Paddle", "Elementor"}]


def samme_leverandoer(a, b):
    return a == b or any(a in g and b in g for g in ALIASER)


# Momsækvivalens: koder i samme gruppe giver samme momsbeløb (men evt. anden rubrik på momsangivelsen).
MOMS_GRUPPE = {"K": "dansk 25 %", "KR": "repræsentation", "KF": "momsfri",
               "KYE": "omvendt betalingspligt", "KVE": "omvendt betalingspligt",
               "KYU": "omvendt betalingspligt", "KVU": "omvendt betalingspligt", "KOB": "omvendt betalingspligt"}
# Udgiftskonti med fuldt, straks fradrag. Udstyr (afskrives) og momskonto er særlige (kontonumre i config billy_konti).
SAERLIGE_KONTI = {_CFG["billy_konti"]["udstyr"], _CFG["billy_konti"]["momskonto"]}


def ikke_regning(tekst):
    for rx, kind, why in IKKE_REGNING:
        if rx.search((tekst or "").strip()):
            return kind, why
    return None


EU = "AT BE BG CY CZ DE EE EL ES FI FR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split()


def momsland(tekst, eget_cvr=None):
    """Gæt sælgers momsland ud fra fakturatekst. Returnerer 'DK', 'EU', 'UDLAND' eller None.

    Eget CVR (køberen, config virksomhed.cvr) ignoreres, så udenlandske fakturaer med 'DK VAT DK<eget CVR>'
    ikke tolkes som danske.
    """
    t = tekst or ""
    cvr = EGET_CVR if eget_cvr is None else eget_cvr
    if cvr:
        t = t.replace(cvr, "")
    # EU-momsnumre: landekode + cifre UDEN mellemrum (fx IE6388047V, DE123456789), eller med 'VAT'/'USt' lige foran.
    # Svenske momsnumre er SE + 10 cifre + '01' — så et dansk 'SE 12345678' (SE-nummer) tæller ikke.
    for cc in EU:
        if cc == "SE":
            if re.search(r"\bSE\d{10}01\b", t):
                return "EU"
            continue
        if re.search(rf"\b{cc}\d[\dA-Z]{{6,11}}\b", t) or re.search(rf"(?:VAT|USt|TVA|BTW|IVA|Momsnummer|Momsnr|CVR)[^.\n]{{0,25}}\b{cc} ?\d[\dA-Z]{{6,11}}\b", t):
            return "EU"
    if re.search(r"\b(CVR|SE)[- .:nr]*\d{8}\b|\bDK ?\d{8}\b", t) and re.search(r"moms|25 ?%", t, re.I):
        return "DK"
    if re.search(r"United States|USA|\bInc\.|LLC|Singapore|PTE\. LTD|Canada|Australia|United Kingdom|GB ?\d{9}", t):
        return "UDLAND"
    if re.search(r"Danmark|Denmark", t) and re.search(r"moms", t, re.I):
        return "DK"
    return None
