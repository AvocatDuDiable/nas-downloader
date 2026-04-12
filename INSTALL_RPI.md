# Installation sur Raspberry Pi 1 (sans Docker)

## Prérequis

- Raspberry Pi OS Lite (Bullseye ou Bookworm)
- SSH activé
- Connecté au réseau local

---

## Étape 1 — Créer le dossier sur le RPi

```bash
ssh rpi@rpi.local "mkdir -p ~/nas-downloader"
```

---

## Étape 2 — Transférer les fichiers (depuis ton PC)

```bash
scp -r src config rpi@rpi.local:/home/rpi/nas-downloader/
```

---

## Étape 3 — Se connecter au RPi

```bash
ssh rpi@rpi.local
```

---

## Étape 4 — Installer les dépendances système

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

---

## Étape 5 — Installer les dépendances Python

```bash
pip3 install flask requests
```

> Sur les versions récentes de Raspberry Pi OS, pip3 peut refuser d'installer
> des paquets sans environnement virtuel. Si c'est le cas :
>
> ```bash
> pip3 install flask requests --break-system-packages
> ```

---

## Étape 6 — Tester le lancement

```bash
cd ~/nas-downloader
python3 src/main.py
```

Ouvre `http://rpi.local:8080` dans ton navigateur pour vérifier.

Arrête avec `Ctrl+C`.

---

## Étape 7 — Service systemd (démarrage automatique)

```bash
sudo tee /etc/systemd/system/nas-downloader.service > /dev/null <<EOF
[Unit]
Description=NAS Downloader
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/rpi/nas-downloader/src/main.py
WorkingDirectory=/home/rpi/nas-downloader
Restart=always
RestartSec=5
User=rpi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable nas-downloader
sudo systemctl start nas-downloader
```

---

## Commandes utiles

```bash
# Voir les logs en temps réel
sudo journalctl -u nas-downloader -f

# Statut du service
sudo systemctl status nas-downloader

# Redémarrer après une mise à jour des fichiers
sudo systemctl restart nas-downloader

# Arrêter
sudo systemctl stop nas-downloader
```

---

## Mettre à jour l'application

Depuis ton PC :

```bash
scp -r src config rpi@rpi.local:/home/rpi/nas-downloader/
```

Sur le RPi :

```bash
sudo systemctl restart nas-downloader
```

Pour modifier les destinations ou les credentials, édite `~/nas-downloader/config/config.py`
sur le RPi puis redémarre le service (`sudo systemctl restart nas-downloader`).
