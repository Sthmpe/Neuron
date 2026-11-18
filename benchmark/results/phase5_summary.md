# Phase 5: locked evaluation results

12 tasks locked on 2026-11-17 before the system was built or tuned on them (`benchmark/phase5/LOCKED.md`, three
recorded examiner amendments). Network off, every process inside the tier's memory limit, results judged only by
independent examiners. Official runs are the first run per tier; 'rerun' files are labelled reruns after fixing
NEURON bugs that an official run exposed, and are not a clean held-out measurement.

| Run | Solved |
|---|---|
| locked-2gb | 5 of 12 |
| locked-4gb | 4 of 12 |
| locked-8gb | 7 of 12 |
| locked-4gb-rerun-after-portfix | 1 of 2 |
| locked-4gb-rerun2-after-fixes | 1 of 2 |

### locked-2gb

Model: qwen2.5-coder-1.5b-q4 | tier limit 2048 MB | code 08d449fc96 | network: new empty network namespace (loopback only)

| Task | Solved | Checks | Minutes | Peak MB | Model calls | Agent said | False claim | Made by |
|---|---|---|---|---|---|---|---|---|
| L01_pdf_research | no | 9/16 | 2.5 | 1479 | 24 | PARTIAL |  | deterministic 1 |
| L02_excel_summary | yes | 14/14 | 0.2 | 1574 | 1 | VERIFIED |  | deterministic 2, model 1, template 1 |
| L03_word_proposal | yes | 5/5 | 1.6 | 1459 | 6 | VERIFIED |  | model 1, model+template 1, deterministic 1 |
| L04_pptx_pitch | yes | 9/9 | 0.4 | 1518 | 1 | VERIFIED |  | model 1, template 1, deterministic 1 |
| L05_cpp_budget_cli | no | 0/1 | 24.1 | 1565 | 37 | PARTIAL |  | model 1 |
| L06_cpp_bug_stock | yes | 1/1 | 0.6 | 1564 | 5 | VERIFIED |  | deterministic 1, model 1 |
| L07_cpp_bug_discount | no | 0/1 | 1.0 | 1558 | 7 | PARTIAL |  | deterministic 1 |
| L08_cpp_bug_parse | no | 0/1 | 0.7 | 1563 | 7 | PARTIAL |  | deterministic 1 |
| L09_go_bug_rate | no | 0/1 | 1.2 | 1774 | 7 | PARTIAL |  | deterministic 1 |
| L10_go_bug_round | no | 0/1 | 1.1 | 1759 | 7 | PARTIAL |  | deterministic 1 |
| L11_business_app | no | 0/17 | 2.7 | ? | 9 | FAILED |  |  |
| L12_long_docstrings | yes | 4/4 | 1.3 | 1407 | 31 | VERIFIED |  | deterministic 2, model 1 |

Solved 5 of 12.

