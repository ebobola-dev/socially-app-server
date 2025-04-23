import random
from datetime import datetime, timedelta, date

def generate_date(start_date = datetime(1990, 1, 1), end_date = datetime(2025, 1, 1)) -> date:
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
    delta = (end_date - start_date).days
    random_days = random.randint(0, delta)
    return (start_date + timedelta(days=random_days)).date()