from models import indicF5
from models import indicTrans2
from models import Qwen

def pipeline_message (input):
    translation = indicTrans2.translate_to_english (input)
    json_format = Qwen.run_model (translation)

    return {
        "original message": input,
        "translation": translation,
        "format": json_format
    }
