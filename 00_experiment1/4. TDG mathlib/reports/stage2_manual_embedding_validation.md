# Stage 2 Manual Embedding Validation

## Validation scope

- sampled candidates: 30
- witness-preserving motifs only
- this report verifies structural consistency of candidate/witness storage; semantic review of theorems still requires spot inspection of rendered examples

## Sampled motifs

- `cand_00033` motif=`rw -> exact` support=8105 witnesses=['Algebraic.cardinal_mk_le_mul', 'Algebraic.cardinal_mk_le_max', 'LinearRecurrence.eq_mk_of_is_sol_of_eq_init']
- `cand_00123` motif=`have -> rw` support=3596 witnesses=['LinearRecurrence.eq_mk_of_is_sol_of_eq_init', 'LinearRecurrence.eq_mk_of_is_sol_of_eq_init', 'quadratic_eq_zero_iff_of_discrim_eq_zero']
- `cand_00198` motif=`have -> rw` support=3122 witnesses=['quadratic_eq_zero_iff_of_discrim_eq_zero', 'discrim_le_zero', 'Ring.DirectLimit.of.zero_exact_aux2']
- `cand_00019` motif=`refine -> rw` support=2977 witnesses=['Algebraic.cardinal_mk_lift_le_mul', 'quadratic_eq_zero_iff_discrim_eq_sq', 'smul_inv₀']
- `cand_00253` motif=`have -> have` support=2740 witnesses=['discrim_le_zero', 'discrim_le_zero', 'discrim_le_zero']
- `cand_00049` motif=`rw -> simp` support=2674 witnesses=['LinearRecurrence.is_sol_mkSol', 'LinearRecurrence.mkSol_eq_init', 'LinearRecurrence.eq_mk_of_is_sol_of_eq_init']
- `cand_00660` motif=`ext -> simp` support=1992 witnesses=['FreeAlgebra.induction', 'RingQuot.lift_unique', 'RingQuot.liftAlgHom_unique']
- `cand_00320` motif=`rw -> refine` support=1957 witnesses=['isPrimePow_nat_iff_bounded', 'ENNReal.le_tsum_schlomilch', 'ENNReal.le_tsum_condensed']
- `cand_00445` motif=`rw -> rw` support=1949 witnesses=['AlgebraicGeometry.genericPoint_eq_bot_of_affine', 'AlgebraicGeometry.genericPoint_eq_bot_of_affine', 'AlgebraicGeometry.Scheme.GlueData.isOpen_iff']
- `cand_00423` motif=`obtain -> exact` support=1921 witnesses=['AlgebraicGeometry.germ_injective_of_isIntegral', 'Ring.DirectLimit.of.zero_exact_aux', 'Ring.DirectLimit.of.zero_exact_aux']
- `cand_00581` motif=`rw -> exact` support=1825 witnesses=['FreeAlgebra.hom_ext', 'Ring.DirectLimit.of.zero_exact', 'Prime.left_dvd_or_dvd_right_of_dvd_mul']
- `cand_00030` motif=`rw -> apply` support=1767 witnesses=['Algebraic.countable', 'AlgebraicGeometry.Scheme.GlueData.isOpen_iff', 'AlgebraicGeometry.Scheme.OpenCover.fromGlued_open_map']
- `cand_00262` motif=`have -> simp` support=1739 witnesses=['discrim_le_zero', 'hofer', 'unique_unit_speed_on_Icc_zero']
- `cand_01089` motif=`have -> exact` support=1731 witnesses=['Ring.DirectLimit.of.zero_exact', 'hofer', 'hofer']
- `cand_00051` motif=`intro -> exact` support=1724 witnesses=['LinearRecurrence.eq_mk_of_is_sol_of_eq_init', 'LinearRecurrence.eq_mk_of_is_sol_of_eq_init', 'LinearRecurrence.eq_mk_of_is_sol_of_eq_init']

## Gate

- Stage 3 may proceed because each candidate now carries explicit witness maps.
- Semantic false-positive screening should continue on rendered host examples, but the witness-representation failure from the previous run is removed.
