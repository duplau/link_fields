#!/bin/sh

python preprocess_fields.py -l > doc/metamodel_legend.gv
ccomps -x doc/metamodel_legend.gv | dot | gvpack -array3 | neato -Tpng -n2 -o doc/metamodel_legend.png 
python preprocess_fields.py -g > doc/metamodel.gv
ccomps -x doc/metamodel.gv | dot | gvpack -array3 | neato -Tpng -n2 -o doc/metamodel.png 
