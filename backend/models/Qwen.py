import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# # Load tokenizer
# tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

# # Load model
# model = AutoModelForCausalLM.from_pretrained(
#     MODEL_NAME,
#     torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
#     device_map="auto"
# )

MODEL = "Qwen/Qwen2.5-1.5B"

dtype = (
    torch.bfloat16
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    else torch.float16
    if torch.cuda.is_available()
    else torch.float32
)


def load_model():
    global tokenizer, model
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )


def run_model(prompt):

    finalPrompt = f"""
        Extract the medicine reminder information.
        User message:
        {prompt}
        Return JSON with:
        medicine
        dose
        time
        frequency
        """

    print(finalPrompt)

    inputs = tokenizer(finalPrompt, return_tensors="pt").to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=300,
        temperature=0.2,
        top_p=1.0,
        do_sample=True,
    )

    generated = outputs[0][inputs["input_ids"].shape[1] :]
    response = tokenizer.decode(generated, skip_special_tokens=True)

    print(response)

    return response
