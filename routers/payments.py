import hmac
import hashlib
import json
import httpx
from fastapi import APIRouter, HTTPException, Request, Header
from models import PaystackInitRequest
from config import PAYSTACK_SECRET_KEY, PAYSTACK_CALLBACK_URL, PLANS
import store

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/initialize")
async def initialize_payment(req: PaystackInitRequest):
    plan = PLANS.get(req.plan)
    if not plan:
        raise HTTPException(400, "Invalid plan")

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.paystack.co/transaction/initialize",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
            json={
                "email": req.email,
                "amount": plan["amount"],
                "metadata": {"plan": req.plan, "credits": plan["credits"]},
                "callback_url": PAYSTACK_CALLBACK_URL,
            },
        )
    data = res.json()
    if not data.get("status"):
        raise HTTPException(400, data.get("message", "Paystack error"))
    return {
        "authorization_url": data["data"]["authorization_url"],
        "reference": data["data"]["reference"],
    }


@router.post("/webhook")
async def paystack_webhook(request: Request, x_paystack_signature: str = Header(None)):
    body = await request.body()
    expected = hmac.new(
        key=PAYSTACK_SECRET_KEY.encode(),
        msg=body,
        digestmod=hashlib.sha512,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_paystack_signature or ""):
        raise HTTPException(400, "Invalid signature")

    event = json.loads(body)
    if event.get("event") == "charge.success":
        data   = event["data"]
        email  = data["customer"]["email"]
        credits = int(data["metadata"]["credits"])
        store.add_credits(email, credits)

    return {"status": "ok"}


@router.get("/verify/{reference}")
async def verify_payment(reference: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
        )
    data = res.json()
    if data.get("data", {}).get("status") == "success":
        meta    = data["data"]["metadata"]
        email   = data["data"]["customer"]["email"]
        credits = int(meta["credits"])
        total   = store.add_credits(email, credits)
        return {"success": True, "credits": total}
    return {"success": False}