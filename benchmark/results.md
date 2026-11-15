# fix_code benchmark results

- Model: `qwen2.5-coder-1.5b-instruct-q6_k.gguf` (1396 MB, sha256 `9b05dce8089197c8…`)
- llama.cpp: version: 0.5.0-dev (build 1, commit 0c1e570)
- Machine: 4 CPU threads, 16088 MB RAM, x86_64
- Network during the run: new empty network namespace (loopback only); internet reachable: False
- Model load: 4.6s, 1692 MB resident after loading
- **Solved: 5 of 10**

| Project | Solved | Attempts | Time (s) | Tokens/s | Peak RAM model server (MB) | Peak RAM total (MB) | What happened |
|---|---|---|---|---|---|---|---|
| 01_shopping_cart | yes | 1 | 42.4 | 9.1 | 1757 | 1796 | changed cart.py: tests passed |
| 02_text_stats | NO | 3 | 85.5 | 9.6 | 1771 | 1810 | rejected: the proposed file is identical to the original (no change); changed textstats.py: tests still failing; changed textstats.py: tests still failing |
| 03_binary_search | NO | 3 | 286.3 | 9.1 | 1781 | 1821 | changed search.py: timed out; changed search.py: timed out; changed search.py: timed out |
| 04_bank_transfer | NO | 3 | 114.1 | 10.2 | 1838 | 1878 | rejected: the proposed file is identical to the original (no change); rejected: the proposed file is identical to the original (no change); changed bank.py: tests still failing |
| 05_date_utils | yes | 2 | 71.4 | 9.9 | 1838 | 1878 | rejected: the proposed file is identical to the original (no change); changed dateutils.py: tests passed |
| 06_matrix | yes | 1 | 46.8 | 8.8 | 1838 | 1878 | changed matrix.py: tests passed |
| 07_lru_cache | yes | 3 | 103.6 | 9.4 | 1838 | 1878 | changed lru.py: tests still failing; changed lru.py: tests still failing; changed lru.py: tests passed |
| 08_csv_parser | NO | 3 | 111.0 | 10.5 | 1838 | 1878 | rejected: the proposed file is identical to the original (no change); rejected: the reply names 'tests/test_csvlite.py', which is not an editable source file; rejected: the proposed file is identical to the original (no change) |
| 09_todo_app | NO | 3 | 93.6 | 9.9 | 1838 | 1878 | rejected: the proposed file is identical to the original (no change); rejected: the proposed file is identical to the original (no change); rejected: the proposed file is identical to the original (no change) |
| 10_intervals | yes | 2 | 64.2 | 9.8 | 1838 | 1878 | rejected: the proposed file is identical to the original (no change); changed intervals.py: tests passed |
