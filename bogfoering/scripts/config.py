"""Konfiguration til bogføringsskillet.

Config-filen ligger som standard i ~/.bogfoering/config.json og kan flyttes med miljøvariablen
BOGFOERING_CONFIG. Findes filen ikke, bruges standardværdierne (token skal så komme fra miljøet).
Config læses hver gang load() kaldes, så miljøvariablen altid gælder.

Felter (se config.example.json):
  virksomhed            {"navn", "cvr"}. CVR bruges til at ignorere egen CVR, når sælgers momsland gættes.
  tilstand_mappe        Hvor regler, skyggelog, cache og backups ligger. Standard ~/.bogfoering
  billy_token_fil       Valgfri sti til en env-fil med linjen BILLY_API_TOKEN=... (miljøvariablen vinder).
  bank                  {"data_mappe": mappe med bank-JSON, "konti": {"<Billy-kontonr>": "<kontoens slutcifre>"}}
  billy_konti           Kontonumre i jeres kontoplan: momskonto, udstyr (afskrives), småanskaffelser (straksafskrives)
                        og restaurant (repræsentation).
  skyggedrift_markoer   Fil, der spærrer skrivning til Billy, så længe den findes. Standard <tilstand_mappe>/SKYGGEDRIFT

Tokenet printes aldrig.
"""
import json
import os

STANDARD_CONFIG = "~/.bogfoering/config.json"


def standard():
    return {
        "virksomhed": {"navn": "", "cvr": ""},
        "tilstand_mappe": "~/.bogfoering",
        "billy_token_fil": None,
        "bank": {"data_mappe": None, "konti": {}},
        "billy_konti": {"momskonto": "5715", "udstyr": "1880", "restaurant": "1660", "smaaanskaffelser": "1840"},
        "skyggedrift_markoer": None,
    }


def config_sti():
    return os.path.expanduser(os.environ.get("BOGFOERING_CONFIG") or STANDARD_CONFIG)


def _sti(p):
    return os.path.abspath(os.path.expanduser(p)) if p else None


def load(sti=None):
    """Returnér konfigurationen med standardværdier udfyldt og stier udvidet. Manglende fil = standardværdier."""
    cfg = standard()
    sti = sti or config_sti()
    if os.path.exists(sti):
        try:
            with open(sti, encoding="utf-8") as fh:
                user = json.load(fh)
        except (OSError, ValueError) as e:
            raise SystemExit(f"Kan ikke læse config {sti}: {type(e).__name__}")
        if not isinstance(user, dict):
            raise SystemExit(f"Config {sti} skal være et JSON-objekt")
        for k, v in user.items():
            if k.startswith("_"):
                continue  # kommentarfelter
            if k in ("virksomhed", "bank", "billy_konti") and isinstance(v, dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    cfg["tilstand_mappe"] = _sti(cfg["tilstand_mappe"])
    cfg["billy_token_fil"] = _sti(cfg["billy_token_fil"])
    cfg["bank"]["data_mappe"] = _sti(cfg["bank"]["data_mappe"]) or os.path.join(cfg["tilstand_mappe"], "bank")
    cfg["skyggedrift_markoer"] = _sti(cfg["skyggedrift_markoer"]) or os.path.join(cfg["tilstand_mappe"], "SKYGGEDRIFT")
    cfg["bank"]["konti"] = {str(k): str(v) for k, v in (cfg["bank"].get("konti") or {}).items()}
    return cfg


def token(cfg=None):
    """BILLY_API_TOKEN fra miljøet, ellers fra billy_token_fil. Fejler tydeligt og printer aldrig tokenet."""
    t = os.environ.get("BILLY_API_TOKEN", "").strip()
    if t:
        return t
    cfg = cfg or load()
    fil = cfg.get("billy_token_fil")
    if fil:
        try:
            with open(fil, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if line.startswith("BILLY_API_TOKEN="):
                        t = line.split("=", 1)[1].strip().strip("\"'")
                        if t:
                            return t
        except OSError:
            raise SystemExit(f"Kan ikke læse billy_token_fil ({fil})")
        raise SystemExit(f"BILLY_API_TOKEN findes ikke i {fil}")
    raise SystemExit("Ingen Billy-token: sæt miljøvariablen BILLY_API_TOKEN eller 'billy_token_fil' i " + config_sti())
