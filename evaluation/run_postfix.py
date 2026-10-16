"""
Post-evaluation fix check (run AFTER the main evaluation in run_eval.py).

The main evaluation (results/) found that clock times like "7:30" were corrupted to "1:30" by IndicTransToolkit
preprocessing, and that Qwen sometimes dropped or garbled times. Two fixes were then made:
  1. models/indicTrans2.py: protect_times() pads single-digit hours ("8:03" -> "08:03") before translation
  2. services/validation.py: time_from_sentence() reads an explicit clock time from the translated sentence

This script re-runs translation + Qwen-0.5B on the SAME 100-item test set with the fixed code and writes
results_postfix/. Because the fixes were designed after looking at errors on this test set, these numbers are
optimistic and are reported separately from the original results.

Note: results/ was produced by the code at git commit b0b0b1e (before these fixes); re-running run_eval.py now
uses the fixed code and would not reproduce those original numbers exactly.

    cd backend
    venv/bin/python ../evaluation/run_postfix.py translate
    venv/bin/python ../evaluation/run_postfix.py qwen
    venv/bin/python ../evaluation/run_postfix.py score
"""

import contextlib
import io
import json
import statistics
import sys
import time

import run_eval as E   # same test set, prompts, scoring and statistics as the main evaluation

OUT = E.EVAL_DIR / "results_postfix"
ORIGINAL = E.RESULTS


