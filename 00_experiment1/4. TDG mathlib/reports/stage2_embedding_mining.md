# Stage 2 Embedding Mining

## Method

- mined directed tactic-only path motifs of 2-4 nodes
- kept explicit witness mappings for every host theorem occurrence
- canonicalized motifs by local node order plus edge-type sequence
- excluded `premise_use` from structural matching

## Top candidates

- `cand_00033` | nodes=2 | support=8105 | motif=`rw -> exact` | edges=['goal_to_goal']
- `cand_00123` | nodes=2 | support=3596 | motif=`have -> rw` | edges=['goal_to_goal']
- `cand_00198` | nodes=2 | support=3122 | motif=`have -> rw` | edges=['hyp_to_goal']
- `cand_00019` | nodes=2 | support=2977 | motif=`refine -> rw` | edges=['goal_to_goal']
- `cand_00253` | nodes=2 | support=2740 | motif=`have -> have` | edges=['goal_to_goal']
- `cand_00049` | nodes=2 | support=2674 | motif=`rw -> simp` | edges=['goal_to_goal']
- `cand_00660` | nodes=2 | support=1992 | motif=`ext -> simp` | edges=['goal_to_goal']
- `cand_00320` | nodes=2 | support=1957 | motif=`rw -> refine` | edges=['goal_to_goal']
- `cand_00445` | nodes=2 | support=1949 | motif=`rw -> rw` | edges=['goal_to_goal']
- `cand_00423` | nodes=2 | support=1921 | motif=`obtain -> exact` | edges=['hyp_to_goal']
- `cand_00581` | nodes=2 | support=1825 | motif=`rw -> exact` | edges=['hyp_to_goal']
- `cand_00030` | nodes=2 | support=1767 | motif=`rw -> apply` | edges=['goal_to_goal']
- `cand_00262` | nodes=2 | support=1739 | motif=`have -> simp` | edges=['goal_to_goal']
- `cand_01089` | nodes=2 | support=1731 | motif=`have -> exact` | edges=['hyp_to_goal']
- `cand_00051` | nodes=2 | support=1724 | motif=`intro -> exact` | edges=['hyp_to_goal']
- `cand_00122` | nodes=2 | support=1567 | motif=`have -> exact` | edges=['goal_to_goal']
- `cand_01131` | nodes=2 | support=1563 | motif=`refine -> exact` | edges=['goal_to_goal']
- `cand_00280` | nodes=2 | support=1550 | motif=`rcases -> exact` | edges=['hyp_to_goal']
- `cand_00172` | nodes=2 | support=1541 | motif=`simp -> exact` | edges=['goal_to_goal']
- `cand_00028` | nodes=2 | support=1530 | motif=`rintro -> exact` | edges=['hyp_to_goal']
