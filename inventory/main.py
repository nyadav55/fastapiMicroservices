
# FastAPI: Create REST APIs
# Depends: Inject database session into API functions
# HTTPException: Return errors like 404 Not Found
from fastapi import FastAPI, Depends, HTTPException

# SQLAlchemy: Connect Python code to PostgreSQL
from sqlalchemy import create_engine, String

# Tools to define database models and manage sessions
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column,
    sessionmaker, Session
)

# Pydantic: Validate incoming and outgoing data
from pydantic import BaseModel, ConfigDict

# Redis: Store frequently accessed data in cache
from redis import Redis

# Convert Python dictionaries to/from JSON
import json


# Create the FastAPI application
app = FastAPI()


# ---------------- POSTGRESQL CONNECTION ----------------

# Connection URL: database type, username, password,
# host, port and database name
DATABASE_URL = (
    "postgresql+psycopg://inventory:devpass"
    "@localhost:5432/inventory_db"
)

# Create the database engine (manages DB connectivity)
engine = create_engine(DATABASE_URL)

# Create a factory for database sessions
SessionLocal = sessionmaker(bind=engine)


# Base class for all SQLAlchemy database models
class Base(DeclarativeBase):
    pass


# Define the products table in PostgreSQL
class Product(Base):
    __tablename__ = "products"

    # Auto-generated primary key for each product
    id: Mapped[int] = mapped_column(primary_key=True)

    # Product name, maximum 100 characters
    name: Mapped[str] = mapped_column(String(100))

    # Available stock quantity
    quantity: Mapped[int]


# Create the products table if it does not exist
Base.metadata.create_all(bind=engine)


# ---------------- REDIS CONNECTION ----------------

# Connect to Redis running on localhost, port 6379
# decode_responses=True makes Redis return strings
redis_client = Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


# ---------------- REQUEST / RESPONSE SCHEMAS ----------------

# Validates the data sent when creating a product
class ProductCreate(BaseModel):
    name: str
    quantity: int


# Defines the structure of a product response
class ProductResponse(BaseModel):
    id: int
    name: str
    quantity: int

    # Allows Pydantic to read values from SQLAlchemy objects
    model_config = ConfigDict(from_attributes=True)


# ---------------- DATABASE SESSION MANAGEMENT ----------------

# FastAPI calls this function to get a DB session
def get_db():
    db = SessionLocal()

    try:
        # Provide the session to the API endpoint
        yield db
    finally:
        # Always close the session after the request
        db.close()


# ---------------- CREATE PRODUCT API ----------------

# POST /products
# Example body: {"name": "Laptop", "quantity": 10}
@app.post("/products", response_model=ProductResponse)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db)
):
    # Convert validated request data into a DB model
    db_product = Product(
        name=product.name,
        quantity=product.quantity
    )

    # Stage the new product for insertion
    db.add(db_product)

    # Save the product permanently in PostgreSQL
    db.commit()

    # Fetch generated fields, such as the product ID
    db.refresh(db_product)

    # Return the created product
    return db_product


# ---------------- GET PRODUCT API ----------------

# GET /products/1
@app.get("/products/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    # Use a unique Redis key for this product
    cache_key = f"product:{product_id}"

    # First, check Redis for cached product data
    cached = redis_client.get(cache_key)

    # If found, return the cached data without querying DB
    if cached:
        return {
            "source": "Redis cache",
            "product": json.loads(cached)
        }

    # Cache miss: fetch the product from PostgreSQL
    product = db.get(Product, product_id)

    # If the product does not exist, return HTTP 404
    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    # Convert the database object into a dictionary
    data = {
        "id": product.id,
        "name": product.name,
        "quantity": product.quantity
    }

    # Save the product in Redis for 60 seconds
    # json.dumps converts the dictionary into a JSON string
    redis_client.set(
        cache_key,
        json.dumps(data),
        ex=60
    )

    # Return the data retrieved from PostgreSQL
    return {
        "source": "PostgreSQL database",
        "product": data
    }