def run_translate():
    from models import indicTrans2

    indicTrans2.load_model()
    rows = {}
    for item, lang in E.ITEMS:
        start = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            translation = indicTrans2.translate_to_english(item["text"][lang], indicTrans2.get_src_lang(lang))
        rows[E.key(item, lang)] = {"text": item["text"][lang], "translation": translation,
                                   "translation_latency": time.perf_counter() - start}
    OUT.mkdir(exist_ok=True)
    (OUT / "translations.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print("translated", len(rows))


def run_qwen():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from models import Qwen as deployed

    tok = AutoTokenizer.from_pretrained(E.QWEN_MODELS["0.5B"])
    model = AutoModelForCausalLM.from_pretrained(E.QWEN_MODELS["0.5B"], torch_dtype=torch.float16,
                                                 device_map="auto").eval()
    tr = json.loads((OUT / "translations.json").read_text())
    results = {}
    for item, lang in E.ITEMS:
        k = E.key(item, lang)
        prompt = tok.apply_chat_template(deployed.build_messages(tr[k]["translation"]), tokenize=False,
                                         add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        start = time.perf_counter()
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=80, do_sample=False, pad_token_id=tok.eos_token_id)
        raw = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        results[k] = {"input": tr[k]["translation"], "raw": raw, "latency": time.perf_counter() - start}
    (OUT / "qwen_0.5B.json").write_text(json.dumps({"chat_fewshot": results}, ensure_ascii=False, indent=1))
    print("qwen done, mean latency", statistics.mean(r["latency"] for r in results.values()))


def run_score():
    from services import validation

    tr = json.loads((OUT / "translations.json").read_text())
    q = json.loads((OUT / "qwen_0.5B.json").read_text())["chat_fewshot"]

    def validate(data, sentence, time_rule=True):
        if time_rule:
            return validation.validate_reminder(data, sentence)
        original = validation.time_from_sentence
        validation.time_from_sentence = lambda s: ""      # ablation: trust Qwen's time again
        try:
            return validation.validate_reminder(data, sentence)
        finally:
            validation.time_from_sentence = original

    systems = {
        "Ours, post-fix (time-safe translation + time rule)":
            lambda k: validate(E.extract_json(q[k]["raw"]), tr[k]["translation"]),
        "Ours, translation fix only (no time rule)":
            lambda k: validate(E.extract_json(q[k]["raw"]), tr[k]["translation"], time_rule=False),
        "B1 rule-based, post-fix translation":
            lambda k: validate(E.rule_based_extract(tr[k]["translation"]), tr[k]["translation"]),
    }

    fields = ["exact", "medicine", "medicine_lenient", "dose", "time", "frequency", "schedulable"]
    per_item, summary = {}, {}
    for name, fn in systems.items():
        rows = []
        for item, lang in E.ITEMS:
            v = fn(E.key(item, lang))
            s = E.score_item(v["data"], item["gold"], v["valid"])
            s.update(id=item["id"], lang=lang, prediction=v["data"])
            rows.append(s)
        per_item[name] = rows
        res = {f: {"mean": statistics.mean(1.0 if r[f] else 0.0 for r in rows),
                   "ci95": list(E.bootstrap_ci([1.0 if r[f] else 0.0 for r in rows]))} for f in fields}
        no_dose = [r for r in rows if r["dose_hallucinated"] is not None]
        res["dose_hallucination_rate"] = statistics.mean(1.0 if r["dose_hallucinated"] else 0.0 for r in no_dose)
        res["by_language"] = {l: statistics.mean(1.0 if r["exact"] else 0.0 for r in rows if r["lang"] == l)
                              for l in E.LANGS}
        summary[name] = res

    # original (pre-fix) per-item exact matches, for paired tests
    original = {}
    with open(ORIGINAL / "per_item.csv") as fh:
        import csv
        for r in csv.DictReader(fh):
            original.setdefault(r["system"], {})[(int(r["id"]), r["lang"])] = r["exact"] == "1"
    orig_ours = [original["Ours (Qwen-0.5B, chat + few-shot, v2 validation)"][(i["id"], l)] for i, l in E.ITEMS]
    orig_b1 = [original["B1 Rule-based (IndicTrans2 + regex, no LLM)"][(i["id"], l)] for i, l in E.ITEMS]

    post = [r["exact"] for r in per_item["Ours, post-fix (time-safe translation + time rule)"]]
    trans_only = [r["exact"] for r in per_item["Ours, translation fix only (no time rule)"]]
    b1_post = [r["exact"] for r in per_item["B1 rule-based, post-fix translation"]]

    tests = []
    for label, a, b in [("Post-fix vs original system", post, orig_ours),
                        ("Post-fix vs translation fix only", post, trans_only),
                        ("Post-fix vs B1 rule-based (post-fix translation)", post, b1_post)]:
        a_only, b_only, p = E.mcnemar_exact(a, b)
        tests.append({"comparison": label, "a_only": a_only, "b_only": b_only, "p": p})
    for t, p_adj in zip(tests, E.holm([t["p"] for t in tests])):
        t["p_holm"] = p_adj

    from scipy.stats import chi2_contingency
    table = [[sum(1 for r in per_item["Ours, post-fix (time-safe translation + time rule)"] if r["lang"] == l and r["exact"]),
              sum(1 for r in per_item["Ours, post-fix (time-safe translation + time rule)"] if r["lang"] == l and not r["exact"])]
             for l in E.LANGS]
    chi2, p_lang, _, _ = chi2_contingency(table)

    t_lat = [tr[E.key(i, l)]["translation_latency"] for i, l in E.ITEMS]
    q_lat = [q[E.key(i, l)]["latency"] for i, l in E.ITEMS]
    out = {
        "systems": summary,
        "original_exact": {"ours": statistics.mean(orig_ours), "b1": statistics.mean(orig_b1)},
        "tests": tests,
        "language_chi2": {"table": dict(zip(E.LANGS, table)), "chi2": chi2, "p": p_lang},
        "latency_end_to_end": {"mean": statistics.mean(a + b for a, b in zip(t_lat, q_lat)),
                               "p95": E.percentile([a + b for a, b in zip(t_lat, q_lat)], 95)},
        "remaining_failures": sum(1 for x in post if not x),
    }
    (OUT / "summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in out.items() if k != "systems"}, indent=1))
    for name, res in summary.items():
        print(f"{name:52} exact {100*res['exact']['mean']:.0f}% {[round(100*x) for x in res['exact']['ci95']]} "
              f"med {100*res['medicine']['mean']:.0f} dose {100*res['dose']['mean']:.0f} time {100*res['time']['mean']:.0f} "
              f"freq {100*res['frequency']['mean']:.0f} sched {100*res['schedulable']['mean']:.0f} "
              f"halluc {100*res['dose_hallucination_rate']:.0f} langs {res['by_language']}")


if __name__ == "__main__":
    {"translate": run_translate, "qwen": run_qwen, "score": run_score}[sys.argv[1]]()
