"""Style-layer extension of existing personas that have a background but no typing style.

Sources: the Nemotron-Personas country releases (structured demographics + persona texts in the country's language)
and PersonaHub (one English sentence). Each source persona becomes one bank-format persona: the background is a
faithful English conversion of the source (country, sub-region, occupation, education, hobbies), the style layer is
generated with the same rules as the joint bank prompt (generate_bank.style_layer_rules), and the original record is
kept verbatim under `source`.

Field provenance (`extension_meta`):
  pinned   copied from the source and enforced after generation (Nemotron: age, gender, country, region, main_language)
  sampled  drawn by us: ai_stance (fixed hash of the source id, uniform over the four stances) and the typing-style
           seed (grid_extended.sample_style_seed, seeded with the same hash)
  inferred digital_fluency comes from a short first call on the source (infer_fluency) and is then enforced, so the
           style seed is conditioned on it and llm_user_segment follows it (Low -> underrepresented), as in the bank;
           everything else the model fills (dialect, settlement_type, life_stage, job_title, ...)
For languages written in a caseless script (Japanese, Korean, Hindi, ...) the capitalization seed is fixed to
'Standard', since lowercase / first-word-only / ALL-CAPS have no meaning there.
PersonaHub personas are kept English: main_language is pinned to English, age / gender / country are inferred.

Stages:
  prep     sample N personas per Nemotron country + M PersonaHub personas from the local Hugging Face cache
           (download the datasets first: nvidia/Nemotron-Personas-<Country> for the 12 releases in NEMO, and
           proj-persona/PersonaHub) -> OUT/sources.jsonl
  gen      one shard of sources against an OpenAI-compatible endpoint (Gemma 4 31B), resumable
           -> OUT/gen/shard_XXXX.jsonl (failed sources are recorded with a `failed` reason)
  collect  successful rows of all shards -> OUT/raw/persona_bank_extend.jsonl (one per source) + OUT/gen_summary.json
Judge OUT/raw with judge_shards.py split + validate_personas.py like the bank (MiniMax-M2.5).

Usage:
    python -m personafactory.persona_bank.extend_style prep --out ./data/style_extension --per_country 160 --personahub 220
    python -m personafactory.persona_bank.extend_style gen --out ./data/style_extension --base_url http://HOST:8000/v1 \
        --shard_count 16 --shard_index 0 --concurrency 48
    python -m personafactory.persona_bank.extend_style collect --out ./data/style_extension
"""
import argparse, collections, concurrent.futures as cf, functools, glob, hashlib, json, os, random, threading

from personafactory.persona_bank.schema import json_schema


def hf_hub_cache():
    """Hugging Face hub cache directory (HF_HUB_CACHE, else $HF_HOME/hub, else ~/.cache/huggingface/hub)."""
    if os.environ.get('HF_HUB_CACHE'):
        return os.environ['HF_HUB_CACHE']
    return os.path.join(os.environ.get('HF_HOME', os.path.expanduser('~/.cache/huggingface')), 'hub')


NEMO_TEXT = ('persona', 'professional_persona', 'cultural_background', 'linguistic_background', 'hobbies_and_interests_list',
             'career_goals_and_ambitions')
NEMO_FACTS = ('age', 'sex', 'marital_status', 'household_type', 'family_type', 'migration_background', 'education_level',
              'education_degree', 'bachelors_field', 'employment_status', 'job_position', 'occupation', 'industry',
              'first_language', 'second_language', 'languages_spoken', 'zone', 'area', 'city', 'municipality', 'commune',
              'district', 'kreis', 'departement', 'department', 'planning_area', 'prefecture', 'province', 'state',
              'bundesland', 'region')
# release -> (bank country name, home language; None = per row)
NEMO = {'USA': ('USA', 'English'), 'UK': ('UK', 'English'), 'Singapore': ('Singapore', 'English'),
        'Germany': ('Germany', 'German'), 'France': ('France', 'French'), 'Belgium': ('Belgium', None),
        'Japan': ('Japan', 'Japanese'), 'Korea': ('South Korea', 'Korean'), 'Vietnam': ('Vietnam', 'Vietnamese'),
        'Brazil': ('Brazil', 'Portuguese'), 'El-Salvador': ('El Salvador', 'Spanish'), 'India': ('India', None)}
