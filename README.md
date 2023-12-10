## CODEBYGPT

![Logo Discord](https://zupimages.net/up/23/26/rumo.png)
[Rejoignez le Discord !](https://discord.gg/rSfTxaW)

[![Utilisateurs en ligne](https://img.shields.io/discord/347412941630341121?style=flat-square&logo=discord&colorB=7289DA)](https://discord.gg/347412941630341121)



## Script de Gestion des Machines Virtuelles Proxmox avec FastAPI

Ce script est une application basée sur FastAPI pour la gestion des machines virtuelles (VM) sur Proxmox. Il fournit une API RESTful pour diverses opérations liées aux VM, notamment le clonage, la mise à jour de la configuration, la vérification de l'état et la liste des VM.

### Premiers Pas
  
1. **Installation**
   - Clonez ce dépôt sur votre machine locale.

- Renseignez les IPs dans le fichier `config.json` pour une utilisation automatique des IPs
  
2. **Configuration de l'Environnement**
   - Copier le fichier `exemple.env` avec les variables d'environnement suivantes :
     - `PROXMOX_HOST` - Adresse du serveur du cluster Proxmox.
     - `PROXMOX_USER` - Nom d'utilisateur de l'API Proxmox.
     - `PROXMOX_PASSWORD` - Mot de passe de l'API Proxmox.
     - `PROXMOX_NODE` - Nom du nœud Proxmox.

3. **Dépendances**
   - Installez les packages Python requis en exécutant :
     ```
     pip install -r requirements.txt
     ```

### Utilisation

- Exécutez le script à l'aide d'Uvicorn :
```
  uvicorn main:app --host 0.0.0.0 --port 8000
```

- Accédez à l'API à l'adresse `http://127.0.0.1:8000`.

### Points d'Accès de l'API

- **Cloner une VM** : Créez une nouvelle VM en clonant une existante.
- **Point d'accès** : `/clone_vm`
- **Méthode** : POST

##### Paramètres

- `source_vm_id` (obligatoire) : ID de la VM source à cloner.
- `new_vm_id` : (optionnel) : ID de la nouvelle VM (généré automatiquement s'il n'est pas spécifié).
- `new_vm_name` : (optionnel) : Nom de la nouvelle VM.
- `cpu` : (optionnel) : Nombre de cœurs de CPU pour la nouvelle VM.
- `ram` : (optionnel) : Quantité de mémoire RAM pour la nouvelle VM.
- `disk_type` : (optionnel) : Type de disque pour la nouvelle VM.
- `disk_size` : (optionnel) : Taille du disque pour la nouvelle VM.
- `bridge` : (optionnel) : Pont réseau pour la nouvelle VM.
- `ipv4` : (optionnel) : Adresse IPv4 pour la nouvelle VM.
- `ipv6` : (optionnel) : Adresse IPv6 pour la nouvelle VM.
- `start_vm` : (optionnel) : Démarrer la nouvelle VM après le clonage (par défaut, non démarrée).

Exemple de demande JSON :

```json
{
  "source_vm_id": 12345,
  "new_vm_name": "NouvelleVM",
  "cpu": 2,
  "ram": 4096,
  "disk_type": "scsi",
  "disk_size": "50G",
  "bridge": "vmbr0",
  "ipv4": "192.168.1.100",
  "ipv6": "2001:db8::1/64",
  "start_vm": true
}
```

#### Mettre à Jour la Configuration d'une VM (suite)

Mettez à jour la configuration d'une VM existante.

- **Point d'accès** : `/update_vm_config`
- **Méthode** : POST

##### Paramètres

- `vm_id` (obligatoire) : ID de la VM à mettre à jour.
- `bridge` : (optionnel) : Pont réseau pour la VM.
- `ipv4` : (optionnel) : Adresse IPv4 pour la VM.
- `ipv6` : (optionnel) : Adresse IPv6 pour la VM.
- `cpu` : (optionnel) : Nombre de cœurs de CPU pour la VM.
- `ram` : (optionnel) : Quantité de mémoire RAM pour la VM.
- `disk_type` : (optionnel) : Type de disque pour la VM.
- `disk_size` : (optionnel) : Taille du disque pour la VM.

Exemple de demande JSON :

```json
{
    "vm_id": 12345,
    "bridge": "vmbr0",
    "ipv4": "192.168.1.100",
    "cpu": 4,
    "ram": 8192
}
```

#### Supprimer une VM (suite)

Supprimez une VM existante.

- **Point d'accès** : `/delete_vm/{vm_id}`
- **Méthode** : DELETE

##### Paramètres

- `vm_id` (obligatoire) : ID de la VM à supprimer.

Exemple de demande : `/delete_vm/12345`

#### Vérifier l'État d'une Tâche

Vérifiez l'état d'une tâche en cours ou terminée.

- **Point d'accès** : `/check_status`
- **Méthode** : GET

##### Paramètres

- `task_id` (obligatoire) : ID de la tâche à vérifier.

Exemple de demande : `/check_status/task_id`

#### Liste des VMs

Obtenez la liste des VMs existantes.

- **Point d'accès** : `/list_vms`
- **Méthode** : GET

##### Paramètres

- `vmid` : (optionnel) : ID d'une VM spécifique à obtenir. Si non spécifié, la liste de toutes les VMs sera renvoyée.

Exemple de demande : `/list_vms` (pour obtenir la liste de toutes les VMs)

Exemple de demande : `/list_vms/12345` (pour obtenir les détails de la VM avec l'ID 12345)

### Gestion des Tâches

- Le script suit l'état des tâches à l'aide d'identifiants de tâche.
- Les tâches sont marquées comme "En cours" lors de leur initiation et comme "Terminées" lorsqu'elles sont terminées.
- Les identifiants de tâche sont renvoyés dans la réponse lors de la création de tâches.

---

# Utilisation : 
- Renseignez les infos du proxmox dans le fichier `.env `
- Renseignez les IPs dans le fichier `config.json` pour une utilisation automatique des IPs
  
```bash
git clone https://github.com/micferna/vm-proxmox.git
cd vm-proxmox
cp exemple.env .env
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
uvicorn main:app --reload
```

---
### Cloner une VM

### Avec le minimum
```bash
curl -X POST http://127.0.0.1:8000/clone_vm \
     -H "Content-Type: application/json" \
     -d '{"source_vm_id": 100000, "cpu": 8, "ram": 8096, "disk_type": "sata0", "disk_size": "50G", "start_vm": true}'
```

---
### Suprimer une VM
```bash
curl -X DELETE http://127.0.0.1:8000/delete_vm/IDVM
```
---

### Vérifier l'état d'une tâche
```bash
curl -X GET http://127.0.0.1:8000/check_status?task_id=<task_id>
```
---
### Affiche toute les VMs présent sur le proxmox
```bash
curl -X GET "http://127.0.0.1:8000/list_vms"
```
### Info détailler sur une VM
```bash
curl -X GET "http://127.0.0.1:8000/list_vms?vmid=100"
```
---
### Update une VM
### Chaque paramettre est optionnel pour les modifications
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "vm_id": 101,
  "cpu": 1,
  "ram": 512
}' http://127.0.0.1:8000/update_vm_config

# Modifier uniquement le type de disque et la taille du disque
curl -X POST -H "Content-Type: application/json" -d '{
  "vm_id": 101,
  "disk_type": "sata0",
  "disk_size": "+200G"
}' http://127.0.0.1:8000/update_vm_config

```
---
# A REVOIR

```bash
# Cloner une VM full param
curl -X POST http://127.0.0.1:8000/clone_vm \
     -H "Content-Type: application/json" \
     -d '{"source_vm_id": 100000, "new_vm_id": 101, "new_vm_name": "VMTESTFASTAPI", "cpu": 8, "ram": 8096, "disk_type": "sata0", "disk_size": "50G", "bridge": "vmbr0", "ipv4": "192.168.1.10/24", "ipv6": "fd00::10/64", "start_vm": false}'
```

```bash
# Modifier uniquement les adresses IP IPv4 et IPv6
curl -X POST -H "Content-Type: application/json" -d '{
  "vm_id": 19075,
  "ipv4": "NOUVELLE_IP_IPV4",
  "ipv6": "NOUVELLE_IP_IPV6"
}' http://127.0.0.1:8000/update_vm_config
```
