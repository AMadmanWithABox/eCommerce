import json

from apiflask import APIFlask, Schema, abort
from apiflask.fields import Integer, String, Float, UUID, List
from bson import ObjectId
from flask.json import JSONEncoder
from flask_cors import CORS
from flask_pymongo import PyMongo
import uuid


DB_URL = "mongodb://mongo:27017/eCommerceApp"


class Items(Schema):
    """
    Item Schema

    :param item_uuid: Unique identifier for the item
    :param item_name: Name of the item
    :param item_description: Description of the item
    :param item_price: Price of the item
    """
    item_uuid = UUID(missing=lambda: str(uuid.uuid4()))
    item_name = String(required=True)
    item_description = String(required=True)
    item_price = Float(required=True)


class ItemsIn(Schema):
    """
    Item Schema for input endpoints

    :param item_name: Name of the item
    :param item_description: Description of the item
    :param item_price: Price of the item
    """
    item_name = String(required=True)
    item_description = String(required=True)
    item_price = Float(required=True)


class ItemsOut(Schema):
    """
    Item Schema for output endpoints

    :param item_uuid: Unique identifier for the item
    :param item_name: Name of the item
    :param item_description: Description of the item
    :param item_price: Price of the item
    """
    item_uuid = UUID()
    item_name = String()
    item_description = String()
    item_price = Float()


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        """
        Custom JSON encoder to handle ObjectId

        :param obj: Object to be encoded
        :return: JSON representation of the object
        """
        if isinstance(obj, ObjectId):
            return str(obj)
        return super(CustomJSONEncoder, self).default(obj)


app = APIFlask(__name__)
CORS(app)
app.json_encoder = CustomJSONEncoder

try:
    app.config["MONGO_URI"] = DB_URL
    mongo = PyMongo(app)
except:
    print("Could not connect to mongo")
    exit(1)


# def load_sample_data(filename='sample_data.json'):
#     with open(filename, 'r') as f:
#         raw_data = json.load(f)
#     data = [Items().load(item) for item in raw_data]
#     return data
#
#
# sample_data = load_sample_data()
# for item in sample_data:
#     mongo.db.items.insert_one(item)


@app.get('/api/v1/items')
@app.input({'_start': Integer(), '_end': Integer()}, location='query', schema_name='PaginationQuery')
@app.output(ItemsOut(many=True))
@app.doc(responses=[200, 404])
def get_items(query):
    """
    Get all items
    :return: JSON representation of all items
    """
    if query:
        start = query.get('_start', 0)
        end = query.get('_end', 10)
        items = mongo.db.items.find().skip(start).limit(end - start)
    else:
        items = mongo.db.items.find()
    return list(items)


@app.get('/api/v1/items/<item_uuid>')
@app.get('/api/v1/item_uuid/<item_uuid>')
@app.output(ItemsOut)
@app.doc(responses=[200, 404])
def get_item(item_uuid):
    """
    Get an item by its UUID
    :param item_uuid: UUID of the item to be retrieved
    :return: JSON representation of the item
    """
    item = mongo.db.items.find_one_or_404({"item_uuid": item_uuid})
    return item


@app.get('/api/v1/item_uuid')
@app.input({'id': List(String())}, location='query', schema_name='StringQuery')
@app.output(ItemsOut(many=True))
@app.doc(responses=[200, 404])
def get_items_by_ids(query):
    """
    Get multiple items by their UUIDs
    :param query: Query parameter that contains the UUIDs of the items to be retrieved
    :return: JSON representation of the item
    """
    items = []
    ids = query.get('id')
    if ids:
        for uid in ids:
            items.append(mongo.db.items.find_one_or_404({"item_uuid": uid}))
        return items
    else:
        abort(400, "No id provided")


@app.get('/api/v1/items/search')
@app.input({'search': String()}, location='query', schema_name='StringQuery')
@app.output(ItemsOut(many=True))
@app.doc(responses=[200, 404])
def search_items(search_term):
    """
    Search items by name
    :param search_term: Term to be searched
    :return: JSON representation of the items
    """
    search_term = search_term.get('search')
    items = mongo.db.items.find({"item_name": {"$regex": search_term, "$options": 'i'}})
    return list(items)


@app.delete('/api/v1/items/<item_uuid>')
@app.doc(responses=[204, 404])
def delete_item(item_uuid):
    """
    Delete an item by its UUID
    :param item_uuid: UUID of the item to be deleted
    :return: Empty response with status code 204
    """
    mongo.db.items.delete_one({"item_uuid": item_uuid})
    return '', 204


@app.put('/api/v1/items')
@app.input({'item_uuid': String()}, location='query', schema_name='StringQuery')
@app.input(ItemsIn, location='json')
@app.output(ItemsOut)
@app.doc(responses=[200, 400, 404])
def update_item(item_uuid, data):
    """
    Update an item by its UUID
    :param item_uuid: UUID of the item to be updated
    :param data: JSON representation of the item to be updated
    :return: JSON representation of the updated item
    """
    item_uuid = item_uuid.get('item_uuid')
    if not item_uuid:
        abort(400, "No item_uuid provided")
    try:
        item = Items().load(data)
        mongo.db.items.replace_one({"item_uuid": item_uuid}, item)
        return item
    except Exception as e:
        abort(400, str(e.with_traceback(None)))


@app.post('/api/v1/items')
@app.input(ItemsIn, location='json')
@app.output(Items, status_code=201)
@app.doc(responses=[201, 400])
def create_item(data):
    """
    Create an item
    :param data: JSON representation of the item to be created
    :return: JSON representation of the item along with the status code
    """
    try:
        item = Items().load(data)
        mongo.db.items.insert_one(item)
        return item, 201
    except Exception as e:
        abort(400, str(e.with_traceback(None)))


@app.post('/api/v1/items/bulk')
@app.input(ItemsIn(many=True), location='json')
@app.output(Items(many=True), status_code=201)
@app.doc(responses=[201, 400])
def create_items(data):
    """
    Create multiple items
    :param data: JSON representation of the items to be created
    :return: JSON representation of the items along with the status code
    """
    try:
        items = [Items().load(item) for item in data]
        mongo.db.items.insert_many(items)
        return items, 201
    except Exception as e:
        abort(400, str(e.with_traceback(None)))


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
