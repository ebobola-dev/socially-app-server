# % Я вообще без понятия куда это пихать


def parse_short_flag(query: dict[str, str]) -> bool:
    raw = query.get("short", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
