# Term Proofs Explained

## What You're Looking At in corpus.jsonl

The entry you selected (lines 23-24) shows a **class definition**, not a term proof. Let me break down what you're seeing and then explain what term proofs actually look like.

## Structure of corpus.jsonl Entries

Each line in `corpus.jsonl` represents a **premise definition** (theorem, definition, class, etc.) that can be used as a premise. The format is:

```json
{
  "path": "file/path.lean",
  "imports": ["dependency1.lean", "dependency2.lean"],
  "premises": [
    {
      "full_name": "Name.space.item",
      "code": "the actual Lean code",
      "start": [line, column],
      "end": [line, column],
      "kind": "commanddeclaration"
    },
    ...
  ]
}
```

## Your Example: Class Definition

```json
{
  "full_name": "IncidenceGeometry",
  "code": "class IncidenceGeometry where\n  Point : Type u₁\n  Line : Type u₂\n  Circle : Type u₃\n\n  between : Point → Point → Point → Prop\n  onLine : Point → Line → Prop\n  ...",
  "start": [25, 1],
  "end": [49, 70],
  "kind": "commanddeclaration"
}
```

**What this is:**
- **Type**: A `class` declaration (like a typeclass in Lean)
- **Purpose**: Defines a structure with fields and axioms
- **Not a proof**: This is a definition/declaration, not a proof

**Parts explained:**
- `full_name`: `"IncidenceGeometry"` - the fully qualified name
- `code`: The actual Lean source code for this class
- `start`/`end`: Position in the source file `[line, column]`
- `kind`: `"commanddeclaration"` - indicates it's a declaration (could be `theorem`, `def`, `class`, etc.)

## What is a Term Proof?

In Lean, there are **two types of proofs**:

### 1. Tactic Proof (what we parse)
```lean
theorem add_zero (n : ℕ) : n + 0 = n := by
  induction n with
  | zero => rfl
  | succ n ih => simp [ih]
```

**Structure:**
- Uses `by` keyword
- Contains tactics like `induction`, `simp`, `rfl`
- We parse these manually to extract premises

### 2. Term Proof (what you're asking about)
```lean
theorem add_zero (n : ℕ) : n + 0 = n := 
  Nat.rec (rfl) (fun n ih => congrArg Nat.succ ih) n
```

**Structure:**
- **No `by` keyword** - it's a direct expression
- Uses **function application** and **lambda expressions**
- The proof is a **term** (expression) that has the theorem's type

## Example: Term Proof Breakdown

```lean
theorem add_comm (n m : ℕ) : n + m = m + n :=
  Nat.recOn m
    (Nat.add_zero n)
    (fun m ih => 
      congrArg Nat.succ 
        (Eq.trans ih (Nat.add_succ n m).symm))
```

**Parts explained:**

1. **`Nat.recOn m`**: 
   - Recursion operator on natural numbers
   - Takes `m` as the value to recurse on
   - First argument: base case proof
   - Second argument: inductive step (function)

2. **`Nat.add_zero n`**:
   - Base case: `n + 0 = n`
 
3. **`fun m ih => ...`**:
   - Lambda function for inductive step
   - `m`: current natural number
   - `ih`: induction hypothesis (`n + m = m + n`)

4. **`congrArg Nat.succ`**:
   - Congruence argument: if `a = b`, then `Nat.succ a = Nat.succ b`
   - Another **premise** being used

5. **`Eq.trans ih (Nat.add_succ n m).symm`**:
   - Transitivity of equality
   - `ih`: induction hypothesis
   - `Nat.add_succ n m`: another premise
   - `.symm`: symmetry (`a = b` → `b = a`)

## Term Proof vs Tactic Proof

| Aspect | Tactic Proof | Term Proof |
|--------|-------------|------------|
| **Syntax** | Uses `by` + tactics | Direct expression |
| **Readability** | More readable, step-by-step | More compact, functional |
| **Premises** | Extracted from tactic text | Embedded in expression |
| **Example** | `by simp [add_comm]` | `add_comm n m` |
| **Parsing** | We parse manually | Harder to parse (not done) |

## Why We Don't Parse Term Proofs

Looking at `00_build_unified_v2.py` lines 508-521:

```python
has_tactic = tt.has_tactic_proof() if hasattr(tt, 'has_tactic_proof') else False

if has_tactic:
    stats["tactic_proofs"] += 1
    proof_type = "tactic"
    proof_text = tt.get_tactic_proof()
    # ... parse tactics to extract premises
else:
    stats["term_proofs"] += 1
    proof_type = "term"
    proof_text = ""  # Empty! We don't extract from term proofs
```

**Why:**
1. **Term proofs are expressions**: They're functional code, not text we can regex-parse
2. **Premises are embedded**: They're function applications, not strings
3. **Would require AST parsing**: Need to traverse the expression tree, not just text
4. **Complexity**: Much harder than parsing tactic strings

## What's in corpus.jsonl?

The corpus contains **all premise definitions**, including:

1. **Theorems with tactic proofs**:
   ```json
   {
     "full_name": "Nat.add_comm",
     "code": "theorem add_comm (n m : ℕ) : n + m = m + n := by\n  ...",
     "kind": "commanddeclaration"
   }
   ```

2. **Theorems with term proofs**:
   ```json
   {
     "full_name": "Nat.add_zero",
     "code": "theorem add_zero (n : ℕ) : n + 0 = n := rfl",
     "kind": "commanddeclaration"
   }
   ```

3. **Definitions**:
   ```json
   {
     "full_name": "Set",
     "code": "def Set (α : Type u) := α → Prop",
     "kind": "commanddeclaration"
   }
   ```

4. **Classes** (like your example):
   ```json
   {
     "full_name": "IncidenceGeometry",
     "code": "class IncidenceGeometry where\n  ...",
     "kind": "commanddeclaration"
   }
   ```

## Key Insight

**The corpus includes theorems (both tactic and term proofs)**, but:
- We **extract premises** only from **tactic proofs** (by parsing tactic text)
- For **term proofs**, we don't extract premises (too complex)
- The corpus is used as a **lookup table** to resolve premise names we've already extracted

So when we parse `"simp [add_comm]"` from a tactic, we can look up `"add_comm"` in the corpus to get its full name `"Nat.add_comm"`, regardless of whether `add_comm` itself has a tactic proof or term proof.

## Summary

- **Your example**: A class definition, not a proof
- **Term proof**: A functional expression proving a theorem (no `by` keyword)
- **We don't parse term proofs**: Too complex, would require AST traversal
- **Corpus includes both**: Theorems with tactic proofs AND term proofs
- **Corpus purpose**: Lookup table for resolving premise names we've extracted from tactic text
