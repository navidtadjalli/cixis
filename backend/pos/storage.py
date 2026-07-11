"""Upload the rendered QR menu to an S3-compatible bucket (Arvan Cloud).

The bucket is configured for static website hosting, so publishing the menu means
putting the rendered HTML at the bucket root as ``index.html``. Two upload details
are load-bearing:

* ``ACL: public-read`` -- without it the object is private and customers get 403.
* ``ContentType: text/html`` -- without it the object is served as
  ``application/octet-stream`` and phones download the file instead of showing it.

Credentials are read from AppSetting at call time. They are never baked into the
build, so a packaged installer carries no secrets.

boto3 is imported lazily: the POS must still boot and take orders on a machine
where the bundled wheel is missing, with publish the only thing that breaks.
"""
from .models import AppSetting

UPLOAD_TIMEOUT = 15

# Arvan signs with a literal "default" region regardless of which datacentre the
# bucket lives in; the configured region only names the website hostname.
SIGNING_REGION = "default"

SETTING_KEYS = (
    "s3_access_key",
    "s3_secret_key",
    "s3_bucket",
    "s3_endpoint_url",
    "s3_region",
)


class StorageNotConfigured(RuntimeError):
    """Raised when one or more S3 settings are still blank."""


def _setting(key, default=""):
    obj = AppSetting.objects.filter(key=key).first()
    return (obj.value if obj else default).strip()


def storage_config() -> dict:
    """Read the five S3 settings, or raise if any is still blank."""
    config = {key: _setting(key) for key in SETTING_KEYS}
    missing = [key for key, value in config.items() if not value]
    if missing:
        raise StorageNotConfigured(
            "تنظیمات فضای ذخیره‌سازی کامل نیست: " + ", ".join(missing)
        )
    return config


def website_url(config: dict) -> str:
    """Public address the QR code should point at."""
    return (
        f"https://{config['s3_bucket']}."
        f"s3-website.{config['s3_region']}.arvanstorage.ir"
    )


def _client(config: dict):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=config["s3_endpoint_url"],
        aws_access_key_id=config["s3_access_key"],
        aws_secret_access_key=config["s3_secret_key"],
        region_name=SIGNING_REGION,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=UPLOAD_TIMEOUT,
            read_timeout=UPLOAD_TIMEOUT,
            retries={"max_attempts": 2},
        ),
    )


def upload_html(object_name: str, html: str, config: dict) -> None:
    """Put a UTF-8 HTML string at ``object_name``, publicly readable.

    Wraps botocore's two exception families into RuntimeError so callers only
    have to catch one thing.
    """
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        _client(config).put_object(
            Bucket=config["s3_bucket"],
            Key=object_name,
            Body=html.encode("utf-8"),
            ACL="public-read",
            ContentType="text/html; charset=utf-8",
            CacheControl="no-cache",
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        raise RuntimeError(
            f"خطای فضای ذخیره‌سازی {error.get('Code')}: {error.get('Message')}"
        ) from exc
    except BotoCoreError as exc:
        raise RuntimeError(f"خطای اتصال به فضای ذخیره‌سازی: {exc}") from exc
