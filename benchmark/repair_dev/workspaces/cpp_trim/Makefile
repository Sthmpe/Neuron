test: tests/run
	./tests/run
tests/run: src/text.cpp src/text.h tests/test.cpp
	g++ -std=c++17 -O1 -Isrc -o tests/run src/text.cpp tests/test.cpp
