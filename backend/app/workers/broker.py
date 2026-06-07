import dramatiq
from dramatiq.brokers.redis import RedisBroker

from app.core.config import get_settings
from app.core.observability import configure_observability

settings = get_settings()
configure_observability(settings)
redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)
