# Feature Specification: Validateur de schémas sans dépendance

**Feature Branch**: `feat/p1-1-validate`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "P1.1 — Validateur de schémas sans dépendance. Valide les documents PEO contre les schémas de src/peo/schemas/ en implémentant exactement le sous-ensemble NF2. Un mot-clé hors sous-ensemble dans un schéma est une erreur au chargement. Erreurs renvoyées avec chemin JSON et code stable. Critère d'acceptation : test A2.6, même verdict que jsonschema sur tous les fichiers de examples et invalid."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Valider un document PEO sans dépendance (Priority: P1)

Un composant de PEO (catalogue, discovery, plan, verrou, journal) doit savoir si un document respecte son schéma, sans qu'aucune bibliothèque tierce ne soit installée chez l'utilisateur.

**Why this priority**: tous les fichiers écrits ou lus par PEO sont validés ; sans ce validateur, aucune fonctionnalité en aval ne peut garantir ses entrées (NF1, NF2).

**Independent Test**: valider chaque fichier de `examples/` et `invalid/` et comparer le verdict à celui de l'oracle de référence (A2.6, SC-001).

**Acceptance Scenarios**:

1. **Given** un fichier de `docs/design/spec/schemas/examples`, **When** il est validé contre son schéma, **Then** aucune erreur n'est renvoyée.
2. **Given** un fichier de `docs/design/spec/schemas/invalid`, **When** il est validé, **Then** au moins une erreur est renvoyée, avec le même verdict que l'oracle de référence (SC-001).
3. **Given** un document avec plusieurs défauts, **When** il est validé, **Then** toutes les erreurs sont renvoyées dans un ordre stable.

---

### User Story 2 - Localiser et identifier chaque erreur (Priority: P2)

Un mainteneur de catalogue ou un autre composant doit savoir où et pourquoi un document est invalide.

**Why this priority**: `peo catalog validate` doit permettre de corriger une fiche en un seul passage.

**Independent Test**: valider un document comportant des erreurs imbriquées et vérifier chemin et code de chaque erreur.

**Acceptance Scenarios**:

1. **Given** une valeur invalide dans un tableau d'objets, **When** le document est validé, **Then** l'erreur porte le chemin JSON exact de la valeur (par exemple `/components/0/name`).
2. **Given** deux validations du même document invalide, **When** on compare les erreurs, **Then** elles sont identiques, chemins et codes compris.

---

### User Story 3 - Refuser un schéma hors sous-ensemble (Priority: P3)

Un mainteneur qui ajoute un mot-clé non pris en charge à un schéma doit en être averti immédiatement, et non découvrir plus tard qu'une contrainte n'est pas appliquée.

**Why this priority**: évite qu'un schéma soit silencieusement validé trop mollement.

**Independent Test**: charger des schémas contenant un mot-clé hors sous-ensemble ou une référence non locale.

**Acceptance Scenarios**:

1. **Given** un schéma contenant `format` ou `allOf`, **When** il est chargé, **Then** une erreur de schéma est levée avant toute validation de document.
2. **Given** un `$ref` non local ou non résolu, **When** le schéma est chargé, **Then** une erreur de schéma est levée.

---

### Edge Cases

- Booléen et entier : `true` n'est ni `integer` ni `number` ; `1.0` est un `integer`.
- `enum` et `const` ne confondent pas `true` et `1`.
- Un mot-clé qui ne concerne pas le type de l'instance (`minimum` sur une chaîne) est ignoré.
- Un mot-clé hors sous-ensemble situé dans une branche que le document ne visite pas est tout de même rejeté (erreur au chargement, pas à la traversée).
- Les clés contenant `/` ou `~` sont échappées dans les chemins JSON.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système MUST valider un document contre un schéma en n'employant que la bibliothèque standard.
- **FR-002**: Le système MUST implémenter exactement le sous-ensemble NF2 : `type`, `required`, `properties`, `additionalProperties` (`false` ou sous-schéma), `items`, `enum`, `const`, `pattern`, `minimum`, `minItems`, `$ref` local (`#/$defs/<nom>`), `$defs`, `oneOf`.
- **FR-003**: Le système MUST signaler comme erreur de schéma, au chargement du schéma, tout mot-clé hors sous-ensemble et tout `$ref` non local ou non résolu. Les annotations `$schema`, `$id`, `title`, `description` sont ignorées.
- **FR-004**: Le système MUST renvoyer toutes les erreurs de validation, chacune avec un chemin JSON (JSON Pointer) et un code stable, égal au mot-clé violé (`type`, `required`, `enum`, `const`, `pattern`, `minimum`, `minItems`, `additionalProperties`, `oneOf`).
- **FR-005**: Le système MUST renvoyer les erreurs triées de façon déterministe (NF8).
- **FR-006**: Le système MUST donner le même verdict que l'oracle de référence de A2.6 (SC-001) sur tous les fichiers de `docs/design/spec/schemas/examples` et `invalid` et sur les fichiers golden de `fx-epure`.
- **FR-007**: Le système MUST appliquer à `oneOf` la sémantique générale « exactement une alternative valide » sans contrôler sa forme : la restriction de NF2 décrit l'emploi qu'en font les schémas de PEO, et la parité avec l'oracle de référence (FR-006, SC-001) la garde.

### Key Entities

- **Schéma** : document JSON décrivant les contraintes d'un type de fichier PEO ; un des sept schémas livrés.
- **Erreur de validation** : chemin JSON de la valeur fautive, code stable (mot-clé violé), message lisible.
- **Erreur de schéma** : signal que le schéma lui-même sort du sous-ensemble ; distinct des erreurs de validation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des fichiers de `examples` et `invalid` (et les fichiers golden de `fx-epure`) reçoivent le même verdict que l'oracle de référence du test A2.6, la bibliothèque `jsonschema` (Draft 2020-12), utilisée en dépendance de développement uniquement.
- **SC-002**: aucune dépendance d'exécution n'est ajoutée au paquet.
- **SC-003**: la validation de deux exécutions successives du même document produit des listes d'erreurs identiques octet pour octet.
- **SC-004**: 100 % des mots-clés du sous-ensemble ont au moins un cas valide et un cas invalide testés.

## Assumptions

- Le contrat déjà décrit dans la spec 10 (section 4, « Contrat de `validate.py` ») reste la référence ; cette fonctionnalité le précise et l'étend si les clarifications ci-dessus l'exigent.
- `load_schema(name)` charge un schéma livré dans `src/peo/schemas/` ; `Schema.from_dict(d)` construit un schéma à partir d'un dictionnaire (cas de test). Les deux passent par le même contrôle du sous-ensemble, et `validate` n'accepte que `Schema`.
- Les fichiers TOML sont lus en amont ; le validateur ne reçoit que des documents déjà décodés.
- Les messages d'erreur sont en anglais (NF12) et ne font pas partie du verdict comparé à l'oracle (SC-001).
- L'implémentation existante (PR #3) valide actuellement le schéma à la traversée ; la présente spécification exige un contrôle complet au chargement.
