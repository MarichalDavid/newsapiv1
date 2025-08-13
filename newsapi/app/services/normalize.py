from dateutil import parser, tz
from dateutil.parser import UnknownTimezoneWarning
import warnings
from typing import Optional

# Abréviations courantes -> tz réelles
TZINFOS = {
    "UTC": tz.gettz("UTC"), "GMT": tz.gettz("UTC"),
    "BST": tz.gettz("Europe/London"),
    "CET": tz.gettz("Europe/Paris"), "CEST": tz.gettz("Europe/Paris"),
    "EET": tz.gettz("Europe/Bucharest"), "EEST": tz.gettz("Europe/Bucharest"),
    "EST": tz.gettz("US/Eastern"), "EDT": tz.gettz("US/Eastern"),
    "CST": tz.gettz("US/Central"), "CDT": tz.gettz("US/Central"),
    "MST": tz.gettz("US/Mountain"), "MDT": tz.gettz("US/Mountain"),
    "PST": tz.gettz("US/Pacific"), "PDT": tz.gettz("US/Pacific"),
    "JST": tz.gettz("Asia/Tokyo"),
    "IST": tz.gettz("Asia/Kolkata"),
}

def to_utc_naive(dt_str: Optional[str]):
    """Parse une date en entrée et renvoie un datetime en UTC *sans tzinfo* (naïf)."""
    if not dt_str:
        return None
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UnknownTimezoneWarning)
            dt = parser.parse(dt_str, tzinfos=TZINFOS)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=tz.UTC)
        # UTC aware -> UTC naive (pour TIMESTAMP WITHOUT TIME ZONE)
        return dt.astimezone(tz.UTC).replace(tzinfo=None)
    except Exception:
        return None

def guess_lang(text: str) -> str:
    try:
        from langdetect import detect
        return detect(text) if text else None
    except Exception:
        return None
