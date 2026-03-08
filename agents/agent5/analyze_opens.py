import json, re, os, sys
sys.path.insert(0, '/mnt/e/LeanATP Harness/agents/agent5/verifier')
from test_corpus import MATHLIB_ROOT

entries = []
with open('/mnt/e/LEAN-experiments/00_experiment1/jsons/traced_theorems_unified_v2.jsonl') as f:
    for line in f:
        d = json.loads(line.strip())
        if d.get('proof_type') == 'tactic' and len(d.get('proof_text') or '') >= 20:
            entries.append(d)
            if len(entries) >= 500:
                break

# For each file in the corpus, track the namespace context when each open appears
seen_files = {}
for e in entries:
    file_rel = e.get('file', '').replace(chr(92), '/')
    if file_rel in seen_files:
        continue

    full_path = os.path.join(MATHLIB_ROOT, file_rel)
    try:
        fh = open(full_path)
        src = fh.read()
        fh.close()
    except:
        seen_files[file_rel] = {}
        continue

    ns_stack = []
    in_block = False
    opens_with_context = []

    for line in src.splitlines():
        stripped = line.strip()
        if not in_block:
            if stripped.startswith('/-'):
                if not (stripped.count('/-') == stripped.count('-/') and '-/' in stripped):
                    in_block = True
                continue
        else:
            if '-/' in stripped:
                in_block = False
            continue

        if stripped.startswith('--'):
            continue
        if line and line[0] in (' ', '\t'):
            continue

        if re.match(r'^namespace\s+\S', stripped):
            ns_stack.append(stripped.split()[1])
        elif re.match(r'^end\s+\S', stripped):
            end_name = stripped.split()[1]
            if ns_stack and ns_stack[-1] == end_name:
                ns_stack.pop()
        elif re.match(r'^open', stripped) and 'in ' not in stripped:
            m = re.match(r'^open(\s+scoped)?\s+(.+)', stripped)
            if m:
                scoped = m.group(1) or ''
                names_part = m.group(2).strip()
                for name in names_part.split():
                    if name in ('in', 'with', 'hiding', 'renaming', '--') or name.startswith('(') or name.startswith('--'):
                        break
                    name = name.rstrip(',;)')
                    if not name or not re.match(r'^[A-Z]', name):
                        break
                    key = 'open' + scoped + ' ' + name
                    opens_with_context.append((key, list(ns_stack)))

    seen_files[file_rel] = opens_with_context

print('Files with opens inside namespaces:')
for f, opens_ctx in sorted(seen_files.items()):
    if not opens_ctx:
        continue
    inner = [(k, ns) for k, ns in opens_ctx if ns]
    if inner:
        print('  ' + f + ':')
        for key, ns in inner:
            print('    ' + key + '  [inside: ' + ' -> '.join(ns) + ']')
