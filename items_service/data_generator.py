from faker import Faker
import json
import random

fake = Faker()


def generate_item_data():
    item_data = []
    for _ in range(100):
        item = {
            'item_name': fake.catch_phrase(),
            'item_description': fake.sentence(),
            'item_price': round(random.uniform(1, 100), 2)
        }
        item_data.append(item)
    return item_data


if __name__ == '__main__':
    data = generate_item_data()
    with open('sample_data.json', 'w') as f:
        json.dump(data, f, indent=2)
