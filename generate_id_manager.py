# generate_id_manager.py
import asyncio
import random
import proxmoxer

class GenerateIDManager:
    def __init__(self, api_manager):
        self.api_manager = api_manager

    async def generate_unique_vmid(self, node, min_vmid=300, max_vmid=500):
        loop = asyncio.get_running_loop()
        proxmox = await self.api_manager.get_proxmox_api()
        while True:
            vmid = random.randint(min_vmid, max_vmid)
            try:
                # Exécution dans un thread séparé car la méthode n'est pas asynchrone
                await loop.run_in_executor(None, lambda: proxmox.nodes(node).qemu(vmid).status.current.get())
                # Si aucune exception n'est levée, cela signifie que le VMID existe déjà, alors on continue la boucle pour en trouver un autre
            except proxmoxer.ResourceException:
                # Si une ResourceException est levée, cela signifie que le VMID est unique et peut être utilisé
                return vmid
