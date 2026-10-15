import torch
import json
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
tokenizer = None
model = None

dtype = (
    torch.bfloat16
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    else torch.float16
)

import time
from transformers.generation.streamers import BaseStreamer

MAX_NEW_TOKENS = 80  # the JSON answer is ~40 tokens

# Running averages from earlier queries, used for the up-front estimate
stats = {
    "tokens_per_sec": None,
    "prefill_sec": None,
    "avg_output_tokens": 60,
}

# Timing of the most recent query (pipeline.py can return this to the frontend)
last_run = {}


class ProgressStreamer(BaseStreamer):
    """
    Called by model.generate() every time a token is produced.
    Prints a live progress line with tokens/sec and an ETA.
    """

    def __init__(self, expected_tokens):
        self.expected_tokens = expected_tokens
        self.count = 0
        self.skipped_prompt = False
        self.start = time.perf_counter()
        self.first_token_time = None

    def put(self, value):
        # The first call is the prompt itself, not generated tokens
        if not self.skipped_prompt:
            self.skipped_prompt = True
            return

        self.count += value.numel()
        now = time.perf_counter()

        # First token: the time so far is "prefill" (reading the prompt)
        if self.first_token_time is None:
            self.first_token_time = now
            print(f"Qwen: prompt processed in {now - self.start:.1f}s, generating...")
            return

        rate = (self.count - 1) / (now - self.first_token_time)

        # If we've passed the usual length, the worst case is max_new_tokens
        target = self.expected_tokens if self.count < self.expected_tokens else MAX_NEW_TOKENS
        eta = (target - self.count) / rate if rate > 0 else 0

        print(
            f"\rQwen: {self.count} tokens | {rate:.1f} tok/s | ~{eta:.0f}s left   ",
            end="",
            flush=True,
        )

    def end(self):
        print()


def estimate_seconds():
    """Estimated total time for the next query, based on earlier ones."""
    if stats["tokens_per_sec"] is None:
        return None

    return stats["prefill_sec"] + stats["avg_output_tokens"] / stats["tokens_per_sec"]


def update_stats(prefill_sec, output_tokens, generate_sec):
    """Blend this query's numbers into the running averages."""
    if output_tokens < 2 or generate_sec <= 0:
        return

    rate = output_tokens / generate_sec

    if stats["tokens_per_sec"] is None:
        stats["tokens_per_sec"] = rate
        stats["prefill_sec"] = prefill_sec
        stats["avg_output_tokens"] = output_tokens
    else:
        # 70% old average, 30% new query
        stats["tokens_per_sec"] = 0.7 * stats["tokens_per_sec"] + 0.3 * rate
        stats["prefill_sec"] = 0.7 * stats["prefill_sec"] + 0.3 * prefill_sec
        stats["avg_output_tokens"] = 0.7 * stats["avg_output_tokens"] + 0.3 * output_tokens

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


# Instructions for Qwen: the exact formats the scheduler can understand
SYSTEM_PROMPT = """You extract medicine reminders from a user's message and reply with ONLY a JSON object, no other text.

Fields:
- "medicine": the medicine name only, e.g. "Crocin", "Dolo 650", "vitamin D".
- "dose": amount and unit, e.g. "500 mg", "2 tablets", "1 capsule", "10 units", "half tablet". Use "" if not mentioned.
- "time": clock time in the format "H:MM AM" or "H:MM PM", e.g. "9:00 PM", "7:30 AM". Convert words: morning = "8:00 AM", afternoon = "2:00 PM", evening = "6:00 PM", night = "9:00 PM".
- "frequency": exactly one of:
    "daily"
    "every monday" ... "every sunday"
    "next N days"     (e.g. "next 5 days")
    "next N months"   (e.g. "next 3 months")
  If no frequency is mentioned, use "daily". If a duration is mentioned ("for the next 3 months"), use the "next N ..." form.

Never invent information that is not in the message."""

# Worked examples, shown to Qwen as earlier turns of the chat
FEW_SHOT_EXAMPLES = [
    (
        "Remind me to take 2 tablets of Paracetamol at 10 pm every day",
        {"medicine": "Paracetamol", "dose": "2 tablets", "time": "10:00 PM", "frequency": "daily"},
    ),
    (
        "I take Azithromycin 250 mg every Friday morning",
        {"medicine": "Azithromycin", "dose": "250 mg", "time": "8:00 AM", "frequency": "every friday"},
    ),
    (
        "Remind me about my cough syrup at 8:30 pm for the next 4 days",
        {"medicine": "cough syrup", "dose": "", "time": "8:30 PM", "frequency": "next 4 days"},
    ),
]


def build_messages(prompt):
    """System instructions + examples + the user's (translated) message."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for user_text, answer in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": user_text})
        messages.append({"role": "assistant", "content": json.dumps(answer)})

    messages.append({"role": "user", "content": prompt})

    return messages


def run_model(prompt):

    if model is None or tokenizer is None:
        raise RuntimeError("Qwen model has not been loaded.")

    print("Qwen input:", prompt)

    # Instruct models follow instructions much better in their own chat format
    finalPrompt = tokenizer.apply_chat_template(
        build_messages(prompt),
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(
        finalPrompt,
        return_tensors="pt"
    ).to(model.device)

    estimate = estimate_seconds()

    if estimate is None:
        print("Qwen: first query, ETA will appear once tokens start coming in...")
    else:
        print(f"Qwen: estimated time ~{estimate:.0f}s")

    streamer = ProgressStreamer(
        expected_tokens=round(stats["avg_output_tokens"])
    )

    start = time.perf_counter()

    outputs = model.generate(
        **inputs,
        max_new_tokens=MAX_NEW_TOKENS,
        do_sample=False,
        streamer=streamer,
    )

    total_sec = time.perf_counter() - start

    generated = outputs[0][inputs["input_ids"].shape[1]:]

    # Record timing and improve the estimate for next time
    prefill_sec = (streamer.first_token_time or start) - start
    update_stats(prefill_sec, len(generated), total_sec - prefill_sec)

    last_run.update({
        "estimated_sec": round(estimate, 1) if estimate else None,
        "actual_sec": round(total_sec, 1),
        "output_tokens": len(generated),
    })

    print(f"Qwen: finished in {total_sec:.1f}s ({len(generated)} tokens)")

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
