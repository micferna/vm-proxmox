        
import random
import asyncio
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import proxmoxer
import json
import logging
import yaml
import os

from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

class ProxmoxVMManager:
    def __init__(self, ip_manager, api_manager):
        self.ip_manager = ip_manager
        self.api_manager = api_manager
        self.logger = logging.getLogger(__name__)  # Initialisation du logger

    async def update_vm_network_config(self, proxmox, node, vmid, bridge, ipv4_config=None, ipv4_gateway=None, ipv6_config=None, ipv6_gateway=None):
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

        response = proxmox.nodes(node).qemu(vmid).config.put(**config_update)

    async def generate_unique_vmid(self, proxmox, node, min_vmid=300, max_vmid=500):
        loop = asyncio.get_running_loop()
        while True:
            vmid = random.randint(min_vmid, max_vmid)
            try:
                # Exécution dans un thread séparé car la méthode n'est pas asynchrone
                await loop.run_in_executor(None, lambda: proxmox.nodes(node).qemu(vmid).status.current.get())
                # Si aucune exception n'est levée, cela signifie que le VMID existe déjà, alors on continue la boucle pour en trouver un autre
            except proxmoxer.ResourceException:
                # Si une ResourceException est levée, cela signifie que le VMID est unique et peut être utilisé
                return vmid

    async def clone_vm_async(self, task_id, data, node, ip_pools, tasks):
        try:
            proxmox = await self.api_manager.get_proxmox_api()
            executor = ThreadPoolExecutor()
            loop = asyncio.get_running_loop()

            new_vm_id = await self.generate_unique_vmid(proxmox, node)
            new_vm_name = data.get('new_vm_name') or f"MACHINE-{new_vm_id}"
            clone_response = proxmox.nodes(node).qemu(data['source_vm_id']).clone.create(newid=new_vm_id, name=new_vm_name)

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

            await self.update_vm_network_config(proxmox, node, new_vm_id, bridge, ipv4_config, selected_pool['gateway_ipv4'], ipv6_config, selected_pool['gateway_ipv6'])

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

            await self.update_ansible_inventory(new_vm_id, ipv4, ipv6, 'add')

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


    async def update_ansible_inventory(self, vmid, ipv4, ipv6, action, dns_name=None):
        inventory_file_name = os.getenv("INVENTORY_FILE")
        self.logger.debug(f"Mise à jour de l'inventaire Ansible pour la VM {vmid}: Action = {action}")

        try:
            with open(inventory_file_name, 'r') as file:
                try:
                    inventory = yaml.safe_load(file) or {}  # Charge le fichier YAML ou initialise à {} si vide
                except yaml.YAMLError:
                    # Fichier mal formaté, initialiser un nouvel inventaire
                    inventory = {}
        except FileNotFoundError:
            # Fichier non trouvé, initialiser un nouvel inventaire
            inventory = {}

        if action == 'add':
            inventory[str(vmid)] = {'ipv4': ipv4, 'ipv6': ipv6, 'role': 'default_role'}
        elif action == 'remove' and str(vmid) in inventory:
            del inventory[str(vmid)]

        with open(inventory_file_name, 'w') as file:
            yaml.dump(inventory, file, default_flow_style=False)

        self.logger.debug(f"Inventaire Ansible mis à jour: {action} VM {vmid}")

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
                logger.error(f"Erreur lors de la mise à jour de la taille du disque: {e}")

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

            # Retirer la VM de l'inventaire
            await self.update_ansible_inventory(vm_id, None, None, 'remove')

            tasks[task_id] = "Completed"
        except Exception as e:
            tasks[task_id] = f"Failed: {str(e)}"