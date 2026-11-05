"""LLM-as-judge plausibility / quality filter for a persona bank.

Judges each persona on: internal coherence (occupation vs fluency vs age vs
education), profession-vs-location plausibility, LLM-user plausibility (would this
person realistically use an AI chat assistant?), stereotype severity, and realism.

Default mode is SCORE-AND-TAG: every persona is kept and annotated with a
`validation` block, so you can tune the threshold later. Pass --reject to split
the bank into kept vs rejected files.

Non-optimistic fallback (per the audit): a parse failure or an unavailable judge
is recorded as verdict "unscored" and is NEVER counted as a pass. In --reject mode
unscored rows go to the rejected file, not the clean one.

Repairs (two-pass): the judge may return a corrected digital_fluency (implausibly low
fluency for a technical role), a concise job_title (age-incoherent or rambling title), and
corrected reference_pool / linguistic_quirks lists. Repairs are applied in place and the
repaired persona is judged a second time for the final verdict.

Usage (base-grid profiles: 120 shards of one file, --max_tokens 1600, merged with finalize_bank;
extended-grid profiles: pre-split files from judge_shards.py split, default --max_tokens 3072):
    python -m personafactory.persona_bank.validate_personas \
        --input  ./data/persona_bank/base/persona_bank_all.jsonl \
        --output ./data/persona_bank/base/persona_bank_all.validated.jsonl \
        --judge-model MiniMaxAI/MiniMax-M2.5 \
        --base-url http://localhost:30000/v1 \
        --shard_count 120 --shard_index 0 --max_tokens 1600
    # add --sample 300 to judge a random 300 first as a spot check
"""
import os
import json
import argparse
import random
import threading
import time
import concurrent.futures as cf
from openai import OpenAI
try:  # optional: read PF_* variables from a local .env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_BASE_URL = os.environ.get("PF_JUDGE_BASE_URL", "http://localhost:8000/v1")
# MiniMax is the natural judge: it is NOT one of the generators, so no self-preference.
DEFAULT_JUDGE = "MiniMaxAI/MiniMax-M2.5"

REQUIRED_KEYS = ("coherent", "location_plausible", "llm_user_plausible",
                 "stereotype_severity", "realism", "verdict", "fluency_fix", "job_title_fix",
                 "reference_fix", "quirks_fix")

# Guided-decoding schema for the judge: forces a clean verdict JSON (no reasoning
# leakage), so reasoning judges like MiniMax don't blow the token budget on <think>.
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "coherent": {"type": "boolean"},
        "location_plausible": {"type": "boolean"},
        "llm_user_plausible": {"type": "boolean"},
        "stereotype_severity": {"type": "integer", "minimum": 0, "maximum": 3},
        "realism": {"type": "integer", "minimum": 0, "maximum": 3},
        "verdict": {"type": "string", "enum": ["keep", "reject"]},
        "reason": {"type": "string"},
        "fluency_fix": {"type": "string", "enum": ["keep_as_is", "Low", "Medium", "High"]},
        "job_title_fix": {"type": "string"},
        # reference_fix / quirks_fix: [] = keep as-is; a non-empty list REPLACES the field with an
        # age-coherent, contemporary, non-caricatured version (see prompt).
        "reference_fix": {"type": "array", "items": {"type": "string"}},
        "quirks_fix": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["coherent", "location_plausible", "llm_user_plausible",
                 "stereotype_severity", "realism", "verdict", "reason",
                 "fluency_fix", "job_title_fix", "reference_fix", "quirks_fix"],
    "additionalProperties": False,
}


def _line(r) -> str:
    """Readable JSON line, resilient to broken lone surrogates in model output."""
    s = json.dumps(r, ensure_ascii=False)
    try:
        s.encode("utf-8")
        return s + "\n"
    except UnicodeEncodeError:
        return json.dumps(r, ensure_ascii=True) + "\n"


