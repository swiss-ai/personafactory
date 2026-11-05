"""Helpers shared by the downstream fine-tuning scripts: loading the released corpus and persona bank (Hugging Face
dataset, local parquet, or a pipeline release directory), message cleaning, the held-out persona rule, the token cap
and the SFT source record format."""
import glob, hashlib, json, os

HF_REPO = 'swiss-ai/PersonaFactory'
SETTING = {'free': 'language_matched', 'multilingual': 'cross_lingual'}
HELDOUT_SEED = 'pf-downstream-20261104'   # fixes the 5% held-out persona set of the paper
HELDOUT_FRAC = 0.05
MAX_TOKENS = 3800                          # contents + 10 tokens per turn must fit the 4,096-token packing window


def _rows_parquet(files):
    import pyarrow.parquet as pq
    for fp in files:
        for batch in pq.ParquetFile(fp).iter_batches(batch_size=4096):
            yield from batch.to_pylist()


def _rows_jsonl(files):
    for fp in files:
        with open(fp, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def iter_rows(spec, config):
    """Rows of a local file / dir / glob (parquet or JSONL) or of a Hugging Face dataset (`repo` or `repo:config`)."""
    if os.path.isdir(spec):
        for pattern in ('data/*.jsonl', '*.jsonl', f'{config}/*.parquet', 'data/*.parquet', '*.parquet', '**/*.parquet'):
            files = sorted(glob.glob(os.path.join(spec, pattern), recursive=True))
            if files:
                spec = os.path.join(spec, pattern)
                break
    files = sorted(glob.glob(spec))
    if files:
        return _rows_parquet(files) if files[0].endswith('.parquet') else _rows_jsonl(files)
    from datasets import load_dataset
    repo, _, cfg = spec.partition(':')
    return iter(load_dataset(repo, cfg or config, split='train', streaming=True))


def responder_name(model_id):
    m = (model_id or '').lower()
    return 'gemma' if 'gemma' in m else 'ministral' if 'ministral' in m else model_id


def load_release(spec=HF_REPO):
    """Yield released conversations in one shape: id, messages, persona_id, language, setting, match_tier, source,
    source_id, original_prompt, num_turns, responder (pipeline responder name: gemma / ministral).
    Accepts the published `chats` subset (hub id, local snapshot or parquet) or a pipeline release directory."""
    for r in iter_rows(spec, 'chats'):
        if 'messages' in r:   # published schema
            lang = r.get('language')
            yield {'id': r['id'], 'messages': r['messages'], 'persona_id': r['persona_id'], 'language': lang or 'Unknown',
                   'setting': r['setting'], 'match_tier': r.get('match_tier'), 'source': r.get('source'),
                   'source_id': r.get('source_id'), 'original_prompt': r.get('original_prompt'),
                   'num_turns': r.get('num_turns'), 'responder': responder_name(r.get('responder'))}
        else:                 # pipeline release directory (release/build_release.py schema)
            yield {'id': r['id'], 'messages': r['conversation'], 'persona_id': r['persona_id'],
                   'language': r.get('text_language') or 'Unknown', 'setting': SETTING.get(r.get('language_mode')),
                   'match_tier': r.get('match_basis'), 'source': r.get('source_name'),
                   'source_id': r.get('source_id') or (r['id'] if ':' in r['id'] else None),
                   'original_prompt': r.get('source_text'), 'num_turns': r.get('num_turns'),
                   'responder': responder_name(r.get('responder'))}


def load_bank(spec, ids=None):
    """Persona bank records (JSONL, parquet, or the published `persona_bank` subset) whose id is in ids (all if None)."""
    bank = {}
    for p in iter_rows(spec, 'persona_bank'):
        if ids is None or p['id'] in ids:
            bank[p['id']] = p
    return bank


def clean(conv):
    """[{role, content}] with strictly alternating, non-empty user/assistant turns ending with the assistant, else None."""
    msgs = [{'role': m['role'], 'content': m['content']} for m in conv or [] if m['role'] in ('user', 'assistant')]
    ok = (len(msgs) >= 2 and len(msgs) % 2 == 0
          and all(m['role'] == ('user' if i % 2 == 0 else 'assistant') for i, m in enumerate(msgs))
          and all(isinstance(m['content'], str) and m['content'].strip() for m in msgs))
    return msgs if ok else None


def heldout(pid, frac=HELDOUT_FRAC, seed=HELDOUT_SEED):
    """Persona-level hold-out: a fixed hash of (seed, persona id) puts frac of all personas out of every arm."""
    return int(hashlib.sha256(f'{seed}\0{pid}'.encode()).hexdigest(), 16) % 10000 < frac * 10000


def token_counter(tokenizer):
    """Apertus tokenizer (tokenizer.json path, model dir or hub id) -> conv -> contents tokens + 10 per turn
    (the chat template adds about 10 tokens per turn)."""
    from tokenizers import Tokenizer
    if os.path.isdir(tokenizer):
        tokenizer = os.path.join(tokenizer, 'tokenizer.json')
    tok = Tokenizer.from_file(tokenizer) if os.path.isfile(tokenizer) else Tokenizer.from_pretrained(tokenizer)
    return lambda conv: sum(len(e.ids) + 10 for e in tok.encode_batch([m['content'] for m in conv]))


def sft_record(rid, language, messages):
    """Source record of the Megatron prepare step (megatron/prepare_dataset.py): one conversation, split by family_id."""
    return {'id': rid, 'family_id': rid, 'language': language, 'response_mode': 'chat', 'training_role': 'chat',
            'messages': messages}


def sha256_file(path):
    d = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            d.update(chunk)
    return d.hexdigest()
