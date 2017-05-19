# Acronym Processing

_Examples of pertinent acronyms_

    institutions : CNRS, CEA, INRIA, INSERM, CEMAGREF, INRA
    référentiels : RNSR, BCE, SIRET, FINESS
    divers : Conseil Général, Centre technique, Communauté urbaine

_Examples of organization labels found in data that could be matched by "acronym slot"_

UMR
    UMR728 INSERM Unité d'immuno-hématologie (UIH) and laboratoire d'hématologie, Hôpital St-Louis, AP-HP
    Laboratoire de Géographie Physique, Environnements Quaternaires et Actuels, UMR8591 CNRS, Meudon, France
    ANTE-INSERM U836, équipe 11, Fonctions cérébrales et neuromodulation

CHU
    AP-HP Hôpital Universitaire Pitié Salpêtrière

## Implementation method

Steps 1.x operate on "reference" data, steps 2.y and after on "source" data.

### 1.a Collect Acronyms from Reference

This step collects all acronyms with length within given bounds (e.g. [3, 6]) and tallies their occurrences

Output fields: 

    acronym|refOccurrences

Usage to produce refFile.acro:

    $collect_acronyms.sh refFile

### 1.b Collect Expansions from Reference

This step collects all expansions associated to an acronym produced in step 1.a, and tallies their occurrences along with distance from the acronym (with dist >= 0 if it occurs in a neighborhood, we cap at maxDist e.g. maxDist=10, 0 means just before or after the acronym, and -1 means outside a neighborhood). Note we print the distance for each and every occurrence. This distance then allows to score ambiguous expansions, e.g. by summing over 1/2^dist with dist=maxDist if outside neighborhood. 

The acronyms file is modified in place, with output fields: 

    acronym|refOccurrences|expansion_1|dist_1|...|dist_k1
    acronym|refOccurrences|expansion_2|dist_1|...|dist_k2

Use the -ce or --collect_expansions option (along with -f0 for the reference acronyms file):

    python acronyms.py -ce -f0 refFile.acro < refFile

### 1.c Check Reference for Ambiguous Expansions

This step checks for ambiguities in acronym expansions produced by step 1.b: it computes the score for each (acronym, expansion) pair, which enables sorting ambiguous acronyms. It comes with two options, one (-sa or --show_ambiguous) to just display a message and produce the sorted output, the other (-da or --delete_ambiguous) to remove duplicate expansions.

The acronyms file is modified in place, with the same output fields as in step 1.b, but with unique values of the first field (acronym) if option -da is used.

Usage to show ambiguous expansions:

    python acronyms.py -sa -f0 refFile.acro

Usage to delete ambiguous expansions:

    python acronyms.py -da -f0 refFile.acro

### 1.d Check Reference for Ambiguous Acronyms

This step checks for acronyms that are either common words (e.g. CAT, DOG, etc.) or known acronyms we want to exclude (e.g. in the scenario we are not interested in acronyms of the geopolitical or military domains, we want to exclude an acronym like "NATO" which is likely non-ambiguous and will thus refer to an irrelevant concept).

Note that a pattern like a common word "masquerading as an acronym" might just indicate someone writing in all-caps (ideally step 1.a should bail out if most of the input data is capitalized, this would be easy but still require changing our little bash script...)

### 2.a Collect Acronyms from Source

Same as step 1.a, but on source (a.k.a. messy or ugly) data.

Usage to produce srcFile.acro:

    $collect_acronyms.sh srcFile

### 2.b Collect Expansions from Source

This step counts occurrences of every acronym belonging to the input acronyms file. It shows expansions of those acronyms, whether in the neighborhood or outside, both the expansions that are in the acronyms file and those outside (in other words, ambiguities in the source file). Note it can thus operate on the output file produced by any of the steps 1.x since comparison to reference acronyms will only be done in step 2.c.

It is similar to step 1.b except that it takes a parameter (the reference acronyms file) containing acronyms to filter against.

The source acronyms file is modified in place, with the same output fields as in step 1.b but based on the source data: 

    acronym|srcOccurrences|expansion_1|dist_1|...|dist_n1
    acronym|srcOccurrences|expansion_2|dist_1|...|dist_n2

Use the -f1 argument to point to the source acronyms file produced in step 2.a (and as previously, -f0 for the reference acronyms file):

    python acronyms.py -ce -f0 refFile.acro -f1 srcFile.acro < srcFile

### 2.c Check Source for Unexpected Expansions

This steps checks for unexpected expansions found in the source file, i.e. either expansions that did not appear in the source (in case ambiguous source acronyms have not been deleted in step 3) or those that did not appear as primary expansion in the source (in case step 3 has deleted secondary expansions).

The source acronyms file is modified in place, with the same output fields as in step 1.c which operated on the reference acronyms file.

Usage to show unexpected expansions:

    python acronyms.py -su -f0 refFile.acro -f1 srcFile.acro

Usage to delete unexpected expansions:

    python acronyms.py -du -f0 refFile.acro -f1 srcFile.acro

### 2.d Check Source for Ambiguous Acronyms

This will operate exactly like step 1.d (though neither of these two steps has been implemented...)
