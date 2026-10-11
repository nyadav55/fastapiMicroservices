
from fastapi import FastAPI
from redis import Redis

app = FastAPI()

redis_client = Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

@app.post("/cache/{key}/{value}")
def set_cache(key: str, value: str):
    redis_client.set(key, value)
    return {"message": "Data saved in Redis", "key": key, "value": value}

@app.get("/cache/{key}")
def get_cache(key: str):
    value = redis_client.get(key)
    return {"key": key, "value": value}
