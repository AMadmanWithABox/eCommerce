import json
import uuid
import jwt
from datetime import datetime, timedelta
from apiflask import APIFlask, Schema, HTTPTokenAuth
from apiflask.fields import String, URL, UUID, Float, Email, DateTime, Boolean, List
from flask_cors import CORS
from flask import request, jsonify, make_response, g
from werkzeug.security import generate_password_hash, check_password_hash
import couchdb
from couchdb import json as couchdb_json
from marshmallow import ValidationError


app = APIFlask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')
CORS(app)
app.security_schemes = {
    'Bearer': {
        'type': 'http',
        'scheme': 'bearer',
    }
}
app.config['SECRET_KEY'] = 'thisissecret'

basket_service_url = 'http://localhost:5001/api/v1/basket/'

couch_server = couchdb.Server('http://admin:password@couchdb:5984/')
db_name = 'orderservice'
if db_name not in couch_server:
    orderservice_db = couch_server.create(db_name)
else:
    orderservice_db = couch_server[db_name]


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


couchdb_json.encode = CustomJSONEncoder().encode


payment_method_design_doc = {
    "_id": "_design/payment_method",
    "views": {
        "payment_method_by_uuid": {
            "map": "function(doc) { if (doc.type === 'payment_method') { emit(doc.payment_uuid, doc); } }"
        },
        "payment_methods_by_user_uuid": {
            "map": "function(doc) { if (doc.type === 'payment_method') { emit(doc.user_uuid, doc); } }"
        }
    },
    "language": "javascript"
}


if '_design/payment_method' not in orderservice_db:
    orderservice_db.save(payment_method_design_doc)


user_design_doc = {
    "_id": "_design/user",
    "views": {
        "user_by_email": {
            "map": "function(doc) { if (doc.type === 'user') { emit(doc.email, doc); } }"
        },
        "user_by_uuid": {
            "map": "function(doc) { if (doc.type === 'user') { emit(doc.user_uuid, doc); } }"
        }
    },
    "language": "javascript"
}

# Save the design document to the database
if '_design/user' not in orderservice_db:
    orderservice_db.save(user_design_doc)


class User(Schema):
    _id = String(data_key='_id', required=False, allow_none=True)
    _rev = String(data_key='_rev', required=False, allow_none=True)
    type = String(required=False, allow_none=True)
    user_uuid = UUID(missing=lambda: str(uuid.uuid4()))
    first_name = String(required=True)
    last_name = String(required=True)
    payment_methods = List(URL())
    basket = URL()
    email = Email(required=True)
    password = String(required=True)
    shipping_address = String(required=True)


class UserIn(Schema):
    first_name = String(required=True)
    last_name = String(required=True)
    email = Email(required=True)
    password = String(required=True)
    shipping_address = String(required=True)


class UserUpdateIn(Schema):
    first_name = String(required=True)
    last_name = String(required=True)
    email = Email(required=True)
    password = String(required=True)
    new_password = String(required=False)
    shipping_address = String(required=True)


class UserOut(Schema):
    user_uuid = UUID()
    first_name = String()
    last_name = String()
    email = Email()
    shipping_address = String()


class LogIn(Schema):
    email = Email(required=True)
    password = String(required=True)


class PaymentMethod(Schema):
    payment_uuid = UUID(missing=lambda: str(uuid.uuid4()))
    name_on_card = String(required=True)
    card_number = String(required=True)
    expiry_date = DateTime(required=True)
    security_code = String(required=True)
    billing_address_zip = String(required=True)
    user = URL()


class CreditCardNumber(String):
    @staticmethod
    def __validate_luhn(value):
        """
        Validate a credit card number using the Luhn algorithm
        :param value: The card number
        :return: True if the card number is valid, False otherwise
        """

        def digits_of(n):
            return [int(digit) for digit in str(n)]

        digits = digits_of(value)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = 0
        checksum += sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10 == 0

    def _validate(self, value):
        """
        Validate the credit card number. Throws a ValidationError if the card number is invalid
        :param value: The card number
        :return:
        """
        if not value.isdigit():
            raise ValidationError('Card number must be numeric')
        if len(value) != 16:
            raise ValidationError('Card number must be 16 digits long')
        if not self.__validate_luhn(value):
            raise ValidationError('Card number is invalid')


class PaymentMethodIn(Schema):
    name_on_card = String(required=True)
    card_number = CreditCardNumber(required=True)
    expiry_date = DateTime(required=True)
    security_code = String(required=True)
    billing_address_zip = String(required=True)


class Order(Schema):
    order_uuid = UUID(missing=lambda: str(uuid.uuid4()))
    items = URL(many=True)
    total_cost = Float()
    is_paid = Boolean()
    user = URL()


def generate_auth_token(user_id, secret_key):
    """
    Generate an auth token
    :param user_id: the id of the user to generate the token for
    :param secret_key: the secret key to use to generate the token
    :return: the generated token
    """
    payload = {
        'user_uuid': str(user_id),
        'exp': datetime.utcnow() + timedelta(days=1),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, secret_key, algorithm='HS256')


def get_user_by_email(email):
    """
    Get a user by their email
    :param email: The user's email
    :return: The user
    """
    for user in orderservice_db.view('_design/user/_view/user_by_email', key=email):
        return User().load(user.value)


