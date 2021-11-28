import logging
from celery import shared_task
from identity.models import User

logger = logging.getLogger(__name__)


@shared_task
def task_terminate_cluster(cluster_id:str, user_id:str):
    logger.debug(f"Received async task to terminate VM: {cluster_id}")
    user = User.objects.get(user_id=user_id)
    #VmManager().terminate_instance(vm_id, user)


@shared_task
def task_create_cluster(prepared_cluster_id:str, user_id:str):
    logger.debug(f"Received async task to create disk image for: {vm_id}")
    user = User.objects.get(user_id=user_id)
    manager = ImageManager(prepared_id)
    try:
        VmManager().create_virtual_machine_image(vm_id, user, prepared_manager=manager)
    except Exception as e:
        logger.error("Image creation process from VM failed")
        logger.error(e)
        manager.mark_image_as_failed()
