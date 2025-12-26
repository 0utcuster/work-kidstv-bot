import datetime as dt


def parse_dt(s: str, default_time: str = "12:00") -> dt.datetime:
    """
    Принимает:
      - "YYYY-MM-DD HH:MM"
      - "YYYY-MM-DD"  -> подставит default_time (по умолчанию 12:00)

    Бросает ValueError только если вообще не похоже на дату.
    """
    s = (s or "").strip()

    # 1) Полный формат
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        pass

    # 2) Только дата -> добавляем время
    try:
        d = dt.datetime.strptime(s, "%Y-%m-%d").date()
        hh, mm = default_time.split(":")
        return dt.datetime(d.year, d.month, d.day, int(hh), int(mm))
    except ValueError:
        raise ValueError("Неверный формат. Нужно YYYY-MM-DD HH:MM или YYYY-MM-DD")