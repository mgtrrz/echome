import logging
from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task
def add(x, y):
    return x + y


@shared_task
def mul(x, y):
    logger.debug("Is this working?")
    return x * y


@shared_task
def xsum(numbers):
    return sum(numbers)
