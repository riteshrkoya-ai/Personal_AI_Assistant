import logging
import time

import httpx

from app.bot.application import build_telegram_application
from app.core.config import get_settings


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
settings = get_settings()


def wait_for_backend(
    max_attempts: int = 30,
    delay_seconds: int = 2,
) -> None:
    health_url = f"{settings.api_base_url}/health"

    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.get(
                health_url,
                timeout=5.0,
            )

            if response.status_code == 200:
                logger.info("Assistant backend is ready.")
                return

        except Exception:
            logger.info(
                "Waiting for assistant backend... attempt %s/%s",
                attempt,
                max_attempts,
            )

        time.sleep(delay_seconds)

    raise RuntimeError(
        "Assistant backend was not ready after waiting."
    )


def main() -> None:
    wait_for_backend()

    application = build_telegram_application(webhook=False)

    logger.info("Starting Telegram polling worker...")

    application.run_polling(
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()