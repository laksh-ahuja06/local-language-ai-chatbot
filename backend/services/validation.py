def validate_reminder(data):

    # If Qwen returns nothing at all
    if data is None:
        data = {}

    # Get values from Qwen
    medicine = data.get("medicine", "").strip()
    dose = data.get("dose", "").strip()
    time = data.get("time", "").strip()
    frequency = data.get("frequency", "").strip()

    # Apply default values
    if not medicine:
        medicine = "medicine"

    if not dose:
        dose = "1 tablet"

    if not time:
        time = "night"

    if not frequency:
        frequency = "everyday"

    # Create cleaned reminder
    validated_reminder = {
        "medicine": medicine,
        "dose": dose,
        "time": time,
        "frequency": frequency
    }

    return {
        "valid": True,
        "errors": [],
        "data": validated_reminder
    }
