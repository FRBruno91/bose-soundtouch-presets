# Présélections radio Bose SoundTouch

Depuis l’arrêt du cloud Bose, le 6 mai 2026, les boutons de présélection ont cessé de lancer la radio, aussi bien avec l’intégration officielle Bose SoundTouch qu’avec SoundTouch Plus. Cette vue Home Assistant range les stations dans Home Assistant, les cherche par leur nom, les associe à 6 touches d’un clavier, les joue sur l’enceinte SoundTouch choisie, et peut synchroniser les autres enceintes SoundTouch de la même façon que la carte SoundTouch Plus : `media_player.join` et `media_player.unjoin`, par le script `script.bose_sync`.

Les enceintes SoundTouch lisent le `http`. Le relais convertit ce `https` en MP3 128 kbit/s, à vitesse normale, puis le donne à l’enceinte en `http`. Sous le titre en cours, **http** s’affiche en vert et **https** en rouge. Les flux HLS (`.m3u8`) restent refusés.

« J’ai fait ça dans mon coin, pour mes enceintes. Je le partage comme n’importe quel autre projet. Le développement n’est pas mon métier : s’il y a des bugs, ou si ça ne convient pas à votre installation, je n’en suis pas responsable. Vous l’utilisez librement, sans garantie. »

Merci à Todd Lucas pour SoundTouch Plus : https://github.com/thlucas1/homeassistantcomponent_soundtouchplus

La recherche par nom passe par l’API publique Radio Browser. Le projet est gratuit.

## Installation

La vue a été faite avec Home Assistant 2026.10. Il faut HACS.

1. Dans HACS, onglet Intégrations, installez **SoundTouch Plus** (Todd Lucas), puis redémarrez Home Assistant. Ensuite : Paramètres, Appareils et services, Ajouter une intégration, SoundTouch Plus, et ajoutez vos enceintes. La vue utilise les entités `media_player` de cette intégration.

2. Dans HACS, onglet Frontend, installez ces trois cartes, puis redémarrez :
   - button-card
   - auto-entities
   - card-mod

   La carte Lovelace SoundTouch Plus n’est pas utilisée par ce YAML. Vous n’avez pas à l’installer pour cette vue.

3. Copiez `bose_radio_search.py` et `bose_https_relay.py` à la racine du dossier de configuration de Home Assistant, à côté de `configuration.yaml`. Les noms doivent rester ceux-là. Avec l’add-on File editor : ouvrez le dossier de configuration, puis téléversez les deux fichiers. Home Assistant doit pouvoir joindre Internet : c’est lui qui interroge Radio Browser et, s’il le faut, le flux `https`.

4. Activez les packages s’ils ne le sont pas déjà. Dans `configuration.yaml`, s’il y a déjà un bloc `homeassistant:`, ajoutez seulement la ligne `packages` en dessous, sans créer un second bloc `homeassistant:` :

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

   Créez le dossier `packages` dans le dossier de configuration s’il n’existe pas. Copiez-y `packages/bose_soundtouch_presets.yaml`.

   Ce fichier crée d’un coup le `shell_command` de recherche, les aides textuelles (bibliothèque de 12 stations, 6 touches, recherche, enceinte choisie) et les scripts. Quelques stations d’exemple, en flux HTTP publics, sont déjà remplies. Vous pouvez les remplacer ou les vider depuis la vue.

5. Outils de développement, YAML, Vérifier la configuration. Si le contrôle est bon, redémarrez Home Assistant. Un simple rechargement des scripts ne suffit pas : le `shell_command` est pris en compte au démarrage.

6. Copiez le fichier `images/clavier-soundtouch.png` dans le dossier de configuration de Home Assistant, sous ce chemin :

   `/config/www/clavier-soundtouch.png`

   Le tableau de bord le voit à l’adresse `/local/clavier-soundtouch.png`. Le YAML pointe déjà vers ce fichier. Rien à aligner : les touches du dessin tombent sur les zones cliquables.

   Une photo personnelle ne correspondra pas, sauf si elle est recadrée exactement comme ce dessin.

7. Ajoutez la vue à un tableau de bord. Sur le tableau de bord : les trois points, Modifier le tableau de bord, encore les trois points, Éditeur de configuration brute. Sous `views:`, collez tout le contenu de `lovelace/test-bose-2.yaml`. Le fichier commence déjà par `- type: sections`. Enregistrez.

   Le titre est « TEST BOSE 2 » et le chemin est `test-bose-2`. Vous pouvez changer les deux. Le chemin doit être unique dans ce tableau de bord.

8. Ouvrez la vue. Choisissez l’enceinte, cherchez une station par son nom, ou collez une adresse `http://` ou `https://`, puis placez-la sur une des 6 touches. Vert `http` : l’enceinte lit la radio directement. Rouge `https` : Home Assistant fait le relais. Les touches du clavier lancent la lecture, le volume, l’auxiliaire et la marche. « Écouter aussi sur » ajoute ou retire une autre enceinte SoundTouch Plus du groupe.

Le script `script.bose_retirer` vide un emplacement de la bibliothèque (paramètre `slot`, de 1 à 12) et retire cet emplacement des touches. La vue n’affiche pas de bouton pour lui : il est dans le package si vous voulez l’appeler vous-même.

Un café si le cœur vous en dit : https://buymeacoffee.com/i3runo
