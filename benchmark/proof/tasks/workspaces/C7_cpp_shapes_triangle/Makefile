test: tests/run
	./tests/run
tests/run: src/shapes.cpp src/shapes.h tests/test.cpp
	g++ -std=c++17 -O1 -Isrc -o tests/run src/shapes.cpp tests/test.cpp
