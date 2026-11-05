#!/usr/bin/env python3
"""Upload the Hugging Face release built by build_hf.py and build_hf_cards.py to one dataset repo with two subsets.

Repo layout: README.md, persona_bank/train-*.parquet, chats/train-*.parquet. Every shard of a subset goes into the
single train split (renumbered). stats.json and an optional id map stay local. Needs internet access and a Hugging
Face token with write access (HF_TOKEN or `huggingface-cli login`).

  python -m personafactory.release.upload_hf --hf-dir $PF_OUT_DIR/hf_release --repo <org>/<name> [--private]
"""
import argparse, os

from huggingface_hub import CommitOperationAdd, HfApi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--hf-dir', required=True, help='output directory of build_hf.py with README.md from build_hf_cards.py')
    ap.add_argument('--repo', required=True, help='dataset repo id, e.g. swiss-ai/PersonaFactory')
    ap.add_argument('--private', action='store_true', help='create the repo as private (and refuse to upload to a public one)')
    a = ap.parse_args()
    api = HfApi()
    api.create_repo(a.repo, repo_type='dataset', private=a.private, exist_ok=True)
    if a.private:
        assert api.repo_info(a.repo, repo_type='dataset').private, 'repo exists and is not private'
    for sub, src in (('persona_bank', 'bank/data'), ('chats', 'chats/data')):
        d = os.path.join(a.hf_dir, src)
        files = sorted(f for f in os.listdir(d) if f.endswith('.parquet'))
        ops = [CommitOperationAdd(path_in_repo=f'{sub}/train-{i:05d}-of-{len(files):05d}.parquet',
                                  path_or_fileobj=os.path.join(d, f)) for i, f in enumerate(files)]
        api.create_commit(repo_id=a.repo, repo_type='dataset', operations=ops, commit_message=f'Add {sub} subset')
        print('uploaded', sub, len(files), 'shards', flush=True)
    api.upload_file(path_or_fileobj=os.path.join(a.hf_dir, 'README.md'), path_in_repo='README.md', repo_id=a.repo,
                    repo_type='dataset', commit_message='Add dataset card')
    print('done', f'https://huggingface.co/datasets/{a.repo}')


if __name__ == '__main__':
    main()
