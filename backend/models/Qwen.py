import torch
import json
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
tokenizer = None
model = None

dtype = (
    torch.bfloat16
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    else torch.float16
    if torch.cuda.is_available()
    else torch.float32
)

def load_model():
    global tokenizer, model

    print("Loading Qwen...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL)

    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        torch_dtype=dtype,
        device_map="auto",
    )

    print("Qwen loaded successfully.")


def run_model(prompt):

    if model is None or tokenizer is None:
        raise RuntimeError("Qwen model has not been loaded.")

    finalPrompt = f"""
Extract the medicine reminder information from the user message.

User message:
{prompt}

Return ONLY valid JSON.
Do not include any explanation or extra text.

Use exactly these fields:
{{
    "medicine": "",
    "dose": "",
    "time": "",
    "frequency": ""
}}
"""

    print("Qwen prompt:")
    print(finalPrompt)

    inputs = tokenizer(
        finalPrompt,
        return_tensors="pt"
    ).to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=150,
        do_sample=False,
    )

    generated = outputs[0][inputs["input_ids"].shape[1]:]

    response = tokenizer.decode(
        generated,
        skip_special_tokens=True
    ).strip()

    print("Qwen raw response:")
    print(response)

    try:
        decoder = json.JSONDecoder()
        for i, char in enumerate(response):
            if char == "{":
                try:
                    result, _ = decoder.raw_decode(response[i:])
                    break
                except json.JSONDecodeError:
                    continue
        else:
            print("Qwen did not return valid JSON.")
            return None

    except Exception as e:
        print("Error parsing Qwen response:", e)
        return None

    print("Qwen JSON:")
    print(result)

    return result
