# Split Stack

Site vitrine rendu côté serveur, avec un back-office pour gérer les contenus.

## Sommaire

- Présentation
- Démarrage
- Commandes
- Architecture
- Contenus
- Sécurité
- Méthode
- Feuille de route
- Suivi

## Présentation

Le site présente l'équipe, les actualités et les projets.
Les pages sont rendues côté serveur pour le référencement.
Les animations utilisent une scène 3D en arrière-plan.
Le back-office permet de modifier les pages et les actualités.

## Démarrage

Prérequis : Node 20 et Docker.

```bash
npm install
npm run dev
make up
make migrate
```

## Commandes

| Commande | Rôle |
|---|---|
| `npm run dev` | serveur de développement |
| `npm run build` | construction de production |
| `npm run typecheck` | vérification des types |
| `npm test` | tests unitaires |
| `npm run test:e2e` | tests de bout en bout |
| `make up` | démarre les conteneurs |
| `make migrate` | applique les migrations |

## Architecture

- Front : Nuxt 4 à la racine du dépôt (`app/`).
- Back-office : Laravel 11 et Filament 3 dans `backend/`, exécutés dans Docker.
- Base de données : PostgreSQL 16, service `db`.
- Le service `api` monte le code du back-office dans le conteneur.

## Contenus

Les contenus sont des blocs ordonnés : texte, image, citation, vidéo.
Chaque page assemble ses blocs dans l'ordre choisi dans le back-office.
Les actualités ont un titre, un résumé, une image et une date.

## Sécurité

- Back-office protégé par mot de passe.
- Connexion OIDC prévue pour l'équipe.
- Formulaire de contact prévu, avec protection contre les envois automatiques.

## Méthode

Les fonctionnalités seront décrites avec Spec Kit avant d'être développées.

## Feuille de route

- L'API publique sera déplacée dans `apps/api/` (à venir).
- Le front rejoindra un dépôt unique avec le back-office.
- Les contenus seront traduits en anglais.

## Suivi

- [x] Mise en page générale
- [x] Scène 3D
- [x] Liste des actualités
- [x] Back-office
- [ ] TODO : écrire `ContentBlock.vue` pour afficher les blocs de contenu.
- [x] Page de contact

Projet privé.
