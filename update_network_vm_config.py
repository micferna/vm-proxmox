# update_network_vm_config.py

import asyncio
import logging

class UpdateNetworkVMConfig:
    def __init__(self, api_manager):
        self.api_manager = api_manager
        self.logger = logging.getLogger(__name__)

    async def update_vm_network_config(self, node, vmid, bridge, ipv4_config=None, ipv4_gateway=None, ipv6_config=None, ipv6_gateway=None):
        proxmox = await self.api_manager.get_proxmox_api()
        net_config = f"model=virtio,bridge={bridge}"
        ipconfig0 = ''

        if ipv4_config:
            ipconfig0 += f"ip={ipv4_config}"
            if ipv4_gateway:
                ipconfig0 += f",gw={ipv4_gateway}"
        if ipv6_config:
            ipconfig0 += f",ip6={ipv6_config}"
            if ipv6_gateway:
                ipconfig0 += f",gw6={ipv6_gateway}"

        config_update = {'net0': net_config}
        if ipconfig0:
            config_update['ipconfig0'] = ipconfig0

        # Si la méthode `put` est bloquante, utilisez `asyncio.to_thread` pour l'exécuter dans un thread séparé.
        response = await asyncio.to_thread(proxmox.nodes(node).qemu(vmid).config.put, **config_update)

        return response
