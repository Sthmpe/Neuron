#pragma once
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#include "item.h"

struct OutOfStock : std::runtime_error {
    using std::runtime_error::runtime_error;
};

class Inventory {
  public:
    void add(const Item& item);
    Item& get(const std::string& sku);
    void receive(const std::string& sku, int quantity);
    // Removes stock for an order. Throws OutOfStock and changes nothing if there is not enough.
    void take(const std::string& sku, int quantity);
    std::vector<std::string> reorder_list() const;   // SKUs needing reorder, lowest stock first, then by SKU
    long total_value() const;
    size_t size() const { return items_.size(); }
  private:
    std::map<std::string, Item> items_;
};
