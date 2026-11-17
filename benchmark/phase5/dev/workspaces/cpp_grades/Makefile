CXX ?= g++
test: tests/run
	./tests/run
tests/run: src/grades.cpp tests/test.cpp
	$(CXX) -std=c++17 -Isrc -o $@ $^
clean:
	rm -f tests/run
