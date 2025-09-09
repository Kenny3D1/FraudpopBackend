from fastapi import FastAPI
from .routes.vault import router as vault_router
from .routes.capture import router as capture_router
from .routes.webhooks import router as webhooks_router

app = FastAPI(title="FraudPop Backend + Defender3D Risk Vault")

app.include_router(vault_router, prefix="/proxy")
app.include_router(capture_router, prefix="/proxy")
app.include_router(webhooks_router, prefix="/proxy")

@app.get("/health")
def health():
    return {"ok": True}
