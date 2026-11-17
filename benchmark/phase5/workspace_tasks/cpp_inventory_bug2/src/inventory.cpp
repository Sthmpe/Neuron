#include "inventory.h"
#include <algorithm>

void Inventory::add(const Item& item) {
    if (items_.count(item.sku)) throw std::invalid_argument("duplicate sku " + item.sku);
    items_[item.sku] = item;
}

Item& Inventory::get(const std::string& sku) {
    auto it = items_.find(sku);
    if (it == items_.end()) throw std::out_of_range("no item " + sku);
    return it->second;
}

void Inventory::receive(const std::string& sku, int quantity) {
    if (quantity <= 0) throw std::invalid_argument("quantity must be positive");
    get(sku).stock += quantity;
}

void Inventory::take(const std::string& sku, int quantity) {
    Item& item = get(sku);
    if (quantity > item.stock) throw OutOfStock(sku + ": only " + std::to_string(item.stock) + " left");
    item.stock -= quantity;
}

std::vector<std::string> Inventory::reorder_list() const {
    std::vector<const Item*> low;
    for (const auto& kv : items_)
        if (kv.second.needs_reorder()) low.push_back(&kv.second);
    std::sort(low.begin(), low.end(), [](const Item* a, const Item* b) {
        if (a->stock != b->stock) return a->stock < b->stock;
        return a->sku < b->sku;
    });
    std::vector<std::string> out;
    for (auto* i : low) out.push_back(i->sku);
    return out;
}

long Inventory::total_value() const {
    long total = 0;
    for (const auto& kv : items_) total += kv.second.stock_value();
    return total;
}
