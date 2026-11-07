# Bot Discord Forex Factory — installation gratuite

Ce projet publie dans **un seul salon Discord** :
- un résumé de toutes les annonces du jour à **07:00, heure de Paris** ;
- une alerte pour chaque annonce Forex Factory classée **High (rouge)**, lors du premier passage du bot dans les 15 minutes qui précèdent l'annonce ;
- les heures sont converties dans le fuseau `Europe/Paris` (heure d'été/hiver automatique).

Le bot utilise le flux JSON hebdomadaire public de Forex Factory :
https://nfs.faireconomy.media/ff_calendar_thisweek.json

Il ne nécessite ni bot Discord, ni token Discord, ni serveur personnel : un **webhook Discord** suffit.
Le programme utilise uniquement la bibliothèque standard de Python.

## Important : précision et limites

- Le workflow est vérifié toutes les 5 minutes. L'alerte est donc envoyée au premier passage dans la fenêtre de 15 minutes, généralement entre 10 et 15 minutes avant l'annonce.
- GitHub Actions peut retarder les tâches planifiées en période de forte charge. Une alerte exactement à la minute près ne peut donc pas être garantie.
- Le flux Forex Factory est un export hebdomadaire, actualisé environ une fois par heure. Le bot le met en cache et ne le télécharge qu'environ une fois toutes les 55 minutes pour éviter les requêtes excessives.
- Le calendrier Forex Factory indique que les heures sont approximatives et peuvent changer. Vérifie toujours les annonces importantes sur le site.
- « 100 % gratuit » dépend des limites et conditions des services utilisés. Un dépôt GitHub public permet généralement d'éviter la facturation des runners GitHub standard ; un dépôt privé reste soumis aux quotas gratuits du compte.
- Dans un dépôt public, le code est visible par tous. **Ne place jamais le webhook dans un fichier du dépôt** : il doit rester dans les Secrets GitHub.

## 1. Créer le salon Discord

1. Dans ton serveur Discord, crée un salon texte, par exemple `#calendrier-economique`.
2. Ouvre **Modifier le salon** → **Intégrations** → **Webhooks**.
3. Clique sur **Nouveau webhook**.
4. Donne-lui le nom `Forex Factory Bot`.
5. Vérifie qu'il est associé au salon `#calendrier-economique`.
6. Clique sur **Copier l'URL du webhook**.
7. Garde cette URL privée : toute personne qui la possède peut publier dans le salon.

Tu n'as pas besoin de créer une application ou un bot dans le portail développeur Discord.

## 2. Créer le dépôt GitHub

1. Connecte-toi sur https://github.com/
2. Clique sur **New repository**.
3. Nom du dépôt : `forex-factory-discord-bot`.
4. Pour rester gratuit, tu peux choisir **Public**. Si tu choisis Private, vérifie les quotas GitHub Actions inclus dans ton compte.
5. Coche **Add a README file** ou laisse le dépôt vide.
6. Clique sur **Create repository**.

## 3. Ajouter les fichiers

Dans le dépôt GitHub, ajoute les fichiers suivants en respectant exactement les noms et dossiers :

```text
forex-factory-discord-bot/
├── .github/
│   └── workflows/
│       └── forex-factory.yml
├── bot.py
├── .gitignore
└── README.md
```

Les fichiers `calendar_cache.json` et `bot_state.json` seront créés automatiquement lors de la première exécution.

Pour chaque fichier :
1. Clique sur **Add file** → **Create new file**.
2. Saisis le chemin complet dans le champ du nom.
3. Colle le contenu du fichier correspondant fourni dans l'archive.
4. Clique sur **Commit changes**.

## 4. Ajouter le webhook comme secret GitHub

1. Dans le dépôt, ouvre **Settings**.
2. Va dans **Secrets and variables** → **Actions**.
3. Clique sur **New repository secret**.
4. Nom exact : `DISCORD_WEBHOOK_URL`
5. Valeur : colle l'URL du webhook Discord copiée à l'étape 1.
6. Clique sur **Add secret**.

Ne mets jamais cette URL dans `bot.py`, dans le workflow ou dans un message public.

## 5. Autoriser GitHub Actions à sauvegarder l'état

Le bot conserve deux petits fichiers dans le dépôt :
- `calendar_cache.json` : copie temporaire du calendrier, pour éviter de solliciter Forex Factory toutes les 5 minutes ;
- `bot_state.json` : mémorise le résumé quotidien déjà envoyé et les alertes déjà envoyées, pour éviter les doublons.

Pour autoriser leur mise à jour :
1. Va dans **Settings** → **Actions** → **General**.
2. Descends à **Workflow permissions**.
3. Sélectionne **Read and write permissions**.
4. Clique sur **Save**.

## 6. Activer et tester le bot

1. Ouvre l'onglet **Actions** du dépôt.
2. Si GitHub te le demande, clique sur **I understand my workflows, go ahead and enable them**.
3. Sélectionne **Forex Factory vers Discord** dans la colonne de gauche.
4. Clique sur **Run workflow**.
5. Pour le premier test, coche **Envoyer un message de test dans Discord** (`test_discord`).
6. Clique sur **Run workflow**.

Tu dois recevoir dans `#calendrier-economique` :
`✅ Test réussi ! Le webhook du bot Forex Factory fonctionne.`

Lance ensuite le workflow manuellement une seconde fois sans cocher le test pour effectuer une première récupération du calendrier et initialiser le cache.

## 7. Fonctionnement automatique

- Toutes les 5 minutes : le bot vérifie si une alerte rouge doit être envoyée.
- À 07:00 heure de Paris : le bot publie le calendrier du jour.
- Les annonces rouges sont signalées au premier passage du bot dans les 15 minutes avant leur horaire.
- Les alertes et le résumé quotidien ne sont pas répétés si l'état a été sauvegardé.

Le workflow planifié doit être présent sur la branche par défaut (`main`) pour fonctionner. GitHub peut retarder les exécutions planifiées. Dans un dépôt public, GitHub peut désactiver les workflows planifiés après 60 jours sans activité du dépôt : surveille l'onglet Actions et réactive-les si nécessaire.

## 8. Dépannage

### Aucun message n'arrive
- Vérifie que le secret s'appelle exactement `DISCORD_WEBHOOK_URL`.
- Vérifie que l'URL du webhook est toujours valide.
- Ouvre **Actions** et consulte le journal de la dernière exécution.

### Le workflow échoue au moment de sauvegarder
Vérifie **Settings → Actions → General → Workflow permissions → Read and write permissions**.

### Le bot envoie plusieurs fois le même résumé
Vérifie que `bot_state.json` est bien sauvegardé dans le dépôt et que le push du workflow réussit.

### Le calendrier n'est pas actualisé
Le bot réutilise volontairement le cache si Forex Factory ne répond pas. Consulte le journal Actions. Le flux hebdomadaire peut être indisponible ou refuser temporairement une requête.

### Le bot ne démarre pas à 07:00 pile
Les tâches planifiées GitHub peuvent être retardées. Le code accepte une exécution jusqu'à 07:14 pour le résumé du matin, mais aucune heure d'exécution exacte n'est garantie.

## Références

- Calendrier Forex Factory : https://www.forexfactory.com/calendar
- Export JSON hebdomadaire : https://nfs.faireconomy.media/ff_calendar_thisweek.json
- Documentation GitHub Actions (planification) : https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

Respecte les conditions d'utilisation et les limites de Forex Factory. Ce bot est un outil d'information, pas un conseil financier.
