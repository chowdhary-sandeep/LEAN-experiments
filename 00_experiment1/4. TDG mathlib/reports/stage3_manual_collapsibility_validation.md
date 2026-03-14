# Stage 3 Manual Collapsibility Validation

- accepted candidate sample size: 20
- rejected candidate sample size: 20

## Accepted examples

- `cand_00031` motif=`rw -> exact` support=7969
- `cand_00149` motif=`have -> rw` support=3130
- `cand_00047` motif=`rw -> simp` support=2533
- `cand_00018` motif=`refine -> rw` support=2263
- `cand_00471` motif=`have -> exact` support=2116
- `cand_00049` motif=`intro -> exact` support=1984
- `cand_00201` motif=`have -> have` support=1942
- `cand_00208` motif=`rw -> refine` support=1909
- `cand_00478` motif=`ext -> simp` support=1888
- `cand_00299` motif=`obtain -> exact` support=1864

## Rejected examples

- `cand_02357` motif=`let -> have -> have -> rw` support=111
- `cand_03893` motif=`let -> let -> have -> have` support=94
- `cand_03246` motif=`let -> let -> have -> have` support=87
- `cand_09971` motif=`have -> obtain -> exact` support=71
- `cand_03867` motif=`have -> have -> have -> exact` support=65
- `cand_01987` motif=`obtain -> let -> have -> have` support=60
- `cand_04198` motif=`have -> let -> have -> have` support=58
- `cand_00853` motif=`let -> have -> have -> exact` support=57
- `cand_06065` motif=`obtain -> have -> have -> rw` support=56
- `cand_03897` motif=`let -> let -> have -> have` support=55

## Gate

- Rejected cases are retained with explicit failure reasons in `data/stage3_collapsible_witnesses.parquet`.
- Manual inspection should focus on whether the accepted path motifs are genuinely refactorable in Lean, not just graph-collapsible.
