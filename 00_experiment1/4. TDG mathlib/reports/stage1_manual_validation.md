# Stage 1 Manual Validation

## Sampling policy

- 10 tiny proofs
- 20 medium proofs
- 20 large proofs
- total sampled theorems: 50

## Automated agentic pre-check

This file is a supervision gate, not a claim that human inspection is finished. The script checked whether:

- every sampled tactic has parseable `state_before`,
- every sampled tactic has parseable `state_after` unless it is terminal,
- active-goal lineage is preserved strongly enough to support conservative `goal_to_goal` edges.

## Aggregate results

- Mean node alignment rate: 100.00%
- Mean edge alignment rate: 100.00%

## Sampled theorem snapshots

### MeasureTheory.Measure.map_of_not_aemeasurable
- file: `Mathlib\MeasureTheory\Measure\MeasureSpace.lean`
- tactics: 1
- node alignment rate: 100.00%
- edge alignment rate: 100.00%
- first tactic: `simp [map, hf]`

### differentiableAt_jacobiTheta
- file: `Mathlib\NumberTheory\ModularForms\JacobiTheta\OneVariable.lean`
- tactics: 2
- node alignment rate: 100.00%
- edge alignment rate: 100.00%
- first tactic: `simp_rw [funext jacobiTheta_eq_jacobiTheta₂]`

### PrimeMultiset.prod_dvd_iff'
- file: `Mathlib\Data\PNat\Factors.lean`
- tactics: 3
- node alignment rate: 100.00%
- edge alignment rate: 100.00%
- first tactic: `let h := @prod_dvd_iff u n.factorMultiset`

### MeasureTheory.union_ae_eq_left_iff_ae_subset
- file: `Mathlib\MeasureTheory\Measure\MeasureSpace.lean`
- tactics: 4
- node alignment rate: 100.00%
- edge alignment rate: 100.00%
- first tactic: `rw [ae_le_set]`

### CategoryTheory.types_ext
- file: `Mathlib\CategoryTheory\Types.lean`
- tactics: 2
- node alignment rate: 100.00%
- edge alignment rate: 100.00%
- first tactic: `funext x`

### Finset.image_diag_union_image_offDiag
- file: `Mathlib\Data\Finset\Sym.lean`
- tactics: 1
- node alignment rate: 100.00%
- edge alignment rate: 100.00%
- first tactic: `rw [← image_union, diag_union_offDiag, sym2_eq_image]`

### EuclideanGeometry.Sphere.dist_div_sin_oangle_div_two_eq_radius
- file: `Mathlib\Geometry\Euclidean\Angle\Sphere.lean`
- tactics: 3
- node alignment rate: 100.00%
- edge alignment rate: 100.00%
- first tactic: `convert dist_div_cos_oangle_center_div_two_eq_radius hp₁ hp₃ hp₁p₃`

### InnerProductGeometry.angle_sub_eq_arcsin_of_inner_eq_zero
- file: `Mathlib\Geometry\Euclidean\Angle\Unoriented\RightAngle.lean`
- tactics: 3
- node alignment rate: 100.00%
- edge alignment rate: 100.00%
- first tactic: `rw [← neg_eq_zero, ← inner_neg_right] at h`


## Failure modes to inspect manually next

- branch-heavy proofs where the active branch is not obviously the first visible goal
- compound tactics that rewrite and split goals in one step
- hypothesis names introduced under bullets and reused later

## Acceptance status

- Stage 1 is accepted as a conservative baseline for further inspection if manual spot checks agree with these samples.
- Stage 2 should not proceed without reviewing `data/stage1_validation_samples.jsonl`.
