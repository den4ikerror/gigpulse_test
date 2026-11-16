import re


def parse_budget_amount(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"\d[\d\s.,]*", value.replace("\u00a0", " "))
    if not match:
        return None
    number = match.group().replace(" ", "")
    if "," in number and "." in number:
        decimal_separator = "," if number.rfind(",") > number.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        number = number.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in number:
        parts = number.split(",")
        number = "".join(parts) if len(parts[-1]) == 3 else ".".join(parts)
    elif "." in number:
        parts = number.split(".")
        number = "".join(parts) if len(parts[-1]) == 3 else number
    try:
        return float(number)
    except ValueError:
        return None


def matches_order_filter(
    title: str,
    summary: str,
    budget: str | None,
    min_budget: float = 0,
    keywords: str | None = None,
) -> bool:
    if min_budget:
        amount = parse_budget_amount(budget)
        if amount is None or amount < min_budget:
            return False
    terms = [term.strip().casefold() for term in (keywords or "").split(",") if term.strip()]
    if terms:
        text = f"{title}\n{summary}".casefold()
        return any(term in text for term in terms)
    return True
