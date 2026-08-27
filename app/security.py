from fastapi import Header, HTTPException, status

from app.config import get_webhook_secret


async def verify_webhook_secret(
    x_webhook_secret: str = Header(default=None, alias="X-Webhook-Secret")
) -> None:
    expected = get_webhook_secret()
    if not expected:
        # No secret configured: authentication is disabled (not recommended
        # for production, but convenient for local testing).
        return
    if x_webhook_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook secret",
        )
