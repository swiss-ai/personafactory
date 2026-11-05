"""Judge-free rewrite metrics shared by the persona-format comparison.

Lexical transformation depth (token Jaccard, core-vocabulary retention, normalized edit distance), entity retention
(numbers, code, quoted literals), LaBSE similarity (sentence-transformers, GPU), and style-register adherence
(capitalization, punctuation, emoji) of a rewrite against a persona's declared structured style keys. These are the
corpus-scale fidelity metric definitions of the evaluation appendix, applied per item.
"""
import os
import re
from typing import Dict, List, Any, Tuple, Set, Optional
import numpy as np

MAX_LEVENSHTEIN_CHARS = 500
STYLE_ADHERENCE_THRESHOLD = 0.70


# -----------------------------------------------------------------------------
# Lexical, entity and embedding metrics
# -----------------------------------------------------------------------------

def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1] * (len(s2) + 1)
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr[j + 1] = min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost)
        prev = curr
    return prev[-1]


def tokenize_multilingual(text: str) -> List[str]:
    # CJK as individual chars; all other scripts as word sequences
    tokens = re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]|\w+', text.lower())
    return [t for t in tokens if t.strip()]


def check_truncation(orig: str, rw: str, ratio_threshold: float = 0.3, min_orig_chars: int = 150) -> Tuple[int, int, bool]:
    orig_len = len(orig.strip()) if orig else 0
    rw_len = len(rw.strip()) if rw else 0
    if orig_len >= min_orig_chars and rw_len < (orig_len * ratio_threshold):
        return orig_len, rw_len, True
    return orig_len, rw_len, False


def compute_lexical_metrics(orig: Optional[str], rw: Optional[str]) -> Dict[str, Any]:
    if not orig or not rw:
        return {
            "jaccard_similarity": np.nan,
            "jaccard_distance": np.nan,
            "token_retention_rate": np.nan,
            "core_vocab_retention_rate": np.nan,
            "norm_levenshtein_distance": np.nan,
            "levenshtein_truncated": False,
        }
    orig_tokens = tokenize_multilingual(orig)
    rw_tokens = tokenize_multilingual(rw)
    s_orig = set(orig_tokens)
    s_rw = set(rw_tokens)
    intersection = len(s_orig & s_rw)
    union = len(s_orig | s_rw)
    jaccard_sim = intersection / max(union, 1)
    jaccard_dist = 1.0 - jaccard_sim
    token_retention = intersection / max(len(s_orig), 1)

    # Core vocab = tokens longer than 2 chars or non-ASCII (filters "the", "a", "is")
    orig_core = [t for t in orig_tokens if len(t) > 2 or not t.isascii()]
    rw_core = [t for t in rw_tokens if len(t) > 2 or not t.isascii()]
    s_orig_core = set(orig_core)
    s_rw_core = set(rw_core)
    core_retention = len(s_orig_core & s_rw_core) / max(len(s_orig_core), 1) if s_orig_core else 1.0

    is_truncated = bool(len(orig) > MAX_LEVENSHTEIN_CHARS or len(rw) > MAX_LEVENSHTEIN_CHARS)
    orig_sub = orig[:MAX_LEVENSHTEIN_CHARS]
    rw_sub = rw[:MAX_LEVENSHTEIN_CHARS]
    lev_dist = levenshtein_distance(orig_sub, rw_sub)
    norm_lev_dist = lev_dist / max(len(orig_sub), len(rw_sub), 1)

    return {
        "jaccard_similarity": round(jaccard_sim, 4),
        "jaccard_distance": round(jaccard_dist, 4),
        "token_retention_rate": round(token_retention, 4),
        "core_vocab_retention_rate": round(core_retention, 4),
        "norm_levenshtein_distance": round(norm_lev_dist, 4),
        "levenshtein_truncated": is_truncated,
    }


def extract_numbers(text: str) -> Set[str]:
    clean = re.sub(r'```[\s\S]*?```', ' ', text)
    found = set()
    
    # Plain numbers, currencies, percentages
    for m in re.finditer(r'(?:[\$€£]\s?)?[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s?%)?', clean):
        # Normalize: strip symbols and commas
        val = re.sub(r'[,\$€£%\s]', '', m.group(0))
        if val:
            found.add(val)
    
    # Version numbers: v1.2, version 3.5.1
    for m in re.finditer(r'\bv(?:ersion)?\s?(\d+(?:\.\d+)+)\b', clean, re.IGNORECASE):
        found.add('v' + m.group(1))
    
    return found


