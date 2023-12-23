# delete_manager.py
from concurrent.futures import ThreadPoolExecutor
import asyncio
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class DeleteManager:
    def __init__(self, api_manager, ansible_manager):
        self.api_manager = api_manager
        self.ansible_manager = ansible_manager
        self.logger = logging.getLogger(__name__)  # Initialisation du logger

    async def delete_vm_async(self, vm_id, node, task_id, tasks):
        proxmox = await self.api_manager.get_proxmox_api()
        try:
            executor = ThreadPoolExecutor()
            loop = asyncio.get_running_loop()

            # Vérifier si la VM existe
            vm_list = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu.get())
            if not any(vm['vmid'] == vm_id for vm in vm_list):
                self.logger.info(f"La VM avec l'ID {vm_id} n'existe plus sur le noeud {node}.")
                tasks[task_id] = "VM n'existe plus"
                return

            # Vérification de l'état de la VM
            vm_status_response = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.current.get())
            #self.logger.debug(f"État actuel de la VM {vm_id}: {vm_status_response}")

            if vm_status_response.get("status") in ["running", "blocked"]:
                # Arrêt de la VM
                self.logger.info(f"Arrêt de la VM {vm_id}.")
                await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.stop.post())

                # Attente que la VM soit arrêtée
                while True:
                    status = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.current.get())
                    if status.get("status") in ["stopped", "offline"]:
                        self.logger.info(f"La VM {vm_id} est maintenant arrêtée.")
                        break
                    await asyncio.sleep(2)  # Ajustez ce délai au besoin

            # Suppression de la VM
            self.logger.info(f"Suppression de la VM {vm_id}.")
            await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).delete())

            # Mise à jour de l'inventaire Ansible
            await self.ansible_manager.update_ansible_inventory(vm_id, None, None, 'remove')

            self.logger.info(f"La VM {vm_id} a été supprimée avec succès.")
            tasks[task_id] = "Completed"
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression de la VM {vm_id}: {e}")
            tasks[task_id] = f"Failed: {str(e)}"
