// A tiny test runner: each CHECK that fails is printed; the exit code is the number of failures.
#include <iostream>
#include "../src/csv.h"
#include "../src/inventory.h"
#include "../src/pricing.h"

static int failures = 0;
#define CHECK(cond) do { if (!(cond)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #cond "\n"; } } while (0)

static Inventory shop() {
    Inventory inv;
    inv.add({"RICE", "Rice 5kg", 850000, 10, 5});
    inv.add({"OIL", "Palm oil", 240000, 40, 10});
    inv.add({"BOOK", "Exercise book", 50000, 3, 5});
    inv.add({"SUGAR", "Sugar 1kg", 190000, 6, 5});
    return inv;
}

int main() {
    {   // stock
        Inventory inv = shop();
        inv.take("BOOK", 3);
        CHECK(inv.get("BOOK").stock == 0);
        bool thrown = false;
        try { inv.take("RICE", 11); } catch (const OutOfStock&) { thrown = true; }
        CHECK(thrown);
        CHECK(inv.get("RICE").stock == 10);
        inv.receive("RICE", 5);
        CHECK(inv.get("RICE").stock == 15);
    }
    {   // reorder list
        Inventory inv = shop();
        auto r = inv.reorder_list();
        CHECK(r.size() == 1 && r[0] == "BOOK");
        inv.take("SUGAR", 1);
        r = inv.reorder_list();
        CHECK(r.size() == 2 && r[0] == "BOOK" && r[1] == "SUGAR");
        CHECK(inv.total_value() == 10L * 850000 + 40L * 240000 + 3L * 50000 + 5L * 190000);
    }
    {   // pricing
        CHECK(discount_percent(9) == 0);
        CHECK(discount_percent(10) == 5);
        CHECK(discount_percent(50) == 10);
        CHECK(order_total({{1000, 2}}) == 2000);
        CHECK(order_total({{1000, 10}}) == 9500);
        CHECK(order_total({{999, 10}}) == 9490);       // 499.5 discount rounds up to 500
        CHECK(order_total({{100, 30}, {200, 20}}) == 6300);
        CHECK(money(123456) == "1234.56");
        CHECK(money(5) == "0.05");
    }
    {   // csv
        auto f = split_csv("a,\"b, c\",d");
        CHECK(f.size() == 3 && f[1] == "b, c");
        auto g = split_csv("x,\"say \"\"hi\"\"\",");
        CHECK(g.size() == 3 && g[1] == "say \"hi\"" && g[2].empty());
        CHECK(parse_cents("12.5") == 1250);
        CHECK(parse_cents("12") == 1200);
        CHECK(parse_cents("12.05") == 1205);
        CHECK(parse_cents("0.99") == 99);
    }
    if (failures == 0) std::cout << "all tests passed\n";
    return failures;
}
