# Stage 4B Connected Compression Power

## Method

- started from accepted connected-subgraph collapsible witnesses
- selected theorem-local disjoint witnesses by node-set non-overlap
- estimated corpus savings as `disjoint_witness_count * (Size(candidate) - 1)`

## Top connected candidates by estimated corpus savings

- `conn_00016` | nodes=2 | motif=`rw / exact` | disjoint_hits=8147 | estimated_corpus_savings=8147
- `conn_00286` | nodes=2 | motif=`have / have` | disjoint_hits=3317 | estimated_corpus_savings=3317
- `conn_00032` | nodes=2 | motif=`rw / simp` | disjoint_hits=2726 | estimated_corpus_savings=2726
- `conn_00007` | nodes=2 | motif=`refine / rw` | disjoint_hits=2709 | estimated_corpus_savings=2709
- `conn_00236` | nodes=2 | motif=`have / rw` | disjoint_hits=2693 | estimated_corpus_savings=2693
- `conn_00148` | nodes=2 | motif=`have / rw` | disjoint_hits=2112 | estimated_corpus_savings=2112
- `conn_00343` | nodes=2 | motif=`rw / refine` | disjoint_hits=2052 | estimated_corpus_savings=2052
- `conn_00013` | nodes=2 | motif=`rw / apply` | disjoint_hits=1971 | estimated_corpus_savings=1971
- `conn_00643` | nodes=2 | motif=`ext / simp` | disjoint_hits=1954 | estimated_corpus_savings=1954
- `conn_00820` | nodes=2 | motif=`have / rw` | disjoint_hits=1738 | estimated_corpus_savings=1738
- `conn_00442` | nodes=2 | motif=`rw / rw` | disjoint_hits=1717 | estimated_corpus_savings=1717
- `conn_02400` | nodes=3 | motif=`have / have / have` | disjoint_hits=788 | estimated_corpus_savings=1576
- `conn_00582` | nodes=2 | motif=`rw / exact` | disjoint_hits=1515 | estimated_corpus_savings=1515
- `conn_04770` | nodes=3 | motif=`by_cases / rw / rw` | disjoint_hits=721 | estimated_corpus_savings=1442
- `conn_02723` | nodes=2 | motif=`refine / exact` | disjoint_hits=1423 | estimated_corpus_savings=1423
- `conn_03229` | nodes=3 | motif=`by_cases / simp / simp` | disjoint_hits=709 | estimated_corpus_savings=1418
- `conn_01107` | nodes=2 | motif=`have / exact` | disjoint_hits=1388 | estimated_corpus_savings=1388
- `conn_01164` | nodes=2 | motif=`refine / simp` | disjoint_hits=1273 | estimated_corpus_savings=1273
- `conn_00219` | nodes=2 | motif=`simp / exact` | disjoint_hits=1268 | estimated_corpus_savings=1268
- `conn_00439` | nodes=2 | motif=`apply / rw` | disjoint_hits=1266 | estimated_corpus_savings=1266
- `conn_00446` | nodes=2 | motif=`rw / rfl` | disjoint_hits=1240 | estimated_corpus_savings=1240
- `conn_01535` | nodes=2 | motif=`have / have` | disjoint_hits=1235 | estimated_corpus_savings=1235
- `conn_02660` | nodes=3 | motif=`refine / rw / exact` | disjoint_hits=602 | estimated_corpus_savings=1204
- `conn_00303` | nodes=2 | motif=`have / simp` | disjoint_hits=1204 | estimated_corpus_savings=1204
- `conn_00084` | nodes=2 | motif=`intro / exact` | disjoint_hits=1183 | estimated_corpus_savings=1183

## Larger connected candidates (size >= 3)

- `conn_02400` | nodes=3 | motif=`have / have / have` | disjoint_hits=788 | estimated_corpus_savings=1576
- `conn_04770` | nodes=3 | motif=`by_cases / rw / rw` | disjoint_hits=721 | estimated_corpus_savings=1442
- `conn_03229` | nodes=3 | motif=`by_cases / simp / simp` | disjoint_hits=709 | estimated_corpus_savings=1418
- `conn_02660` | nodes=3 | motif=`refine / rw / exact` | disjoint_hits=602 | estimated_corpus_savings=1204
- `conn_00334` | nodes=3 | motif=`have / have / rw` | disjoint_hits=516 | estimated_corpus_savings=1032
- `conn_00178` | nodes=3 | motif=`have / rw / exact` | disjoint_hits=506 | estimated_corpus_savings=1012
- `conn_00159` | nodes=3 | motif=`have / rw / rw` | disjoint_hits=492 | estimated_corpus_savings=984
- `conn_03998` | nodes=3 | motif=`rw / refine / rw` | disjoint_hits=418 | estimated_corpus_savings=836
- `conn_02236` | nodes=3 | motif=`constructor / rintro / rintro` | disjoint_hits=378 | estimated_corpus_savings=756
- `conn_00210` | nodes=3 | motif=`constructor / intro / intro` | disjoint_hits=362 | estimated_corpus_savings=724
- `conn_02535` | nodes=4 | motif=`have / have / have / have` | disjoint_hits=234 | estimated_corpus_savings=702
- `conn_04774` | nodes=4 | motif=`by_cases / rw / rw / rw` | disjoint_hits=230 | estimated_corpus_savings=690
- `conn_01005` | nodes=3 | motif=`have / rw / exact` | disjoint_hits=345 | estimated_corpus_savings=690
- `conn_03203` | nodes=3 | motif=`have / rw / rw` | disjoint_hits=344 | estimated_corpus_savings=688
- `conn_01893` | nodes=3 | motif=`rcases / exact / exact` | disjoint_hits=332 | estimated_corpus_savings=664
- `conn_02374` | nodes=3 | motif=`by_cases / exact / exact` | disjoint_hits=328 | estimated_corpus_savings=656
- `conn_03326` | nodes=3 | motif=`have / exact / exact` | disjoint_hits=328 | estimated_corpus_savings=656
- `conn_10845` | nodes=4 | motif=`by_cases / simp / simp / simp` | disjoint_hits=215 | estimated_corpus_savings=645
- `conn_01863` | nodes=3 | motif=`apply / rw / exact` | disjoint_hits=322 | estimated_corpus_savings=644
- `conn_04442` | nodes=3 | motif=`have / rw / rw` | disjoint_hits=312 | estimated_corpus_savings=624
