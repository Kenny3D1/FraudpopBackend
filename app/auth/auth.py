# app/auth.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .shopify_oauth import _nonce, _sign_ok, build_install_url, exchange_token
from ..models import Shop

router = APIRouter(prefix="/auth", tags=["auth"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.get("")
def start_auth(shop: str, db: Session = Depends(get_db)):
    """
    Entry: /auth?shop=mystore.myshopify.com
    Creates a CSRF state (nonce) in a short-lived cookie and redirects to Shopify.
    """
    state = _nonce()
    url = build_install_url(shop, state)
    resp = RedirectResponse(url)
    # set HttpOnly cookie for state (you can use server-side store/redis if preferred)
    resp.set_cookie("shopify_state", state, httponly=True, samesite="lax", max_age=600)
    return resp

@router.get("/callback")
def oauth_callback(request: Request, db: Session = Depends(get_db)):
    q = dict(request.query_params)
    shop = q.get("shop")
    code = q.get("code")
    state = q.get("state")
    cookie_state = request.cookies.get("shopify_state")

    if not shop or not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth params")

    if cookie_state != state:
        raise HTTPException(status_code=400, detail="State mismatch")

    if not _sign_ok(q):
        raise HTTPException(status_code=400, detail="Invalid HMAC")

    token_resp = exchange_token(shop, code)
    access_token = token_resp.get("access_token")
    scopes = token_resp.get("scope", "")

    if not access_token:
        raise HTTPException(status_code=400, detail="No access token returned")

    # upsert shop
    existing = db.query(Shop).filter(Shop.shop_domain == shop).one_or_none()
    if existing:
        existing.access_token = access_token
        existing.scopes = scopes
    else:
        db.add(Shop(shop_domain=shop, access_token=access_token, scopes=scopes))
    db.commit()

    # OPTIONAL: ensure_metafield_definitions(shop, access_token)

    # Redirect to your embedded admin (or a success page)
    return RedirectResponse(url=f"/app?shop={shop}")
