import random
from datetime import date, timedelta

from database.db import get_connection


def generate_data():
    connection = get_connection()
    cursor = connection.cursor()

    print("Connected to MySQL.")

    # -------------------------
    # Customers: 1,000
    # -------------------------
    customers = []

    cities = [
        "Chennai",
        "Bangalore",
        "Mumbai",
        "Delhi",
        "Hyderabad",
        "Pune",
        "Kolkata",
        "Jaipur"
    ]

    for i in range(1, 1001):
        customers.append((
            f"Customer {i}",
            f"customer{i}@example.com",
            random.choice(cities)
        ))

    cursor.executemany(
        """
        INSERT INTO customers
        (customer_name, email, city)
        VALUES (%s, %s, %s)
        """,
        customers
    )

    print("Inserted 1,000 customers.")

    # -------------------------
    # Products: 1,000
    # -------------------------
    products = []

    categories = [
        "Electronics",
        "Clothing",
        "Books",
        "Sports",
        "Home"
    ]

    for i in range(1, 1001):
        products.append((
            f"Product {i}",
            random.choice(categories),
            round(random.uniform(10, 5000), 2)
        ))

    cursor.executemany(
        """
        INSERT INTO products
        (product_name, category, price)
        VALUES (%s, %s, %s)
        """,
        products
    )

    print("Inserted 1,000 products.")

    # -------------------------
    # Orders: 10,000
    # -------------------------
    orders = []

    start_date = date(2023, 1, 1)

    for _ in range(10000):
        customer_id = random.randint(1, 1000)

        order_date = start_date + timedelta(
            days=random.randint(0, 1095)
        )

        total_amount = round(random.uniform(50, 10000), 2)

        status = random.choice([
            "Pending",
            "Shipped",
            "Delivered",
            "Cancelled"
        ])

        orders.append((
            customer_id,
            order_date,
            total_amount,
            status
        ))

    cursor.executemany(
        """
        INSERT INTO orders
        (customer_id, order_date, total_amount, status)
        VALUES (%s, %s, %s, %s)
        """,
        orders
    )

    print("Inserted 10,000 orders.")

    # -------------------------
    # Order Items: ~30,000
    # -------------------------
    order_items = []

    for order_id in range(1, 10001):
        number_of_items = random.randint(1, 5)

        for _ in range(number_of_items):
            product_id = random.randint(1, 1000)
            quantity = random.randint(1, 5)
            unit_price = round(random.uniform(10, 5000), 2)

            order_items.append((
                order_id,
                product_id,
                quantity,
                unit_price
            ))

    cursor.executemany(
        """
        INSERT INTO order_items
        (order_id, product_id, quantity, unit_price)
        VALUES (%s, %s, %s, %s)
        """,
        order_items
    )

    print(f"Inserted {len(order_items):,} order items.")

    connection.commit()

    cursor.close()
    connection.close()

    print("\nData generation completed successfully.")


if __name__ == "__main__":
    generate_data()