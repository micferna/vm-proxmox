# ansible_manager.py
import asyncio
import os
import yaml
from ansible_runner import run
import logging

class AnsibleManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.inventory_file = os.getenv('INVENTORY_FILE')
        self.ssh_user = os.getenv('SSH_USER')
        self.ssh_key_path = os.getenv('SSH_KEY_PATH')
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.private_data_dir = os.path.join(self.script_dir, 'playbook')

    async def update_ansible_inventory(self, vmid, ipv4, ipv6, action, dns_name=None, application=None):
        try:
            with open(self.inventory_file, 'r') as file:
                inventory = yaml.safe_load(file) or {}
        except (FileNotFoundError, yaml.YAMLError):
            inventory = {}

        if action == 'add':
            inventory_entry = {'ipv4': ipv4, 'ipv6': ipv6, 'dns_name': dns_name, 'role': 'default_role'}
            if application:
                inventory_entry['application'] = application
            inventory[str(vmid)] = inventory_entry
        elif action == 'remove' and str(vmid) in inventory:
            del inventory[str(vmid)]

        with open(self.inventory_file, 'w') as file:
            yaml.dump(inventory, file, default_flow_style=False)

        self.logger.debug(f"Inventaire Ansible mis à jour: {action} VM {vmid}")

    async def run_ansible_playbook(self, vmid, application):
        playbook_path = os.path.join(self.private_data_dir, f'{application}.yml')
        runner_params = {
            'private_data_dir': self.private_data_dir,
            'inventory': self.inventory_file,
            'playbook': playbook_path,
            'extravars': {'ansible_user': self.ssh_user, 'ansible_ssh_private_key_file': self.ssh_key_path},
            'limit': f'{vmid}'
        }

        result = await asyncio.to_thread(run, **runner_params)
        if result.rc != 0:
            self.logger.error(f'Erreur lors de l’exécution du playbook Ansible pour la VM {vmid}: {result.stdout}')
        else:
            self.logger.info(f'Playbook Ansible exécuté avec succès pour la VM {vmid}')
        return result
