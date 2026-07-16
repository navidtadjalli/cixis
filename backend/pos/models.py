"""POS data models for the CiXiS local backend.

Conventions:
- Money is stored as integers in واحد «هزار تومان» (thousand Tomans), matching menu.json.
- Category/Product/Table use soft delete via ``is_active`` — never hard-deleted.
- Order/OrderItem/Payment carry nullable ``*_user_id`` fields for future staff support.
"""
from django.db import models
from django.db.models import Max


class TimeStamped(models.Model):
    """Abstract base adding auto-managed created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserStamped(models.Model):
    """Abstract base adding nullable actor ids (future staff accounts)."""

    created_by_user_id = models.IntegerField(null=True, blank=True)
    updated_by_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True


class Category(TimeStamped):
    name = models.CharField(max_length=120)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(TimeStamped):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    # Price in thousand-Tomans.
    price = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    # Whether this product appears in the published QR menu. Unlike is_available
    # (in-stock flag, still shown but struck through), an unpublishable product is
    # sold in-house via the POS but omitted from the public menu entirely.
    is_publishable = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class Table(TimeStamped):
    name = models.CharField(max_length=80)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class Order(TimeStamped, UserStamped):
    class Mode(models.TextChoices):
        TABLE = "table", "میز"
        EVENT = "event", "رویداد"

    class Status(models.TextChoices):
        OPEN = "open", "باز"
        PARTIALLY_PAID = "partially_paid", "پرداخت جزئی"
        PAID = "paid", "پرداخت‌شده"
        CLOSED = "closed", "بسته‌شده"

    order_number = models.IntegerField(unique=True, editable=False)
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.TABLE)
    table = models.ForeignKey(
        Table,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    event_customer_label = models.CharField(max_length=160, null=True, blank=True)
    # Bulk-generated event "code" slots, created ahead of service from the setup
    # page. Until an item is rung up on one it behaves like a table, not an
    # order: it survives leaving the order panel, stays out of the closing
    # register, and is not settled by a close. See closing.untouched_preset_ids.
    is_preset = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    subtotal = models.IntegerField(default=0)
    paid_amount = models.IntegerField(default=0)
    remaining_amount = models.IntegerField(default=0)
    business_date = models.DateField(null=True, blank=True)
    # Set when the day is closed: links the order to its DayClosing snapshot so
    # the live preview can exclude already-settled orders (register resets to
    # zero) while reports still read history by business_date.
    day_closing = models.ForeignKey(
        "DayClosing",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at", "-id"]

    def save(self, *args, **kwargs):
        if self.order_number is None:
            last = Order.objects.aggregate(m=Max("order_number"))["m"] or 0
            self.order_number = last + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.order_number}"


class OrderItem(TimeStamped, UserStamped):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL
    )
    product_name_snapshot = models.CharField(max_length=160)
    unit_price_snapshot = models.IntegerField(default=0)
    quantity = models.IntegerField(default=1)
    # How many units of this item have been settled via split payments.
    paid_quantity = models.IntegerField(default=0)
    line_total = models.IntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.product_name_snapshot} x{self.quantity}"


class Payment(TimeStamped, UserStamped):
    class Method(models.TextChoices):
        CASH = "cash", "نقدی"
        CARD = "card", "کارت"
        BANK_TRANSFER = "bank_transfer", "کارت‌به‌کارت"

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.IntegerField(default=0)
    method = models.CharField(max_length=20, choices=Method.choices)
    payer_label = models.CharField(max_length=160, null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.amount} ({self.method})"


class DayClosing(TimeStamped):
    class SyncStatus(models.TextChoices):
        PENDING = "pending", "در انتظار"
        SYNCED = "synced", "همگام‌شده"
        FAILED = "failed", "ناموفق"
        # Terminal: remote sync is switched off, so this close will never be
        # pushed anywhere. Distinct from PENDING, which invites a retry.
        LOCAL_ONLY = "local_only", "فقط محلی"

    # Not unique: closing is a cashier-driven settlement event, not a per-day
    # record. One calendar day may have several closings (or none), and a single
    # closing may settle orders spanning several days. business_date is just the
    # date the close happened, for report grouping.
    business_date = models.DateField()
    total_sales = models.IntegerField(default=0)
    # Booked value of every settled order (paid + remaining items), the
    # supervisor's "how much sold so far" figure; >= total_sales when open
    # orders carried unpaid items into the close.
    gross_sales = models.IntegerField(default=0)
    cash_total = models.IntegerField(default=0)
    card_total = models.IntegerField(default=0)
    bank_transfer_total = models.IntegerField(default=0)
    orders_count = models.IntegerField(default=0)
    closed_orders_count = models.IntegerField(default=0)
    open_orders_count = models.IntegerField(default=0)
    table_usage_count = models.IntegerField(default=0)
    purchases_total = models.IntegerField(default=0)
    resource_suggestions_snapshot = models.JSONField(default=list, blank=True)
    sync_status = models.CharField(
        max_length=16, choices=SyncStatus.choices, default=SyncStatus.PENDING
    )
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-business_date"]

    def __str__(self):
        return f"DayClosing {self.business_date}"


class ResourcePurchase(TimeStamped):
    name = models.CharField(max_length=160)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=40, blank=True, default="")
    cost = models.IntegerField(default=0)
    note = models.TextField(blank=True, default="")
    business_date = models.DateField()

    class Meta:
        ordering = ["-business_date", "-id"]

    def __str__(self):
        return self.name


class ResourceSuggestion(TimeStamped):
    resource_name = models.CharField(max_length=160)
    reason = models.CharField(max_length=255, blank=True, default="")
    suggested_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    created_for_date = models.DateField()

    class Meta:
        ordering = ["-created_for_date", "-id"]

    def __str__(self):
        return self.resource_name


class BackupRecord(TimeStamped):
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(default=0)
    app_version = models.CharField(max_length=40, default="")

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.file_path


class MenuPublishRecord(TimeStamped):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        SUCCESS = "success", "موفق"
        FAILED = "failed", "ناموفق"

    version = models.CharField(max_length=40)
    payload_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    error_message = models.TextField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"MenuPublish {self.version} ({self.status})"


class SyncRecord(TimeStamped):
    class SyncType(models.TextChoices):
        DAY_CLOSING = "day_closing", "بستن روز"
        MENU = "menu", "منو"

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        SYNCED = "synced", "همگام‌شده"
        FAILED = "failed", "ناموفق"

    sync_type = models.CharField(max_length=20, choices=SyncType.choices)
    local_object_id = models.IntegerField(null=True, blank=True)
    payload_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(null=True, blank=True)
    attempt_count = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"Sync {self.sync_type} #{self.local_object_id} ({self.status})"


class AppSetting(TimeStamped):
    key = models.CharField(max_length=80, unique=True)
    value = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.key}={self.value}"
