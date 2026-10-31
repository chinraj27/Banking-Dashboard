def mask_number(number: str | None, group: int = 4) -> str | None:
    """Mask everything except the last four characters: '4111222233334444' -> '**** **** **** 4444'."""
    if not number:
        return None
    digits = "".join(ch for ch in number if ch.isalnum())
    last4 = digits[-4:]
    hidden = max(len(digits) - 4, 0)
    stars = "*" * hidden
    groups = [stars[i : i + group] for i in range(0, hidden, group)]
    return " ".join([*groups, last4])
