from models import indicTrans2
from models import Qwen

from services.validation import validate_reminder
from services.scheduler import schedule_reminder

from services.connectToMongoDB import save_reminder
from services.connectToMongoDB import save_reminder, update_job_ids

def pipeline_message(message):

    # STEP 1: Translate
    translation = indicTrans2.translate_to_english(message)

    # STEP 2: Extract JSON
    json_format = Qwen.run_model(translation)

    # STEP 3: Validate
    validation = validate_reminder(json_format)

    # STEP 4: Database + Scheduler
    schedule_result = None
    database_result = None

    if validation["valid"]:

        database_result = save_reminder({
            "medicine": json_format["medicine"],
            "dose": json_format["dose"],
            "time": json_format["time"],
            "frequency": json_format["frequency"],
            "original_message": message
        })

        schedule_result = schedule_reminder(
            medicine=json_format["medicine"],
            dose=json_format["dose"],
            time=json_format["time"],
            frequency=json_format["frequency"],
            reminder_id=database_result
        )

        update_job_ids(
            database_result,
            schedule_result["job_ids"]
        )


    # STEP 5: Return result
    return {
        "original_message": message,
        "translation": translation,
        "format": json_format,
        "validation": validation,
        "database": database_result,
        "schedule": schedule_result
    }
