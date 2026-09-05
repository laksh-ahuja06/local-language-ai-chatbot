import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from IndicTransToolkit.processor import IndicProcessor

# recommended to run this on a gpu with flash_attn installed
# don't set attn_implemetation if you don't have flash_attn

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

src_lang = "tam_Taml"
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

def translate_to_english (input):

    input_sentences = [
        # "When I was young, I used to go to the park every day.",
        # "We watched a new movie last week, which was very inspiring.",
        # "If you had met me at that time, we would have gone out to eat.",
        # "My friend has invited me to his birthday party, and I will give him a gift.",
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