def extract_code_elements(text: str) -> Set[str]:
    blocks = re.findall(r'```[\w]*\n([\s\S]*?)```', text)
    inline = re.findall(r'`([^`\n]+)`', text)
    elements = set()
    
    # Inline code: split into atomic tokens
    for item in inline:
        for token in re.findall(r'\S+', item):
            token = token.strip('"\'').lower()
            if len(token) >= 2:
                elements.add(token)
    
    # Code blocks: extract multiple element types
    all_code = ' '.join(blocks)
    
    # Identifiers
    for token in re.findall(r'\b[a-zA-Z_]\w{2,}\b', all_code):
        elements.add(token.lower())
    
    # URLs
    for url in re.findall(r'https?://[^\s"\')]+', all_code):
        elements.add(url.lower().rstrip('/.,;'))
    
    # Paths (Unix-style)
    for path in re.findall(r'(?:/[\w._-]+)+/?', all_code):
        elements.add(path.lower().rstrip('/'))
    
    # CLI flags
    for flag in re.findall(r'--[\w-]+|[-][\w]+', all_code):
        elements.add(flag.lower())
    
    return elements


def extract_quoted_strings(text: str) -> Set[str]:
    double_q = re.findall(r'"([^"\n]{1,})"', text)
    single_q = re.findall(r"'([^'\n]{1,})'", text)
    smart_q = re.findall(r'[“”«»「」]([^“”«»「」\n]{1,})[“”«»「」]', text)
    return set(double_q + single_q + smart_q)


def compute_entity_retention(orig: str, rw: str) -> Dict[str, Any]:
    if not orig or not rw:
        return {
            "has_entities": False,
            "entities_fully_preserved": True,
            "total_entities_orig": 0,
            "num_retention_rate": 1.0,
            "code_retention_rate": 1.0,
            "quote_retention_rate": 1.0,
            "has_numbers": False,
            "has_code": False,
            "has_quotes": False,
        }
    orig_nums = extract_numbers(orig)
    orig_code = extract_code_elements(orig)
    orig_quotes = extract_quoted_strings(orig)

    rw_nums = extract_numbers(rw)
    rw_code = extract_code_elements(rw)
    rw_quotes = extract_quoted_strings(rw)

    num_ret = len(orig_nums & rw_nums) / max(len(orig_nums), 1) if orig_nums else 1.0
    code_ret = len(orig_code & rw_code) / max(len(orig_code), 1) if orig_code else 1.0
    quote_ret = len(orig_quotes & rw_quotes) / max(len(orig_quotes), 1) if orig_quotes else 1.0

    has_nums = len(orig_nums) > 0
    has_code = len(orig_code) > 0
    has_quotes = len(orig_quotes) > 0
    has_entities = has_nums or has_code or has_quotes

    fully_preserved = bool(
        (not has_nums or orig_nums.issubset(rw_nums)) and
        (not has_code or orig_code.issubset(rw_code)) and
        (not has_quotes or orig_quotes.issubset(rw_quotes))
    ) if has_entities else True
    total_entities = len(orig_nums) + len(orig_code) + len(orig_quotes)

    return {
        "has_entities": has_entities,
        "entities_fully_preserved": fully_preserved,
        "total_entities_orig": total_entities,
        "num_retention_rate": round(num_ret, 4),
        "code_retention_rate": round(code_ret, 4),
        "quote_retention_rate": round(quote_ret, 4),
        "has_numbers": has_nums,
        "has_code": has_code,
        "has_quotes": has_quotes,
    }


