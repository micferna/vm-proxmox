![Logo Discord](https://zupimages.net/up/23/26/rumo.png)
[Rejoignez le Discord !](https://discord.gg/rSfTxaW)

[![Utilisateurs en ligne](https://img.shields.io/discord/347412941630341121?style=flat-square&logo=discord&colorB=7289DA)](https://discord.gg/347412941630341121)

---
### Cloner une VM
```bash
curl -X POST http://localhost:5000/clone_vm \
     -H "Content-Type: application/json" \
     -d '{
           "source_vm_id": "100000",
           "new_vm_id": "101",
           "new_vm_name": "vmclone101",
           "ipv4": "192.168.1.10",
           "ipv6": "fd00::10/64",
           "gateway_ipv4": "192.168.1.1",
           "gateway_ipv6": "fd00::1",
           "cpu": 4,
           "ram": 8192,
           "disk_type": "sata0",
           "disk_size": "30G",
	   "start_vm": true
         }'


curl -X POST http://localhost:5000/clone_vm \
     -H "Content-Type: application/json" \
     -d '{
           "source_vm_id": "100000",
           "ipv4": "192.168.1.10",
           "ipv6": "fd00::10/64",
           "gateway_ipv4": "192.168.1.1",
           "gateway_ipv6": "fd00::1",
           "cpu": 4,
           "ram": 8192,
           "disk_type": "sata0",
           "disk_size": "30G",
           "start_vm": true
         }'
```

### Update une VM
### Chaque paramettre est optionnel pour les modifications
```bash
curl -X POST http://localhost:5000/update_vm_config \
     -H "Content-Type: application/json" \
     -d '{
           "vm_id": "101",
           "cpu": "4",
           "ram": "2096",
           "disk_type": "sata0",
           "disk": "150"
         }'

curl -X POST http://localhost:5000/update_vm_config \
     -H "Content-Type: application/json" \
     -d '{
           "vm_id": "ID_DE_LA_VM",
           "cpu": "NB_DE_CORES_CPU",
           "ram": "TAILLE_DE_LA_RAM",
           "disk": "TYPE_ET_TAILLE_DU_DISQUE",
           "ipv4": "ADRESSE_IPV4",
           "ipv6": "ADRESSE_IPV6",
           "gateway_ipv4": "PASSERELLE_IPV4",
           "gateway_ipv6": "PASSERELLE_IPV6"
         }'
```

### Vérifier l'état d'une tâche
```bash
curl -X GET "http://localhost:5000/check_status?task_id=<ID_TACHE>"
```

### Suprimer une VM
```bash
curl -X DELETE "http://localhost:5000/delete_vm?vm_id=101"
```

### Liste toute les VMs
```bash
curl http://localhost:5000/list_vms
```

### Information en plus
```bash
curl http://localhost:5000/list_vms/IDVM
```