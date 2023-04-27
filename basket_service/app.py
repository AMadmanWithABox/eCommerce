import uuid
import redis
import requests
from apiflask import APIFlask, Schema
from apiflask.fields import String, UUID
from flask_cors import CORS

app = APIFlask(__name__)
CORS(app)

redis_client = redis.StrictRedis(host='redis', port=6379, db=0, decode_responses=True)

items_service_url = 'http://items_service:5000/api/v1/items/'


class BasketItemIn(Schema):
    """
    Basket Item Schema

    :param item_uuid: Unique identifier for the item
    """
    item_uuid = String(required=True)


class BasketItemOut(Schema):
    """
    Basket Item Schema for output endpoints

    :param item_uuid: Unique identifier for the item
    :param url: URL of the item in the items_service
    """
    item_uuid = UUID()
    item_url = String()


class BasketIDOut(Schema):
    """
    Basket ID Schema

    :param basket_id: Unique identifier for the basket
    """
    basket_id = String()


@app.post('/api/v1/basket')
@app.output(BasketIDOut, status_code=201)
def create_basket():
    """
    Create a new basket

    :return: The basket ID
    """
    basket_id = str(uuid.uuid4())
    redis_client.hset(basket_id, 'basket_id', basket_id)
    return {"basket_id": basket_id}, 201


@app.post('/api/v1/basket/<basket_id>/add_item')
@app.input({'item_uuid': String()}, location='query', schema_name='StringQuery')
@app.output(BasketItemOut, status_code=201)
def add_item_to_basket(basket_id, item):
    """
    Add item to basket
    :param item: Item data
    :param basket_id: Unique identifier for the basket
    :return: The item data that was added to the basket
    """
    item_uuid = item['item_uuid']
    item_url = items_service_url + str(item_uuid)
    response = requests.get(item_url)
    response.raise_for_status()
    data = {'item_uuid': item_uuid, 'item_url': item_url}
    redis_client.rpush(f'basket_items:{basket_id}', item_uuid)
    return BasketItemOut().load(data), 201


@app.get('/api/v1/basket/<basket_id>')
@app.output(BasketItemOut(many=True))
def get_basket(basket_id):
    """
    Get basket items

    :param basket_id: Unique identifier for the basket
    :return: A list of items in the basket
    """
    basket_items = redis_client.lrange(f'basket_items:{basket_id}', 0, -1)
    items = []
    for item_uuid in basket_items:
        item_url = items_service_url + str(item_uuid)
        items.append({'item_uuid': item_uuid, 'item_url': item_url})
    return BasketItemOut(many=True).load(items)


@app.delete('/api/v1/basket/<basket_id>/remove_item/<item_id>')
def remove_item_from_basket(basket_id, item_id):
    """
    Remove item from basket

    :param basket_id: Unique identifier for the basket
    :param item_id: Unique identifier for the item
    :return: Nothing
    """
    redis_client.lrem(f'basket_items:{basket_id}', 1, item_id)
    return '', 204


@app.delete('/api/v1/basket/<basket_id>')
def delete_basket(basket_id):
    """
    Empty basket

    :param basket_id: Unique identifier for the basket
    :return: Nothing
    """
    redis_client.delete(f'basket_items:{basket_id}')
    return '', 204


if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
