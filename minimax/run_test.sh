#!/bin/bash
cd '/mnt/e/LeanATP Harness/minimax'
python3 -u test_corpus_mode2.py --count 10 --workers 1 2>&1 | tee /tmp/mode2_test.log
