#include "item.h"

// True when stock has fallen to the reorder level or below.
bool Item::needs_reorder() const { return stock <= reorder_level; }

long Item::stock_value() const { return price_cents * stock; }
