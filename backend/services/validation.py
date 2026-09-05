def validate_reminder(data):

    errors = []

    medicine = data.get("medicine", "").strip()
    dose = data.get("dose", "").strip()
    time = data.get("time", "").strip()
    frequency = data.get("frequency", "").strip()

    if not medicine:
        errors.append("Medicine is missing.")

    if not dose:
        errors.append("Dose is missing.")

    if not time:
        errors.append("Time is missing.")

    if not frequency:
        errors.append("Frequency is missing.")

    if errors:
        return {
            "valid": False,
            "errors": errors
        }

    return {
        "valid": True,
        "errors": []
    }
