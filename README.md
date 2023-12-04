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
```

### Suprimer une VM
```bash
curl -X DELETE "http://localhost:5000/delete_vm?vm_id=101"
```