def persona_summary(p: dict) -> str:
    """Compact human-readable rendering of a persona for the judge."""
    b = p.get("background", {})
    s = p.get("style", {})
    edu = b.get("education", {})
    edu_str = edu.get("level", "") if isinstance(edu, dict) else str(edu)
    lines = [
        f"Region/Country/Sub-region: {b.get('region')} / {b.get('country')} / {b.get('sub_region')}",
        f"Profession (sector): {b.get('occupation')} ({b.get('sector')})",
        f"Job title: {b.get('job_title')}",
        f"Age / Gender: {b.get('age')} / {b.get('gender')}",
        f"Education: {edu_str}",
        f"Native language (dialect): {b.get('native_language')} ({b.get('dialect')})",
        f"AI stance / Digital fluency: {b.get('ai_stance')} / {b.get('digital_fluency')}",
        f"LLM-user segment (self-declared): {b.get('llm_user_segment', 'core')}",
        f"Chatting style: {s.get('chatting_style')}",
        f"Example message: {s.get('example_message')}",
        f"Linguistic quirks: {s.get('linguistic_quirks')}",
        f"Reference pool: {s.get('reference_pool')}",
        f"Character: {p.get('character_description')}",
    ]
    # extended grid: seeded settlement / life stage are shown to the judge when present (base-grid rows have
    # neither field, so their summary does not change).
    extra = []
    if b.get("settlement_type"):
        extra.append(f"Settlement type: {b.get('settlement_type')}")
    if b.get("life_stage"):
        extra.append(f"Life stage: {b.get('life_stage')}")
    if extra and b.get("main_language"):   # extended-grid rows only: lets the judge check seeded home languages
        extra.append(f"Main language: {b.get('main_language')}")
    if extra and b.get("region") == "LATAM":   # display only: the judge reads "LATAM" as excluding the Caribbean
        lines[0] = lines[0].replace("LATAM /", "Latin America & Caribbean /", 1)
    if extra:
        lines[5:5] = extra
    return "\n".join(lines)


def build_judge_prompt(p: dict) -> str:
    return f"""You are a strict data-quality auditor for a synthetic persona bank used to
personalise chat-assistant prompts. Judge ONE persona. Be skeptical — it is better to
flag a borderline persona than to wave it through.

Evaluate:
- coherence: are occupation, digital_fluency, age, and education mutually consistent?
  (e.g. a backend developer must NOT be "Low" digital fluency; a 75-year-old subsistence
  worker is unlikely to be an "Enthusiastic High-fluency" AI user.)
- location plausibility: could this profession plausibly exist for someone in this
  country/sub-region? Remote work and regional exceptions are allowed; obvious mismatches
  are not.
- LLM-user plausibility: would THIS person realistically open and use an AI chat assistant?
  (An "underrepresented" low-fluency persona may still be plausible for very simple requests;
  judge honestly.)
- stereotype severity: 0 = none, 3 = egregious demographic caricature.
- realism: 0 = generic/fake, 3 = vivid and believable.

Return ONLY this JSON object (no markdown, no commentary):
{{
  "coherent": true or false,
  "location_plausible": true or false,
  "llm_user_plausible": true or false,
  "stereotype_severity": 0,
  "realism": 0,
  "fluency_fix": "keep_as_is" or "Low" or "Medium" or "High",
  "job_title_fix": "keep_as_is" or a short corrected title,
  "reference_fix": [] or a corrected list of 3-6 reference items,
  "quirks_fix": [] or a corrected list of 2-4 linguistic quirks,
  "verdict": "keep" or "reject",
  "reason": "one short sentence"
}}
Job-title repair: if "job_title" is incoherent with the age (implausible seniority — e.g.
"Senior"/"Head"/"Lead"/"Chief" or "N years of experience" for someone in their 20s) OR is
rambling (a full sentence/paragraph, or narrates day-to-day tasks), set "job_title_fix" to a
concise corrected title — a brief phrase, max ~12 words, consistent with the occupation and
age (do NOT restate the country/region). Otherwise set "job_title_fix" to "keep_as_is".
Digital-fluency repair: if the ONLY coherence problem is that digital_fluency is
implausibly LOW (or high) for this occupation (e.g. a developer, designer, video
editor, engineer, urban planner, accountant marked "Low"), set "fluency_fix" to the
plausible level and judge "coherent"/"verdict" AS IF the fluency were already corrected
to that level. Otherwise set "fluency_fix" to "keep_as_is". Do NOT raise fluency for
personas where a low level is genuinely plausible (manual/rural/elderly/low-education
"underrepresented" users) — those low-fluency personas are intentional and valid.
Reference-pool / quirks repair (AGE COHERENCE — important): "reference_pool" and
"linguistic_quirks" must be culturally coherent AND fit the persona's AGE. A person in their
teens/20s/30s references the culture THEY grew up with (2010s-2020s: current apps, creators,
games, streamers, music, memes, slang) — NOT obsolete tech (floppy disks, VHS, cassettes,
dial-up, rotary phones, fax, typewriters, disk drives), NOT dead decades (1960s-1990s / Cold-War
/ Soviet / "old country" nostalgia), NOT ancestor tropes ("grandmother's joke book",
"dad's war stories") presented as THEIR own world. Only genuinely older personas (roughly 50+)
carry firsthand older-era references. Every item must also be internally coherent (no
mislabelled objects, e.g. calling a smartphone "headphones"). Using bygone-era or Soviet/Russian
clichés to signal a nationality is a caricature, not realism. If "reference_pool" contains ANY
age-mismatched, anachronistic, incoherent, or nationality-caricature item, set "reference_fix" to
a fully corrected 3-6 item list (contemporary, age- and locale-appropriate, coherent); otherwise
set "reference_fix" to []. Apply the SAME rule to "linguistic_quirks" via "quirks_fix" (a
corrected 2-4 item list, or [] to keep). These two repairs do NOT change the verdict.
Set "verdict" to "reject" if (after any fluency_fix and job_title_fix) coherent is false, OR
llm_user_plausible is false, OR location_plausible is false, OR stereotype_severity >= 2.

Persona:
{persona_summary(p)}
"""


