from models import indicF5
from models import indicTrans2
from models import Qwen

def pipeline_message (message):
    translation = indicTrans2.translate_to_english (message)
    json_format = Qwen.run_model (translation)

    return {
        "original_message": message,
        "translation": translation,
        "format": json_format
    }
