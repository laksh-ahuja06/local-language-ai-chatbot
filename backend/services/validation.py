import re

from services.scheduler import parse_time, parse_frequency

# Default values used when Qwen leaves a field out
DEFAULT_MEDICINE = "medicine"
DEFAULT_DOSE = "1 tablet"
DEFAULT_TIME = "9:00 PM"
DEFAULT_FREQUENCY = "daily"

# Words Qwen uses for a time of day -> a time the scheduler understands
TIME_WORDS = {
    "morning": "8:00 AM",
    "afternoon": "2:00 PM",
    "evening": "6:00 PM",
    "night": "9:00 PM",
    "bedtime": "10:00 PM",
}

# Other ways Qwen says "every day" -> "daily"
DAILY_WORDS = [
    "once a day",
    "once daily",
    "every 24 hours",
    "each day",
    "per day",
    "a day",
    "day",
]


def to_text(value):
    """
    Turn whatever Qwen returned into a clean string.
    Handles None, numbers and lists (e.g. dose: 500).
    """

    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(str(v) for v in value)

    return str(value).strip()


def normalize_time(time):
    """Map words like "night" to a clock time."""

    return TIME_WORDS.get(time.lower(), time)


# A clock time written in the (translated) sentence:
#   "7:30 p.m.", "07:30", "9 am", "8.15 pm"  (minutes and am/pm are optional, but one of them must be there)
CLOCK_TIME_PATTERN = re.compile(
    r"\b(\d{1,2})(?:[:.]\s?(\d{2}))?\s*(a\.?\s?m\.?|p\.?\s?m\.?)?(?![\w:])",
    re.IGNORECASE,
)

# Words that say whether a time without am/pm is in the morning or later in the day
PM_WORDS = ("afternoon", "evening", "night", "tonight", "bedtime", "dinner")
AM_WORDS = ("morning", "breakfast")


def time_from_sentence(sentence):
    """
    Read an explicit clock time from the translated sentence, e.g.
    "at 07:30 in the evening" -> "7:30 PM", "Remind me of 08:03" -> "8:03 AM".
    Returns "" if the sentence has no clock time.
    """

    text = sentence.lower()

    for match in CLOCK_TIME_PATTERN.finditer(text):

        hour = int(match.group(1))
        minute = match.group(2)
        period = match.group(3)

        # A bare number ("500 mg", "for 3 days") is not a time
        if minute is None and period is None:
            continue

        minute = int(minute) if minute else 0

        if hour > 23 or minute > 59:
            continue

        if period:
            period = "PM" if period.startswith("p") else "AM"

        elif hour <= 12:
            if any(word in text for word in PM_WORDS):
                period = "PM"
            elif any(word in text for word in AM_WORDS):
                period = "AM"

        if period and 1 <= hour <= 12:
            return f"{hour}:{minute:02d} {period}"

        # 24-hour time ("20:00") or no hint at all ("08:03"): read it as 24-hour,
        # then write it in the same 12-hour form as above ("8:00 PM", "8:03 AM")
        return f"{hour % 12 or 12}:{minute:02d} {'PM' if hour >= 12 else 'AM'}"

    return ""


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

# "next 3 days", "for the next three months", ...
NEXT_N_PATTERN = re.compile(
    r"next\s+(\d+|" + "|".join(NUMBER_WORDS) + r")\s+(day|month)s?"
)


def rule_based_frequency(frequency, sentence):
    """
    Work out the frequency with simple rules instead of trusting Qwen.
    Looks at Qwen's answer first, then the user's (translated) sentence:
        "next N days/months"  ->  "next N days" / "next N months"
        a weekday name        ->  "every <weekday>"
        anything else         ->  "daily"
    """

    for text in (frequency.lower(), sentence.lower()):

        match = NEXT_N_PATTERN.search(text)

        if match:
            number = match.group(1)
            number = NUMBER_WORDS.get(number, number)
            return f"next {number} {match.group(2)}s"

        for day in WEEKDAYS:
            if day in text:
                return f"every {day}"

    return DEFAULT_FREQUENCY


def normalize_frequency(frequency, sentence=""):
    """Map phrases like "once a day" to "daily", then apply the frequency rules."""

    if frequency.lower() in DAILY_WORDS:
        frequency = DEFAULT_FREQUENCY

    return rule_based_frequency(frequency, sentence)


def validate_reminder(data, sentence=""):
    """
    data:     Qwen's JSON output
    sentence: the translated English message, used by the frequency rules
    """

    # If Qwen returns nothing at all (or not a JSON object)
    if not isinstance(data, dict):
        data = {}

    # Get values from Qwen
    medicine = to_text(data.get("medicine"))
    dose = to_text(data.get("dose"))
    time = to_text(data.get("time"))
    frequency = to_text(data.get("frequency"))

    # If the user said an explicit clock time, read it from the sentence
    # with rules instead of trusting Qwen (which sometimes drops or garbles it)
    sentence_time = time_from_sentence(to_text(sentence))

    if sentence_time:
        time = sentence_time

    # Apply default values
    if not medicine:
        medicine = DEFAULT_MEDICINE

    if not dose:
        dose = DEFAULT_DOSE

    if not time:
        time = DEFAULT_TIME

    if not frequency:
        frequency = DEFAULT_FREQUENCY

    time = normalize_time(time)
    frequency = normalize_frequency(frequency, to_text(sentence))

    # Check that the scheduler can actually understand the time and frequency
    errors = []

    try:
        parse_time(time)
    except ValueError:
        errors.append(
            f'I couldn\'t understand the time "{time}". '
            'Please say a time like "9 PM" or "8:30 AM".'
        )

    try:
        parse_frequency(frequency)
    except ValueError:
        errors.append(
            f'I couldn\'t understand how often "{frequency}". '
            'Please say "daily", "every Monday" or "for the next 5 days".'
        )

    # Create cleaned reminder
    validated_reminder = {
        "medicine": medicine,
        "dose": dose,
        "time": time,
        "frequency": frequency
    }

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "data": validated_reminder
    }