def parse_verdict(text: str) -> dict:
    """Extract the judge JSON. Returns an 'unscored' verdict on any failure,
    NEVER a silent pass."""
    if not text:
        return {"verdict": "unscored", "error": "empty_response"}
    if "</think>" in text:
        text = text.split("</think>")[-1]
    if "```json" in text:
        text = text.split("```json")[-1]
    text = text.replace("```", "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {"verdict": "unscored", "error": "no_json"}
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {"verdict": "unscored", "error": "bad_json"}
    if not all(k in data for k in REQUIRED_KEYS):
        return {"verdict": "unscored", "error": "missing_keys", "raw": data}
    if data.get("verdict") not in ("keep", "reject"):
        return {"verdict": "unscored", "error": "bad_verdict", "raw": data}
    return data


# Per-persona judge bookkeeping: calls, tokens, truncations. Stored in validation.judge_meta.
# Per thread, so --concurrency workers do not mix each other's counts; single-threaded it is a plain dict.
class _PerThreadDict(threading.local):
    def __init__(self):
        self.d = {}

    def __getattr__(self, name):
        return getattr(self.d, name)

    def __getitem__(self, k):
        return self.d[k]

    def __setitem__(self, k, v):
        self.d[k] = v

    def __iter__(self):
        return iter(self.d)


JUDGE_META = _PerThreadDict()
MAX_TOKENS = 3072   # set from --max_tokens; MiniMax-M2.5 always thinks first, 1600 truncated some verdicts


def judge_persona(client, model, p, retries=2):
    prompt = build_judge_prompt(p)
    for _ in range(retries + 1):
        try:
            JUDGE_META["calls"] = JUDGE_META.get("calls", 0) + 1
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=MAX_TOKENS,   # thinking + room for reference_fix/quirks_fix corrected lists
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "verdict", "schema": VERDICT_SCHEMA}},
            )
            u = getattr(resp, "usage", None)
            if u is not None:
                JUDGE_META["prompt_tokens"] = JUDGE_META.get("prompt_tokens", 0) + (u.prompt_tokens or 0)
                JUDGE_META["completion_tokens"] = JUDGE_META.get("completion_tokens", 0) + (u.completion_tokens or 0)
            if getattr(resp.choices[0], "finish_reason", None) == "length":
                JUDGE_META["truncated"] = JUDGE_META.get("truncated", 0) + 1
            msg = resp.choices[0].message
            content = msg.content or getattr(msg, "reasoning_content", "") or ""
            verdict = parse_verdict(content)
            if verdict.get("verdict") != "unscored":
                return verdict
        except Exception as e:
            last = {"verdict": "unscored", "error": f"api:{type(e).__name__}"}
            continue
    return locals().get("last", {"verdict": "unscored", "error": "exhausted"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Persona bank JSONL to validate.")
    ap.add_argument("--output", required=True, help="Annotated JSONL output.")
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE)
    ap.add_argument("--base-url", default=API_BASE_URL)
    ap.add_argument("--sample", type=int, default=0,
                    help="Judge a random N (0 = all). Deterministic under --seed.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reject", action="store_true",
                    help="Split output into kept vs <output>.rejected.jsonl.")
    ap.add_argument("--shard_count", type=int, default=1,
                    help="Parallel judge shards over the (sampled) personas.")
    ap.add_argument("--shard_index", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=1,
                    help="Personas judged in parallel against the endpoint (1 = sequential, as before).")
    ap.add_argument("--max_tokens", type=int, default=3072,
                    help="Judge completion budget (MiniMax-M2.5 reasons first). Base-grid profiles were judged "
                         "with 1600, extended-grid profiles with 3072.")
    args = ap.parse_args()
    global MAX_TOKENS
    MAX_TOKENS = args.max_tokens

    # Self-served OpenAI-compatible endpoints accept any key; set PF_API_KEY if yours needs one.
    api_key = os.environ.get("PF_API_KEY", "EMPTY")
    client = OpenAI(api_key=api_key, base_url=args.base_url)

    personas = []
    with open(args.input) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    personas.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    print(f"Loaded {len(personas)} personas from {args.input}")

    if args.sample and args.sample < len(personas):
        random.seed(args.seed)
        personas = random.sample(personas, args.sample)
        print(f"Sampling {len(personas)} for judging.")

    if args.shard_count > 1:
        personas = personas[args.shard_index::args.shard_count]
        base, ext = os.path.splitext(args.output)
        args.output = f"{base}.shard{args.shard_index:02d}of{args.shard_count:02d}{ext}"
        print(f"Shard {args.shard_index}/{args.shard_count}: {len(personas)} personas -> {args.output}")

    # Incremental + resumable (default annotate mode): skip personas already present in
    # the output file and append as we go, so a killed/timed-out shard can be re-run to
    # continue instead of restarting from zero.
    out_fh = None
    if not args.reject:
        done_ids = set()
        if os.path.exists(args.output):
            with open(args.output, errors="ignore") as f:
                for line in f:
                    try:
                        done_ids.add(json.loads(line).get("id"))
                    except Exception:
                        pass
        if done_ids:
            before = len(personas)
            personas = [p for p in personas if p.get("id") not in done_ids]
            print(f"Resuming: {len(done_ids)} already judged, {len(personas)} of {before} remaining.")
        out_fh = open(args.output, "a")

    stats = {"keep": 0, "reject": 0, "unscored": 0}
    stereo = {0: 0, 1: 0, 2: 0, 3: 0}
    realism_sum = realism_n = 0
    repaired = 0        # digital_fluency repairs
    jt_repaired = 0     # job_title repairs
    ref_repaired = 0    # reference_pool repairs (age-coherence / anti-caricature)
    quirks_repaired = 0 # linguistic_quirks repairs
    kept, rejected = [], []

    def _clean_list(x, lo, hi):
        """Accept the judge's corrected list only if it's a sane, non-trivial replacement."""
        if not isinstance(x, list):
            return None
        items = [str(t).strip() for t in x if str(t).strip()]
        return items if lo <= len(items) <= hi else None

    def judge_one(p):
        JUDGE_META.clear()
        t_start = time.time()
        v = judge_persona(client, args.judge_model, p)
        first_verdict = v.get("verdict")
        bg = p.get("background", {})
        fr = jr = None
        # Judge-repair 1: bump an implausibly-low digital_fluency for occupation-incoherent
        # personas (keep them instead of discarding); genuine low-fluency personas are left
        # alone (judge returns keep_as_is for those).
        fix = v.get("fluency_fix")
        if fix in ("Low", "Medium", "High") and fix != bg.get("digital_fluency"):
            fr = {"from": bg.get("digital_fluency"), "to": fix}
            bg["digital_fluency"] = fix
            bg["llm_user_segment"] = "underrepresented" if fix == "Low" else "core"
        # Judge-repair 2: rewrite an age-incoherent or rambling job_title into a concise one.
        jt = (v.get("job_title_fix") or "").strip()
        if jt and jt.lower() != "keep_as_is" and jt != (bg.get("job_title") or "").strip():
            jr = {"from": bg.get("job_title"), "to": jt}
            bg["job_title"] = jt
        # Judge-repair 3/4: rewrite an age-mismatched / caricatured reference_pool or
        # linguistic_quirks with the judge's corrected, contemporary list. [] means keep.
        stl = p.setdefault("style", {})
        rrf = qrf = None
        rf = _clean_list(v.get("reference_fix"), 3, 8)
        if rf and rf != (stl.get("reference_pool") or []):
            rrf = {"from": stl.get("reference_pool"), "to": rf}
            stl["reference_pool"] = rf
        qf = _clean_list(v.get("quirks_fix"), 2, 5)
        if qf and qf != (stl.get("linguistic_quirks") or []):
            qrf = {"from": stl.get("linguistic_quirks"), "to": qf}
            stl["linguistic_quirks"] = qf
        # The judge applies a fix but does NOT reliably re-score "as if corrected" (it
        # rejects citing the very issue it just fixed). So when we repaired something,
        # re-judge the now-repaired persona for a truthful final verdict.
        if fr or jr or rrf or qrf:
            v = judge_persona(client, args.judge_model, p)
        if fr:
            v["fluency_repaired"] = fr
        if jr:
            v["job_title_repaired"] = jr
        if rrf:
            v["reference_repaired"] = rrf
        if qrf:
            v["quirks_repaired"] = qrf
        v["judge_meta"] = dict(JUDGE_META, first_pass_verdict=first_verdict,
                               second_pass=bool(fr or jr or rrf or qrf),
                               seconds=round(time.time() - t_start, 2), t_done=time.time())
        p["validation"] = v
        return p, bool(fr), bool(jr), bool(rrf), bool(qrf)

    def results():
        if args.concurrency <= 1:
            for p in personas:
                yield judge_one(p)
            return
        with cf.ThreadPoolExecutor(args.concurrency) as ex:
            for f in cf.as_completed([ex.submit(judge_one, p) for p in personas]):
                yield f.result()

    for i, (p, fr, jr, rrf, qrf) in enumerate(results(), 1):
        v = p["validation"]
        repaired += fr
        jt_repaired += jr
        ref_repaired += rrf
        quirks_repaired += qrf
        if out_fh is not None:
            out_fh.write(_line(p))
            out_fh.flush()
        verdict = v.get("verdict", "unscored")
        stats[verdict] = stats.get(verdict, 0) + 1
        if verdict != "unscored":
            sev = v.get("stereotype_severity")
            if sev in stereo:
                stereo[sev] += 1
            if isinstance(v.get("realism"), (int, float)):
                realism_sum += v["realism"]
                realism_n += 1
        (kept if verdict == "keep" else rejected).append(p)
        if i % 50 == 0:
            print(f"  [{i}/{len(personas)}] keep={stats['keep']} "
                  f"reject={stats['reject']} unscored={stats['unscored']}")

    if args.reject:
        with open(args.output, "w") as f:
            for p in kept:
                f.write(json.dumps(p) + "\n")
        rej_path = args.output + ".rejected.jsonl"
        with open(rej_path, "w") as f:
            for p in rejected:  # rejected + unscored (unscored is NOT a pass)
                f.write(json.dumps(p) + "\n")
        print(f"\nWrote {len(kept)} kept -> {args.output}")
        print(f"Wrote {len(rejected)} rejected/unscored -> {rej_path}")
    else:
        if out_fh is not None:
            out_fh.close()
        print(f"\nWrote {len(personas)} annotated (incremental) -> {args.output}")

    total_scored = stats["keep"] + stats["reject"]
    print("\n=== Summary ===")
    print(f"keep={stats['keep']}  reject={stats['reject']}  unscored={stats['unscored']}")
    print(f"fluency-repaired: {repaired}  job_title-repaired: {jt_repaired}  "
          f"reference_pool-repaired: {ref_repaired}  quirks-repaired: {quirks_repaired}")
    if total_scored:
        print(f"keep rate (of scored): {stats['keep'] / total_scored:.1%}")
    if realism_n:
        print(f"mean realism: {realism_sum / realism_n:.2f} / 3")
    print(f"stereotype severity dist: {stereo}")
    if stats["unscored"]:
        print(f"NOTE: {stats['unscored']} unscored (judge/parse failures), NOT counted as pass.")


if __name__ == "__main__":
    main()
