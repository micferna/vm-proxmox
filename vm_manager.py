# vm_manager.py        
import random
import asyncio
import ipaddress
import proxmoxer
import logging
import yaml
import os
from concurrent.futures import ThreadPoolExecutor
from ansible_manager import AnsibleManager
from delete_manager import DeleteManager
from update_config_vm_manager import UpdateVMManager
from update_network_vm_config import UpdateNetworkVMConfig
from generate_id_manager import GenerateIDManager

from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

class ProxmoxVMManager:
    def __init__(self, ip_manager, api_manager):
        self.ip_manager = ip_manager
        self.api_manager = api_manager
        self.logger = logging.getLogger(__name__)
        self.ansible_manager = AnsibleManager() 
        self.delete_manager = DeleteManager(api_manager, self.ansible_manager)
        self.update_vm_manager = UpdateVMManager(api_manager)
        self.network_config_manager = UpdateNetworkVMConfig(api_manager)
        self.id_manager = GenerateIDManager(api_manager)

    async def delete_vm_async(self, vm_id, node, task_id, tasks):
        await self.delete_manager.delete_vm_async(vm_id, node, task_id, tasks)

    async def update_vm_network_config(self, node, vmid, bridge, ipv4_config=None, ipv4_gateway=None, ipv6_config=None, ipv6_gateway=None):
        return await self.network_config_manager.update_vm_network_config(node, vmid, bridge, ipv4_config, ipv4_gateway, ipv6_config, ipv6_gateway)

    async def clone_vm_async(self, task_id, data, node, ip_pools, tasks):
        try:
            proxmox = await self.api_manager.get_proxmox_api()
            executor = ThreadPoolExecutor()
            loop = asyncio.get_running_loop()

            new_vm_id = await self.id_manager.generate_unique_vmid(node)
            new_vm_name = data.get('new_vm_name') or f"MACHINE-{new_vm_id}"
            clone_response = proxmox.nodes(node).qemu(data['source_vm_id']).clone.create(newid=new_vm_id, name=new_vm_name)
            application = data.get('application', None)

            vm_config = {
                'cores': data.get('cpu'),
                'memory': data.get('ram')
            }
            proxmox.nodes(node).qemu(new_vm_id).config.put(**vm_config)

            if 'disk_type' in data and 'disk_size' in data:
                proxmox.nodes(node).qemu(new_vm_id).resize.put(disk=data['disk_type'], size=data['disk_size'])

            selected_pool = None
            for pool in ip_pools:
                if data.get('ipv4') and ipaddress.ip_address(data['ipv4'].split('/')[0]) in ipaddress.ip_network(pool['network_ipv4']):
                    selected_pool = pool
                    break
                if data.get('ipv6') and ipaddress.ip_address(data['ipv6'].split('/')[0]) in ipaddress.ip_network(pool['network_ipv6']):
                    selected_pool = pool
                    break

            if not selected_pool:
                selected_pool = ip_pools[0]

            bridge = selected_pool['bridge']
            ipv4_config = data.get('ipv4') or (await self.ip_manager.find_free_ip(proxmox, node, selected_pool['network_ipv4'], selected_pool['gateway_ipv4']) + '/24')
            ipv6_config = data.get('ipv6') or (await self.ip_manager.find_free_ip(proxmox, node, selected_pool['network_ipv6'], selected_pool['gateway_ipv6']) + '/64')

            await self.update_vm_network_config(node, new_vm_id, bridge, ipv4_config, selected_pool['gateway_ipv4'], ipv6_config, selected_pool['gateway_ipv6'])

            if data.get('start_vm'):
                await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(new_vm_id).status.start.post())

            vm_status = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(new_vm_id).status.current.get())
            vm_config = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(new_vm_id).config.get())
            ipconfig0 = vm_config.get('ipconfig0', '')

            ipv4 = 'N/A'
            ipv6 = 'N/A'
            for part in ipconfig0.split(','):
                if part.startswith('ip='):
                    ipv4 = part.split('=')[1]
                elif part.startswith('ip6='):
                    ipv6 = part.split('=')[1]

            # Mise à jour de l'inventaire Ansible
            await self.ansible_manager.update_ansible_inventory(
            new_vm_id, 
            ipv4.split('/')[0],  # Enlever le masque de sous-réseau
            ipv6.split('/')[0],  # Enlever le masque de sous-réseau
            'add', 
            dns_name=new_vm_name,  # Passer new_vm_name comme dns_name
            application=application
        )

            # Exécution du playbook si une application est spécifiée
            if application:
                await self.ansible_manager.run_ansible_playbook(new_vm_id, application)

            tasks[task_id] = {
                'status': 'Completed',
                'vm_status': vm_status.get('status', 'N/A'),
                'vmid': new_vm_id,
                'ipv4': ipv4,
                'ipv6': ipv6
            }

        except Exception as e:
            if 'ipv4_config' in locals():
                self.ip_manager.unlock_ip(ipv4_config.split('/')[0])
            if 'ipv6_config' in locals():
                self.ip_manager.unlock_ip(ipv6_config.split('/')[0])
            raise e
        finally:
            if 'ipv4_config' in locals():
                self.ip_manager.unlock_ip(ipv4_config.split('/')[0])
            if 'ipv6_config' in locals():
                self.ip_manager.unlock_ip(ipv6_config.split('/')[0])
