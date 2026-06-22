from fastapi import FastAPI

app = FastAPI(title="idea-to-deploy API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

