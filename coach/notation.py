"""Display encoding for MuseScore's native Roman-numeral font."""
import re


def roman_components(roman):
    match = re.fullmatch(r"([ivIV]+[°ø]?)([0-9](?:/[0-9])?)?", roman)
    if not match:
        return roman, ()
    symbol, figures = match.groups()
    return symbol, tuple((figures or "").split("/")) if figures else ()


def campania_text(roman):
    """Campania shapes consecutive digits as small, vertically stacked figures."""
    symbol, figures = roman_components(roman)
    return symbol.replace("°", "o").replace("ø", "0") + "".join(figures)
