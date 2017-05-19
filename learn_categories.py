#!/usr/bin/python
# coding=utf-8

import csv, logging, optparse
from pattern.vector import Document, NB
from pattern.db import csv
from infer_types_v2 import toASCII

def learnCategories(tn):
	nb = NB()
	for (cat, content) in csv('resource/%s.catdata' % tn, separator = ';', headers = True):
		if not cat or not content: continue
		t = cat # toASCII(cat)
		v = Document(content, type = t, stemmer = None, stopwords = False, language = 'fr') 
		nb.train(v)
	# cr = csv('resource/%s.catdata' % tn, separator = ';', headers = True)
	# for (i, r) in enumerate(cr):
	# 	v = Document(str(i), type = r[0], stemmer = None, stopwords = False, language = 'fr') 
	# 	nb.train(v)
	logging.info('TRAINED %s on %d categories', tn, len(nb.classes))
	nb.save('resource/%s.classifier' % tn)

if __name__ == '__main__':
	logging.basicConfig(filename='log/learn_categories.log',level=logging.DEBUG)
	parser = optparse.OptionParser()
	parser.add_option("-t", "--type", dest = "typeName",
					  help = "name of the classifier file that will be produced")
	(options, args) = parser.parse_args()
	tn = options.typeName
	learnCategories(tn)