# Code repair dev set (not locked: used to improve C++/Go bug fixing, step 5)

Six small projects whose own tests fail. Four have a one-token bug (C++: cpp_tickets, cpp_grades; Go: go_parking,
go_stock); two need real code (Go: go_split, C++: cpp_trim), to check that the model path still works.
None of them is in a locked evaluation. `python3 -m benchmark.repair_dev.validate` proves each reference fix passes
and each shipped bug fails; `python3 -m benchmark.repair_dev.run --tier 4gb` runs NEURON on all six (network cut,
memory off) and records solved, time, who made the fix and whether the tests were left untouched.

To measure the small-change search fairly, the same set is also run with it switched off
(`NEURON_REPAIR_SEARCH=0 python3 -m benchmark.repair_dev.run --tier 4gb --tag no-search`).
