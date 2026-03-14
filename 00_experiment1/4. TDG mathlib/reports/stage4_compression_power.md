# Stage 4 Compression Power Analysis

## Method

- started from accepted collapsible witnesses only
- grouped witnesses by `(candidate, theorem)`
- selected theorem-local disjoint witnesses by node-set non-overlap using a deterministic greedy selector
- estimated savings per selected witness as `Size(candidate) - 1`, where size is the number of tactic nodes in the candidate
- estimated corpus compression power as `disjoint_witness_count * (Size(candidate) - 1)`

## Important note

- This is an overlap-aware compression proxy, not the final paper-faithful refactoring metric.
- It is still useful because it corrects the current support-only bias toward very small motifs.

## Top candidates by estimated corpus savings

- `cand_00033` motif=`rw -> exact` size=2 disjoint_hits=8147 savings_per_hit=1 estimated_corpus_savings=8147
- `cand_00198` motif=`have -> rw` size=2 disjoint_hits=4034 savings_per_hit=1 estimated_corpus_savings=4034
- `cand_00253` motif=`have -> have` size=2 disjoint_hits=3317 savings_per_hit=1 estimated_corpus_savings=3317
- `cand_00049` motif=`rw -> simp` size=2 disjoint_hits=2726 savings_per_hit=1 estimated_corpus_savings=2726
- `cand_00019` motif=`refine -> rw` size=2 disjoint_hits=2709 savings_per_hit=1 estimated_corpus_savings=2709
- `cand_00423` motif=`obtain -> exact` size=2 disjoint_hits=2225 savings_per_hit=1 estimated_corpus_savings=2225
- `cand_01089` motif=`have -> exact` size=2 disjoint_hits=2139 savings_per_hit=1 estimated_corpus_savings=2139
- `cand_00123` motif=`have -> rw` size=2 disjoint_hits=2112 savings_per_hit=1 estimated_corpus_savings=2112
- `cand_00051` motif=`intro -> exact` size=2 disjoint_hits=2053 savings_per_hit=1 estimated_corpus_savings=2053
- `cand_00320` motif=`rw -> refine` size=2 disjoint_hits=2052 savings_per_hit=1 estimated_corpus_savings=2052
- `cand_00581` motif=`rw -> exact` size=2 disjoint_hits=1984 savings_per_hit=1 estimated_corpus_savings=1984
- `cand_00030` motif=`rw -> apply` size=2 disjoint_hits=1971 savings_per_hit=1 estimated_corpus_savings=1971
- `cand_00660` motif=`ext -> simp` size=2 disjoint_hits=1954 savings_per_hit=1 estimated_corpus_savings=1954
- `cand_01327` motif=`have -> have` size=2 disjoint_hits=1922 savings_per_hit=1 estimated_corpus_savings=1922
- `cand_00028` motif=`rintro -> exact` size=2 disjoint_hits=1842 savings_per_hit=1 estimated_corpus_savings=1842
- `cand_00280` motif=`rcases -> exact` size=2 disjoint_hits=1809 savings_per_hit=1 estimated_corpus_savings=1809
- `cand_00445` motif=`rw -> rw` size=2 disjoint_hits=1717 savings_per_hit=1 estimated_corpus_savings=1717
- `cand_01608` motif=`have -> have -> have` size=3 disjoint_hits=788 savings_per_hit=2 estimated_corpus_savings=1576
- `cand_01130` motif=`refine -> exact` size=2 disjoint_hits=1569 savings_per_hit=1 estimated_corpus_savings=1569
- `cand_00052` motif=`intro -> rw` size=2 disjoint_hits=1545 savings_per_hit=1 estimated_corpus_savings=1545

## Top candidates by raw collapsible support

- `cand_00033` motif=`rw -> exact` raw_theorem_support=6887 raw_witnesses=8485 estimated_corpus_savings=8147
- `cand_00198` motif=`have -> rw` raw_theorem_support=3122 raw_witnesses=5420 estimated_corpus_savings=4034
- `cand_00049` motif=`rw -> simp` raw_theorem_support=2470 raw_witnesses=2841 estimated_corpus_savings=2726
- `cand_00253` motif=`have -> have` raw_theorem_support=2357 raw_witnesses=4375 estimated_corpus_savings=3317
- `cand_00019` motif=`refine -> rw` raw_theorem_support=2295 raw_witnesses=2890 estimated_corpus_savings=2709
- `cand_00423` motif=`obtain -> exact` raw_theorem_support=1921 raw_witnesses=4888 estimated_corpus_savings=2225
- `cand_00660` motif=`ext -> simp` raw_theorem_support=1891 raw_witnesses=1975 estimated_corpus_savings=1954
- `cand_00123` motif=`have -> rw` raw_theorem_support=1881 raw_witnesses=2875 estimated_corpus_savings=2112
- `cand_00581` motif=`rw -> exact` raw_theorem_support=1825 raw_witnesses=2264 estimated_corpus_savings=1984
- `cand_00320` motif=`rw -> refine` raw_theorem_support=1812 raw_witnesses=2077 estimated_corpus_savings=2052
- `cand_01089` motif=`have -> exact` raw_theorem_support=1731 raw_witnesses=3273 estimated_corpus_savings=2139
- `cand_00051` motif=`intro -> exact` raw_theorem_support=1724 raw_witnesses=3779 estimated_corpus_savings=2053
- `cand_00030` motif=`rw -> apply` raw_theorem_support=1700 raw_witnesses=2000 estimated_corpus_savings=1971
- `cand_00280` motif=`rcases -> exact` raw_theorem_support=1550 raw_witnesses=4261 estimated_corpus_savings=1809
- `cand_00028` motif=`rintro -> exact` raw_theorem_support=1530 raw_witnesses=4137 estimated_corpus_savings=1842

## Interpretation

- If support and compression rankings agree, the motif is both frequent and useful.
- If they diverge, support-only mining was overvaluing small frequent motifs or undervaluing somewhat larger motifs.
- This ranking should replace raw support as the main candidate ordering for the next round of tactic discovery work.
