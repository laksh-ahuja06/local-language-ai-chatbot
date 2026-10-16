from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re
import subprocess

# CREATE SCHEDULER
scheduler = BackgroundScheduler()

# MAC NOTIFICATION
def send_mac_notification(title, message, subtitle=""):
    """
    Show a native macOS notification using AppleScript.
    """

    # Escape characters that would break the AppleScript string
    def escape(text):
        return str(text).replace("\\", "\\\\").replace('"', '\\"')

    script = (
        f'display notification "{escape(message)}" '
        f'with title "{escape(title)}" '
        f'subtitle "{escape(subtitle)}" '
        f'sound name "Glass"'
    )

    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True
        )

    except Exception as e:
        print("Could not send Mac notification:", e)


# REMINDER FUNCTION
def reminder_function(medicine, dose):
    """
    Function that runs when the reminder is triggered.
    """

    current_time = datetime.now().strftime('%I:%M %p')

    print("\n==============================")
    print("💊 MEDICINE REMINDER")
    print(f"Medicine: {medicine}")
    print(f"Dose: {dose}")
    print(f"Time: {current_time}")
    print("==============================\n")

    send_mac_notification(
        title="MEDICINE REMINDER 💊💊",
        subtitle=f"It's {current_time}!!",
        message=f"Take {dose} of {medicine} right now"
    )


# TIME PARSER
def parse_time(time_string):
    """
    Convert different human-readable time formats
    into hour and minute.

    Examples:

        "8:00 PM"  -> (20, 0)
        "8 PM"     -> (20, 0)
        "8 pm"     -> (20, 0)
        "8 P.M."   -> (20, 0)
        "8:00 P.M."-> (20, 0)
        "20:00"    -> (20, 0)
    """

    time_string = time_string.strip().upper()

    # Remove periods from AM/PM
    # "P.M." -> "PM"
    # "A.M." -> "AM"
    time_string = time_string.replace(".", "")

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
    reminder_id,
    start=None
):
    """
    start: when the reminder was created (MongoDB created_at).
    "next N days/months" are counted from this moment, so rebuilding
    jobs after a restart does not push the end date further out.
    """

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

        created = start or datetime.now()


        # First reminder: the reminder time on the creation day,
        # or the next day if that time had already passed.
        first_time = created.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )

        if first_time <= created:

            first_time += timedelta(
                days=1
            )


        # One daily job that stops after N reminders
        last_time = first_time + timedelta(
            days=number_of_days - 1
        )


        if last_time < datetime.now():

            print(
                f"\nReminder {reminder_id} has finished "
                f"(last reminder was {last_time}). Not scheduled."
            )

        else:

            job_id = f"{reminder_id}_days"

            scheduler.add_job(
                reminder_function,
                "cron",
                id=job_id,
                hour=hour,
                minute=minute,
                start_date=first_time,
                end_date=last_time,
                args=[
                    medicine,
                    dose
                ],
                replace_existing=True,
            )

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

        created = start or datetime.now()


        start_time = created.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )


        # If the reminder time had already passed on the
        # creation day, start the next day.
        if start_time <= created:

            start_time += timedelta(
                days=1
            )


        end_time = created + relativedelta(
            months=number_of_months
        )


        if end_time < datetime.now():

            print(
                f"\nReminder {reminder_id} has finished "
                f"(ended {end_time}). Not scheduled."
            )

        else:

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
# MONGODB IS THE SOURCE OF TRUTH
# ==========================================
#
# Jobs are only ever built from reminders stored in MongoDB.
# On start-up and every SYNC_INTERVAL_SECONDS the scheduler is
# reconciled with the database:
#   - active reminders without jobs get scheduled
#   - reminders that were edited get rescheduled
#   - reminders that were deleted or made inactive lose their jobs

SYNC_JOB_ID = "__sync_with_mongodb__"
SYNC_INTERVAL_SECONDS = 60

# reminder_id -> the fields its jobs were built from (to detect edits)
scheduled_reminders = {}


def reminder_fingerprint(reminder):
    return (
        reminder.get("medicine"),
        reminder.get("dose"),
        reminder.get("time"),
        reminder.get("frequency"),
        str(reminder.get("created_at")),
    )


def is_active(reminder):
    # Reminders saved before "status" existed count as active
    return reminder.get("status", "active") == "active"


def unschedule_reminder(reminder_id):
    """Remove every job that belongs to this reminder."""

    prefix = f"{reminder_id}_"

    for job in scheduler.get_jobs():

        if job.id.startswith(prefix):

            scheduler.remove_job(job.id)
            print(f"Scheduler job removed: {job.id}")

    scheduled_reminders.pop(reminder_id, None)


def schedule_from_database(reminder):
    """(Re)build the jobs for one MongoDB reminder document."""

    from services.connectToMongoDB import update_job_ids

    reminder_id = str(reminder["_id"])

    unschedule_reminder(reminder_id)

    result = schedule_reminder(
        medicine=reminder["medicine"],
        dose=reminder["dose"],
        time=reminder["time"],
        frequency=reminder["frequency"],
        reminder_id=reminder_id,
        start=reminder.get("created_at"),
    )

    scheduled_reminders[reminder_id] = reminder_fingerprint(reminder)

    if reminder.get("job_ids") != result["job_ids"]:
        update_job_ids(reminder_id, result["job_ids"])

    return result


def schedule_reminder_by_id(reminder_id):
    """Schedule a reminder exactly as it is stored in MongoDB."""

    from services.connectToMongoDB import get_reminders

    reminder = next(
        (r for r in get_reminders() if r["_id"] == str(reminder_id)),
        None
    )

    if reminder is None:
        raise ValueError(f"Reminder {reminder_id} is not in the database")

    return schedule_from_database(reminder)


def sync_with_database():
    """Make the scheduler's jobs match the reminders in MongoDB."""

    from services.connectToMongoDB import get_reminders

    try:
        reminders = get_reminders()

    except Exception as e:
        # Keep the current jobs if MongoDB is briefly unreachable
        print("Scheduler sync skipped, MongoDB not reachable:", e)
        return

    active = {r["_id"]: r for r in reminders if is_active(r)}

    # Remove jobs of reminders that were deleted or made inactive
    for reminder_id in list(scheduled_reminders):

        if reminder_id not in active:
            unschedule_reminder(reminder_id)

    # Schedule new reminders and reschedule edited ones
    for reminder_id, reminder in active.items():

        if scheduled_reminders.get(reminder_id) == reminder_fingerprint(reminder):
            continue

        try:
            schedule_from_database(reminder)

        except Exception as e:
            # One bad document must not stop the others
            print(f"Could not schedule reminder {reminder_id}:", e)


def start_database_sync():
    """Build all jobs from MongoDB now, then keep them in sync."""

    start_scheduler()

    sync_with_database()

    scheduler.add_job(
        sync_with_database,
        "interval",
        id=SYNC_JOB_ID,
        seconds=SYNC_INTERVAL_SECONDS,
        replace_existing=True,
    )

    print(
        f"Scheduler synced with MongoDB "
        f"({len(scheduled_reminders)} reminders); "
        f"re-syncing every {SYNC_INTERVAL_SECONDS}s."
    )


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
