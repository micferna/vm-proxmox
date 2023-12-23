<?php
$apiUrl = "http://127.0.0.1:8000"; // URL de l'API

function clonePredefinedVM($preset) {
    global $apiUrl;
    $predefinedConfigs = [
        'machine1' => ['source_vm_id' => 100, 'new_vm_id' => null, 'new_vm_name' => null, 'ram' => 2048, 'cpu' => 2, 'disk_size' => '10G'],
        'machine2' => ['source_vm_id' => 101, 'new_vm_id' => null, 'new_vm_name' => null, 'ram' => 4096, 'cpu' => 4, 'disk_size' => '20G'],
        'machine3' => ['source_vm_id' => 102, 'new_vm_id' => null, 'new_vm_name' => null, 'ram' => 8192, 'cpu' => 6, 'disk_size' => '40G'],
    ];
    return cloneVM($predefinedConfigs[$preset]);
}

function getListOfVMs() {
    global $apiUrl;
    $ch = curl_init("$apiUrl/list_vms");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $response = curl_exec($ch);
    curl_close($ch);
    return json_decode($response, true);
}

function startVM($vmId) {
    global $apiUrl;
    $ch = curl_init("$apiUrl/start_vm/$vmId");
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $response = curl_exec($ch);
    curl_close($ch);
    return $response;
}

function stopVM($vmId) {
    global $apiUrl;
    $ch = curl_init("$apiUrl/stop_vm/$vmId");
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $response = curl_exec($ch);
    curl_close($ch);
    return $response;
}

function rebootVM($vmId) {
    global $apiUrl;
    $ch = curl_init("$apiUrl/reboot_vm/$vmId");
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $response = curl_exec($ch);
    curl_close($ch);
    return $response;
}

function deleteVM($vmId) {
    global $apiUrl;
    $ch = curl_init("$apiUrl/delete_vm/$vmId");
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "DELETE");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $response = curl_exec($ch);
    curl_close($ch);
    return $response;
}

function cloneVM($config) {
    global $apiUrl;
    $ch = curl_init("$apiUrl/clone_vm");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($config));
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    $response = curl_exec($ch);
    curl_close($ch);
    return json_decode($response, true);
}

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    if (isset($_POST['start_vm'])) {
        $vmId = $_POST['vm_id'];
        startVM($vmId);
    } elseif (isset($_POST['stop_vm'])) {
        $vmId = $_POST['vm_id'];
        stopVM($vmId);
    } elseif (isset($_POST['reboot_vm'])) {
        $vmId = $_POST['vm_id'];
        rebootVM($vmId);
    } elseif (isset($_POST['delete_vm'])) {
        $vmId = $_POST['vm_id'];
        deleteVM($vmId);
    }

    if (isset($_POST['clone_custom_vm'])) {
        $config = [
            'source_vm_id' => $_POST['source_vm_id'],
            'new_vm_id' => $_POST['new_vm_id'] ?? null,
            'new_vm_name' => $_POST['new_vm_name'] ?? null,
            'cpu' => $_POST['cpu'] ?? 1,
            'ram' => $_POST['ram'] ?? 512,
            'disk_type' => $_POST['disk_type'] ?? 'sata0',
            'disk_size' => $_POST['disk_size'] ?? '10G',
            'start_vm' => true,
        ];
        $result = cloneVM($config);
    } elseif (isset($_POST['clone_predefined_vm'])) {
        $preset = $_POST['clone_predefined_vm'];
        $result = clonePredefinedVM($preset);
    }

    if (isset($result) && $result['status'] == 'success') {
        $message = "<div class='alert alert-success'>VM clonée avec succès. IP: {$result['ip']}</div>";
    } elseif (isset($result)) {
        $message = "<div class='alert alert-danger'>Erreur lors du clonage de la VM.</div>";
    }

    header("Refresh:5; url=index.php?action=list_vms");
}

$vms = getListOfVMs();

function formatIpConfig($ipconfig) {
    preg_match('/ip=([0-9\.\/]+),/', $ipconfig, $ipv4Match);
    preg_match('/ip6=([0-9a-fA-F:\/]+),?/', $ipconfig, $ipv6Match);

    $ipv4 = isset($ipv4Match[1]) ? "<strong>IPv4:</strong> <span style='color: darkslategray;'>" . $ipv4Match[1] . "</span>" : "";
    $ipv6 = isset($ipv6Match[1]) ? "<strong>IPv6:</strong> <span style='color: darkslategray;'>" . $ipv6Match[1] . "</span>" : "";

    return trim("$ipv4 $ipv6");
}
?>


