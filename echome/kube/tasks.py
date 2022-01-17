import logging
from celery import shared_task
from vmmanager.instance_definitions import InstanceDefinition
from identity.models import User
from .manager import KubeClusterManager

logger = logging.getLogger(__name__)


@shared_task
def task_create_cluster(prepared_cluster_id:str, user_id:str, instance_def: str, image_id:str, 
        network_profile:str, controller_ip:str, kubernetes_version:str, key_name:str, disk_size:str):
    logger.debug(f"Received async task to create cluster for: {prepared_cluster_id}")

    user = User.objects.get(user_id=user_id)
    manager = KubeClusterManager(prepared_cluster_id)

    try:
        manager.create_cluster(
            user = user,
            instance_def = InstanceDefinition(instance_def),
            controller_ip = controller_ip,
            image_id = image_id,
            network_profile = network_profile,
            kubernetes_version = kubernetes_version,
            key_name = key_name,
            disk_size = disk_size, 
        )
    except Exception as e:
        logger.error("KubeCluster creation process failed")
        logger.error(e)
        
