from flask import Flask, request, jsonify
import proxmoxer
import os
from dotenv import load_dotenv
import logging
import random

# Configuration du journal
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)

def get_proxmox_api():
    host = os.getenv('PROXMOX_HOST')
    user = os.getenv('PROXMOX_USER')
    password = os.getenv('PROXMOX_PASSWORD')
    return proxmoxer.ProxmoxAPI(host, user=user, password=password, verify_ssl=True)

def update_vm_network_config(proxmox, node, vmid, ipv4_config, ipv6_config):
    try:
        ipconfig0 = f"ip={ipv4_config}"
        if ipv6_config:
            ipconfig0 += f",ip6={ipv6_config}"

        response = proxmox.nodes(node).qemu(vmid).config.put(ipconfig0=ipconfig0)
        logger.debug(f"Réponse de la mise à jour de la configuration réseau: {response}")
        return response
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la configuration réseau: {e}")
        raise

# Fonction pour générer un identifiant unique pour la nouvelle VM
def generate_unique_vmid(proxmox, node, min_vmid=10000, max_vmid=20000):
    while True:
        vmid = random.randint(min_vmid, max_vmid)
        try:
            proxmox.nodes(node).qemu(vmid).status.current.get()
            logger.debug(f"vmid {vmid} existe déjà, en générant un nouveau...")
        except proxmoxer.ResourceException:
            logger.debug(f"vmid {vmid} généré avec succès.")
            return vmid

@app.route('/clone_vm', methods=['POST'])
def clone_vm():
    data = request.json
    logger.debug(f"Requête reçue pour cloner la VM: {data}")
    proxmox = get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')

    try:
        # Générer un nouvel identifiant unique pour la VM
        new_vm_id = generate_unique_vmid(proxmox, node)
        logger.debug(f"new_vm_id généré : {new_vm_id}")

        # Utiliser le préfixe "machine-VMID" pour le champ "new_vm_name"
        new_vm_name = f"machine-{new_vm_id}"

        # Cloner la VM en spécifiant newid (utilisant l'identifiant numérique)
        logger.debug("Début du processus de clonage...")
        clone_response = proxmox.nodes(node).qemu(data['source_vm_id']).clone.create(newid=new_vm_id, name=new_vm_name)
        logger.debug(f"Réponse du clonage: {clone_response}")

        # Mise à jour de la configuration CPU et RAM de la VM clonée
        vm_config = {
            'cores': data.get('cpu'),
            'memory': data.get('ram')
        }
        update_vm_config_response = proxmox.nodes(node).qemu(new_vm_id).config.put(**vm_config)
        logger.debug(f"Réponse de la mise à jour de la configuration VM (CPU/RAM): {update_vm_config_response}")

        # Redimensionnement du disque (si spécifié)
        disk_to_resize = data.get('disk_type', None)
        new_size = data.get('disk_size', None)
        if disk_to_resize and new_size:
            resize_response = proxmox.nodes(node).qemu(new_vm_id).resize.put(disk=disk_to_resize, size=new_size)
            logger.debug(f"Réponse du redimensionnement du disque: {resize_response}")

        # Mise à jour de la configuration réseau de la VM clonée
        ipv4_config = f"{data['ipv4']}/24,gw={data['gateway_ipv4']}"
        ipv6_config = f"{data['ipv6']},gw6={data['gateway_ipv6']}"
        network_update_response = update_vm_network_config(proxmox, node, new_vm_id, ipv4_config, ipv6_config)

        # Démarrer la VM si demandé
        if data.get('start_vm'):
            start_vm_response = proxmox.nodes(node).qemu(new_vm_id).status.start.post()
            logger.debug(f"Réponse du démarrage de la VM: {start_vm_response}")

        return jsonify({
            'clone_response': clone_response, 
            'update_vm_config_response': update_vm_config_response, 
            'network_update_response': network_update_response,
            'start_vm_response': 'VM started' if data.get('start_vm') else 'VM not started'
        })

    except Exception as e:
        logger.error(f"Erreur lors du clonage ou de la configuration de la VM: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update_vm_config', methods=['POST'])
def update_vm_config():
    data = request.json
    proxmox = get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')

    try:
        # Vérifier l'état de la VM
        vm_status = proxmox.nodes(node).qemu(data['vm_id']).status.current.get()
        vm_was_running = vm_status['status'] == 'running'

        # Arrêter la VM si elle est en cours d'exécution
        if vm_was_running:
            proxmox.nodes(node).qemu(data['vm_id']).status.stop.post()
            # Attendre l'arrêt complet de la VM (ajouter ici une logique d'attente)

        # Effectuer les modifications de configuration
        vm_config = {
            'cores': data['cpu'],
            'memory': data['ram'],
            'disk': data['disk'],
            'net0': f"virtio,bridge=vmbr0,ip={data['ipv4']}/24,gw={data['ipv4'].rsplit('.', 1)[0]}.1,ip6={data['ipv6']}"
        }
        update_vm_config_response = proxmox.nodes(node).qemu(data['vm_id']).config.put(**vm_config)

        # Redémarrer la VM si elle était en cours d'exécution
        if vm_was_running:
            proxmox.nodes(node).qemu(data['vm_id']).status.start.post()

        return jsonify(update_vm_config_response)

    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la configuration de la VM: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/delete_vm', methods=['DELETE'])
def delete_vm():
    vm_id = request.args.get('vm_id')
    proxmox = get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')

    try:
        # Vérifier l'état de la VM
        vm_status = proxmox.nodes(node).qemu(vm_id).status.current.get()

        # Si la VM est en cours d'exécution, l'arrêter
        if vm_status.get('status') == 'running':
            stop_response = proxmox.nodes(node).qemu(vm_id).status.stop.post()
            logger.debug(f"Réponse de l'arrêt forcé de la VM: {stop_response}")

            # Attendre que la VM soit complètement arrêtée avant de continuer
            # Ajoutez ici une logique pour attendre ou vérifier à nouveau l'état si nécessaire

        # Supprimer la VM
        delete_response = proxmox.nodes(node).qemu(vm_id).delete()
        logger.debug(f"Réponse de la suppression de la VM: {delete_response}")

        return jsonify({'delete_response': delete_response})

    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la VM: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
