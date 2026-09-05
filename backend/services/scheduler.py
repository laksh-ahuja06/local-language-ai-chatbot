from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import re


# Create scheduler
scheduler = BackgroundScheduler()


# REMINDER FUNCTION
def reminder_function(medicine, dose):
    print("\n==============================")
    print("💊 MEDICINE REMINDER")
    print(f"Medicine: {medicine}")
    print(f"Dose: {dose}")
    print(f"Time: {datetime.now().strftime('%I:%M %p')}")
    print("==============================\n")


# TIME PARSER
def parse_time(time_string):
    """
    Convert human-readable time into hour and minute.

    Examples:
        "8:00 PM" -> (20, 0)
        "8 PM"    -> (20, 0)
        "20:00"   -> (20, 0)
    """
    time_string = time_string.strip().upper()
    formats = [
        "%I:%M %p",
        "%I %p",
        "%H:%M",
    ]
    for fmt in formats:
        try:
            parsed_time = datetime.strptime(time_string, fmt)
            return parsed_time.hour, parsed_time.minute
        except ValueError:
            continue
    raise ValueError(
        f"Could not understand time: {time_string}"
    )

# FREQUENCY PARSER
def parse_frequency(frequency_string):
    """
    Understand different frequency formats.

    Examples:
        "daily"
        "every day"
        "every Thursday"
        "next 3 days"
    """

    frequency = frequency_string.lower().strip()

    # DAILY
    daily_keywords = [
        "daily",
        "every day",
        "every night",
        "every morning",
        "every evening",
    ]

    if frequency in daily_keywords:
        return {
            "type": "daily"
        }

    # WEEKDAY
    weekdays = {
        "monday": "mon",
        "tuesday": "tue",
        "wednesday": "wed",
        "thursday": "thu",
        "friday": "fri",
        "saturday": "sat",
        "sunday": "sun",
    }

    for day, scheduler_day in weekdays.items():

        if frequency == f"every {day}":

            return {
                "type": "weekday",
                "day": scheduler_day
            }

    # NEXT N DAYS
    match = re.fullmatch(
        r"next\s+(\d+)\s+days?",
        frequency
    )

    if match:
        number_of_days = int(match.group(1))
        if number_of_days <= 0:
            raise ValueError(
                "Number of days must be greater than 0."
            )
        return {
            "type": "next_days",
            "days": number_of_days
        }

    # UNKNOWN FREQUENCY
    raise ValueError(
        f"Could not understand frequency: {frequency_string}"
    )


# START SCHEDULER
def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        print("Scheduler started.")


# STOP SCHEDULER
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("Scheduler stopped.")


# SCHEDULE REMINDER
def schedule_reminder(medicine, dose, time, frequency):
    # Parse time
    hour, minute = parse_time(time)
    # Parse frequency
    parsed_frequency = parse_frequency(frequency)

    # DAILY
    if parsed_frequency["type"] == "daily":
        scheduler.add_job(
            reminder_function,
            "cron",
            hour=hour,
            minute=minute,
            args=[medicine, dose],
        )
        print("\nDaily reminder scheduled!")

    # WEEKDAY
    elif parsed_frequency["type"] == "weekday":
        day = parsed_frequency["day"]
        scheduler.add_job(
            reminder_function,
            "cron",
            day_of_week=day,
            hour=hour,
            minute=minute,
            args=[medicine, dose],
        )

        print("\nWeekly reminder scheduled!")

    # NEXT N DAYS
    elif parsed_frequency["type"] == "next_days":
        number_of_days = parsed_frequency["days"]
        now = datetime.now()
        for day in range(number_of_days):
            reminder_time = now.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0
            ) + timedelta(days=day)

            # Don't schedule a time that has already passed today
            if reminder_time <= now:
                reminder_time += timedelta(days=1)

            scheduler.add_job(
                reminder_function,
                "date",
                run_date=reminder_time,
                args=[medicine, dose],
            )

        print(
            f"\nReminder scheduled for the next "
            f"{number_of_days} days!"
        )

    # DISPLAY DETAILS
    print("------------------------------")
    print(f"Medicine : {medicine}")
    print(f"Dose     : {dose}")
    print(f"Time     : {hour:02d}:{minute:02d}")
    print(f"Frequency: {frequency}")
    print("------------------------------")

    return {
            "scheduled": True,
            "medicine": medicine,
            "dose": dose,
            "time": time,
            "frequency": frequency
        }

# testing function
# schedule_reminder ("paracetamol", "1 tablet", "8:00 AM", "every wednesday")
