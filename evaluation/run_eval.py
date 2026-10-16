"""
MedVoice evaluation: reminder extraction from Hindi / Tamil / Telugu / Bengali requests.

Runs in stages so only one model is loaded at a time (fits in 8 GB of RAM):

    cd backend
    venv/bin/python ../evaluation/run_eval.py translate          # IndicTrans2 -> results/translations.json
    venv/bin/python ../evaluation/run_eval.py qwen --model 0.5B  # Qwen 0.5B configs -> results/qwen_0.5B.json
    venv/bin/python ../evaluation/run_eval.py qwen --model 1.5B  # Qwen 1.5B configs -> results/qwen_1.5B.json
    venv/bin/python ../evaluation/run_eval.py score              # metrics, CIs, tests -> results/summary.json, results/tables.md

Or run everything with:  venv/bin/python ../evaluation/run_eval.py all
"""

import argparse
import contextlib
import csv
import difflib
import io
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent / "backend"
RESULTS = EVAL_DIR / "results"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(EVAL_DIR))

TESTSET = json.loads((EVAL_DIR / "testset.json").read_text())
LANGS = TESTSET["languages"]
ITEMS = [(item, lang) for lang in LANGS for item in TESTSET["items"]]  # 100 (item, language) pairs

QWEN_MODELS = {"0.5B": "Qwen/Qwen2.5-0.5B-Instruct", "1.5B": "Qwen/Qwen2.5-1.5B-Instruct"}
NOISE_RATE = 0.05          # share of characters deleted to simulate speech-recognition errors
SAMPLING_SEEDS = [0, 1, 2]  # extra runs with temperature sampling, to measure output variance
SAMPLING_TEMPERATURE = 0.7
N_BOOTSTRAP = 10000


def key(item, lang):
    return f"{item['id']}-{lang}"


def add_noise(text, seed):
    """Delete ~5% of non-space characters (simulates ASR dropping sounds)."""
    rng = random.Random(seed)
    return "".join(ch for ch in text if ch == " " or rng.random() >= NOISE_RATE)


# ---------------------------------------------------------------------------
# Stage 1: translation
# ---------------------------------------------------------------------------

def run_translate():
    from models import indicTrans2

    indicTrans2.load_model()

    def translate(text, src):
        start = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            out = indicTrans2.translate_to_english(text, src)
        return out, time.perf_counter() - start

    rows = {}
    for n, (item, lang) in enumerate(ITEMS, 1):
        text = item["text"][lang]
        noisy = add_noise(text, seed=item["id"] * 10 + LANGS.index(lang))
        correct, t_correct = translate(text, indicTrans2.get_src_lang(lang))
        wrong, _ = translate(text, "tam_Taml")          # old behaviour: everything treated as Tamil
        noisy_tr, _ = translate(noisy, indicTrans2.get_src_lang(lang))
        rows[key(item, lang)] = {
            "text": text, "noisy_text": noisy,
            "translation": correct, "translation_latency": t_correct,
            "translation_as_tamil": wrong, "translation_noisy": noisy_tr,
        }
        print(f"[{n}/{len(ITEMS)}] {lang} #{item['id']}: {correct}")

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "translations.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------------------
# Stage 2: Qwen
# ---------------------------------------------------------------------------

