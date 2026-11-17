from shopkeeper.models import Customer, Product
from shopkeeper.services.inventory import Inventory
from shopkeeper.services.orders import OrderService
from shopkeeper.storage.repository import Repository


def shop():
    repo = Repository()
    repo.add_product(Product("RICE5", "Rice 5kg", 850000, stock=10))
    repo.add_product(Product("OIL1", "Palm Oil 1L", 240000, stock=40, reorder_level=10))
    repo.add_product(Product("BOOK", "Exercise Book", 50000, stock=3, vat_exempt=True))
    repo.add_product(Product("SUG1", "Sugar 1kg", 190000, stock=6))
    repo.add_customer(Customer("C1", "Ada Obi"))
    repo.add_customer(Customer("C2", "Bola Adeyemi", lifetime_spend=150_000_00))
    repo.add_customer(Customer("C3", "Chuka Nwosu", lifetime_spend=600_000_00))
    inv = Inventory(repo)
    return repo, inv, OrderService(repo, inv)
