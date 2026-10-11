# Import FastAPI to create APIs and HTTPException to return HTTP errors.
from fastapi import FastAPI, HTTPException

# BaseModel validates incoming request data; Field adds validation rules.
from pydantic import BaseModel, Field

# HTTPX lets the Order Service communicate with the Inventory Service.
import httpx

# Create the FastAPI application.
app = FastAPI(title="Order Service")

# URL of the Inventory Service running on port 8000.
INVENTORY_URL = "http://127.0.0.1:8000"

# Demo storage: orders are kept in RAM and disappear when the service restarts.
orders = {}

# The first order will receive ID 1.
next_order_id = 1


# Define the expected data when a client creates an order.
class OrderCreate(BaseModel):
    # Product ID must be greater than zero.
    product_id: int = Field(gt=0)

    # Requested quantity must be greater than zero.
    quantity: int = Field(gt=0)


# Health-check endpoint to verify that the Order Service is running.
@app.get("/")
def home():
    return {"message": "Order Service Running"}


# Create a new order. Return HTTP 201 when successful.
@app.post("/orders", status_code=201)
def create_order(order: OrderCreate):
    # Allow this function to read and update the global order ID counter.
    global next_order_id

    # Call the Inventory Service to retrieve product details.
    try:
        response = httpx.get(
            f"{INVENTORY_URL}/products/{order.product_id}",
            timeout=5.0  # Stop waiting after five seconds.
        )

    # Handle connection failures and timeouts.
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Inventory Service is unavailable"
        )

    # If Inventory Service says the product does not exist, return 404.
    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Product not found in Inventory"
        )

    # Handle other unexpected responses from Inventory Service.
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Inventory Service returned an error"
        )

    # Convert the Inventory Service JSON response into a Python dictionary.
    # The inventory API returns product data inside the "product" field.
    product = response.json()["product"]

    # Check whether enough stock is available for the requested order.
    if product["quantity"] < order.quantity:
        raise HTTPException(
            status_code=409,
            detail="Insufficient stock"
        )

    # Prepare the order details.
    order_data = {
        "order_id": next_order_id,       # Assign the current order ID.
        "product_id": order.product_id,  # Store the requested product ID.
        "quantity": order.quantity,      # Store the requested quantity.
        "status": "confirmed"            # Mark the order as confirmed.
    }

    # Save the order in the in-memory dictionary using its ID as the key.
    orders[next_order_id] = order_data

    # Increment the counter so the next order gets a new ID.
    next_order_id += 1

    # Return the created order to the client.
    return order_data


# Retrieve an existing order using its ID.
@app.get("/orders/{order_id}")
def get_order(order_id: int):
    # Look up the order in the dictionary; return None if it doesn't exist.
    order = orders.get(order_id)

    # Return 404 when the requested order ID is not found.
    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # Return the order details as JSON.
    return order