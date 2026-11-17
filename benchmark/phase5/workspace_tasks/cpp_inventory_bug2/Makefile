CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -O1 -Isrc
SRC = src/item.cpp src/inventory.cpp src/pricing.cpp src/csv.cpp

inventory: $(SRC) src/main.cpp
	$(CXX) $(CXXFLAGS) -o $@ $^

test: tests/run_tests
	./tests/run_tests

tests/run_tests: $(SRC) tests/test_main.cpp
	$(CXX) $(CXXFLAGS) -o $@ $^

clean:
	rm -f inventory tests/run_tests
