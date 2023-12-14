import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

class UpdateVMManager:
    def __init__(self, api_manager):
        self.api_manager = api_manager
        self.logger = logging.getLogger(__name__)

    async def update_vm_config_async(self, data, node):
        proxmox = await self.api_manager.get_proxmox_api()
        vm_id = data['vm_id']
        bridge = data.get('bridge')
        ipv4_config = data.get('ipv4')
        ipv6_config = data.get('ipv6')
        cpu = data.get('cpu')
        ram = data.get('ram')
        disk_type = data.get('disk_type')
        disk_size = data.get('disk_size')

        executor = ThreadPoolExecutor()
        loop = asyncio.get_running_loop()

        # Vérifier l'état actuel de la VM
        vm_status_before = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.current.get())
        vm_was_running_before_update = vm_status_before['status'] == 'running'

        if vm_was_running_before_update:
            # Arrêter la VM si elle est en cours d'exécution
            await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.stop.post())
            await asyncio.sleep(10)

        # Mise à jour de la configuration
        update_config = {}
        if cpu is not None:
            update_config['cores'] = cpu
        if ram is not None:
            update_config['memory'] = ram
        if disk_type is not None and disk_size is not None:
            try:
                resize_param = {"disk": disk_type, "size": disk_size}
                await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).resize.put(**resize_param))
            except Exception as e:
                self.logger.error(f"Erreur lors de la mise à jour de la taille du disque: {e}")

        if bridge or ipv4_config or ipv6_config:
            net_config = f"model=virtio,bridge={bridge}" if bridge else ""
            ipconfig0 = ''
            if ipv4_config:
                ipconfig0 += f"ip={ipv4_config}"
            if ipv6_config:
                ipconfig0 += f",ip6={ipv6_config}"
            update_config['net0'] = net_config
            if ipconfig0:
                update_config['ipconfig0'] = ipconfig0

        if update_config:
            await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).config.put(**update_config))

        # Redémarrer la VM après la mise à jour, indépendamment de son état initial
        await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.start.post())
