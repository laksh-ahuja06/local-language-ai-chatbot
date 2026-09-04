def validate_reminder(reminder):

    if not reminder["medicine"]:
        return {
            "valid": False,
            "reason": "Medicine name is missing"
        }

    if not reminder["time"]:
        return {
            "valid": False,
            "reason": "Time is missing"
        }

    return {
        "valid": True,
        "data": reminder
    }
