"""
Service A: Order Processing Service
Receives order requests, validates them, and coordinates payment processing.
"""

from typing import Dict, Any
from datetime import datetime
import json


class OrderProcessor:
    """Processes incoming orders"""

    def __init__(self, queue_client, db_client):
        self.queue_client = queue_client
        self.db_client = db_client

    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new order"""
        # Validate order
        if not self._validate_order(order_data):
            return {
                'status': 'error',
                'message': 'Invalid order data'
            }

        # Generate order ID
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Save to database
        order_record = {
            'order_id': order_id,
            'customer_id': order_data['customer_id'],
            'items': order_data['items'],
            'total': self._calculate_total(order_data['items']),
            'status': 'pending_payment',
            'created_at': datetime.now().isoformat()
        }
        self.db_client.insert('orders', order_record)

        # Publish to payment queue
        payment_message = {
            'order_id': order_id,
            'amount': order_record['total'],
            'customer_id': order_data['customer_id']
        }
        self.queue_client.publish('payment_queue', payment_message)

        return {
            'status': 'success',
            'order_id': order_id,
            'message': 'Order created and payment queued'
        }

    def _validate_order(self, order_data: Dict[str, Any]) -> bool:
        """Validate order data"""
        required_fields = ['customer_id', 'items']
        if not all(field in order_data for field in required_fields):
            return False

        if not isinstance(order_data['items'], list) or len(order_data['items']) == 0:
            return False

        for item in order_data['items']:
            if not all(key in item for key in ['product_id', 'quantity', 'price']):
                return False

        return True

    def _calculate_total(self, items: list) -> float:
        """Calculate order total"""
        return sum(item['quantity'] * item['price'] for item in items)

    def update_order_status(self, order_id: str, status: str) -> Dict[str, Any]:
        """Update order status after payment processing"""
        self.db_client.update('orders', order_id, {'status': status})

        # If payment successful, trigger notification
        if status == 'paid':
            order = self.db_client.get('orders', order_id)
            notification_message = {
                'order_id': order_id,
                'customer_id': order['customer_id'],
                'total': order['total']
            }
            self.queue_client.publish('notification_queue', notification_message)

        return {
            'status': 'success',
            'message': f'Order {order_id} updated to {status}'
        }


if __name__ == '__main__':
    # Simple test
    from queue_client import QueueClient
    from db_client import DatabaseClient

    queue = QueueClient()
    db = DatabaseClient()
    processor = OrderProcessor(queue, db)

    order = {
        'customer_id': 'CUST-001',
        'items': [
            {'product_id': 'PROD-001', 'quantity': 2, 'price': 10.0},
            {'product_id': 'PROD-002', 'quantity': 1, 'price': 25.0}
        ]
    }

    result = processor.create_order(order)
    print(json.dumps(result, indent=2))
