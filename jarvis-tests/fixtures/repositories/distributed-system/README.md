# Distributed System Fixture

A distributed system with three services in two languages, a message queue, and a database.

## Architecture

- **Service A** (Python): Order processing service
- **Service B** (Node.js): Payment processing service
- **Service C** (Python): Notification service
- **Message Queue**: RabbitMQ (simulated)
- **Database**: PostgreSQL (simulated with SQLite)

## Request Lifecycle

The system processes a single endpoint: `POST /orders`

1. Service A receives order request
2. Validates order and publishes to message queue
3. Service B processes payment via message queue
4. Service B publishes payment result to queue
5. Service A updates order status
6. Service C sends notification on completion

## Files

- `service_a/` - Order processing (Python)
- `service_b/` - Payment processing (Node.js)
- `service_c/` - Notification service (Python)
- `shared/` - Shared types and utilities
- `queue/` - Message queue simulation
- `database/` - Database schema and migrations
