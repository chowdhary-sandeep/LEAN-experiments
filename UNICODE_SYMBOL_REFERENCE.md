# Unicode Symbol Normalization Reference

## Problem
Corpus.jsonl stores Unicode symbols as escape sequences (e.g., `\u22d9` for left arrow `←`), while our extraction code expects actual Unicode characters. We need to normalize all symbols before matching.

## Symbol Mapping List

### Arrows
| Unicode Escape | Character | Name | Usage in Lean |
|---------------|-----------|------|---------------|
| `\u22d9` | `←` | Left Arrow | Rewrite direction |
| `\u2190` | `←` | Leftwards Arrow | Alternative left arrow |
| `\u2192` | `→` | Rightwards Arrow | Function type, rewrite direction |
| `\u2194` | `↔` | Left Right Arrow | Biconditional |
| `\u27f5` | `⟵` | Long Leftwards Arrow | Category theory |
| `\u27f6` | `⟶` | Long Rightwards Arrow | Category theory (morphism) |
| `\u27f7` | `⟷` | Long Left Right Arrow | Category theory |
| `\u27f9` | `⟹` | Long Rightwards Double Arrow | Implication |

### Logic Symbols
| Unicode Escape | Character | Name | Usage in Lean |
|---------------|-----------|------|---------------|
| `\u2200` | `∀` | For All | Universal quantifier |
| `\u2203` | `∃` | There Exists | Existential quantifier |
| `\u22a2` | `⊢` | Right Tack | Turnstile (goal separator) |
| `\u22a3` | `⊣` | Left Tack | Left turnstile |

### Set Theory
| Unicode Escape | Character | Name | Usage in Lean |
|---------------|-----------|------|---------------|
| `\u2208` | `∈` | Element Of | Membership |
| `\u2209` | `∉` | Not An Element Of | Non-membership |
| `\u2282` | `⊂` | Subset Of | Subset |
| `\u2286` | `⊆` | Subset Of Or Equal To | Subset or equal |

### Relations
| Unicode Escape | Character | Name | Usage in Lean |
|---------------|-----------|------|---------------|
| `\u2264` | `≤` | Less-Than Or Equal To | Less or equal |
| `\u2265` | `≥` | Greater-Than Or Equal To | Greater or equal |
| `\u2260` | `≠` | Not Equal To | Inequality |
| `\u226a` | `≪` | Much Less-Than | Much less |
| `\u226b` | `≫` | Much Greater-Than | Much greater |

### Lattice Operations
| Unicode Escape | Character | Name | Usage in Lean |
|---------------|-----------|------|---------------|
| `\u2293` | `⊓` | Square Cap | Meet/infimum |
| `\u2294` | `⊔` | Square Cup | Join/supremum |

### Operators
| Unicode Escape | Character | Name | Usage in Lean |
|---------------|-----------|------|---------------|
| `\u22c5` | `⋅` | Dot Operator | Multiplication |
| `\u2218` | `∘` | Function Composition | Composition |
| `\u00d7` | `×` | Multiplication Sign | Cartesian product |
| `\u220f` | `∏` | N-Ary Product | Product |
| `\u2211` | `∑` | N-Ary Summation | Sum |

### Greek Letters (Common)
| Unicode Escape | Character | Name | Usage in Lean |
|---------------|-----------|------|---------------|
| `\u03b1` | `α` | Greek Small Letter Alpha | Type variable |
| `\u03b2` | `β` | Greek Small Letter Beta | Type variable |
| `\u03b3` | `γ` | Greek Small Letter Gamma | Type variable |
| `\u03b9` | `ι` | Greek Small Letter Iota | Index type |
| `\u03c0` | `π` | Greek Small Letter Pi | Projection |
| `\u03c3` | `σ` | Greek Small Letter Sigma | Summation |
| `\u03c9` | `ω` | Greek Small Letter Omega | Universe level |

### Directional
| Unicode Escape | Character | Name | Usage in Lean |
|---------------|-----------|------|---------------|
| `\u2191` | `↑` | Upwards Arrow | Coercion |
| `\u2193` | `↓` | Downwards Arrow | Coercion |

## Implementation

The `normalize_unicode_symbols()` function in `00_myutils2.py` handles:
1. Decoding JSON-style Unicode escape sequences (`\uXXXX`)
2. Replacing known escape sequences with actual characters
3. Ensuring consistent representation for matching

## Usage

Always normalize:
- **Before extracting candidates** from tactics
- **Before matching candidates** against corpus
- **When loading corpus data** (convert escape sequences to characters)

## Example

```python
# Corpus has: "rw [\u22d9 norm_div]"
# After normalization: "rw [← norm_div]"
# Extraction will correctly find "norm_div"
```