<title>Gestion des VMs</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3">
                <h3>Menu</h3>
                <ul class="nav flex-column">
                    <li class="nav-item">
                        <a class="nav-link" href="index.php?action=clone_vm">Cloner une VM</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="index.php?action=list_vms">Liste des VMs</a>
                    </li>
                </ul>
            </div>
            <div class="col-md-9">
                <?php if (isset($_GET['action']) && $_GET['action'] == 'clone_vm'): ?>
                    <?php if (isset($message)) echo $message; ?>
                    <h2>Cloner une VM</h2>
                    <form method="post">
                        <div class="form-group">
                            <label>ID de la VM source :</label>
                            <input type="number" class="form-control" name="source_vm_id" required>
                        </div>
                        <div class="form-group">
                            <label>Nouvel ID VM (optionnel) :</label>
                            <input type="number" class="form-control" name="new_vm_id">
                        </div>
                        <div class="form-group">
                            <label>Nom DNS (optionnel) :</label>
                            <input type="text" class="form-control" name="new_vm_name">
                        </div>
                        <div class="form-group">
                            <label>CPU :</label>
                            <input type="number" class="form-control" name="cpu">
                        </div>
                        <div class="form-group">
                            <label>RAM (en MB) :</label>
                            <input type="number" class="form-control" name="ram">
                        </div>
                        <div class="form-group">
                            <label>Type de Disque :</label>
                            <input type="text" class="form-control" name="disk_type">
                        </div>
                        <div class="form-group">
                            <label>Taille du Disque :</label>
                            <input type="text" class="form-control" name="disk_size">
                        </div>

                        
                        <form method="post">
                            <button type="submit" class="btn btn-primary mb-2" name="clone_predefined_vm" value="machine1">Cloner Machine 1</button>
                            <button type="submit" class="btn btn-primary mb-2" name="clone_predefined_vm" value="machine2">Cloner Machine 2</button>
                            <button type="submit" class="btn btn-primary mb-2" name="clone_predefined_vm" value="machine3">Cloner Machine 3</button>
                        </form>
                    </div>
                        <button type="submit" class="btn btn-primary" name="clone_custom_vm">Cloner VM Personnalisée</button>
                    </form>
                <?php elseif (isset($_GET['action']) && $_GET['action'] == 'list_vms'): ?>
                    <h2>Liste des VMs</h2>
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Nom</th>
                                <th>État</th>
                                <th>Cœurs</th>
                                <th>Mémoire</th>
                                <th>IP Config</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($vms as $vm): ?>
                                <tr>
                                    <td><?= htmlspecialchars($vm['vmid']) ?></td>
                                    <td><?= htmlspecialchars($vm['name']) ?></td>
                                    <td style="color: <?= $vm['status'] == 'running' ? 'green' : 'red' ?>;">
                                        <?= htmlspecialchars($vm['status']) ?>
                                    </td>
                                    <td><?= htmlspecialchars($vm['cores']) ?></td>
                                    <td><?= htmlspecialchars($vm['memory']) ?></td>
                                    <td><?= formatIpConfig($vm['ipconfig0']) ?></td>
                                    <td>
                                        <form method="post">
                                            <input type="hidden" name="vm_id" value="<?= htmlspecialchars($vm['vmid']) ?>">
                                            <button type="submit" class="btn btn-success btn-sm" name="start_vm">Démarrer</button>
                                            <button type="submit" class="btn btn-warning btn-sm" name="stop_vm">Arrêter</button>
                                            <button type="submit" class="btn btn-secondary btn-sm" name="reboot_vm">Redémarrer</button>
                                            <button type="submit" class="btn btn-danger btn-sm" name="delete_vm">Supprimer</button>
                                        </form>
                                    </td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                <?php endif; ?>
            </div>
        </div>
    </div>
    <script src="https://code.jquery.com/jquery-3.3.1.slim.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.7/umd/popper.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/js/bootstrap.min.js"></script>
</body>
</html>