FEMALE = {'female', 'femme', 'vrouw', 'feminino', 'femenino', 'weiblich', '女', '여자', 'nữ'}
AI_STANCES = ['Pragmatic', 'Skeptical', 'Enthusiastic', 'Naive']
# main languages of the sources whose script has letter case; every other language gets capitalization = Standard
CASED_LANGUAGES = {'English', 'German', 'French', 'Dutch', 'Portuguese', 'Spanish', 'Vietnamese'}
FLUENCY_SCHEMA = {'type': 'object', 'properties': {'digital_fluency': {'type': 'string', 'enum': ['Low', 'Medium', 'High']}},
                  'required': ['digital_fluency']}
_RNG_LOCK = threading.Lock()   # sample_style_seed draws from the global RNG


@functools.lru_cache(maxsize=1)
def bank_regions():
    from personafactory.persona_bank import grid_extended as GX
    return {l[1]: l[0] for l in GX.all_locations_extended()}


# ---------------------------------------------------------------------------
# prep
# ---------------------------------------------------------------------------
def _nemo_rows(release, hf):
    import pyarrow.parquet as pq
    files = sorted(glob.glob(f'{hf}/datasets--nvidia--Nemotron-Personas-{release}/snapshots/*/data/*.parquet'))
    if release == 'Belgium':   # nl_BE and fr_BE hold the same people translated: Flanders in Dutch, the rest in French
        nl = [f for f in files if 'nl_BE' in f]
        fr = [f for f in files if 'fr_BE' in f]
        rows = {r['uuid']: r for r in pq.read_table(fr[0]).to_pylist()}
        for r in pq.read_table(nl[0]).to_pylist():
            if r['region'] == 'Vlaanderen':
                rows[r['uuid']] = r
        return [dict(r, _lang='Dutch' if r['region'] == 'Vlaanderen' else 'French') for r in rows.values()]
    if release == 'India':
        files = [f for f in files if 'en_IN' in f]
    return pq.read_table(files[0]).to_pylist()


def prep(a):
    rng = random.Random(a.seed)
    os.makedirs(a.out, exist_ok=True)
    n = 0
    with open(a.out + '/sources.jsonl', 'w', encoding='utf-8') as fo:
        for release, (country, lang) in NEMO.items():
            rows = _nemo_rows(release, a.hf_cache)
            if release == 'India':
                rows = [r for r in rows if r.get('first_language') not in (None, '', '-')]
            rows = [r for r in rows if 18 <= int(r['age']) <= 80]   # bank age range (schema: 18-80); no minors
            for r in rng.sample(rows, min(a.per_country, len(rows))):
                rec = {k: r[k] for k in NEMO_TEXT + NEMO_FACTS if r.get(k) not in (None, '', '-')}
                src = {'source': f'nvidia/Nemotron-Personas-{release}', 'source_id': r['uuid'], 'country': country,
                       'home_language': lang or r.get('_lang') or r['first_language'], 'age': int(r['age']),
                       'gender': 'Female' if str(r['sex']).strip().lower() in FEMALE else 'Male', 'record': rec}
                fo.write(json.dumps(src, ensure_ascii=False) + '\n')
                n += 1
        ph = glob.glob(f'{a.hf_cache}/datasets--proj-persona--PersonaHub/snapshots/*/persona.jsonl')[0]
        lines = open(ph, encoding='utf-8').read().splitlines()
        for i in sorted(rng.sample(range(len(lines)), a.personahub)):
            text = json.loads(lines[i])['persona']
            src = {'source': 'proj-persona/PersonaHub', 'source_id': f'persona.jsonl:{i}', 'country': None,
                   'home_language': 'English', 'age': None, 'gender': None, 'record': {'persona': text}}
            fo.write(json.dumps(src, ensure_ascii=False) + '\n')
            n += 1
    print('sources', n)


