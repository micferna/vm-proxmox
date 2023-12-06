# Utilisez l'image officielle de Python
FROM python:3.11

# Définissez le répertoire de travail dans le conteneur sur /app
WORKDIR /app

# Copiez votre fichier requirements.txt dans le conteneur
COPY requirements.txt /app

# Installez les paquets nécessaires spécifiés dans requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Créez un environnement virtuel et ajoutez son chemin au PATH
RUN python3.11 -m venv venv
ENV PATH="/app/venv/bin:$PATH"

# Ajoutez les fichiers du répertoire courant à /app dans le conteneur
ADD . /app

# Rendez le port 5000 disponible pour le monde extérieur à ce conteneur
EXPOSE 5000

# Exécutez gunicorn lorsque le conteneur se lance
CMD ["gunicorn", "--access-logfile", "-", "-b", "0.0.0.0:5000", "app:app"]
