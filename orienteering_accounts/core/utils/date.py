from datetime import date, timedelta


def get_last_date_of_previous_month() -> date:
    today = date.today()
    first_day_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    return last_day_of_previous_month
