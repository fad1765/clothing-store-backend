from fastapi import FastAPI

app = FastAPI(title="MY BACKEND TEST APP")

@app.get("/")
def root():
    return {"message": "railway ok"}