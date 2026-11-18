#pragma once
#include <vector>
int fare(int age);                            // cents: under 12 pays 150, 65 and over rides free, everyone else 300
int day_total(const std::vector<int>& ages);  // fares for one group
int free_riders(const std::vector<int>& ages);