What failed (examiner's words):
- L01_pdf_research: q2_cites_right_page: needs riverside page 2; q3_answer_correct: Old Town uses the most water per day, with a daily use of 19,500 million litres. (riverside water report 2025, page 4); q3_cites_right_page: needs riverside page 2
- L05_cpp_budget_cli: builds_with_make: iter.cpp: In function ‘int main(int, char**)’: src/transaction_writer.cpp:97:60: error: conversion from ‘vector<Transaction>’ to non
- L07_cpp_bug_discount: original_tests_pass: FAIL line 42: discount_percent(10) == 5 FAIL line 45: order_total({{1000, 10}}) == 9500 FAIL line 46: order_total({{999, 10}}) ==
- L08_cpp_bug_parse: original_tests_pass: FAIL line 56: parse_cents("12.5") == 1250 make: *** [Makefile:9: test] Error 1 
- L09_go_bug_rate: original_tests_pass: --- FAIL: TestRates (0.00s)     ledger_test.go:31: 15000 NGN = 2250000000 USD cents, want 1000 FAIL FAIL	example.com/ledger/ledge
- L10_go_bug_round: original_tests_pass: --- FAIL: TestRoundDiv (0.00s)     ledger_test.go:9: RoundDiv(10,4)=2 want 3     ledger_test.go:9: RoundDiv(-10,4)=-2 want -3    
- L11_business_app: login_required: the app was not running; wrong_password_rejected: the app was not running; login_works: the app was not running

### locked-4gb

Model: qwen3.5-4b-q4 | tier limit 4096 MB | code c8fd549b0c | network: new empty network namespace (loopback only)

| Task | Solved | Checks | Minutes | Peak MB | Model calls | Agent said | False claim | Made by |
|---|---|---|---|---|---|---|---|---|
| L01_pdf_research | no | 15/16 | 2.0 | 3824 | 8 | VERIFIED | yes | deterministic 1, model 1 |
| L02_excel_summary | yes | 14/14 | 0.8 | 3932 | 1 | VERIFIED |  | deterministic 2, model 1, template 1 |
| L03_word_proposal | yes | 5/5 | 7.8 | 3911 | 11 | VERIFIED |  | model 1, model+template 1, deterministic 1 |
| L04_pptx_pitch | yes | 9/9 | 1.4 | 3876 | 1 | VERIFIED |  | model 1, template 1, deterministic 1 |
| L05_cpp_budget_cli | no | 0/1 | 31.5 | 3974 | 10 | PARTIAL |  | model 1 |
| L06_cpp_bug_stock | no | 0/1 | 3.5 | 4002 | 7 | PARTIAL |  | deterministic 1 |
| L07_cpp_bug_discount | yes | 1/1 | 2.5 | 3993 | 5 | VERIFIED |  | deterministic 1, model 1 |
| L08_cpp_bug_parse | no | 0/1 | 1.5 | 4084 | 1 | PARTIAL |  | deterministic 1 |
| L09_go_bug_rate | no | 0/1 | 5.9 | 4076 | 8 | PARTIAL |  | deterministic 1 |
| L10_go_bug_round | no | 0/1 | 3.8 | 4079 | 5 | PARTIAL |  | deterministic 1 |
| L11_business_app | no | 5/17 | 2.5 | 3923 | ? | no report (crashed or killed) |  |  |
| L12_long_docstrings | no | 3/4 (amendment 2) | 1.6 | 3749 | ? | no report (crashed or killed) |  |  |

Solved 4 of 12.

What failed (examiner's words):
- L01_pdf_research: q7_answer_correct: Students with a valid card pay half the adult single fare. (greenline bus policy 2026, page 2)
- L05_cpp_budget_cli: builds_with_make: tialized.h:90:56: error: static assertion failed: result type must be constructible from input type    90 |       static_assert(is_c
- L06_cpp_bug_stock: original_tests_pass: FAIL line 27: inv.get("RICE").stock == 10 FAIL line 29: inv.get("RICE").stock == 15 make: *** [Makefile:9: test] Error 2 
- L08_cpp_bug_parse: original_tests_pass: FAIL line 56: parse_cents("12.5") == 1250 make: *** [Makefile:9: test] Error 1 
- L09_go_bug_rate: original_tests_pass: --- FAIL: TestRates (0.00s)     ledger_test.go:31: 15000 NGN = 2250000000 USD cents, want 1000 FAIL FAIL	example.com/ledger/ledge
- L10_go_bug_round: original_tests_pass: --- FAIL: TestRoundDiv (0.00s)     ledger_test.go:9: RoundDiv(10,4)=2 want 3     ledger_test.go:9: RoundDiv(-10,4)=-2 want -3    
- L11_business_app: login_works: Cannot read properties of null (reading 'fill'); add_products: no field for Price; product_search: locator.fill: Timeout 30000ms exceeded.
- L12_long_docstrings: every_function_documented: 35 of 50; missing ['shopkeeper/services/reports.py:customers_by_tier', 'shopkeeper/storage/repository.py:__init__', 'shopke

### locked-8gb

Model: gemma-4-e4b-q4 | tier limit 8192 MB | code 429243aca4 | network: new empty network namespace (loopback only)

| Task | Solved | Checks | Minutes | Peak MB | Model calls | Agent said | False claim | Made by |
|---|---|---|---|---|---|---|---|---|
| L01_pdf_research | no | 14/16 | 5.7 | 5635 | 8 | VERIFIED | yes | deterministic 1, model 1 |
| L02_excel_summary | yes | 14/14 | 0.8 | 5726 | 1 | VERIFIED |  | deterministic 2, model 1, template 1 |
| L03_word_proposal | yes | 5/5 | 8.1 | 5655 | 11 | VERIFIED |  | model 1, model+template 1, deterministic 1 |
| L04_pptx_pitch | yes | 9/9 | 1.4 | 5767 | 1 | VERIFIED |  | model 1, template 1, deterministic 1 |
| L05_cpp_budget_cli | yes | 7/7 | 15.8 | 5777 | 4 | VERIFIED |  | model 2 |
| L06_cpp_bug_stock | no | 0/1 | 6.2 | 5796 | 7 | PARTIAL |  | deterministic 1 |
| L07_cpp_bug_discount | yes | 1/1 | 1.3 | 5745 | 2 | VERIFIED |  | deterministic 1, model 1 |
| L08_cpp_bug_parse | yes | 1/1 | 6.9 | 5765 | 8 | VERIFIED |  | deterministic 1, model 1 |
| L09_go_bug_rate | no | 0/1 | 7.6 | 6008 | 8 | PARTIAL |  | deterministic 1 |
| L10_go_bug_round | no | 0/1 | 8.2 | 5998 | 7 | PARTIAL |  | deterministic 1 |
| L11_business_app | no | 13/17 | 12.1 | 5878 | 6 | VERIFIED | yes | model (4 files) + code (1 file) 1 |
| L12_long_docstrings | yes | 4/4 | 4.5 | 5614 | 31 | VERIFIED |  | deterministic 2, model 1 |

Solved 7 of 12.

What failed (examiner's words):
- L01_pdf_research: q3_answer_correct: Northbank uses the most water per day, at 31,200 million litres. (riverside water report 2025, page 2); q7_answer_correct: A student pays half the adult single fare. (greenline bus policy 2026, page 2)
- L06_cpp_bug_stock: original_tests_pass: FAIL line 27: inv.get("RICE").stock == 10 FAIL line 29: inv.get("RICE").stock == 15 make: *** [Makefile:9: test] Error 2 
- L09_go_bug_rate: original_tests_pass: --- FAIL: TestRates (0.00s)     ledger_test.go:31: 15000 NGN = 2250000000 USD cents, want 1000 FAIL FAIL	example.com/ledger/ledge
- L10_go_bug_round: original_tests_pass: --- FAIL: TestRoundDiv (0.00s)     ledger_test.go:9: RoundDiv(10,4)=2 want 3     ledger_test.go:9: RoundDiv(-10,4)=-2 want -3    
- L11_business_app: orders_list_shows_totals: needs 6000 and 18000; dashboard_numbers: Skip to content M Mama Ngozi Provisions Dashboard Products Customers Orders ngozi Log out Dashboard Total Revenue 2 Number of Order; own_tests_exist: 0 tests in 0 files

### locked-4gb-rerun-after-portfix

Model: qwen3.5-4b-q4 | tier limit 4096 MB | code 9d8a6ea614 | network: new empty network namespace (loopback only)

| Task | Solved | Checks | Minutes | Peak MB | Model calls | Agent said | False claim | Made by |
|---|---|---|---|---|---|---|---|---|
| L11_business_app | no | 5/17 | 10.8 | 3933 | 10 | FAILED |  |  |
| L12_long_docstrings | yes | 4/4 (amendment 2) | 3.1 | 3749 | 31 | VERIFIED |  | deterministic 2, model 1 |

Solved 1 of 2.

What failed (examiner's words):
- L11_business_app: login_works: Cannot read properties of null (reading 'fill'); add_products: no field for Price; product_search: locator.fill: Timeout 30000ms exceeded.

### locked-4gb-rerun2-after-fixes

Model: qwen3.5-4b-q4 | tier limit 4096 MB | code d921939c61 | network: new empty network namespace (loopback only)

| Task | Solved | Checks | Minutes | Peak MB | Model calls | Agent said | False claim | Made by |
|---|---|---|---|---|---|---|---|---|
| L11_business_app | no | 13/17 | 4.8 | 4055 | 2 | VERIFIED | yes | model (4 files) + code (1 file) 1 |
| L12_long_docstrings | yes | 4/4 (amendment 2) | 3.0 | 3748 | 31 | VERIFIED |  | deterministic 2, model 1 |

Solved 1 of 2.

What failed (examiner's words):
- L11_business_app: orders_list_shows_totals: needs 6000 and 18000; dashboard_numbers: Skip to content M Mama Ngozi Provisions Dashboard Products Customers Orders ngozi Log out Dashboard Total Revenue 2 Total Orders 2 ; own_tests_exist: 0 tests in 0 files

