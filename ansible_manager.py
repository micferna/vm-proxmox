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
        ipv4 = ipv4.split('/')[0] if ipv4 else ipv4
        ipv6 = ipv6.split('/')[0] if ipv6 else ipv6

        try:
            with open(self.inventory_file, 'r') as file:
                inventory = yaml.safe_load(file) or {}
        except (FileNotFoundError, yaml.YAMLError):
            inventory = {}

        # Mettre à jour l'inventaire
        if action == 'add':
            host_entry = {
                'ansible_host': ipv4,
                'ansible_ssh_user': self.ssh_user,
                'ansible_ssh_private_key_file': self.ssh_key_path
                # Ajoutez d'autres variables spécifiques à l'hôte ici si nécessaire
            }
            inventory['all'] = inventory.get('all', {})
            inventory['all']['hosts'] = inventory['all'].get('hosts', {})
            inventory['all']['hosts'][str(vmid)] = host_entry

        elif action == 'remove' and str(vmid) in inventory['all']['hosts']:
            del inventory['all']['hosts'][str(vmid)]

        # Sauvegarder l'inventaire mis à jour
        with open(self.inventory_file, 'w') as file:
            yaml.dump(inventory, file, default_flow_style=False)

        self.logger.debug(f"Inventaire Ansible mis à jour: {action} VM {vmid}")

    async def run_applications(self, vm_id, applications):
        playbook_dir = os.getenv('PLAYBOOK_DIR', '/chemin/par/defaut/des/playbooks')
        try:
            apps_requested = applications.split()

            for app in apps_requested:
                playbook_name = f'{app}.yml'
                full_playbook_path = os.path.join(playbook_dir, playbook_name)

                if os.path.isfile(full_playbook_path):
                    await self.run_ansible_playbook(vm_id, full_playbook_path)
                else:
                    self.logger.warning(f"Aucun playbook trouvé pour l'application '{app}'")
        except FileNotFoundError as e:
            self.logger.error(f"Erreur de fichier non trouvé : {e}")
                
    async def run_ansible_playbook(self, vmid, application):
        playbook_path = os.path.join(self.private_data_dir, f'{application}')
        runner_params = {
            'private_data_dir': self.private_data_dir,
            'inventory': self.inventory_file,  # Assurez-vous que cela pointe vers 'inventory.yaml'
            'playbook': playbook_path,
            'extravars': {
                'ansible_user': self.ssh_user, 
                'ansible_ssh_private_key_file': self.ssh_key_path
            },
            'limit': str(vmid)
        }

        # Log des paramètres de la commande Ansible
        self.logger.debug(f"Exécution du playbook Ansible avec les paramètres : {runner_params}")

        # Exécution du playbook Ansible
        result = await asyncio.to_thread(run, **runner_params)

        # Log du résultat de l'exécution
        self.logger.debug(f"Résultat de l'exécution du playbook Ansible : {result}")

        # Gestion des erreurs
        if result.rc != 0:
            self.logger.error(f'Erreur lors de l’exécution du playbook Ansible pour la VM {vmid}: {result.stdout}')
        else:
            self.logger.info(f'Playbook Ansible exécuté avec succès pour la VM {vmid}')

        return result