# ---------------------------------------------------------------------------
# gen
# ---------------------------------------------------------------------------
def build_extend_prompt(src, region, ai_stance, extra, schema_model):
    from personafactory.persona_bank.generate_bank import AGE_COHERENCE_RULE, LANGUAGE_FIELDS_RULE, list_rules, style_layer_rules
    rec = '\n'.join(f'{k}: {v}' for k, v in src['record'].items())
    if src['country']:
        fixed = (f"- Age: {src['age']}\n- Gender: {src['gender']}\n- Country: {src['country']} (macro region: {region})\n"
                 f"- Main language: {src['home_language']}\n- AI Stance: {ai_stance}\n- Digital Fluency: {extra['fluency']}")
        place = ('- "sub_region": the English name of the most specific REGION-level unit the source gives (state, '
                 'province, prefecture, Bundesland, departement, ...), not a street or a postcode.')
    else:
        fixed = f"- Main language: English\n- AI Stance: {ai_stance}\n- Digital Fluency: {extra['fluency']}"
        place = ('- "age", "gender", "country", "region", "sub_region": take them from the description when it implies '
                 'them; otherwise choose plausible values. The person lives in an English-speaking country (USA, UK, '
                 'Canada, Australia, Ireland, New Zealand) unless the description names another place, and main_language '
                 'stays English either way. "region" is the macro region of that country (e.g. North America, Western '
                 'Europe, Oceania).')
    return f"""You are an expert sociologist and character designer. Below is an EXISTING persona from another dataset ({src['source']}). It says who the person is, but not how they write. Convert it into ONE persona in our JSON schema: keep the background faithful to the source, and design the style layer.

SOURCE PERSONA (may be in another language):
<<<
{rec}
>>>

Fixed values (use EXACTLY these):
{fixed}

BACKGROUND layer — a faithful English conversion of the source, not a new person.
- Every background field must agree with the source. Translate to English; never contradict the source, and do not invent biography beyond what a field needs.
{place}
- "occupation": the source occupation as a concise English profession (turn codes or categories such as "815 Construction operatives" into a plain profession); "sector": a coarse sector grouping; "job_title": a short concrete title consistent with the source (max ~12 words, no real brands or companies).
- "education": the closest schema value for the source education level; field_of_study and institution_type consistent with it.
- "hobbies_interests": 3-6 items from the source hobbies and interests, translated.
- Fields the source does not state: "dialect" ("Standard" unless the source points to a regional variety), "settlement_type" and "life_stage" (from location, marital status and household fields when present).
{LANGUAGE_FIELDS_RULE}

{AGE_COHERENCE_RULE}

{style_layer_rules(extra.get('style_seed_block', ''), list_rules(extra))}
- The character_description must describe THIS source person (role, context, outlook) in English, without their personal name.

Strict JSON schema:
{json.dumps(json_schema(schema_model), indent=2)}

Output ONLY the JSON object, starting with {{ and ending with }}. No markdown wrappers, no explanations."""


def infer_fluency(client, model, src):
    """Step 1: digital fluency from the source alone, so the style seed and llm_user_segment can follow it."""
    rec = '\n'.join(f'{k}: {v}' for k, v in src['record'].items())
    prompt = f"""Below is a persona from {src['source']} (may be in another language). Rate this person's digital fluency:
- Low: phone calls and a messaging app at most; rarely types longer text or uses websites on their own.
- Medium: everyday smartphone and web use (search, shopping, social media, online forms).
- High: works or studies on a computer daily and picks up new software and online tools easily.
Infer it from age, occupation, education, location and the description; do not default to High.

<<<
{rec}
>>>

Answer with JSON only: {{"digital_fluency": "Low" | "Medium" | "High"}}"""
    for _ in range(3):
        try:
            r = client.chat.completions.create(
                model=model, messages=[{'role': 'user', 'content': prompt}], temperature=0.0, max_tokens=50,
                response_format={'type': 'json_schema', 'json_schema': {'name': 'fluency', 'schema': FLUENCY_SCHEMA}})
            f = json.loads(r.choices[0].message.content)['digital_fluency']
            if f in ('Low', 'Medium', 'High'):
                return f
        except Exception:
            continue
    return None


def extend_one(client, model, src, temperature, attempts=2):
    from personafactory.persona_bank import generate_bank as G, grid_extended as GX
    from personafactory.persona_bank.schema import PersonaExtended
    regions = bank_regions()
    h = int(hashlib.md5((src['source'] + src['source_id']).encode()).hexdigest(), 16)
    rnd = random.Random(h)
    ai_stance = AI_STANCES[h % 4]
    region = regions.get(src['country'])
    age = src['age'] or rnd.randint(22, 60)
    fluency = infer_fluency(client, model, src)
    if fluency is None:
        return None, 'fluency_inference'
    with _RNG_LOCK:
        st = random.getstate()
        random.seed(h)
        seed = GX.sample_style_seed(age, fluency, region or 'North America')
        random.setstate(st)
    if src['home_language'] not in CASED_LANGUAGES:
        seed['capitalization'] = 'Standard'
    extra = {'home_language': src['home_language'], 'style_seed_block': GX.style_seed_block(seed),
             'style_seed_canon': GX.style_seed_canonical(seed), 'fluency': fluency}
    seeded = {'main_language': src['home_language'], 'ai_stance': ai_stance, 'digital_fluency': fluency,
              'llm_user_segment': 'underrepresented' if fluency == 'Low' else 'core'}
    if src['country']:
        seeded.update(age=src['age'], gender=src['gender'], country=src['country'], region=region)
    prompt = build_extend_prompt(src, region, ai_stance, extra, PersonaExtended)
    for k in range(attempts):
        out = G.generate_joint_persona(client, model, None, None, None, None, None, None, None, None, None,
                                       temperature=temperature, extra=extra, schema_model=PersonaExtended,
                                       prompt=prompt, seeded=seeded)
        if out:
            bg = out['background']
            if not src['country'] and bg.get('country') in regions:
                bg['region'] = regions[bg['country']]
            pinned = ['main_language'] + (['age', 'gender', 'country', 'region'] if src['country'] else [])
            out['extension_meta'] = {'pinned': pinned, 'sampled': ['ai_stance', 'style_seed'],
                                     'inferred_first': {'digital_fluency': fluency},
                                     'style_seed': seed, 'attempts': k + 1}
            out['source'] = src
            return out, None
    return None, G.LAST_ATTEMPT.get('reason')


