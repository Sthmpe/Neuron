#pragma once
#include <string>
#include <vector>
char letter(int mark);                       // 70+ A, 60+ B, 50+ C, 40+ D, else F
double average(const std::vector<int>& marks);
int count_passes(const std::vector<int>& marks);   // marks of 40 or more
