from fastapi import FastAPI

app = FastAPI(title="FastAPI DDD Clean Architecture")


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
