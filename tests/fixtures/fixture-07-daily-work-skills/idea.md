# Fixture 07: Daily-work skills shared regression fixture

Covers `/bugfix`, `/refactor`, `/perf`, `/security-audit`, `/migrate` — the five skills from the "daily work" and "quality assurance" tiers that do not need a full-project fixture like `/kickstart` does. Each skill operates on an existing file/area and is verified by the scenarios listed in `notes.md`.

## Shared test project

A minimal FastAPI + SQLAlchemy + PostgreSQL snippet intentionally wired with problems that each skill should catch:

### `app/api/users.py` (intentionally buggy)

```python
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db import db

router = APIRouter()

# Hardcoded admin token — /security-audit should flag (SECRET-1)
ADMIN_TOKEN = "sk-live-hardcoded-do-not-ship-abc123"

# N+1 query — /perf should flag
@router.get("/users/{user_id}/orders")
async def get_user_orders(user_id: int):
    user = await db.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))  # SQL injection — /security-audit
    orders = []
    for o in user.orders:          # N+1: separate query per order
        item = await db.execute(text(f"SELECT * FROM items WHERE id = {o.item_id}"))
        orders.append(item)
    return orders

# Long, tangled function — /refactor should flag
def process_checkout(cart, user, coupon, shipping, payment, retry_count, logger):
    if len(cart) == 0: return None
    total = 0
    for item in cart:
        if item.discount: total += item.price * (1 - item.discount / 100)
        else: total += item.price
    if coupon:
        if coupon.type == "percent": total *= (1 - coupon.value / 100)
        elif coupon.type == "fixed": total -= coupon.value
        elif coupon.type == "freeship": shipping.cost = 0
    if total < 0: total = 0
    if user.is_premium: total *= 0.9
    if shipping.express: total += 15
    else: total += 5
    # ... 50 more lines of this
    return total
```

### Migration fixture for `/migrate`

`migrations/20260408_add_users_email_index.sql`:
```sql
-- Wrong: will lock the table on prod
CREATE INDEX idx_users_email ON users(email);
```

`/migrate` should detect the missing `CONCURRENTLY` and refuse on prod.

## Expected results per skill

See `notes.md` for the binary verification checklist per skill.
