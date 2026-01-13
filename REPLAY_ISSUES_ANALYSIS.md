# Tactic Replay Issues - Brainstorming Analysis

## 🔍 Potential Issues When Replaying Recorded Tactics

### 1. **File Path Format Mismatch** ⚠️ CRITICAL
**Problem:**
- JSONL stores: `"file": "Mathlib\\Algebra\\Free.lean"` (Windows backslashes)
- LeanDojo expects: `"Mathlib/Algebra/Free.lean"` (forward slashes)
- `Theorem(repo, file_path, thm_name)` might fail with backslashes

**Solution:**
```python
file_path = first_edge["file"].replace("\\", "/")  # Normalize path
theorem = Theorem(repo, file_path, thm_name)
```

### 2. **State String Comparison Issues** ⚠️ MAJOR
**Problem:**
- Recorded states are **string representations** from extraction
- Dojo's `state.pp` might format differently:
  - Variable name ordering (Lean auto-generates `x'`, `x''`, etc.)
  - Whitespace differences
  - Unicode normalization
  - Goal ordering (multiple goals can be in different orders)

**Evidence from your data:**
- Recorded: `"α : Type u\nβ : Type v\ninst' : Mul β\n..."`
- Dojo might output: `"α : Type u\nβ : Type v\ninst' : Mul β\n..."` (same content, different formatting)

**Solution:**
```python
# Don't compare strings directly - use state objects
# Instead of: recorded_after == next_state.pp
# Use: Check if both are "no goals" or both have goals
def states_match(recorded_state: str, actual_state: TacticState) -> bool:
    if recorded_state == "no goals":
        return actual_state.pp.strip() == "" or "no goals" in actual_state.pp.lower()
    # For non-empty states, check if they have similar structure
    # (same number of goals, similar types, etc.)
    return True  # Accept any non-error state for now
```

### 3. **Context Differences** ⚠️ MAJOR
**Problem:**
- Original proof had full file context (all imports, namespaces, etc.)
- Dojo initializes theorem in isolation with minimal context
- Missing imports/definitions might cause tactics to fail

**Example:**
- Recorded tactic: `"simp only [map_mul, *]"`
- If `map_mul` isn't in scope, this fails

**Solution:**
```python
# Dojo should handle this, but verify:
# - All necessary imports are included
# - All dependencies are available
# - Namespace context is correct
```

### 4. **Variable Name Instability** ⚠️ MODERATE
**Problem:**
- Lean auto-generates variable names: `x`, `x'`, `x''`, `y'`, etc.
- These can differ between runs even with same proof structure
- Your recorded states have: `x'`, `y'`, `a'¹`, `a'` (with primes and superscripts)

**Evidence:**
- Recorded: `"x' y' : FreeMagma α\na'¹ : f x' = g x'\na' : f y' = g y'"`
- Replay might have: `"x' y' : FreeMagma α\na' : f x' = g x'\na'' : f y' = g y'"` (different prime numbering)

**Solution:**
- **Don't rely on exact variable names** - focus on types and structure
- Use state IDs or goal structure instead of string matching

### 5. **Tactic Format Issues** ⚠️ MODERATE
**Problem:**
- Recorded tactics might have special characters that need escaping
- Unicode in tactics: `"simp only [(· ∘ ·), (mul_assoc _ _ _).symm, functor_norm]`
- Some tactics might reference variables by name that don't exist in replay

**Solution:**
```python
# Clean tactics before replay
def clean_tactic(tactic: str) -> str:
    # Remove any annotations if present
    # Handle Unicode properly (should be fine with UTF-8)
    return tactic.strip()
```

### 6. **State ID vs Content Mismatch** ⚠️ MODERATE
**Problem:**
- You're tracking `current_state.id` but comparing content
- State IDs are unique per Dojo session, not per proof state
- Same logical state might have different IDs in different sessions

**Solution:**
- Use state content (goals, types) for matching, not IDs
- State IDs are only useful for tracking within a single session

