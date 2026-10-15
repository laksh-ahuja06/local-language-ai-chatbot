import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from IndicTransToolkit.processor import IndicProcessor

# conda activate indicf5
# recommended to run this on a gpu with flash_attn installed
# don't set attn_implemetation if you don't have flash_attn

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Language codes sent by the React app -> IndicTrans2 language codes
LANGUAGE_CODES = {
    "hi-IN": "hin_Deva",  # Hindi
    "ta-IN": "tam_Taml",  # Tamil
    "te-IN": "tel_Telu",  # Telugu
    "bn-IN": "ben_Beng",  # Bengali
}

DEFAULT_SRC_LANG = "hin_Deva"
tgt_lang = "eng_Latn"
model_name = "ai4bharat/indictrans2-indic-en-dist-200M"
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

ip = IndicProcessor(inference=True)

def load_model ():
    global model
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch.float16, # performance might slightly vary for bfloat16
        attn_implementation="flash_attention_2"
    ).to(DEVICE)
    ip = IndicProcessor(inference=True)

def get_src_lang(language_code):
    """
    Convert the app's language code (e.g. "hi-IN") to IndicTrans2's (e.g. "hin_Deva").
    Returns None if the language isn't supported.
    """
    return LANGUAGE_CODES.get(language_code)


def translate_to_english (input, src_lang=DEFAULT_SRC_LANG):

    input_sentences = [
        input
    ]

    batch = ip.preprocess_batch(input_sentences, src_lang=src_lang, tgt_lang=tgt_lang)

    # Tokenize the sentences and generate input encodings
    inputs = tokenizer(
        batch,
        truncation=True,
        padding="longest",
        return_tensors="pt",
        return_attention_mask=True,
    ).to(DEVICE)

    # Generate translations using the model
    with torch.no_grad():
        generated_tokens = model.generate(
            **inputs,
            use_cache=True,
            min_length=0,
            max_length=256,
            num_beams=5,
            num_return_sequences=1,
        )

    # Decode the generated tokens into text
    generated_tokens = tokenizer.batch_decode(
        generated_tokens,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    )

    # Postprocess the translations, including entity replacement
    translations = ip.postprocess_batch(generated_tokens, lang=tgt_lang)

    for input_sentence, translation in zip(input_sentences, translations):
        print(f"{src_lang}: {input_sentence}")
        print(f"{tgt_lang}: {translation}")

    return translations[0]
