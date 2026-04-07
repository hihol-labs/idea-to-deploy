# Refactoring Catalog

> Reference for `/refactor` skill. Inspired by Martin Fowler's *Refactoring*. Each entry: when to apply, before/after, common pitfalls. The skill picks the appropriate technique based on the code smell observed.

## Index

| Smell | Refactoring |
|---|---|
| Long function | [Extract Function](#extract-function) |
| Deep nesting | [Replace Nested Conditional with Guard Clauses](#replace-nested-conditional-with-guard-clauses) |
| Duplicate code in 2+ places | [Extract Function](#extract-function) + [Pull Up Method](#pull-up-method) |
| Magic numbers | [Replace Magic Number with Symbolic Constant](#replace-magic-number-with-symbolic-constant) |
| Long parameter list | [Introduce Parameter Object](#introduce-parameter-object) |
| Large class doing too much | [Extract Class](#extract-class) |
| Switch on type | [Replace Conditional with Polymorphism](#replace-conditional-with-polymorphism) |
| Repeated null checks | [Introduce Null Object](#introduce-null-object) |
| Stale comments | [Extract Function with descriptive name](#extract-function) |
| Boolean parameter that flips behavior | [Split Function](#split-function) |
| Mutable state passed around | [Replace Method with Method Object](#replace-method-with-method-object) |
| Output parameter (mutates input) | [Replace with Return Value](#replace-with-return-value) |

---

## Extract Function

**When:** A function exceeds ~30 lines, OR a code block needs a comment to explain what it does.

**Before**
```python
def print_invoice(order):
    print(f"Order: {order.id}")
    print(f"Customer: {order.customer.name}")
    # Calculate tax
    subtotal = sum(item.price * item.qty for item in order.items)
    tax_rate = 0.08 if order.customer.state == "CA" else 0.05
    tax = subtotal * tax_rate
    total = subtotal + tax
    print(f"Subtotal: ${subtotal:.2f}")
    print(f"Tax: ${tax:.2f}")
    print(f"Total: ${total:.2f}")
```

**After**
```python
def print_invoice(order):
    print(f"Order: {order.id}")
    print(f"Customer: {order.customer.name}")
    subtotal, tax, total = calculate_totals(order)
    print(f"Subtotal: ${subtotal:.2f}")
    print(f"Tax: ${tax:.2f}")
    print(f"Total: ${total:.2f}")

def calculate_totals(order):
    subtotal = sum(item.price * item.qty for item in order.items)
    tax_rate = 0.08 if order.customer.state == "CA" else 0.05
    tax = subtotal * tax_rate
    return subtotal, tax, subtotal + tax
```

**Pitfalls**
- Don't extract a function used in only one place if the extraction makes the code harder to follow
- Name the new function for **what** it does, not **how** (`calculate_totals`, not `do_subtotal_and_tax`)
- Watch for closures over local variables — explicit parameters are clearer

---

## Replace Nested Conditional with Guard Clauses

**When:** Code has 3+ levels of `if`/`else` nesting, especially around validation.

**Before**
```python
def get_payable_amount(employee):
    if employee.is_separated:
        result = 0
    else:
        if employee.is_retired:
            result = 0
        else:
            # actual logic
            result = employee.base_salary - employee.deductions
    return result
```

**After**
```python
def get_payable_amount(employee):
    if employee.is_separated:
        return 0
    if employee.is_retired:
        return 0
    return employee.base_salary - employee.deductions
```

**Pitfalls**
- Multiple returns are fine for guards but resist returning from deep inside the "real" logic — that becomes confusing
- Order matters: cheapest/fastest checks first

---

## Replace Magic Number with Symbolic Constant

**When:** A literal value appears multiple times or its meaning isn't obvious.

**Before**
```python
def calculate_shipping(weight):
    if weight > 50:
        return weight * 0.15 + 5
    return weight * 0.10
```

**After**
```python
HEAVY_PACKAGE_THRESHOLD_KG = 50
HEAVY_RATE = 0.15
LIGHT_RATE = 0.10
HEAVY_SURCHARGE = 5

def calculate_shipping(weight):
    if weight > HEAVY_PACKAGE_THRESHOLD_KG:
        return weight * HEAVY_RATE + HEAVY_SURCHARGE
    return weight * LIGHT_RATE
```

**Pitfalls**
- Don't extract values that are obvious in context (`if x > 0`, `range(10)` for a fixed loop)
- For values from the domain (tax rates, ZIP codes), consider config files instead of constants

---

## Introduce Parameter Object

**When:** A function takes 4+ parameters that always travel together.

**Before**
```python
def book_flight(origin, destination, depart_date, return_date, passengers, cabin_class):
    ...

book_flight("LAX", "JFK", "2026-05-01", "2026-05-08", 2, "economy")
```

**After**
```python
@dataclass
class FlightSearch:
    origin: str
    destination: str
    depart_date: date
    return_date: date | None
    passengers: int
    cabin_class: Literal["economy", "business", "first"]

def book_flight(search: FlightSearch):
    ...

book_flight(FlightSearch(
    origin="LAX",
    destination="JFK",
    depart_date=date(2026, 5, 1),
    return_date=date(2026, 5, 8),
    passengers=2,
    cabin_class="economy",
))
```

**Pitfalls**
- Don't introduce a parameter object for 2 args — that's overkill
- The object should represent a real concept (`FlightSearch`), not just a bag of args
- Add validation in `__post_init__` for invariants

---

## Extract Class

**When:** A class has fields/methods that form a cohesive sub-responsibility unrelated to the rest.

**Before**
```python
class Person:
    def __init__(self, name, office_area_code, office_number):
        self.name = name
        self.office_area_code = office_area_code
        self.office_number = office_number

    def office_phone(self):
        return f"({self.office_area_code}) {self.office_number}"
```

**After**
```python
class Phone:
    def __init__(self, area_code, number):
        self.area_code = area_code
        self.number = number

    def formatted(self):
        return f"({self.area_code}) {self.number}"

class Person:
    def __init__(self, name, office_phone: Phone):
        self.name = name
        self.office_phone = office_phone
```

**Pitfalls**
- The new class needs a clear name — if naming is hard, the boundary might be wrong
- Be careful with serialization — adding a level of nesting may break consumers

---

## Replace Conditional with Polymorphism

**When:** A switch/if-chain dispatches on a type field.

**Before**
```python
def get_speed(bird):
    if bird.type == "european":
        return base_speed
    elif bird.type == "african":
        return base_speed - load_factor * bird.cargo_count
    elif bird.type == "norwegian_blue":
        return 0 if bird.is_nailed else base_speed * tail_factor
    raise ValueError(f"Unknown bird: {bird.type}")
```

**After**
```python
class Bird:
    def get_speed(self):
        raise NotImplementedError

class EuropeanBird(Bird):
    def get_speed(self):
        return base_speed

class AfricanBird(Bird):
    def __init__(self, cargo_count):
        self.cargo_count = cargo_count
    def get_speed(self):
        return base_speed - load_factor * self.cargo_count

class NorwegianBlueBird(Bird):
    def __init__(self, is_nailed):
        self.is_nailed = is_nailed
    def get_speed(self):
        return 0 if self.is_nailed else base_speed * tail_factor
```

**Pitfalls**
- Polymorphism is overkill for 2 cases — keep the if/else
- Use sparingly in dynamic languages where structural duck typing already works
- Don't add inheritance just to enable this — composition often fits better

---

## Introduce Null Object

**When:** Repeated null checks scatter null-handling logic across the codebase.

**Before**
```python
def get_plan(customer):
    if customer is None:
        return "basic"
    return customer.plan or "basic"

def get_billing_address(customer):
    if customer is None:
        return None
    return customer.billing_address
```

**After**
```python
class NullCustomer:
    plan = "basic"
    billing_address = None
    name = "Guest"

NULL_CUSTOMER = NullCustomer()

def get_customer(id):
    customer = db.find(id)
    return customer or NULL_CUSTOMER

# Now callers don't need null checks:
print(get_customer(123).plan)
```

**Pitfalls**
- Easy to overuse — sometimes None is correct ("not found" should be visible)
- Null object must implement the same interface as the real one

---

## Split Function

**When:** A function takes a boolean parameter that flips its behavior between two modes.

**Before**
```python
def book_concert(customer, is_premium):
    if is_premium:
        seat = best_available_seat()
        price = base_price * 2
    else:
        seat = any_available_seat()
        price = base_price
    save_booking(customer, seat, price)
```

**After**
```python
def book_premium_concert(customer):
    seat = best_available_seat()
    price = base_price * 2
    save_booking(customer, seat, price)

def book_standard_concert(customer):
    seat = any_available_seat()
    price = base_price
    save_booking(customer, seat, price)
```

**Pitfalls**
- Watch for shared logic — extract it into a helper called by both
- Not always cleaner — if the boolean controls one tiny detail, leave it

---

## Pull Up Method

**When:** Two subclasses have nearly-identical methods.

**Before**
```python
class Salesman(Employee):
    def get_name(self): return self.name

class Engineer(Employee):
    def get_name(self): return self.name
```

**After**
```python
class Employee:
    def get_name(self): return self.name

class Salesman(Employee): ...
class Engineer(Employee): ...
```

**Pitfalls**
- Only pull up if the methods are truly identical AND belong logically in the parent
- Don't pull up "by accident" — methods that happen to look the same may diverge

---

## Replace Method with Method Object

**When:** A long function uses many local variables, making it hard to extract pieces.

**Before**
```python
def calculate_price(quantity, item_price):
    base_price = quantity * item_price
    quantity_discount = max(0, quantity - 500) * item_price * 0.05
    shipping = min(base_price * 0.1, 100.0)
    return base_price - quantity_discount + shipping
```

**After**
```python
class PriceCalculator:
    def __init__(self, quantity, item_price):
        self.quantity = quantity
        self.item_price = item_price

    def compute(self):
        return self.base_price() - self.quantity_discount() + self.shipping()

    def base_price(self):
        return self.quantity * self.item_price

    def quantity_discount(self):
        return max(0, self.quantity - 500) * self.item_price * 0.05

    def shipping(self):
        return min(self.base_price() * 0.1, 100.0)

# usage
PriceCalculator(quantity, item_price).compute()
```

**Pitfalls**
- Overkill for short functions
- Each helper method now has access to `self.*` — don't accidentally couple them more than the original

---

## Replace with Return Value

**When:** A function modifies its input parameters (output parameters).

**Before**
```python
def populate_user_stats(user, stats):
    stats["login_count"] = user.login_count
    stats["last_seen"] = user.last_seen

stats = {}
populate_user_stats(user, stats)
```

**After**
```python
def get_user_stats(user):
    return {
        "login_count": user.login_count,
        "last_seen": user.last_seen,
    }

stats = get_user_stats(user)
```

**Pitfalls**
- Pure functions are easier to reason about and test
- For very large objects, mutation may be a perf necessity — measure first

---

## Refactoring rules (universal)

1. **One refactoring at a time.** Don't combine "rename + extract + move" in one commit.
2. **Tests pass before AND after.** Refactoring with broken tests means you're guessing what behavior to preserve.
3. **No feature changes.** If you're tempted to add a feature mid-refactor, stop, commit the refactor, then add the feature.
4. **Small steps.** Each step should be a working state. If you need 50 lines of changes to make tests pass, you took too big a step.
5. **Preserve external API.** Refactor internals first; if you also need to change the public interface, do that as a separate, deliberate change.
6. **Commit per refactoring.** Easier to revert one if it goes wrong.

---

## Anti-refactorings (don't do these)

- **Premature abstraction** — extracting a function "in case it's needed" creates noise without value
- **DRY at all costs** — two similar pieces of code that will diverge later are not duplication
- **Introducing inheritance for code reuse** — composition is usually better
- **Renaming for purity** — `getValue()` → `retrieveValueFromCache()` adds noise
- **Comment-extraction** — replacing a comment with an extracted function is good ONLY if the function name is clearer than the comment