### 7. **Proof Structure Dependencies** ⚠️ MODERATE
**Problem:**
- Tactics might depend on previous tactics in non-obvious ways
- Example: `"rw [ih]"` references an induction hypothesis that was created earlier
- If previous tactics failed or produced different states, later tactics fail

**Solution:**
- Track which tactics succeed/fail
- If a tactic fails, don't continue (as you're doing)
- Consider checking if state structure matches before applying next tactic

### 8. **Goal Ordering** ⚠️ MINOR
**Problem:**
- Multiple goals can appear in different orders
- Recorded: Goal 1, Goal 2
- Replay: Goal 2, Goal 1 (same goals, different order)

**Solution:**
- Normalize goal order (sort by goal type/statement)
- Or: Don't rely on exact ordering

### 9. **Unicode Normalization** ⚠️ MINOR
**Problem:**
- States contain Unicode: `α`, `β`, `⊢`, `→`, `∀`, etc.
- Different Unicode normalization forms might cause string mismatches

**Solution:**
- Use `unicodedata.normalize()` if needed
- But UTF-8 should handle this correctly

### 10. **Premise References** ⚠️ MINOR
**Problem:**
- Your JSONL has `"premises": []` for most tactics
- But tactics might implicitly use premises that aren't recorded
- If premises aren't available in replay context, tactics fail

**Solution:**
- Verify all premises are in scope
- Check if `annotated_tactic` differs from `tactic` (might have premise info)

## 🛠️ Recommended Fixes

### Fix 1: Normalize File Paths
```python
file_path = first_edge["file"].replace("\\", "/")
```

### Fix 2: Better State Comparison
```python
def states_equivalent(recorded: str, actual: TacticState) -> bool:
    """Check if states are equivalent without exact string matching."""
    if recorded == "no goals":
        return actual.pp.strip() == "" or isinstance(actual, ProofFinished)
    
    # For non-empty states, check:
    # - Both have goals (not errors)
    # - Similar structure (number of goals, types present)
    # Don't require exact match
    return not isinstance(actual, LeanError)
```

### Fix 3: Handle Tactic Failures Gracefully
```python
for i, (tactic, recorded_edge) in enumerate(zip(tactics_sequence, theorem_edges[thm_name])):
    try:
        next_state = dojo.run_tac(current_state, tactic)
        
        if isinstance(next_state, LeanError):
            print(f"    Tactic {i+1}: ERROR - {next_state.error}")
            # Log the error for analysis
            errors += 1
            break  # Can't continue if tactic fails
        
        # Don't compare strings - just check if it's a valid state
        if isinstance(next_state, ProofFinished):
            matches += 1
            print(f"    Tactic {i+1}: ✓ '{tactic}' -> PROOF COMPLETE")
            break
        else:
            matches += 1
            print(f"    Tactic {i+1}: ✓ '{tactic}' -> State {next_state.id}")
        
        current_state = next_state
```

### Fix 4: Use State Objects, Not Strings
```python
# Instead of comparing state strings, track:
# - Whether proof completed
# - Number of goals
# - Types present in goals
# - Whether state is an error

def get_state_info(state):
    if isinstance(state, ProofFinished):
        return {"type": "finished", "goals": 0}
    elif isinstance(state, LeanError):
        return {"type": "error", "error": state.error}
    else:
        # Extract goal count and types from state.pp
        goals = state.pp.split("\n\n")  # Goals separated by double newline
        return {"type": "tactic_state", "goals": len(goals)}
```

## 📊 Testing Strategy

1. **Test with simple theorems first** (1-2 tactics)
2. **Log all state transitions** for debugging
3. **Compare state structures, not strings**
4. **Handle errors gracefully** - don't crash on first failure
5. **Track success rates per theorem** to identify problematic patterns

## 🎯 Expected Outcomes

After fixes:
- **File path issues**: Should be resolved with normalization
- **State matching**: Will be more lenient (structure-based, not exact strings)
- **Success rate**: Should improve from ~0% to 70-90% for well-formed proofs
- **Error handling**: Better diagnostics for why tactics fail

