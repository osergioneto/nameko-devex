import json

from marshmallow import ValidationError
from nameko import config
from nameko.exceptions import BadRequest
from nameko.rpc import RpcProxy
from werkzeug import Response

from gateway.entrypoints import http
from gateway.exceptions import OrderNotFound, ProductNotFound
from gateway.schemas import CreateOrderSchema, GetOrderSchema, ProductSchema

class GatewayService(object):
    """
    Service acts as a gateway to other services over http.
    """

    name = 'gateway'

    orders_rpc = RpcProxy('orders')
    products_rpc = RpcProxy('products')

    @http(
        "GET", "/products/<string:product_id>",
        expected_exceptions=ProductNotFound
    )
    def get_product(self, request, product_id):
        """Gets product by `product_id`
        """
        product = self.products_rpc.get(product_id)
        return Response(
            ProductSchema().dumps(product).data,
            mimetype='application/json'
        )

    @http(
        "POST", "/products",
        expected_exceptions=(ValidationError, BadRequest)
    )
    def create_product(self, request):
        """Create a new product - product data is posted as json

        Example request ::

            {
                "id": "the_odyssey",
                "title": "The Odyssey",
                "passenger_capacity": 101,
                "maximum_speed": 5,
                "in_stock": 10
            }


        The response contains the new product ID in a json document ::

            {"id": "the_odyssey"}

        """

        schema = ProductSchema(strict=True)

        try:
            # load input data through a schema (for validation)
            # Note - this may raise `ValueError` for invalid json,
            # or `ValidationError` if data is invalid.
            product_data = schema.loads(request.get_data(as_text=True)).data
        except ValueError as exc:
            raise BadRequest("Invalid json: {}".format(exc))

        # Create the product
        self.products_rpc.create(product_data)
        return Response(
            json.dumps({'id': product_data['id']}), mimetype='application/json'
        )
    
    @http("DELETE", "/products/<string:product_id>")
    def delete_product(self, request, product_id):
        deleted = self.products_rpc.delete(product_id)

        if not deleted:
            return Response(status=404)

        return Response(status=204)
    
    @http("GET", "/orders/<int:order_id>", expected_exceptions=OrderNotFound)
    def get_order(self, request, order_id):
        """Gets the order details for the order given by `order_id`.

        Enhances the order details with full product details from the
        products-service.
        """
        order = self._get_order(order_id)
        return Response(
            GetOrderSchema().dumps(order).data,
            mimetype='application/json'
        )

    def _get_order(self, order_id):
        # Retrieve order data from the orders service.
        # Note - this may raise a remote exception that has been mapped to
        # raise``OrderNotFound``
        order = self.orders_rpc.get_order(order_id)

        # get the configured image root
        image_root = config['PRODUCT_IMAGE_ROOT']

        # Enhance order details with product and image details.
        for item in order['order_details']:
            product_id = item['product_id']
            item['product'] = self.products_rpc.get(product_id)
            # Construct an image url.
            item['image'] = '{}/{}.jpg'.format(image_root, product_id)

        return order
    
    
    @http("GET", "/orders")
    def list_orders(self, request):
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        orders = self._list_orders(page, limit)
        return Response(json.dumps(orders), mimetype='application/json')

    
    def _list_orders(self, page, limit):
        skip = (page - 1) * limit
        orders = self.fetch_orders(skip, limit)
        total_orders = self.calculate_total_orders()
        total_pages = self.calculate_total_pages(total_orders, limit)

        response = {
            'total_orders': total_orders,
            'total_pages': total_pages,
            'page': page,
            'orders': orders
        }

        return response
    
    def fetch_orders(self, skip, limit):
        orders = self.orders_rpc.list_orders(skip, limit)
        product_ids = set()
        for order in orders:
            for item in order['order_details']:
                product_ids.add(item['product_id'])

        products = self.products_rpc.list(list(product_ids))

        for order in orders:
            for item in order['order_details']:
                product_id = item['product_id']
                item['product'] = self.products_rpc.get(product_id)
                item['image'] = 'https://picsum.photos/300'

        return orders
    
    def calculate_total_orders(self):
        return self.orders_rpc.count_orders()

    def calculate_total_pages(self, total_orders, limit):
        return (total_orders + limit - 1) // limit
    
    
    @http(
        "POST", "/orders",
        expected_exceptions=(ValidationError, ProductNotFound, BadRequest)
    )
    def create_order(self, request):
        """Create a new order - order data is posted as json

        Example request ::

            {
                "order_details": [
                    {
                        "product_id": "the_odyssey",
                        "price": "99.99",
                        "quantity": 1
                    },
                    {
                        "price": "5.99",
                        "product_id": "the_enigma",
                        "quantity": 2
                    },
                ]
            }


        The response contains the new order ID in a json document ::

            {"id": 1234}

        """

        schema = CreateOrderSchema(strict=True)

        try:
            # load input data through a schema (for validation)
            # Note - this may raise `ValueError` for invalid json,
            # or `ValidationError` if data is invalid.
            order_data = schema.loads(request.get_data(as_text=True)).data
        except ValueError as exc:
            raise BadRequest("Invalid json: {}".format(exc))

        # Create the order
        # Note - this may raise `ProductNotFound`
        id_ = self._create_order(order_data)
        return Response(json.dumps({'id': id_}), mimetype='application/json')

    def _create_order(self, order_data):
        product_ids = [item['product_id'] for item in order_data['order_details']]
        valid_product_ids = [prod['id']for prod in self.products_rpc.list(product_ids)]

        for item in order_data['order_details']:
            if item['product_id'] not in valid_product_ids:
                raise ProductNotFound(
                    "Product Id {}".format(item['product_id'])
                )

        # Call orders-service to create the order.
        # Dump the data through the schema to ensure the values are serialized
        # correctly.
        serialized_data = CreateOrderSchema().dump(order_data).data
        result = self.orders_rpc.create_order(
            serialized_data['order_details']
        )
        return result['id']
