"""Core proof, category A: app builds. Request (owner's words), the examiner's steps, and a correct reference plan used
only to validate the examiner (a template build of it must pass every check). Written before any tuning."""

def login_page(*pages):
    return ["", *pages]


APPS = [
    {"id": "A1_pharmacy",
     "request": "I run a small pharmacy. Make an app where I log in (user pharm, password pills42). Keep my medicines with "
                "their name, how many are in stock and the price. Keep sales: which medicine, the quantity and the customer's "
                "name; show what each sale costs. When I add a sale, the stock of that medicine must go down, and the sale must "
                "be refused if there is not enough stock. Search sales by customer. The dashboard shows the number of sales, the "
                "total value of all sales, and how many medicines have fewer than 10 in stock.",
     "spec": {"login": ["pharm", "pills42"], "pages": login_page("Medicines", "Sales"), "steps": [
         {"id": "add_medicine_1", "open": "Medicines", "fill": {"Name": "Paracetamol", "Stock": "50", "Price": "200"}, "expect": ["Paracetamol"]},
         {"id": "add_medicine_2", "open": "Medicines", "fill": {"Name": "Vitamin C", "Stock": "8", "Price": "500"}, "expect": ["Vitamin C"]},
         {"id": "add_sale", "open": "Sales", "fill": {"Medicine": "Paracetamol", "Quantity": "5", "Customer": "Ada Eze"}, "expect": ["Ada Eze"]},
         {"id": "sale_cost_shown", "open": "Sales", "expect": ["1000"]},
         {"id": "stock_went_down", "open": "Medicines", "near": [["Paracetamol", "45"]]},
         {"id": "too_large_sale_refused", "open": "Sales", "fill": {"Medicine": "Vitamin C", "Quantity": "20", "Customer": "Bayo Ade"}, "absent": ["Bayo Ade"]},
         {"id": "stock_unchanged_after_refusal", "open": "Medicines", "near": [["Vitamin C", "8"]]},
         {"id": "dashboard_numbers", "open": "/", "near": [["sales", "1"], ["(total|value)", "1000"], ["(fewer|low|below)", "1"]]},
         {"id": "search_by_customer", "open": "Sales", "search": "Ada", "expect": ["Ada Eze"]}],
         "after_restart": {"open": "Sales", "expect": ["Ada Eze"]}},
     "reference": {"app_name": "Pharmacy", "kind": "app", "login_required": True, "username": "pharm", "password": "pills42",
                   "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
                   "entities": [{"name": "medicines", "fields": [{"name": "name", "type": "text"}, {"name": "stock", "type": "number"},
                                                                 {"name": "price", "type": "number"}], "search_field": "name"},
                                {"name": "sales", "fields": [{"name": "medicine", "type": "link", "to": "medicines"}, {"name": "quantity", "type": "number"},
                                                             {"name": "customer", "type": "text"},
                                                             {"name": "cost", "type": "computed", "formula": "quantity * medicine.price"}],
                                 "search_field": "customer"}],
                   "dashboard": [{"label": "Sales", "entity": "sales", "kind": "count"},
                                 {"label": "Sales value", "entity": "sales", "kind": "sum", "field": "cost"},
                                 {"label": "Fewer than 10 in stock", "entity": "medicines", "kind": "count_below", "field": "stock", "below": 10}],
                   "rules": [{"on_add": "sales", "link_field": "medicine", "target_field": "stock", "amount_field": "quantity",
                              "change": "subtract", "block_if_negative": True}]}},

    {"id": "A2_tailor",
     "request": "I am a tailor. Build an app with a login (user stitch, password needle8). Keep customers with name and phone. "
                "Keep orders: which customer, the garment, the price and the deposit paid; show the balance still owed on each "
                "order (price minus deposit). Search orders by garment. The dashboard shows how many customers and orders I have "
                "and the total balance owed.",
     "spec": {"login": ["stitch", "needle8"], "pages": login_page("Customers", "Orders"), "steps": [
         {"id": "add_customer_1", "open": "Customers", "fill": {"Name": "Kemi Bello", "Phone": "0803 111 2222"}, "expect": ["Kemi Bello"]},
         {"id": "add_customer_2", "open": "Customers", "fill": {"Name": "Femi Ade", "Phone": "0805 333 4444"}, "expect": ["Femi Ade"]},
         {"id": "add_order_1", "open": "Orders", "fill": {"Customer": "Kemi", "Garment": "Agbada", "Price": "45000", "Deposit": "20000"}, "expect": ["Agbada"]},
         {"id": "add_order_2", "open": "Orders", "fill": {"Customer": "Femi", "Garment": "Kaftan", "Price": "30000", "Deposit": "30000"}, "expect": ["Kaftan"]},
         {"id": "balance_shown", "open": "Orders", "expect": ["25000"]},
         {"id": "dashboard_numbers", "open": "/", "near": [["customers", "2"], ["orders", "2"], ["(balance|owed)", "25000"]]},
         {"id": "search_by_garment", "open": "Orders", "search": "Agbada", "expect": ["Agbada"], "absent": ["Kaftan"]}],
         "after_restart": {"open": "Orders", "expect": ["Agbada", "Kaftan"]}},
     "reference": {"app_name": "Tailor", "kind": "app", "login_required": True, "username": "stitch", "password": "needle8",
                   "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
                   "entities": [{"name": "customers", "fields": [{"name": "name", "type": "text"}, {"name": "phone", "type": "phone"}], "search_field": "name"},
                                {"name": "orders", "fields": [{"name": "customer", "type": "link", "to": "customers"}, {"name": "garment", "type": "text"},
                                                              {"name": "price", "type": "number"}, {"name": "deposit", "type": "number"},
                                                              {"name": "balance", "type": "computed", "formula": "price - deposit"}],
                                 "search_field": "garment"}],
                   "dashboard": [{"label": "Customers", "entity": "customers", "kind": "count"}, {"label": "Orders", "entity": "orders", "kind": "count"},
                                 {"label": "Balance owed", "entity": "orders", "kind": "sum", "field": "balance"}]}},

    {"id": "A3_school_fees",
     "request": "Make a fee tracker for my school with a login (user bursar, password chalk77). Keep students with name, class "
                "and the term fee. Keep payments: which student and the amount paid. Search students by name. The dashboard shows "
                "the number of students, the total of all term fees, and the total paid.",
     "spec": {"login": ["bursar", "chalk77"], "pages": login_page("Students", "Payments"), "steps": [
         {"id": "add_student_1", "open": "Students", "fill": {"Name": "Ngozi Okafor", "Class": "JSS1", "Fee": "60000"}, "expect": ["Ngozi Okafor"]},
         {"id": "add_student_2", "open": "Students", "fill": {"Name": "Tunde Bakare", "Class": "JSS2", "Fee": "65000"}, "expect": ["Tunde Bakare"]},
         {"id": "add_payment_1", "open": "Payments", "fill": {"Student": "Ngozi", "Amount": "40000"}, "expect": ["40000"]},
         {"id": "add_payment_2", "open": "Payments", "fill": {"Student": "Tunde", "Amount": "65000"}, "expect": ["65000"]},
         {"id": "dashboard_numbers", "open": "/", "near": [["students", "2"], ["fee", "125000"], ["paid", "105000"]]},
         {"id": "search_students", "open": "Students", "search": "Tunde", "expect": ["Tunde Bakare"], "absent": ["Ngozi Okafor"]}],
         "after_restart": {"open": "Students", "expect": ["Ngozi Okafor"]}},
     "reference": {"app_name": "School fees", "kind": "app", "login_required": True, "username": "bursar", "password": "chalk77",
                   "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
                   "entities": [{"name": "students", "fields": [{"name": "name", "type": "text"}, {"name": "class_name", "type": "text"},
                                                                {"name": "term_fee", "type": "number"}], "search_field": "name"},
                                {"name": "payments", "fields": [{"name": "student", "type": "link", "to": "students"}, {"name": "amount", "type": "number"}],
                                 "search_field": "student"}],
                   "dashboard": [{"label": "Students", "entity": "students", "kind": "count"},
                                 {"label": "Term fees", "entity": "students", "kind": "sum", "field": "term_fee"},
                                 {"label": "Total paid", "entity": "payments", "kind": "sum", "field": "amount"}]}},

    {"id": "A4_savings_group",
     "request": "Our savings group needs an app with a login (user treasurer, password coins55). Keep members with name and "
                "phone. Keep contributions: which member, the amount and the month. Search contributions by month. The dashboard "
                "shows the number of members, the total contributed and how many contributions were below 5000.",
     "spec": {"login": ["treasurer", "coins55"], "pages": login_page("Members", "Contributions"), "steps": [
         {"id": "add_member_1", "open": "Members", "fill": {"Name": "Amaka Obi", "Phone": "0802 123 4567"}, "expect": ["Amaka Obi"]},
         {"id": "add_member_2", "open": "Members", "fill": {"Name": "Sani Musa", "Phone": "0806 765 4321"}, "expect": ["Sani Musa"]},
         {"id": "add_contribution_1", "open": "Contributions", "fill": {"Member": "Amaka", "Amount": "10000", "Month": "January"}, "expect": ["January"]},
         {"id": "add_contribution_2", "open": "Contributions", "fill": {"Member": "Sani", "Amount": "3000", "Month": "January"}, "expect": ["3000"]},
         {"id": "add_contribution_3", "open": "Contributions", "fill": {"Member": "Amaka", "Amount": "7000", "Month": "February"}, "expect": ["February"]},
         {"id": "dashboard_numbers", "open": "/", "near": [["members", "2"], ["(total|contributed)", "20000"], ["below", "1"]]},
         {"id": "search_by_month", "open": "Contributions", "search": "February", "expect": ["7000"], "absent": ["3000"]}],
         "after_restart": {"open": "Contributions", "expect": ["February"]}},
     "reference": {"app_name": "Savings group", "kind": "app", "login_required": True, "username": "treasurer", "password": "coins55",
                   "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
                   "entities": [{"name": "members", "fields": [{"name": "name", "type": "text"}, {"name": "phone", "type": "phone"}], "search_field": "name"},
                                {"name": "contributions", "fields": [{"name": "member", "type": "link", "to": "members"}, {"name": "amount", "type": "number"},
                                                                     {"name": "month", "type": "text"}], "search_field": "month"}],
                   "dashboard": [{"label": "Members", "entity": "members", "kind": "count"},
                                 {"label": "Total contributed", "entity": "contributions", "kind": "sum", "field": "amount"},
                                 {"label": "Below 5000", "entity": "contributions", "kind": "count_below", "field": "amount", "below": 5000}]}},

    {"id": "A5_library_loans",
     "request": "Make a library app with a login (user librarian, password books21). Keep books with title, author and the "
                "number of copies on the shelf. Keep loans: which book, the borrower's name and how many copies they take. When a "
                "loan is added, the copies on the shelf go down by that number, and the loan must be refused if not enough copies "
                "are left. Search loans by borrower. The dashboard shows the number of loans and how many books have fewer than 1 "
                "copy on the shelf.",
     "spec": {"login": ["librarian", "books21"], "pages": login_page("Books", "Loans"), "steps": [
         {"id": "add_book_1", "open": "Books", "fill": {"Title": "Arrow of God", "Author": "Chinua Achebe", "Copies": "2"}, "expect": ["Arrow of God"]},
         {"id": "add_book_2", "open": "Books", "fill": {"Title": "Purple Hibiscus", "Author": "Chimamanda Adichie", "Copies": "1"}, "expect": ["Purple Hibiscus"]},
         {"id": "add_loan", "open": "Loans", "fill": {"Book": "Arrow", "Borrower": "Musa Bello", "Copies": "1"}, "expect": ["Musa Bello"]},
         {"id": "copies_went_down", "open": "Books", "near": [["Achebe", "1"]]},
         {"id": "too_large_loan_refused", "open": "Loans", "fill": {"Book": "Purple", "Borrower": "Ife Ojo", "Copies": "2"}, "absent": ["Ife Ojo"]},
         {"id": "dashboard_numbers", "open": "/", "near": [["loans", "1"], ["(fewer|copy|shelf)", "0"]]},
         {"id": "search_by_borrower", "open": "Loans", "search": "Musa", "expect": ["Musa Bello"]}],
         "after_restart": {"open": "Loans", "expect": ["Musa Bello"]}},
     "reference": {"app_name": "Library", "kind": "app", "login_required": True, "username": "librarian", "password": "books21",
                   "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
                   "entities": [{"name": "books", "fields": [{"name": "title", "type": "text"}, {"name": "author", "type": "text"},
                                                             {"name": "copies", "type": "number"}], "search_field": "title"},
                                {"name": "loans", "fields": [{"name": "book", "type": "link", "to": "books"}, {"name": "borrower", "type": "text"},
                                                             {"name": "copies_taken", "type": "number"}], "search_field": "borrower"}],
                   "dashboard": [{"label": "Loans", "entity": "loans", "kind": "count"},
                                 {"label": "Fewer than 1 copy", "entity": "books", "kind": "count_below", "field": "copies", "below": 1}],
                   "rules": [{"on_add": "loans", "link_field": "book", "target_field": "copies", "amount_field": "copies_taken",
                              "change": "subtract", "block_if_negative": True}]}},

    {"id": "A6_gym_members",
     "request": "Build a members app for my gym with a login (user coach, password lift900). Keep members with name, plan and "
                "monthly fee. Search members by name. The dashboard shows how many members there are, the total monthly income "
                "from fees, and how many members pay less than 10000 a month.",
     "spec": {"login": ["coach", "lift900"], "pages": login_page("Members"), "steps": [
         {"id": "add_member_1", "open": "Members", "fill": {"Name": "Halima Yusuf", "Plan": "Gold", "Fee": "15000"}, "expect": ["Halima Yusuf"]},
         {"id": "add_member_2", "open": "Members", "fill": {"Name": "Obinna Eze", "Plan": "Basic", "Fee": "8000"}, "expect": ["Obinna Eze"]},
         {"id": "add_member_3", "open": "Members", "fill": {"Name": "Grace Udo", "Plan": "Basic", "Fee": "8000"}, "expect": ["Grace Udo"]},
         {"id": "dashboard_numbers", "open": "/", "near": [["members", "3"], ["(income|total)", "31000"], ["(less|below)", "2"]]},
         {"id": "search_members", "open": "Members", "search": "Grace", "expect": ["Grace Udo"], "absent": ["Halima Yusuf"]}],
         "after_restart": {"open": "Members", "expect": ["Obinna Eze"]}},
     "reference": {"app_name": "Gym", "kind": "app", "login_required": True, "username": "coach", "password": "lift900",
                   "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
                   "entities": [{"name": "members", "fields": [{"name": "name", "type": "text"}, {"name": "plan", "type": "text"},
                                                               {"name": "monthly_fee", "type": "number"}], "search_field": "name"}],
                   "dashboard": [{"label": "Members", "entity": "members", "kind": "count"},
                                 {"label": "Monthly income", "entity": "members", "kind": "sum", "field": "monthly_fee"},
                                 {"label": "Less than 10000", "entity": "members", "kind": "count_below", "field": "monthly_fee", "below": 10000}]}},

    {"id": "A7_event_tickets",
     "request": "I sell tickets for events. Make an app with a login (user tickets, password stage44). Keep events with name, "
                "ticket price and seats left. Keep ticket sales: which event, how many tickets and the buyer's name; show what each "
                "sale costs. When I add a sale, the seats left for that event go down, and the sale must be refused if there are "
                "not enough seats. Search sales by buyer. The dashboard shows the number of sales and the total ticket revenue.",
     "spec": {"login": ["tickets", "stage44"], "pages": login_page("Events", "Sales"), "steps": [
         {"id": "add_event_1", "open": "Events", "fill": {"Name": "Jazz Night", "Price": "5000", "Seats": "100"}, "expect": ["Jazz Night"]},
         {"id": "add_event_2", "open": "Events", "fill": {"Name": "Comedy Show", "Price": "3000", "Seats": "4"}, "expect": ["Comedy Show"]},
         {"id": "add_sale", "open": "Sales", "fill": {"Event": "Jazz", "Tickets": "3", "Buyer": "Ada Eze"}, "expect": ["Ada Eze"]},
         {"id": "sale_cost_shown", "open": "Sales", "expect": ["15000"]},
         {"id": "seats_went_down", "open": "Events", "expect": ["97"]},
         {"id": "too_large_sale_refused", "open": "Sales", "fill": {"Event": "Comedy", "Tickets": "5", "Buyer": "Bayo Ade"}, "absent": ["Bayo Ade"]},
         {"id": "dashboard_numbers", "open": "/", "near": [["sales", "1"], ["revenue", "15000"]]},
         {"id": "search_by_buyer", "open": "Sales", "search": "Ada", "expect": ["Ada Eze"]}],
         "after_restart": {"open": "Sales", "expect": ["Ada Eze"]}},
     "reference": {"app_name": "Tickets", "kind": "app", "login_required": True, "username": "tickets", "password": "stage44",
                   "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
                   "entities": [{"name": "events", "fields": [{"name": "name", "type": "text"}, {"name": "price", "type": "number"},
                                                              {"name": "seats", "type": "number"}], "search_field": "name"},
                                {"name": "sales", "fields": [{"name": "event", "type": "link", "to": "events"}, {"name": "tickets", "type": "number"},
                                                             {"name": "buyer", "type": "text"},
                                                             {"name": "cost", "type": "computed", "formula": "tickets * event.price"}],
                                 "search_field": "buyer"}],
                   "dashboard": [{"label": "Sales", "entity": "sales", "kind": "count"},
                                 {"label": "Ticket revenue", "entity": "sales", "kind": "sum", "field": "cost"}],
                   "rules": [{"on_add": "sales", "link_field": "event", "target_field": "seats", "amount_field": "tickets",
                              "change": "subtract", "block_if_negative": True}]}},

    {"id": "A8_repair_shop_site",
     "request": "Make a website for Swift Fix, a phone repair shop at 9 Ogui Road, Enugu. We repair cracked screens from 15,000 "
                "naira, replace batteries from 8,000 naira and fix charging ports from 6,000 naira. We are open Monday to "
                "Saturday, 9am to 6pm. Add a form where people leave their name and phone number to ask for a call back, and "
                "thank them afterwards.",
     "spec": {"login": None, "pages": [""], "steps": [
         {"id": "business_and_services", "open": "/", "expect": ["Swift Fix", "15000", "8000", "6000"]},
         {"id": "address_and_hours", "open": "/", "expect": ["9 Ogui Road", "Monday", "Saturday", "9am", "6pm"]},
         {"id": "nothing_invented", "open": "/", "absent": ["@", "testimonial", "years of experience", "award"]},
         {"id": "call_back_form_thanks", "open": "/", "fill": {"Name": "Chidi Okeke", "Phone": "0803 555 1212"}, "stay": True, "expect": ["thank"]}]},
     "reference": {"app_name": "Swift Fix", "kind": "site", "login_required": False, "username": "", "password": "",
                   "home": {"headline": "Swift Fix phone repairs in Enugu", "subheadline": "Screens, batteries and charging ports fixed at 9 Ogui Road.",
                            "sections": [{"title": "Repairs and prices", "text": "", "items": [
                                {"title": "Cracked screens", "text": "From 15,000 naira"}, {"title": "Batteries", "text": "From 8,000 naira"},
                                {"title": "Charging ports", "text": "From 6,000 naira"}]},
                                {"title": "Visit us", "text": "9 Ogui Road, Enugu. Monday to Saturday, 9am to 6pm.", "items": []}]},
                   "forms": [{"name": "callbacks", "title": "Ask for a call back", "fields": [{"name": "name", "type": "text"}, {"name": "phone", "type": "phone"}],
                              "button": "Call me back", "thanks": "Thank you, we will call you back soon."}],
                   "entities": [], "dashboard": []}},
]

for a in APPS:
    a["category"] = "app"
    a["budget_s"] = 900
