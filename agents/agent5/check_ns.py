import json, re, os, sys, subprocess
sys.path.insert(0, '/mnt/e/LeanATP Harness/agents/agent5/verifier')
from test_corpus import MATHLIB_ROOT

# For the problematic open-inside-namespace cases, check if they're valid at top level
problematic_cases = [
    ('StructureSheaf', 'AlgebraicGeometry'),
    ('Spec', 'AlgebraicGeometry'),
    ('FreeCommRing', 'Ring'),
    ('LinearEquiv', 'Module'),
    ('LinearMap', 'Module'),
    ('Polynomial', 'Ring'),
    ('NormalizedMooreComplex', 'AlgebraicTopology'),
    ('CategoryTheory', 'SSet'),
    ('Simplicial', 'SSet'),
    ('Pointwise', 'Set'),
    ('AddAction', 'Pi'),
    ('AddTorsor', 'Pi'),
    ('MulOpposite', 'QuaternionAlgebra'),
    ('Associated', 'Associates'),
]

for name, inside_ns in problematic_cases:
    # Check if a top-level 'namespace X' declaration exists
    result = subprocess.run(
        ['grep', '-rn', '--include=*.lean', '-l', 'namespace ' + name],
        capture_output=True, text=True, cwd=MATHLIB_ROOT
    )
    found = result.stdout.strip()
    count = len(found.split('\n')) if found else 0
    print(name + ' (inside ' + inside_ns + '): found in ' + str(count) + ' files')
    # Also check for 'namespace NS.Name' form
    result2 = subprocess.run(
        ['grep', '-rn', '--include=*.lean', '-l', 'namespace ' + inside_ns + '.' + name],
        capture_output=True, text=True, cwd=MATHLIB_ROOT
    )
    found2 = result2.stdout.strip()
    count2 = len(found2.split('\n')) if found2 else 0
    print('  As ' + inside_ns + '.' + name + ': found in ' + str(count2) + ' files')