PLAIN_PROMPT = """
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


def run_qwen(model_size):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from models import Qwen as deployed  # reuse the deployed SYSTEM_PROMPT / FEW_SHOT_EXAMPLES / build_messages

    name = QWEN_MODELS[model_size]
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float16, device_map="auto").eval()
    translations = json.loads((RESULTS / "translations.json").read_text())

    def chat_inputs(text, few_shot=True):
        messages = deployed.build_messages(text)
        if not few_shot:
            messages = [messages[0], messages[-1]]  # system prompt + user message only
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return tok(prompt, return_tensors="pt").to(model.device)

    def plain_inputs(text):
        return tok(PLAIN_PROMPT.format(prompt=text), return_tensors="pt").to(model.device)

    def generate(inputs, max_new_tokens, seed=None):
        kwargs = dict(max_new_tokens=max_new_tokens, pad_token_id=tok.eos_token_id)
        if seed is None:
            kwargs["do_sample"] = False
        else:
            torch.manual_seed(seed)
            kwargs.update(do_sample=True, temperature=SAMPLING_TEMPERATURE, top_p=1.0, top_k=0)
        start = time.perf_counter()
        with torch.no_grad():
            out = model.generate(**inputs, **kwargs)
        latency = time.perf_counter() - start
        new_tokens = out[0][inputs["input_ids"].shape[1]:]
        return tok.decode(new_tokens, skip_special_tokens=True).strip(), latency, len(new_tokens)

    # config name -> (input text field, prompt builder, max_new_tokens, seed)
    configs = {
        "chat_fewshot": ("translation", lambda t: chat_inputs(t), 80, None),
        "plain": ("translation", plain_inputs, 150, None),
    }
    if model_size == "0.5B":
        configs.update({
            "chat_fewshot_run2": ("translation", lambda t: chat_inputs(t), 80, None),
            "chat_fewshot_run3": ("translation", lambda t: chat_inputs(t), 80, None),
            "chat_system_only": ("translation", lambda t: chat_inputs(t, few_shot=False), 80, None),
            "chat_fewshot_no_translation": ("text", lambda t: chat_inputs(t), 80, None),
            "chat_fewshot_translated_as_tamil": ("translation_as_tamil", lambda t: chat_inputs(t), 80, None),
            "chat_fewshot_noisy": ("translation_noisy", lambda t: chat_inputs(t), 80, None),
        })
        for seed in SAMPLING_SEEDS:
            configs[f"chat_fewshot_sampled_seed{seed}"] = ("translation", lambda t: chat_inputs(t), 80, seed)

    results = {}
    for cfg, (field, build, max_new, seed) in configs.items():
        results[cfg] = {}
        for n, (item, lang) in enumerate(ITEMS, 1):
            k = key(item, lang)
            text = translations[k][field]
            raw, latency, n_tokens = generate(build(text), max_new, seed)
            results[cfg][k] = {"input": text, "raw": raw, "latency": latency, "output_tokens": n_tokens}
        lat = [r["latency"] for r in results[cfg].values()]
        print(f"{model_size} {cfg}: done, mean latency {statistics.mean(lat):.2f}s")

    (RESULTS / f"qwen_{model_size}.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------------------
# Stage 3: scoring
# ---------------------------------------------------------------------------

GENERIC_WORDS = {"tablet", "tablets", "capsule", "capsules", "pill", "pills", "medicine", "medicines",
                 "the", "my", "a", "an", "of", "syrup", "dose"}
NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "a": "1", "an": "1"}
UNIT_ALIASES = {"tablets": "tablet", "units": "unit", "drops": "drop", "spoons": "spoon", "teaspoons": "spoon",
                "teaspoon": "spoon", "tablespoons": "spoon", "tablespoon": "spoon", "spoonfuls": "spoon",
                "spoonful": "spoon", "packets": "packet", "sachets": "packet", "sachet": "packet",
                "capsules": "capsule", "pills": "tablet", "pill": "tablet", "milligrams": "mg"}


def extract_json(raw):
    if not isinstance(raw, str):
        return None
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch == "{":
            try:
                return decoder.raw_decode(raw[i:])[0]
            except json.JSONDecodeError:
                continue
    return None


def norm_medicine(name):
    words = re.sub(r"[^a-z0-9 ]", " ", str(name).lower()).split()
    words = [w for w in words if w not in GENERIC_WORDS]
    words = [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in words]
    return " ".join(words)


def norm_dose(dose):
    text = str(dose).lower().replace("½", "half").replace("1/2", "half")
    text = re.sub(r"(\d)(mg|ml)\b", r"\1 \2", text)
    words = []
    for w in re.sub(r"[^a-z0-9. ]", " ", text).split():
        w = NUMBER_WORDS.get(w, w)
        w = UNIT_ALIASES.get(w, w)
        if w in {"of", "the"}:
            continue
        words.append(w)
    text = " ".join(words)
    text = re.sub(r"\bhalf 1 tablet\b", "half tablet", text)
    return text.strip()


def score_item(validated, gold, valid):
    """validated: the reminder after the validation step; returns per-field correctness."""
    from services.scheduler import parse_time, parse_frequency

    med_pred = norm_medicine(validated.get("medicine", ""))
    med_gold = {norm_medicine(m) for m in gold["medicine"]}
    medicine = med_pred in med_gold
    medicine_lenient = medicine or any(difflib.SequenceMatcher(None, med_pred, g).ratio() >= 0.8 for g in med_gold)

    dose_pred = norm_dose(validated.get("dose", ""))
    if gold["dose"]:
        dose = dose_pred in {norm_dose(d) for d in gold["dose"]}
        dose_hallucinated = None
    else:
        dose = dose_pred in {"", "1 tablet"}
        dose_hallucinated = not dose

    try:
        parsed_time = list(parse_time(validated.get("time", "")))
    except Exception:
        parsed_time = None
    try:
        parsed_freq = parse_frequency(validated.get("frequency", ""))
    except Exception:
        parsed_freq = None
    time_ok = parsed_time == gold["time"]
    freq_ok = parsed_freq == gold["frequency"]

    # Schedulable = the scheduler can actually parse it (not the validator's own claim: the
    # original v1 validation always said valid, even for times like "night").
    schedulable = parsed_time is not None and parsed_freq is not None

    return {
        "medicine": medicine, "medicine_lenient": medicine_lenient, "dose": dose,
        "dose_hallucinated": dose_hallucinated, "time": time_ok, "frequency": freq_ok,
        "exact": medicine and dose and time_ok and freq_ok, "schedulable": schedulable,
    }


def rule_based_extract(english):
    """Baseline B1: regular expressions + keyword rules on the English translation, no LLM."""
    from services.validation import TIME_WORDS, rule_based_frequency

    text = english.lower()
    m = re.search(r"(\d{1,2})(?:[:.](\d{2}))?\s*([ap])\.?\s*m\b\.?", text)
    if m:
        time_str = f"{m.group(1)}:{m.group(2) or '00'} {m.group(3).upper()}M"
    else:
        time_str = next((TIME_WORDS[w] for w in TIME_WORDS if w in text), "")

    unit = r"(mg|ml|units?|drops?|tablets?|capsules?|spoons?|teaspoons?|packets?|sachets?)"
    d = re.search(r"(\d+(?:\.\d+)?)\s*" + unit, text) or \
        re.search(r"\b(one|two|three|half|a|an)\s+(?:a\s+)?" + unit, text)
    dose = f"{d.group(1)} {d.group(2)}" if d else ""

    med = re.search(r"\b(?:take|taking|drink|put|of)\s+(?:a |an |the |my |one |two |half |half a )?"
                    r"(?:\d+\s*(?:mg|units?|drops?)\s+(?:of\s+)?)?"
                    r"([a-z][a-z0-9\- ]{1,30}?)(?=\s+(?:at|every|daily|for|in|before|after|tablet|tablets|"
                    r"capsule|capsules|pill|pills|each|on|from|\d)|[.,]|$)", text)
    medicine = med.group(1).strip() if med else ""

    return {"medicine": medicine, "dose": dose, "time": time_str,
            "frequency": rule_based_frequency("", english)}


def validate_v2(data, sentence, rules=True):
    from services import validation
    if rules:
        return validation.validate_reminder(data, sentence)
    original = validation.rule_based_frequency
    validation.rule_based_frequency = lambda frequency, sentence: frequency   # ablation: trust Qwen's frequency
    try:
        return validation.validate_reminder(data, sentence)
    finally:
        validation.rule_based_frequency = original


def validate_v1(data):
    """Original validation (defaults only). The original pipeline crashed on non-dict output: count as failure."""
    import validation_v1
    try:
        result = validation_v1.validate_reminder(data)
        return result
    except Exception:
        return {"valid": False, "data": {}}


def bootstrap_ci(values, seed=0):
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(N_BOOTSTRAP))
    return means[int(0.025 * N_BOOTSTRAP)], means[int(0.975 * N_BOOTSTRAP) - 1]


def mcnemar_exact(a, b):
    """Exact McNemar test on paired booleans a (system) vs b (comparison)."""
    from scipy.stats import binomtest
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    if only_a + only_b == 0:
        return only_a, only_b, 1.0
    return only_a, only_b, binomtest(only_a, only_a + only_b, 0.5).pvalue


def holm(pvalues):
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted, running = [0.0] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


def run_score():
    from scipy.stats import chi2_contingency

    tr = json.loads((RESULTS / "translations.json").read_text())
    q05 = json.loads((RESULTS / "qwen_0.5B.json").read_text())
    q15 = json.loads((RESULTS / "qwen_1.5B.json").read_text())

    # system name -> function(item, lang) -> (validated reminder, valid, json_ok, qwen latency or None)
    def llm_system(runs, cfg, sentence_field="translation", validator="v2"):
        def fn(item, lang):
            k = key(item, lang)
            r = runs[cfg][k]
            data = extract_json(r["raw"])
            if validator == "v1":
                v = validate_v1(data)
            else:
                v = validate_v2(data, r["input"] if sentence_field is None else tr[k][sentence_field],
                                rules=(validator == "v2"))
            return v.get("data", {}), v.get("valid", False), isinstance(data, dict), r["latency"]
        return fn

    def rule_system(field):
        def fn(item, lang):
            k = key(item, lang)
            v = validate_v2(rule_based_extract(tr[k][field]), tr[k][field])
            return v["data"], v["valid"], None, None
        return fn

    systems = {
        # main comparison
        "B1 Rule-based (IndicTrans2 + regex, no LLM)": rule_system("translation"),
        "B2 Original pipeline (Qwen-1.5B, plain prompt, v1 validation)": llm_system(q15, "plain", validator="v1"),
        "Ours (Qwen-0.5B, chat + few-shot, v2 validation)": llm_system(q05, "chat_fewshot"),
        "Ours with Qwen-1.5B": llm_system(q15, "chat_fewshot"),
        # ablations of Ours
        "- few-shot examples (system prompt only)": llm_system(q05, "chat_system_only"),
        "- system prompt and examples (plain prompt)": llm_system(q05, "plain"),
        "- rule-based frequency": llm_system(q05, "chat_fewshot", validator="v2_no_rules"),
        "- validation layer (v1 defaults only)": llm_system(q05, "chat_fewshot", validator="v1"),
        "- IndicTrans2 (Indic text straight to Qwen)": llm_system(q05, "chat_fewshot_no_translation", sentence_field=None),
        "Wrong source language (all translated as Tamil)": llm_system(q05, "chat_fewshot_translated_as_tamil", sentence_field="translation_as_tamil"),
        # robustness
        "Ours on noisy input (5% characters deleted)": llm_system(q05, "chat_fewshot_noisy", sentence_field="translation_noisy"),
        "B1 on noisy input": rule_system("translation_noisy"),
        # determinism / variance
        "Ours run 2 (greedy)": llm_system(q05, "chat_fewshot_run2"),
        "Ours run 3 (greedy)": llm_system(q05, "chat_fewshot_run3"),
    }
    for seed in SAMPLING_SEEDS:
        systems[f"Ours sampled T={SAMPLING_TEMPERATURE} seed {seed}"] = llm_system(q05, f"chat_fewshot_sampled_seed{seed}")

    fields = ["exact", "medicine", "medicine_lenient", "dose", "time", "frequency", "schedulable"]
    per_item, summary = {}, {}
    for name, fn in systems.items():
        rows = []
        for item, lang in ITEMS:
            validated, valid, json_ok, latency = fn(item, lang)
            s = score_item(validated, item["gold"], valid)
            s.update(id=item["id"], lang=lang, json_ok=json_ok, latency=latency, prediction=validated)
            rows.append(s)
        per_item[name] = rows
        res = {}
        for f in fields:
            vals = [1.0 if r[f] else 0.0 for r in rows]
            lo, hi = bootstrap_ci(vals)
            res[f] = {"mean": statistics.mean(vals), "ci95": [lo, hi]}
        no_dose = [r for r in rows if r["dose_hallucinated"] is not None]
        res["dose_hallucination_rate"] = {"mean": statistics.mean(1.0 if r["dose_hallucinated"] else 0.0 for r in no_dose),
                                          "n": len(no_dose)}
        if rows[0]["json_ok"] is not None:
            res["json_valid_rate"] = statistics.mean(1.0 if r["json_ok"] else 0.0 for r in rows)
        res["by_language"] = {}
        for lang in LANGS:
            vals = [1.0 if r["exact"] else 0.0 for r in rows if r["lang"] == lang]
            lo, hi = bootstrap_ci(vals)
            res["by_language"][lang] = {"exact": statistics.mean(vals), "ci95": [lo, hi]}
        lats = [r["latency"] for r in rows if r["latency"] is not None]
        if lats:
            res["qwen_latency"] = {"mean": statistics.mean(lats), "p95": percentile(lats, 95)}
        summary[name] = res

    ours = "Ours (Qwen-0.5B, chat + few-shot, v2 validation)"
    ours_exact = [r["exact"] for r in per_item[ours]]

    # paired significance tests vs Ours, Holm-corrected
    compare = [n for n in systems if n != ours and not n.startswith("Ours run") and "sampled" not in n
               and n not in ("Ours on noisy input (5% characters deleted)", "B1 on noisy input")]
    tests = []
    for name in compare:
        a_only, b_only, p = mcnemar_exact(ours_exact, [r["exact"] for r in per_item[name]])
        tests.append({"comparison": f"Ours vs {name}", "ours_only_correct": a_only, "other_only_correct": b_only, "p": p})
    for t, p_adj in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = p_adj
    a_only, b_only, p = mcnemar_exact(ours_exact, [r["exact"] for r in per_item["Ours on noisy input (5% characters deleted)"]])
    noise_test = {"ours_clean_only": a_only, "noisy_only": b_only, "p": p}

    # language fairness: chi-square on Ours exact-match by language
    table = [[sum(1 for r in per_item[ours] if r["lang"] == l and r["exact"]),
              sum(1 for r in per_item[ours] if r["lang"] == l and not r["exact"])] for l in LANGS]
    chi2, p_lang, dof, _ = chi2_contingency(table)

    # run-to-run variability
    greedy_runs = [ours, "Ours run 2 (greedy)", "Ours run 3 (greedy)"]
    sampled_runs = [f"Ours sampled T={SAMPLING_TEMPERATURE} seed {s}" for s in SAMPLING_SEEDS]
    greedy_identical = all(per_item[g][i]["prediction"] == per_item[ours][i]["prediction"]
                           for g in greedy_runs for i in range(len(ITEMS)))
    variability = {
        "greedy_exact": [summary[g]["exact"]["mean"] for g in greedy_runs],
        "greedy_outputs_identical": greedy_identical,
        "sampled_exact": [summary[s]["exact"]["mean"] for s in sampled_runs],
        "sampled_exact_mean": statistics.mean(summary[s]["exact"]["mean"] for s in sampled_runs),
        "sampled_exact_sd": statistics.stdev(summary[s]["exact"]["mean"] for s in sampled_runs),
    }

    # latency: translation + Qwen (Ours)
    t_lat = [tr[key(i, l)]["translation_latency"] for i, l in ITEMS]
    q_lat = [r["latency"] for r in per_item[ours]]
    e2e = [a + b for a, b in zip(t_lat, q_lat)]
    latency = {
        "translation": {"mean": statistics.mean(t_lat), "p95": percentile(t_lat, 95)},
        "qwen_0.5B": {"mean": statistics.mean(q_lat), "p95": percentile(q_lat, 95)},
        "end_to_end": {"mean": statistics.mean(e2e), "p95": percentile(e2e, 95)},
        "qwen_1.5B": summary["Ours with Qwen-1.5B"]["qwen_latency"],
    }

    out = {"n_items": len(ITEMS), "systems": summary, "significance_vs_ours": tests, "noise_test": noise_test,
           "language_chi2": {"table_correct_incorrect": dict(zip(LANGS, table)), "chi2": chi2, "dof": dof, "p": p_lang},
           "variability": variability, "latency": latency}
    (RESULTS / "summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))

    with open(RESULTS / "per_item.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["system", "id", "lang", "exact", "medicine", "dose", "time", "frequency", "schedulable",
                    "pred_medicine", "pred_dose", "pred_time", "pred_frequency"])
        for name, rows in per_item.items():
            for r in rows:
                p = r["prediction"] or {}
                w.writerow([name, r["id"], r["lang"], int(r["exact"]), int(r["medicine"]), int(r["dose"]), int(r["time"]),
                            int(r["frequency"]), int(r["schedulable"]), p.get("medicine"), p.get("dose"), p.get("time"),
                            p.get("frequency")])

    pct = lambda x: f"{100 * x:.1f}"
    lines = ["| System | Exact | Medicine | Dose | Time | Frequency | Schedulable | Dose halluc. | JSON valid | Qwen latency (s) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, res in summary.items():
        lo, hi = res["exact"]["ci95"]
        json_valid = pct(res["json_valid_rate"]) if "json_valid_rate" in res else "-"
        latency_cell = f"{res['qwen_latency']['mean']:.2f}" if "qwen_latency" in res else "-"
        cells = [name, f"{pct(res['exact']['mean'])} [{pct(lo)}, {pct(hi)}]", pct(res["medicine"]["mean"]),
                 pct(res["dose"]["mean"]), pct(res["time"]["mean"]), pct(res["frequency"]["mean"]),
                 pct(res["schedulable"]["mean"]), pct(res["dose_hallucination_rate"]["mean"]), json_valid, latency_cell]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "| Comparison | Ours-only correct | Other-only correct | p (exact McNemar) | p (Holm) |", "|---|---|---|---|---|"]
    for t in tests:
        lines.append(f"| {t['comparison']} | {t['ours_only_correct']} | {t['other_only_correct']} | {t['p']:.2g} | {t['p_holm']:.2g} |")
    (RESULTS / "tables.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(json.dumps({"variability": variability, "latency": latency, "language_chi2_p": p_lang,
                      "noise_test": noise_test}, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["translate", "qwen", "score", "all"])
    parser.add_argument("--model", choices=list(QWEN_MODELS), default="0.5B")
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    if args.stage == "translate":
        run_translate()
    elif args.stage == "qwen":
        run_qwen(args.model)
    elif args.stage == "score":
        run_score()
    else:
        import subprocess
        for step in (["translate"], ["qwen", "--model", "0.5B"], ["qwen", "--model", "1.5B"], ["score"]):
            subprocess.run([sys.executable, __file__, *step], check=True)
