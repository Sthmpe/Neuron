"""Placing, paying and cancelling orders."""
from ..models import Order, OrderLine
from .inventory import OutOfStock
from .pricing import price_order


class OrderError(Exception):
    pass


class OrderService:
    def __init__(self, repo, inventory):
        self.repo, self.inventory = repo, inventory

    def place(self, customer_code, items, date):
        """items: list of (sku, quantity). Either the whole order is placed or nothing changes."""
        customer = self.repo.customer(customer_code)
        order = Order(self.repo.new_order_number(), customer.code, date)
        reserved = []
        try:
            for sku, quantity in items:
                product = self.repo.product(sku)
                self.inventory.reserve(sku, quantity)
                reserved.append((sku, quantity))
                order.add(OrderLine(sku, quantity, product.price, product.vat_exempt))
        except OutOfStock:
            for sku, quantity in reserved:
                self.inventory.release(sku, quantity)
            raise
        self.repo.add_order(order)
        return order

    def pay(self, number):
        order = self.repo.order(number)
        if order.status != "open":
            raise OrderError(f"order {number} is {order.status}")
        customer = self.repo.customer(order.customer_code)
        bill = price_order(order, customer)
        order.status = "paid"
        customer.lifetime_spend += bill["total"]
        return bill

    def cancel(self, number):
        order = self.repo.order(number)
        if order.status not in ("open", "paid"):
            raise OrderError(f"order {number} cannot be cancelled")
        for line in order.lines:
            self.inventory.release(line.sku, line.quantity)
        if order.status == "paid":
            customer = self.repo.customer(order.customer_code)
            customer.lifetime_spend -= price_order(order, customer)["total"]
        order.status = "cancelled"

    def deliver(self, number):
        order = self.repo.order(number)
        if order.status != "paid":
            raise OrderError("only paid orders can be delivered")
        order.status = "delivered"
