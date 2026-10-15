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
