#pragma once
#include <string>

struct Item {
    std::string sku;
    std::string name;
    long price_cents = 0;
    int stock = 0;
    int reorder_level = 5;
    bool needs_reorder() const;
    long stock_value() const;
};
