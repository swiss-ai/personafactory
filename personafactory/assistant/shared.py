"""Helpers shared by the scripts of the assistant package: stable hashing, persona-bank lookup, parsing of the
matcher's ranking, resumable output bookkeeping, loading of accepted pipeline records, and the post-hoc
restyler (used by assistant.augment_assistant_only and assistant.pilot_restyle)."""
import glob, hashlib, json, os, re

from personafactory.assistant import model_persona

RESTYLE_GEN = {'max_tokens': 8192, 'temperature': 0.7, 'top_p': 0.95}
API_KEY = os.environ.get('PF_API_KEY', 'dummy')  # local vLLM / SGLang servers ignore the key


def add_server_args(ap, judge_required=True):
    """Endpoints: OpenAI-compatible base URLs (.../v1), comma-separated replicas, plus served model names."""
    env = os.environ.get
    ap.add_argument('--gemma', default=env('PF_GEMMA_URL', ''), help='Gemma responder URL(s) (or PF_GEMMA_URL)')
    ap.add_argument('--ministral', default=env('PF_MINISTRAL_URL', ''), help='Ministral responder URL(s) (or PF_MINISTRAL_URL)')
    ap.add_argument('--minimax', default=env('PF_MINIMAX_URL', ''), required=judge_required and 'PF_MINIMAX_URL' not in os.environ,
                    help='judge / matcher URL(s) (or PF_MINIMAX_URL)')
    ap.add_argument('--gemma-model', default=env('PF_GEMMA_MODEL', 'gemma'), help='served model name')
    ap.add_argument('--ministral-model', default=env('PF_MINISTRAL_MODEL', 'ministral'), help='served model name')
    ap.add_argument('--minimax-model', default=env('PF_MINIMAX_MODEL', 'MiniMax-M2.5'), help='served model name')


def setup_judge(a):
    """Point common.judge_client at the --minimax servers; returns the judge config for the pipeline (or None)."""
    from personafactory.common import judge_client
    mm = [u for u in a.minimax.split(',') if u]
    judge_client.MODEL = a.minimax_model
    if not mm:
        return None
    judge_client.URLS = [u + '/chat/completions' for u in mm]
    return {'base_url': mm[0], 'base_urls': mm, 'api_key': API_KEY, 'model': a.minimax_model}


def responder_urls(a):
    return {'gemma': [u for u in a.gemma.split(',') if u], 'ministral': [u for u in a.ministral.split(',') if u]}


def responders(a, names=('gemma', 'ministral')):
    """Pipeline responder entries (one per replica) for the given responder names; the pipeline picks by name."""
    urls, served = responder_urls(a), {'gemma': a.gemma_model, 'ministral': a.ministral_model}
    return [{'name': n, 'base_url': u, 'api_key': API_KEY, 'model': served[n]} for n in names for u in urls[n]]


def h(*parts):
    """Stable integer hash of the joined parts (drives every deterministic per-conversation choice)."""
    return int(hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest(), 16)


def bank_for(bank_path, ids):
    """Persona-bank records (persona_bank.jsonl) whose id is in ids."""
    bank = {}
    for l in open(bank_path, encoding='utf-8'):
        p = json.loads(l)
        if p['id'] in ids:
            bank[p['id']] = p
    return bank


def parse_ranking(text):
    """Matcher output -> (ranking of valid persona ids, reason), or (None, None) if unusable."""
    text = (text or '').split('</think>')[-1]
    m = re.search(r'\{.*\}', text, re.S)
    try:
        d = json.loads(m.group(0))
        rk = [x for x in d.get('ranking', []) if x in model_persona.BY_ID]
        return (rk, d.get('reason', '')) if rk else (None, None)
    except Exception:
        return None, None


def done_ids(fp):
    """Ids already written to a resumable JSONL output."""
    s = set()
    if os.path.exists(fp):
        for l in open(fp, encoding='utf-8'):
            try:
                s.add(json.loads(l)['id'])
            except Exception:
                pass
    return s


def accepted_records(source_dir):
    """Accepted records (status pass, with a result) of augmentation.run_augmentation output files in source_dir."""
    recs = []
    for fp in sorted(glob.glob(os.path.join(source_dir, '*.jsonl'))):
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            if r.get('status') == 'pass' and r.get('result'):
                recs.append(r)
    return recs


async def restyle(session, responder, persona, user_message, response):
    """Post-hoc restyle of one assistant reply in the persona's style. Code, numbers, URLs and quotes are
    protected; a restyle that loses a protected span or shrinks below 50% of the original is retried (3 tries),
    then the original reply is returned with the failure reason. Returns (text, failure or None)."""
    from personafactory.augmentation import integrity, pipeline
    masked, spans = integrity.protect(response)
    prompt = model_persona.RESTYLE_PROMPT.format(style=model_persona.render_model_persona(persona),
                                                 user_message=user_message, response=masked)
    if spans:
        prompt += '\n\n' + integrity.protection_instruction().strip()
    last = None
    for _ in range(3):
        text, err = await pipeline.call_api(session, responder, RESTYLE_GEN, [{'role': 'user', 'content': prompt}],
                                            error_prefix='RESTYLE', is_judge=False)
        if not text or err:
            last = f'empty_or_error: {err}'
            continue
        try:
            text = pipeline.sanitize_constitution(integrity.restore(text.strip(), spans))
        except ValueError:
            last = 'literal_integrity'
            continue
        if len(response) >= 50 and len(text) < 0.5 * len(response):
            last = 'truncated'
            continue
        return text, None
    return response, last
