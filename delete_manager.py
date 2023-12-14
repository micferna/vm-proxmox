# delete_manager.py
from concurrent.futures import ThreadPoolExecutor
import asyncio

class DeleteManager:
    def __init__(self, api_manager, ansible_manager):
        self.api_manager = api_manager
        self.ansible_manager = ansible_manager

    async def delete_vm_async(self, vm_id, node, task_id, tasks):
        proxmox = await self.api_manager.get_proxmox_api()
        try:
            executor = ThreadPoolExecutor()
            loop = asyncio.get_running_loop()

            # Vérification de l'état de la VM
            vm_status_response = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.current.get())

            if vm_status_response.get("status") in ["running", "blocked"]:
                # Arrêt de la VM
                await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.stop.post())

                # Attente que la VM soit arrêtée
                while True:
                    status = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.current.get())
                    if status.get("status") in ["stopped", "offline"]:
                        break
                    await asyncio.sleep(2)  # Ajustez ce délai au besoin

            # Suppression de la VM
            await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).delete())

            # Mise à jour de l'inventaire Ansible
            await self.ansible_manager.update_ansible_inventory(vm_id, None, None, 'remove')

            tasks[task_id] = "Completed"
        except Exception as e:
            tasks[task_id] = f"Failed: {str(e)}"
