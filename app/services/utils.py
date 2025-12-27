import datetime as dt


def parse_dt(s: str) -> dt.datetime:
    """
    Принимает:
      - 'YYYY-MM-DD HH:MM'
      - 'YYYY-MM-DD'  (тогда ставим 00:00, чтобы "время не показывать")
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("Пустая дата")

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = dt.datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d":
                d = d.replace(hour=0, minute=0)
            return d
        except ValueError:
            pass

    raise ValueError("Неверный формат даты. Нужно: YYYY-MM-DD HH:MM или YYYY-MM-DD")