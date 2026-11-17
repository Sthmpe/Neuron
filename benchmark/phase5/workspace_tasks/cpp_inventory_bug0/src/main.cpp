#include <iostream>
#include "inventory.h"
#include "pricing.h"

int main() {
    Inventory inv;
    inv.add({"RICE", "Rice 5kg", 850000, 10, 5});
    inv.add({"OIL", "Palm oil", 240000, 3, 5});
    for (const auto& sku : inv.reorder_list()) std::cout << "reorder " << sku << "\n";
    std::cout << "value " << money(inv.total_value()) << "\n";
}
