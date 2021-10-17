import logging
from celery import shared_task
from identity.models import User
from .vm_instance import VirtualMachineInstance
from .vm_manager import VmManager
from .image_manager import ImageManager

logger = logging.getLogger(__name__)


@shared_task
def task_stop_instance(vm_id:str):
    logger.debug(f"Received async task to stop VM: {vm_id}")
    VirtualMachineInstance(vm_id).stop()


@shared_task
def task_terminate_instance(vm_id:str, user_id:str):
    logger.debug(f"Received async task to terminate VM: {vm_id}")
    user = User.objects.get(user_id=user_id)
    VmManager().terminate_instance(vm_id, user)


@shared_task
def task_create_image(vm_id:str, user_id:str, prepared_id:str):
    logger.debug(f"Received async task to create disk image for: {vm_id}")
    user = User.objects.get(user_id=user_id)
    manager = ImageManager(prepared_id)
    VmManager().create_virtual_machine_image(vm_id, user, prepared_manager=manager)