def get_user_by_uuid(user_uuid):
    """
    Get a user by their uuid
    :param user_uuid: the user's uuid
    :return: the user
    """
    for user in orderservice_db.view('_design/user/_view/user_by_uuid', key=user_uuid):
        return User().load(user.value)


def get_payment_method(payment_uuid):
    """
    Get a payment method by its uuid
    :param payment_uuid: the payment method's uuid
    :return: the payment method
    """

    user = auth.current_user
    if user:
        for payment_method in orderservice_db.view('_design/payment_method/_view/payment_method_by_uuid', key=str(payment_uuid)):
            return PaymentMethod().load(payment_method.value)
        return jsonify({'error': 'Payment method not found'}), 404
    return jsonify({'error': 'Invalid Token'}), 404


@auth.verify_token
def verify_token(token):
    """
    Verify a token
    :param token: the token to verify
    :return: True if the token is valid, False otherwise
    """
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_uuid']
        user = get_user_by_uuid(user_id)
        return user
    except:
        return None


# User CRUD endpoints
@app.post('/api/v1/users/login')
@app.input(LogIn)
@app.doc(responses=[200, 401])
def login(data):
    """
    Provide a JWT token for a user
    :param data: the user's email and password
    :return: a JWT token for the user to use for future requests
    """
    email = data.get('email')
    password = data.get('password')
    user = get_user_by_email(email)
    if not user or not check_password_hash(user['password'], password):
        return make_response(jsonify({'error': 'Invalid email or password'}), 401)
    token = generate_auth_token(user['user_uuid'], app.config['SECRET_KEY'])
    return jsonify({'token': token})


@app.post('/api/v1/users/')
@app.input(UserIn)
@app.output(UserOut)
@app.doc(responses=[201])
def create_user(data):
    """
    Create a new user
    :param data: The user data
    :return: The created user
    """
    data['password'] = generate_password_hash(data['password'])
    user = User().load(data)
    user['type'] = 'user'
    orderservice_db.save(user)
    return user, 201


@app.get('/api/v1/users/')
@app.output(UserOut)
@app.doc(responses=[200, 404], security='Bearer')
@auth.login_required
def get_user():
    """
    Get the logged-in user's information by the JWT token
    :return: The user's information
    """
    user = auth.current_user
    if user:
        return user, 200
    return jsonify({'error': 'User not found'}), 404


@app.put('/api/v1/users/')
@app.input(UserUpdateIn)
@app.output(UserOut)
@app.doc(responses=[200, 400], security='Bearer')
@auth.login_required
def update_user(data):
    """
    Update the logged-in user's information by the JWT token
    :param data: The user data to update
    :return: The updated user
    """
    user = auth.current_user
    if user:
        user.update(data)
        orderservice_db.save(user)
        return user, 200
    return jsonify({'error': 'Invalid Token'}), 400


@app.delete('/api/v1/users/')
@app.doc(responses=[204, 404], security='Bearer')
@auth.login_required
def delete_user():
    """
    Delete the logged-in user's information by the JWT token
    :return: None
    """
    user = auth.current_user
    if user:
        orderservice_db.delete(user)
        return '', 204
    return jsonify({'error': 'Invalid Token'}), 404


# PaymentMethod CRUD endpoints
@app.post('/api/v1/payment_methods/<user_uuid>/')
@app.input(PaymentMethodIn)
@app.output(PaymentMethod)
@app.doc(responses=[201, 404], security='Bearer')
@auth.login_required
def create_payment_method(data):
    """
    Create a new payment method for a user
    :param data: The payment method data
    :return: The created payment method
    """

    user = auth.current_user
    if user:
        payment_method = PaymentMethod().load(data)
        payment_method['type'] = 'payment_method'
        payment_method['user_uuid'] = user['user_uuid']
        orderservice_db.save(payment_method)
        user['payment_methods'].append(str(payment_method['payment_uuid']))
        return payment_method, 201
    return jsonify({'error': 'Invalid Token'}), 404


@app.get('/api/v1/payment_methods/<payment_uuid>')
@app.output(PaymentMethod)
@app.doc(responses=[200, 404], security='Bearer')
@auth.login_required
def get_payment_method(payment_uuid):
    """
    Get a payment method by its uuid
    :param payment_uuid: the payment method's uuid
    :return: the payment method
    """

    user = auth.current_user
    if user:
        for payment_method in orderservice_db.view('_design/payment_method/_view/payment_method_by_uuid', key=payment_uuid):
            return PaymentMethod().load(payment_method.value), 200
        return jsonify({'error': 'Payment method not found'}), 404
    return jsonify({'error': 'Invalid Token'}), 404


@app.put('/api/v1/payment_methods/<payment_uuid>')
def update_payment_method(payment_uuid):
    pass


@app.delete('/api/v1/payment_methods/<payment_uuid>')
def delete_payment_method(payment_uuid):
    pass


# Order CRUD endpoints
@app.post('/api/v1/orders')
def create_order():
    pass


@app.get('/api/v1/orders/<order_uuid>')
def get_order(order_uuid):
    pass


@app.put('/api/v1/orders/<order_uuid>')
def update_order(order_uuid):
    pass


@app.delete('/api/v1/orders/<order_uuid>')
def delete_order(order_uuid):
    pass


if __name__ == '__main__':
    app.run(debug=True, port=5002, host='0.0.0.0')
