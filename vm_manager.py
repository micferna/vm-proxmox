# vm_manager.py        
import random
import asyncio
import ipaddress
import proxmoxer
import logging
import yaml
import os
import requests
import socket 
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


    async def is_ssh_ready(self, host, retries=5, delay=5):
        port = int(os.getenv('PORT_SSH', 22))
        for _ in range(retries):
            try:
                with socket.create_connection((host, port), timeout=10):
                    return True
            except (socket.timeout, ConnectionRefusedError):
                await asyncio.sleep(delay)
        return False
    
    async def clone_vm_async(self, task_id, data, node, ip_pools, tasks):
        try:
            proxmox = await self.api_manager.get_proxmox_api()
            executor = ThreadPoolExecutor()
            loop = asyncio.get_running_loop()

            new_vm_id = await self.id_manager.generate_unique_vmid(node)
            new_vm_name = data.get('new_vm_name') or f"MACHINE-{new_vm_id}"
            clone_response = proxmox.nodes(node).qemu(data['source_vm_id']).clone.create(newid=new_vm_id, name=new_vm_name)
            vm_status = None
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
                # Démarrer la VM
                await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(new_vm_id).status.start.post())

            # Attendre que la VM soit opérationnelle
            await asyncio.sleep(30)  # Attendre 30 secondes pour permettre à la VM de démarrer

                        # Vérifier la disponibilité de SSH
            ipv4 = ipv4_config.split('/')[0] if ipv4_config else None
            ssh_ready = False
            while not ssh_ready:
                try:
                    if ipv4:
                        ssh_ready = await self.is_ssh_ready(ipv4)
                    if not ssh_ready:
                        await asyncio.sleep(5)  # Attendre 5 secondes avant de réessayer
                except Exception as e:
                    self.logger.error(f"Erreur lors de la vérification de SSH: {e}")
                    await asyncio.sleep(5)  # Attendre et réessayer

            
            # Mise à jour de l'inventaire Ansible
            ipv4_address = ipv4_config.split('/')[0] if ipv4_config else 'N/A'
            ipv6_address = ipv6_config.split('/')[0] if ipv6_config else 'N/A'
            
            await self.ansible_manager.update_ansible_inventory(
                new_vm_id, 
                ipv4_address,  # Enlever le masque de sous-réseau
                ipv6_address,  # Enlever le masque de sous-réseau
                'add', 
                dns_name=new_vm_name,  # Passer new_vm_name comme dns_name
                application=application
            )

            # Exécution du playbook si une application est spécifiée
            if 'application' in data:
                await self.ansible_manager.run_applications(new_vm_id, data['application'])

            # Configurer les informations de tâche comme complétées
            tasks[task_id] = {
                'status': 'Completed',
                'vm_status': vm_status.get('status', 'N/A') if vm_status else 'Unknown',
                'vmid': new_vm_id,
                'ipv4': ipv4_address,
                'ipv6': ipv6_address
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
