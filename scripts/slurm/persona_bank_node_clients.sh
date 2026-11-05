#!/bin/bash
# Client processes of ONE node (started per node with srun --overlap by persona_bank_generate.sbatch and
# persona_bank_judge.sbatch): runs the shards i with i % NNODES == NODE_IDX against the endpoints of this node
# (round-robin) and waits for exactly those processes.
# Env: MODE (gen|judge), NODE_IDX, NNODES, NSH, EPS (space-separated .../v1 endpoints), LOGDIR, PYTHON (python),
#   gen:   MODEL TEMP SEEDBASE OUT, GEN_ARGS (grid flags for generate_bank.py)
#   judge: JIN (directory with shard_XXXX.jsonl, or one JSONL file that every shard strides over), JOUT,
#          JUDGE_MODEL, JUDGE_ARGS (extra validate_personas.py flags), JCONC (personas in flight per client, default 1)
set -u
PY=${PYTHON:-python}
eps=($EPS)
[ ${#eps[@]} -gt 0 ] || { echo "node $NODE_IDX: no endpoints"; exit 1; }
mkdir -p "$LOGDIR"
PIDS=""
k=0
for i in $(seq "$NODE_IDX" "$NNODES" $((NSH - 1))); do
  ep=${eps[$((k % ${#eps[@]}))]}; k=$((k + 1))
  if [ "$MODE" = gen ]; then
    # shellcheck disable=SC2086
    $PY -u -m personafactory.persona_bank.generate_bank --model_name "$MODEL" --base_url "$ep" \
      --shard_count "$NSH" --shard_index "$i" --seed $((SEEDBASE + i)) --temperature "$TEMP" \
      --output_dir "$OUT" ${GEN_ARGS:-} >> "$LOGDIR/c_$i.txt" 2>&1 &
  elif [ -d "$JIN" ]; then
    f=$(printf "%s/shard_%04d.jsonl" "$JIN" "$i")
    [ -s "$f" ] || continue
    # shellcheck disable=SC2086
    $PY -u -m personafactory.persona_bank.validate_personas --input "$f" --output "$(printf "%s/val_%04d.jsonl" "$JOUT" "$i")" \
      --judge-model "$JUDGE_MODEL" --base-url "$ep" --concurrency "${JCONC:-1}" ${JUDGE_ARGS:-} >> "$LOGDIR/j_$i.txt" 2>&1 &
  else
    # one input file, strided shards (writes <JOUT>.shardIIofNN.jsonl; merge with finalize_bank)
    # shellcheck disable=SC2086
    $PY -u -m personafactory.persona_bank.validate_personas --input "$JIN" --output "$JOUT" \
      --shard_count "$NSH" --shard_index "$i" --judge-model "$JUDGE_MODEL" --base-url "$ep" \
      --concurrency "${JCONC:-1}" ${JUDGE_ARGS:-} >> "$LOGDIR/j_$i.txt" 2>&1 &
  fi
  PIDS="$PIDS $!"
done
echo "node $NODE_IDX ($(hostname)): $(echo $PIDS | wc -w) clients on ${#eps[@]} endpoints"
# shellcheck disable=SC2086
wait $PIDS
echo "node $NODE_IDX done $(date)"
