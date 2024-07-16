from datetime import datetime
import pytz


def get_current_time_in_almaty_naive():
    almaty_tz = pytz.timezone("Asia/Almaty")
    current_time_almaty = datetime.now(almaty_tz)
    naive_time = current_time_almaty.replace(tzinfo=None)
    return naive_time
