# Documentation des modules d'inférence / normalisation / référencement

----

## Module 4 : Inférence de types

### Heuristiques d'inférence de type de champ et leurs paramètres

Sortie de chaque heuristique :
* un type `InferredType`
* une plausibilité `Score`
* un type de correspondance `Exact` / `Included` (correspondant pour une regex à un match complet vs. un match sur une sous-chaïne)

__Par regex__

Paramètres:
* minPrecision (pas de défaut car trop spécifique, sinon commencer par 90%, proportion dans l'input qui ont matché avec au moins une regex, attention : mettre très faible si l'ensemble de regex est non exhaustif !)

    score := precision

__Par libellé__

Méthode : on fait un lookup de chaque valeur - sans tokenisation ! - contre un ensemble de valeurs de références)

Paramètres:
* `maxDistance` (2 par défaut, i.e. distance de Levenshtein autorisée entre les 2 chaînes entières)
* `minPrecision` (pas de défaut car trop spécifique, sinon commencer par 60%, proportion de valeurs qui ont matché - approché ou exact - avec au moins une valeur de référence, attention : mettre très faible sauf si l'ensemble de valeurs de référence est exhaustif !)
* `minCoverage` (0 par défaut, proportion dans la liste de valeurs de référence qui ont eu un match, attention : mettre 0 sauf si l'ensemble de valeurs en entrée est supposé exhaustif, ce que l'on ne sait pas en général !)

    score := precision si minCoverage = 0
             precision * (coverage / minCoverage) si minCoverage > 0

__Par lexique__ 

Méthode : chaque valeur contient au moins un - ou quelques - token parmi un vocabulaire de référence, e.g. une adresse va quasi toujours contenir un type de voie, et ce critère est assez spécifique pour identifier une adresse, voire une voie.

Paramètres:
* `maxDistance` (0 par défaut, car le vocabulaire est contrôlé donc on devrait y inclure synonymes, abréviations et autres variantes comme typos les plus fréquentes, de plus a priori le nombre d'occurrences de chaque token du vocabulaire devrait être >> 1 donc quelques erreurs peuvent être ignorées)
* `minPrecision` (pas de défaut car trop spécifique, sinon commencer par 90%, proportion de valeurs qui ont matché - approché ou exact - avec au moins minTokens tokens de référence, en général le vocabulaire sera quasi-exhaustif sinon mettre une minPrecision assez faible)
* `minTokens` (1 par défaut, le nombre de tokens à trouver parmi les références)

    score := precision

__Méthode générale (Matching partiel)__

Si T1, ..., Tk sont des composantes du type T0, on tente dans l'ordre :
- matches complets sur T0
- sinon, matches complets sur le sous-type T1, ..., Tk (si à la fois une sous-composante et le type de base ont matché, on garde les deux même car on ne vise pas la spécificité comme pour une relation de subsumption)
- si ni T0 ni aucune des composantes n'a matché, on teste les matches partiels pour chacun des sous-types. Le score renvoyé est pondéré par le nombre de sous-types ayant matché, autrement dit on utilise la même pondération sur les composantes Ville, CP, Voie, etc. d'une adresse : cela offre l'avantage de fournir une relation d'ordre cohérente sur les champs composites quels que soient les seuils de précision individuels, par exemple une source où Ville et CP ont matché aura toujours un score plus élevé qu'une source où seule Ville a matché, soit un critère assez logique.

__Documentation__

Outre la documentation présente dans le code Python, j'ai implémenté deux mécanismes de génération de doc  graphique de facon automatique (c'est-à-dire que cette doc sera toujours à jour vis-à-vis du code source du module en question), respectivement aux formats
- GraphViz (converti en PNG par exemple)
- JavaScript (pour un rendu sur navigateur). 

Chacun de ces mécanismes produit deux graphiques, l'un montrant tous les types du modèle de données supportés par le module d'inférence de types (fichier `metamodel`) et l'autre étant une légende expliquant les codes couleurs et les formes utilisés dans le premier (fichier `metamodel_legend`).

A titre informatif, en date du 22 mars, les types de colonnes suivants sont reconnus (liste mise à plat, c'est-à-dire que les types parent et enfant apparaissent successivement) :

*  Adresse
*  Titre de personne
*  Code INSEE personnel
*  NIR
*  URL
*  Email
*  Téléphone
*  Pays
*  Institution
*  Nom d'organisation
*  Code Postal
*  Ville
*  Département
*  Région
*  Voie
*  Numéro National de Structure
*  Prénom
*  Nom de personne
*  Date
*  Année
*  SIREN
*  SIRET
*  UAI
*  Numéro UMR
*  Structure de recherche
*  Partenaire de recherche
*  Institution de recherche
*  Etablissement
*  Mention APB
*  Domaine de Recherche
*  Code Postal
*  DOI
*  ISSN
*  Titre de revue
*  Bibliographie
*  Publication
*  Nom d'essai clinique
*  Spécialité médicale
*  Phyto
*  Abstract

__Détails d'implémentation__

On a implémenté entre autres fonctionnalités :
- des codes de contrôle pour valider certains types (SIREN/SIRET, numéro INSEE, etc.)
- différentes méthodes de matching :
    * exact ou approché
    * sur l'intégralité de chaque valeur ou des portions seulement
    * à partir de valeurs tokénisées ou considérées comme une simple chaîne de caractères (noter que la tokénisation utilisée comporte une part de _stemming_ et permet donc de capturer la plupart des variantes syntaxiques ou dérivationnelles comme les conjugaisons et déclinaisons)
- Support pour les acronymes et abréviations :
    * pour certains types de champs, une liste d'acronymes, abréviations ou synonymes est disponible
    * pour d'autres types de champs, une collecte automatique d'acronymes est implémentée (mais pas d'autres variantes comme les synonymes)

----

## Module 5: Normalisation de valeurs

Comme le système gère des types complexes (soit composites e.g. une adresse qui contient voie/ville/CP/etc., soit hiérachiques e.g. un identifiant d'entreprise qui peut être SIRET/SIREN/etc.), et que le but est aussi d'enrichir les données, le mécanisme de normalisation d'une valeur de champ produit en sortie :
- la valeur du champ normalisée intégralement
- une valeur pour chaque sous-élément si le type est composite (ainsi on aura `Adresse.Voie`, `Adresse.Ville`, `Adresse.CodePostal`, etc. pour une adresse, ou encore `Personne.Prenom`, `Personne.Nom`, `Personne.Titre` pour un nom de personne)
- une valeur pour chaque sous-type t1 si le type est un super-type t0 (cette valeur sera nulle si la valeur originale n'est pas du type t1, mais d'un autre type t2)
- des enrichissements éventuels (mais seulement dans le cas où ces enrichissements sont disponibles à ce stade, car la phase d'enrichissement proprement dite, à la base de jointures avec des référentiels internes ou externes, intervient ultérieurement)

Les classes implémentées actuellement (22 mars) sont :

* `PersonNameNormalizer`  utilise mon propre code de parsing et normalisation (titres de personne, prénom, patronyme)
* `AddressNormalizer` utilise https://github.com/openvenues/pypostal (bindings Python de la librairie libpostal). J'ai fait des expérimentations avec mon propre code (espérant bénéficier d'une majorité d'adresses françaises donc avec un format spécifique : pas de nom d'État comme aux USA, etc.) et quelques autres librairies externes, et libpostal semble être la plus robuste, à condition de bien gérer les différents paramètres (par exemple, préciser si le pays doit figurer en sortie dans l'adresse normalisée)
* `TelephoneNormalizer` utilise https://github.com/daviddrysdale/python-phonenumbers (port Python de la librairie libphonenumber de Google)
* `DateNormalizer` utilise le package Python dateparser. La seule difficulté réside dans les cas ambigüs, par exemple quand une partie des données d'une colonne utilise l'ordre DMY (i.e. à la française ou anglais britannique) et une autre partie l'ordre MDY (mois avant le jour, à la mode US), dans ce cas la meilleure heuristique consiste à prendre le format majoritaire pour les valeurs ambigües.
* `BiblioNormalizer` (pas encore activé) utilise du code de parsing de références bibliographiques ad-hoc, à améliorer.

__Détails d'implémentation__

Patterns pour les noms de personnes:
<Last>
<Last> <First>
<First> <Last>
<FirstInitial> <Last>
<Last> <FirstInitial>
LIST_OF<Person> (with any kind of delimiter)