from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re

# CREATE SCHEDULER
scheduler = BackgroundScheduler()

# REMINDER FUNCTION
def reminder_function(medicine, dose):
    """
    Function that runs when the reminder is triggered.
    """

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
        "8 pm"    -> (20, 0)
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

            parsed_time = datetime.strptime(
                time_string,
                fmt
            )

            return (
                parsed_time.hour,
                parsed_time.minute
            )

        except ValueError:
            continue

    raise ValueError(
        f"Could not understand time: {time_string}"
    )


# FREQUENCY PARSER
def parse_frequency(frequency_string):
    """
    Understand different frequency formats.

    Supported:

        daily
        every day
        everyday
        every night
        every morning
        every evening

        every Monday
        every Tuesday
        ...
        every Sunday

        next 3 days
        for the next 3 days

        next 4 months
        for the next 4 months
    """

    frequency = frequency_string.lower().strip()

    # DAILY
    daily_keywords = [
        "daily",
        "every day",
        "everyday",
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
        r"(?:for the\s+)?next\s+(\d+)\s+days?",
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


    # NEXT N MONTHS
    match = re.fullmatch(
        r"(?:for the\s+)?next\s+(\d+)\s+months?",
        frequency
    )

    if match:

        number_of_months = int(match.group(1))

        if number_of_months <= 0:

            raise ValueError(
                "Number of months must be greater than 0."
            )

        return {
            "type": "next_months",
            "months": number_of_months
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
def schedule_reminder(
    medicine,
    dose,
    time,
    frequency,
    reminder_id
):

    # PARSE TIME
    hour, minute = parse_time(time)


    # PARSE FREQUENCY
    parsed_frequency = parse_frequency(
        frequency
    )


    # STORE ALL JOB IDS
    job_ids = []


    # ==========================================
    # DAILY
    # ==========================================

    if parsed_frequency["type"] == "daily":

        job_id = f"{reminder_id}_daily"

        scheduler.add_job(
            reminder_function,
            "cron",
            id=job_id,
            hour=hour,
            minute=minute,
            args=[
                medicine,
                dose
            ],
            replace_existing=True,
        )

        job_ids.append(job_id)

        print(
            "\nDaily reminder scheduled!"
        )


    # ==========================================
    # WEEKDAY
    # ==========================================

    elif parsed_frequency["type"] == "weekday":

        day = parsed_frequency["day"]

        job_id = f"{reminder_id}_weekly"

        scheduler.add_job(
            reminder_function,
            "cron",
            id=job_id,
            day_of_week=day,
            hour=hour,
            minute=minute,
            args=[
                medicine,
                dose
            ],
            replace_existing=True,
        )

        job_ids.append(job_id)

        print(
            "\nWeekly reminder scheduled!"
        )


    # ==========================================
    # NEXT N DAYS
    # ==========================================

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


            # If today's reminder time has already passed,
            # move it to tomorrow.
            if reminder_time <= now:

                reminder_time += timedelta(
                    days=1
                )


            # Create unique job ID
            job_id = f"{reminder_id}_day_{day}"


            scheduler.add_job(
                reminder_function,
                "date",
                id=job_id,
                run_date=reminder_time,
                args=[
                    medicine,
                    dose
                ],
                replace_existing=True,
            )


            # Store job ID
            job_ids.append(job_id)


        print(
            f"\nReminder scheduled for the next "
            f"{number_of_days} days!"
        )


    # ==========================================
    # NEXT N MONTHS
    # ==========================================

    elif parsed_frequency["type"] == "next_months":

        number_of_months = parsed_frequency["months"]

        now = datetime.now()


        start_time = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )


        # If today's reminder time has already passed,
        # start tomorrow.
        if start_time <= now:

            start_time += timedelta(
                days=1
            )


        end_time = now + relativedelta(
            months=number_of_months
        )


        job_id = f"{reminder_id}_monthly"


        scheduler.add_job(
            reminder_function,
            "cron",
            id=job_id,
            hour=hour,
            minute=minute,
            start_date=start_time,
            end_date=end_time,
            args=[
                medicine,
                dose
            ],
            replace_existing=True,
        )


        job_ids.append(job_id)


        print(
            f"\nReminder scheduled daily for the next "
            f"{number_of_months} months!"
        )


    # ==========================================
    # DISPLAY DETAILS
    # ==========================================

    print(
        "------------------------------"
    )

    print(
        f"Medicine : {medicine}"
    )

    print(
        f"Dose     : {dose}"
    )

    print(
        f"Time     : {hour:02d}:{minute:02d}"
    )

    print(
        f"Frequency: {frequency}"
    )

    print(
        f"Job IDs  : {job_ids}"
    )

    print(
        "------------------------------"
    )


    # ==========================================
    # RETURN RESULT
    # ==========================================

    return {
        "scheduled": True,
        "reminder_id": reminder_id,
        "job_ids": job_ids,
        "medicine": medicine,
        "dose": dose,
        "time": time,
        "frequency": frequency
    }


# ==========================================
# TEST CASE
# ==========================================

if __name__ == "__main__":

    # Start scheduler
    start_scheduler()


    # Test reminder
    schedule_reminder(
        medicine="heart",
        dose="not specified",
        time="10:15 pm",
        frequency="Everyday",
        reminder_id="test-reminder-1"
    )


    print(
        "\nScheduler is running..."
    )

    print(
        "Press Ctrl+C to stop."
    )


    try:

        while True:
            pass

    except KeyboardInterrupt:

        stop_scheduler()
