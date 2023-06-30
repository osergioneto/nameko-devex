import pytest

from mock import call
from nameko.exceptions import RemoteError

from orders.models import Order, OrderDetail
from orders.schemas import OrderSchema, OrderDetailSchema


@pytest.fixture
def order(db_session):
    order = Order()
    db_session.add(order)
    db_session.commit()
    return order


@pytest.fixture
def order_details(db_session, order):
    order_details = [
        OrderDetail(order=order, product_id="satoro_goju", price=100, quantity=1),
        OrderDetail(order=order, product_id="ryomen_sukuna", price=66.60, quantity=3)
    ]
    db_session.add_all(order_details)
    db_session.commit()
    return order_details


def test_list_orders_default_options(orders_rpc, order, order_details):
    response = orders_rpc.list_orders()

    assert len(response) == 1
    assert order.id == response[0]['id']

    assert len(response[0]['order_details']) == 2
    assert response[0]['order_details'][0]['id'] == order_details[0].id
    assert response[0]['order_details'][1]['id'] == order_details[1].id
    assert response[0]['order_details'][0]['product_id'] == order_details[0].product_id
    assert response[0]['order_details'][1]['product_id'] == order_details[1].product_id


def test_list_orders_with_custom_options_without_data(orders_rpc, order):
    response = orders_rpc.list_orders(3, 5)
    assert len(response) == 0

def test_count_orders(orders_rpc, order):
    response = orders_rpc.count_orders()
    assert response == 1

def test_count_orders_with_extra_data(db_session, orders_rpc, order):
    orders = [Order() for _ in range(5)]
    db_session.add_all(orders)
    db_session.commit()

    response = orders_rpc.count_orders()
    assert response == 6

def test_list_orders_with_custom_options_with_data(db_session, orders_rpc, order):
    orders = [Order() for _ in range(5)]
    db_session.add_all(orders)
    db_session.commit()

    response = orders_rpc.list_orders(5, 5)
    assert len(response) == 1


def test_get_order(orders_rpc, order):
    response = orders_rpc.get_order(1)
    assert response['id'] == order.id


@pytest.mark.usefixtures('db_session')
def test_will_raise_when_order_not_found(orders_rpc):
    with pytest.raises(RemoteError) as err:
        orders_rpc.get_order(1)
    assert err.value.value == 'Order with id 1 not found'


@pytest.mark.usefixtures('db_session')
def test_can_create_order(orders_service, orders_rpc):
    order_details = [
        {
            'product_id': "the_odyssey",
            'price': 99.99,
            'quantity': 1
        },
        {
            'product_id': "the_enigma",
            'price': 5.99,
            'quantity': 8
        }
    ]
    new_order = orders_rpc.create_order(
        OrderDetailSchema(many=True).dump(order_details).data
    )
    assert new_order['id'] > 0
    assert len(new_order['order_details']) == len(order_details)
    assert [call(
        'order_created', {'order': {
            'id': 1,
            'order_details': [
                {
                    'price': '99.99',
                    'product_id': "the_odyssey",
                    'id': 1,
                    'quantity': 1
                },
                {
                    'price': '5.99',
                    'product_id': "the_enigma",
                    'id': 2,
                    'quantity': 8
                }
            ]}}
    )] == orders_service.event_dispatcher.call_args_list


@pytest.mark.usefixtures('db_session', 'order_details')
def test_can_update_order(orders_rpc, order):
    order_payload = OrderSchema().dump(order).data
    for order_detail in order_payload['order_details']:
        order_detail['quantity'] += 1

    updated_order = orders_rpc.update_order(order_payload)

    assert updated_order['order_details'] == order_payload['order_details']


def test_can_delete_order(orders_rpc, order, db_session):
    orders_rpc.delete_order(order.id)
    assert not db_session.query(Order).filter_by(id=order.id).count()