def gen(a):
    from openai import OpenAI
    srcs = [json.loads(l) for l in open(a.out + '/sources.jsonl', encoding='utf-8')]
    srcs = [s for i, s in enumerate(srcs) if i % a.shard_count == a.shard_index]
    os.makedirs(a.out + '/gen', exist_ok=True)
    path = f'{a.out}/gen/shard_{a.shard_index:04d}.jsonl'
    done = set()
    if os.path.exists(path):
        for l in open(path, encoding='utf-8'):
            try:
                r = json.loads(l)
                done.add(r['source']['source_id'] if 'source' in r else r['source_id'])
            except Exception:
                pass
    todo = [s for s in srcs if s['source_id'] not in done]
    print(f'shard {a.shard_index}: {len(todo)} to do, {len(done)} done', flush=True)
    client = OpenAI(base_url=a.base_url, api_key=os.environ.get('PF_API_KEY', 'EMPTY'), timeout=600)
    lock = threading.Lock()
    with open(path, 'a', encoding='utf-8') as fo, cf.ThreadPoolExecutor(a.concurrency) as ex:
        futs = {ex.submit(extend_one, client, a.model_name, s, a.temperature): s for s in todo}
        for i, f in enumerate(cf.as_completed(futs)):
            s = futs[f]
            out, why = f.result()
            rec = out if out else {'source_id': s['source_id'], 'source': s['source'], 'failed': why}
            with lock:
                fo.write(json.dumps(rec, ensure_ascii=False) + '\n')
                if i % 100 == 0:
                    fo.flush()
                    print(f'  {i}/{len(todo)}', flush=True)


def collect(a):
    """Successful rows of every gen shard -> OUT/raw/persona_bank_extend.jsonl (one per source id)."""
    ok, st = {}, collections.Counter()
    for f in sorted(glob.glob(a.out + '/gen/shard_*.jsonl')):
        for l in open(f, encoding='utf-8'):
            r = json.loads(l)
            if r.get('failed') is not None or 'id' not in r:
                st['failed/' + str(r.get('failed'))] += 1
                continue
            ok[r['source']['source_id']] = r
            st['ok/' + r['source']['source']] += 1
    os.makedirs(a.out + '/raw', exist_ok=True)
    with open(a.out + '/raw/persona_bank_extend.jsonl', 'w', encoding='utf-8') as fo:
        for r in ok.values():
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')
    json.dump(dict(sorted(st.items())), open(a.out + '/gen_summary.json', 'w'), indent=1)
    print(json.dumps(dict(sorted(st.items())), indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stage', choices=['prep', 'gen', 'collect'])
    ap.add_argument('--out', required=True, help='run directory')
    ap.add_argument('--hf_cache', default=hf_hub_cache(), help='Hugging Face hub cache with the source datasets (prep)')
    ap.add_argument('--seed', type=int, default=0, help='sampling seed of prep')
    ap.add_argument('--per_country', type=int, default=500, help='Nemotron-Personas records per country release (prep)')
    ap.add_argument('--personahub', type=int, default=1000, help='PersonaHub records (prep)')
    ap.add_argument('--model_name', default='google/gemma-4-31B-it', help='served generator name (gen)')
    ap.add_argument('--base_url', default=os.environ.get('PF_BASE_URL'), help='OpenAI-compatible .../v1 URL (gen)')
    ap.add_argument('--temperature', type=float, default=0.8)
    ap.add_argument('--concurrency', type=int, default=32, help='sources in flight per shard (gen)')
    ap.add_argument('--shard_count', type=int, default=1)
    ap.add_argument('--shard_index', type=int, default=0)
    a = ap.parse_args()
    {'prep': prep, 'gen': gen, 'collect': collect}[a.stage](a)


if __name__ == '__main__':
    main()
