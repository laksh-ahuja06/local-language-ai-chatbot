from models import indicTrans2
from models import Qwen

## validation function
from services.validation import validate_reminder
from services.scheduler import schedule_reminder

def pipeline_message (message):
    translation = indicTrans2.translate_to_english (message)
    json_format = Qwen.run_model (translation)

    ## validate the json query
    validation = validate_reminder (json_format)

    schedule_result = None

    if validation["valid"]:
        schedule_result = schedule_reminder(
                medicine=json_format["medicine"],
                dose=json_format["dose"],
                time=json_format["time"],
                frequency=json_format["frequency"]
            )

    return {
        "original_message": message,
        "translation": translation,
        "format": json_format,
        "validation": validation,
        "schedule": schedule_result
    }
