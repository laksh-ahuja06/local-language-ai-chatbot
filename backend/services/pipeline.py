import traceback

from models import indicTrans2
from models import Qwen

from services.validation import validate_reminder
from services.scheduler import schedule_reminder

from services.connectToMongoDB import save_reminder, update_job_ids, delete_reminder

def pipeline_message(message, language):

    translation = None
    json_format = None
    validation = None
    database_result = None
    schedule_result = None

    try:

        # STEP 1: Translate from the language the user picked in the app
        src_lang = indicTrans2.get_src_lang(language)

        if src_lang is None:
            return build_result(
                success=False,
                message=f'Sorry, the language "{language}" isn\'t supported yet. Please choose Hindi, Tamil, Telugu or Bengali.',
                original_message=message,
                translation=translation,
                json_format=json_format,
                validation=validation,
            )

        translation = indicTrans2.translate_to_english(message, src_lang)

        # STEP 2: Extract JSON
        json_format = Qwen.run_model(translation)

        # STEP 3: Validate
        validation = validate_reminder(json_format, translation)

        if not validation["valid"]:
            return build_result(
                success=False,
                message=" ".join(validation["errors"]),
                original_message=message,
                translation=translation,
                json_format=json_format,
                validation=validation,
            )

        # Use the cleaned-up data, not Qwen's raw output
        reminder = validation["data"]

        # STEP 4: Database + Scheduler
        database_result = save_reminder({
            "medicine": reminder["medicine"],
            "dose": reminder["dose"],
            "time": reminder["time"],
            "frequency": reminder["frequency"],
            "original_message": message
        })

        try:
            schedule_result = schedule_reminder(
                medicine=reminder["medicine"],
                dose=reminder["dose"],
                time=reminder["time"],
                frequency=reminder["frequency"],
                reminder_id=database_result
            )

        except Exception:
            # Don't leave a saved reminder with no scheduled job behind it
            delete_reminder(database_result)
            database_result = None
            raise

        update_job_ids(
            database_result,
            schedule_result["job_ids"]
        )

    except Exception as e:
        print("Pipeline failed:")
        traceback.print_exc()

        return build_result(
            success=False,
            message=f"Sorry, I couldn't set that reminder ({type(e).__name__}: {e}). Please try again.",
            original_message=message,
            translation=translation,
            json_format=json_format,
            validation=validation,
        )

    # STEP 5: Return result
    return build_result(
        success=True,
        message=f'Reminder set: {reminder["dose"]} of {reminder["medicine"]} at {reminder["time"]}, {reminder["frequency"]}.',
        original_message=message,
        translation=translation,
        json_format=json_format,
        validation=validation,
        database=database_result,
        schedule=schedule_result,
    )


def build_result(success, message, original_message, translation, json_format, validation, database=None, schedule=None):
    return {
        "success": success,
        "message": message,
        "original_message": original_message,
        "translation": translation,
        "format": json_format,
        "validation": validation,
        "database": database,
        "schedule": schedule
    }
