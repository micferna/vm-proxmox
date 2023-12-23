#!/bin/bash

# Vérifiez si la clé de déchiffrement est fournie
if [ -z "$DECRYPTION_KEY" ]; then
    echo "La clé de déchiffrement est manquante"
    exit 1
fi

# Chemin du fichier .env.enc à déchiffrer
ENV_ENC_FILE=".env.enc"

# Vérifiez si le fichier .env.enc existe
if [ ! -f "$ENV_ENC_FILE" ]; then
    echo "Le fichier $ENV_ENC_FILE n'existe pas"
    exit 1
fi

# Déchiffrement du fichier .env.enc
openssl enc -aes-256-cbc -d -in "$ENV_ENC_FILE" -out ".env" -pass pass:"$DECRYPTION_KEY"

echo "Le fichier $ENV_ENC_FILE a été déchiffré en .env"