class MultilingualEmbeddingEvaluator:
    def __init__(self, model_name: str = 'sentence-transformers/LaBSE', batch_size: int = 1024):
        import torch
        from sentence_transformers import SentenceTransformer
        if torch.cuda.is_available():
            best_dev = max(range(torch.cuda.device_count()), key=lambda i: torch.cuda.mem_get_info(i)[0])
            self.device = f'cuda:{best_dev}'
            free_gb = torch.cuda.mem_get_info(best_dev)[0] / (1024**3)
            print(f"  [GPU Init] Selected {self.device} ({free_gb:.1f} GB free VRAM)")
        else:
            self.device = 'cpu'
        self.model = SentenceTransformer(model_name, device=self.device)
        self.batch_size = batch_size

    def compute_similarity_batch(self, orig_texts: List[str], rw_texts: List[str], cache_file: str = "./outputs/labse_sims.npy") -> List[float]:
        import torch
        if not orig_texts or not rw_texts:
            return []
        
        n_total = len(orig_texts)
        chunk_size = 25000
        
        all_sims = []
        if os.path.exists(cache_file):
            try:
                cached_arr = np.load(cache_file)
                if len(cached_arr) == n_total:
                    print(f"Loaded all {n_total:,} pre-computed embedding similarities from {cache_file}!")
                    return [round(float(s), 4) for s in cached_arr.tolist()]
                elif len(cached_arr) > 0 and len(cached_arr) < n_total:
                    all_sims = [round(float(s), 4) for s in cached_arr.tolist()]
                    print(f"Resuming embedding similarity computation from turn {len(all_sims):,}/{n_total:,}...")
            except Exception:
                all_sims = []
        
        start_idx = len(all_sims)
        for i in range(start_idx, n_total, chunk_size):
            end_idx = min(i + chunk_size, n_total)
            orig_chunk = orig_texts[i:end_idx]
            rw_chunk = rw_texts[i:end_idx]
            with torch.inference_mode():
                orig_embs = self.model.encode(orig_chunk, batch_size=self.batch_size, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
                rw_embs = self.model.encode(rw_chunk, batch_size=self.batch_size, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
                cos_sims = (orig_embs * rw_embs).sum(axis=1).tolist()
                all_sims.extend([round(float(s), 4) for s in cos_sims])
                del orig_embs, rw_embs
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            
            # Checkpoint to disk after each chunk
            try:
                np.save(cache_file, np.array(all_sims, dtype=np.float32))
            except Exception:
                pass
            print(f"  [GPU LaBSE] Computed {len(all_sims):,}/{n_total:,} turns ({(len(all_sims)/n_total*100):.1f}%)...", flush=True)
            
        return all_sims


# -----------------------------------------------------------------------------
# Style-register normalizers and evaluators
# -----------------------------------------------------------------------------

def normalise_cap(v: str) -> str:
    if not v or not str(v).strip():
        return 'unmarked'
    v = str(v).strip().lower()
    head = re.split(r'[(\[]', v, maxsplit=1)[0].strip()
    head = head.split(',')[0].strip()
 
    def classify(s: str):
        if 'inconsistent' in s or 'sporadic' in s or 'mixed' in s or 'random' in s or 'erratic' in s:
            return 'inconsistent'
        if 'all lowercase' in s or 'all-lowercase' in s or 'mostly lowercase' in s or s == 'lowercase' or'lower' in s:
            return 'all lowercase'
        if 'all-caps' in s or 'all caps' in s or 'uppercase' in s or 'small caps' in s:
            return 'all caps / emphasis'
        if 'first-word' in s or 'first word' in s:
            return 'first-word-only'
        if 'standard' in s or 'proper' in s or 'normal' in s:
            return 'standard'
        return None
 
    return classify(head) or classify(v) or 'other'


def normalise_punct(v: str) -> str:
    if not v or not str(v).strip():
        return 'unmarked'
    v = str(v).strip().lower()
    head = re.split(r'[(\[]', v, maxsplit=1)[0].strip()
 
    def classify(s: str):
        if 'emoji' in s or 'line-break' in s or 'line break' in s or 'instead of punctuation' in s:
            return 'emoji or line-breaks as punctuation'
        if ('drop' in s or 'minimal' in s or 'omit' in s or 'skip' in s
                or 'lack' in s or 'no period' in s or 'no punctuation' in s):
            return 'minimal / drops end period'
        if 'ellips' in s or '...' in s or '…' in s:
            return 'ellipsis-heavy (...)'
        if 'excessive' in s or 'expressive' in s or '!' in s or '?' in s:
            return 'expressive / multiple (!/?)'
        if 'standard' in s or 'proper' in s or 'normal' in s:
            return 'standard'
        return None
 
    return classify(head) or classify(v) or 'other'


def normalise_emoji(v: str) -> str:
    if not v or not str(v).strip():
        return 'unmarked'
    v = str(v).strip().lower()
    if v.startswith('none') or v in ('no', 'never', 'not used', 'na', 'n a', 'no emojis', 'no emoji', 'zero'):
        return 'none'
    head = re.split(r'[(,;]', v, maxsplit=1)[0]
    head = re.sub(r'[\\*]', '', head)
    head = re.sub(r'\bbut\b', '/', head)
    head = re.sub(r'[\s/]+', '/', head).strip('/ ')
 
    def classify(s: str):
        if any(k in s for k in ('frequent', 'heavy', 'high', 'regular', 'lots', 'decorative')):
            return 'frequent / decorative'
        if any(k in s for k in ('rare', 'occasional', 'minimal', 'sparing', 'low', 'few', 'functional')):
            return 'rare / functional'
        if 'kaomoji' in s or 'sticker' in s or 'ascii art' in s:
            return 'kaomoji / stickers'
        if 'emoticon' in s or 'ascii' in s:
            return 'emoticons only'
        return None
 
    return classify(head) or classify(v) or 'other'


EMOJI_REGEX = re.compile(
    r'[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|'
    r'[\U0001F700-\U0001F77F]|[\U0001F780-\U0001F7FF]|[\U0001F800-\U0001F8FF]|'
    r'[\U0001F900-\U0001F9FF]|[\U0001FA00-\U0001FA6F]|[\U0001FA70-\U0001FAFF]|'
    r'[\U00002702-\U000027B0]|[\U000024C2-\U0001F251]|[\U00002600-\U000026FF]'
)

WESTERN_EMOTICON_REGEX = re.compile(
    r'(?<![a-zA-Z0-9_\(\[\/])[:;=]-?[\'"]?[)D(PpoO/3*]+(?![a-zA-Z0-9_])|'
    r'(?<![a-zA-Z0-9_])<3+(?![a-zA-Z0-9_])|(?<![a-zA-Z0-9_])[xX][dD]+(?![a-zA-Z0-9_])'
)

KAOMOJI_REGEX = re.compile(
    r'(\([^\w\s\n]{1,3}[._^~oO><*T@\-♥\-][^\w\s\n]{1,3}\))|'
    r'(\b\^_\^\b|\^v\^|\b@@\b|\b[oO0]_[oO0]\b|\b[T][._][T]\b|\b[xX]_[xX]\b)|'
    r'([ㅠㅜ]{2,}|[ㅋㅎ]{2,})|(\borz\b|\bOTZ\b|\b\(╯°□°\)╯\b)'
)

def strip_code_blocks(text: str) -> str:
    t = re.sub(r'```[\s\S]*?```', ' ', text)
    t = re.sub(r'`[^`\n]+`', ' ', t)
    return t

def count_unicode_emojis(text: str) -> int:
    return len(EMOJI_REGEX.findall(text))

def count_western_emoticons(text: str) -> int:
    clean_text = strip_code_blocks(text)
    return len(WESTERN_EMOTICON_REGEX.findall(clean_text))

def count_kaomoji(text: str) -> int:
    clean_text = strip_code_blocks(text)
    return len(KAOMOJI_REGEX.findall(clean_text))

def count_text_emoticons(text: str) -> int:
    return count_western_emoticons(text) + count_kaomoji(text)

def evaluate_capitalization(text: str, target_cat: str, orig_text: Optional[str] = None) -> Optional[bool]:
    clean_text = strip_code_blocks(text).strip()
    if not clean_text or target_cat in ('unmarked', 'other', 'inconsistent'):
        return None
        
    cased_chars = [c for c in clean_text if c.lower() != c.upper()]
    if not cased_chars:
        return None  # N/A for languages without case distinction
    
    sentences = [s.strip() for s in re.split(r'[.!?\n]+', clean_text) if s.strip()]
    sentence_starts_cased = [s[0] for s in sentences if s and (s[0].lower() != s[0].upper())]
    starts_cap_ratio = sum(1 for c in sentence_starts_cased if c.isupper()) / max(len(sentence_starts_cased), 1)
    lower_ratio = sum(1 for c in cased_chars if c.islower()) / len(cased_chars)
    upper_ratio = sum(1 for c in cased_chars if c.isupper()) / len(cased_chars)
    
    # Dynamic acronym/emphasis detection against original prompt
    clean_orig = strip_code_blocks(orig_text).strip() if orig_text else ""
    orig_caps = set(re.findall(r'\b[A-Z]{2,}\b', clean_orig))
    rw_caps   = set(re.findall(r'\b[A-Z]{2,}\b', clean_text))
    has_new_caps_emphasis = len(rw_caps - orig_caps) > 0
    
    if target_cat == 'all lowercase':
        return bool(starts_cap_ratio == 0 or clean_text.islower() or lower_ratio >= STYLE_ADHERENCE_THRESHOLD)
    elif target_cat == 'standard':
        return bool(starts_cap_ratio >= STYLE_ADHERENCE_THRESHOLD)
    elif target_cat == 'all caps / emphasis':
        return bool(upper_ratio >= STYLE_ADHERENCE_THRESHOLD or has_new_caps_emphasis)
    elif target_cat == 'first-word-only':
        first_is_upper = bool(sentence_starts_cased and sentence_starts_cased[0].isupper())
        others_lower = all(s.islower() for s in sentence_starts_cased[1:]) if len(sentence_starts_cased) > 1 else True
        no_final_period = not clean_text.endswith('.')
        return bool(first_is_upper and others_lower and no_final_period)
    return None


def evaluate_punctuation(text: str, target_cat: str) -> Optional[bool]:
    clean_text = strip_code_blocks(text).strip()
    if not clean_text or target_cat == 'unmarked' or target_cat == 'other':
        return None
        
    ends_standard_term = bool(clean_text.endswith(('.', '?', '!')))
    has_ellipsis = bool('...' in clean_text or '…' in clean_text)
    has_linebreaks = bool('\n' in clean_text)
    has_expressive = bool(re.search(r'[!?]{2,}', clean_text))
    
    lines = [l.strip() for l in clean_text.split('\n') if l.strip()]
    line_ends_term_ratio = sum(1 for l in lines if l.endswith(('.', '?', '!'))) / max(len(lines), 1)
    unpunctuated_lines_ratio = sum(1 for l in lines if not l.endswith(('.', '?', '!'))) / max(len(lines), 1)
    
    if target_cat == 'standard':
        # Accepts standard terminal punctuation (. ? !) or >= 70% line ends punctuated
        return bool(ends_standard_term or line_ends_term_ratio >= STYLE_ADHERENCE_THRESHOLD)
    elif target_cat == 'minimal / drops end period':
        # Drops terminal punctuation at the end of the message
        return bool(not ends_standard_term or unpunctuated_lines_ratio >= STYLE_ADHERENCE_THRESHOLD)
    elif target_cat == 'ellipsis-heavy (...)':
        return bool(has_ellipsis)
    elif target_cat == 'expressive / multiple (!/?)':
        return bool(has_expressive)
    elif target_cat == 'emoji or line-breaks as punctuation':
        u_count = count_unicode_emojis(clean_text)
        w_count = count_western_emoticons(clean_text)
        k_count = count_kaomoji(clean_text)
        has_emoji_or_linebreak = bool(has_linebreaks or u_count + w_count + k_count > 0)
        return has_emoji_or_linebreak
    return None


def evaluate_emoji(text: str, target_cat: str) -> Optional[bool]:
    clean_text = strip_code_blocks(text).strip()
    if not clean_text or target_cat in ('unmarked', 'other'):
        return None
        
    u_count = count_unicode_emojis(clean_text)
    w_count = count_western_emoticons(clean_text)
    k_count = count_kaomoji(clean_text)
    total = u_count + w_count + k_count
    
    if target_cat == 'none':
        # Zero emojis / emoticons / kaomoji allowed
        return bool(total == 0)
    elif target_cat == 'rare / functional':
        # Normal to have 0 emojis per turn; allows at most 1-2 functional emojis; fails on spam (>2)
        return bool(total <= 2)
    elif target_cat == 'frequent / decorative':
        # Actively expects at least 1 decorative emoji/emoticon/kaomoji
        return bool(total >= 1)
    elif target_cat == 'emoticons only':
        # Western ASCII emoticons only (e.g. :) :D <3), excludes Unicode emojis
        return bool(w_count >= 1 and u_count == 0)
    elif target_cat == 'kaomoji / stickers':
        # Kaomoji / text stickers (e.g. (^_^), orz, ㅠㅠ)
        return bool(k_count >= 1)
    else:
        return None
