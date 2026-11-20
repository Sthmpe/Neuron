test: tests/run
	./tests/run
tests/run: src/account.cpp src/account.h src/ledger.cpp src/ledger.h tests/test.cpp
	g++ -std=c++17 -O1 -Isrc -o tests/run src/account.cpp src/ledger.cpp tests/test.cpp
