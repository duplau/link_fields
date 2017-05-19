#!/usr/bin/python
# coding=utf-8

import optparse, sys, preprocess_fields_v2, vocab_lookup
from functools import partial
from pattern.en import ngrams

def acronymizeTokens(tokens, minAcroSize, maxAcroSize):
	for s in range(max(minAcroSize, len(tokens)), min(maxAcroSize, len(tokens)) + 1):
		tl = tokens[:s]
		yield (''.join([t[0] for t in tl]).upper(), tl)

def acronymizePhrase(phrase, minAcroSize, maxAcroSize): 
	keepAcronyms = True
	tokens = vocab_lookup.normalizeAndValidateTokens(phrase, keepAcronyms)
	return acronymizeTokens(tokens, minAcroSize, maxAcroSize)

def noStopWordValidator(tokens, otc):
	''' otc is the original token count. '''
	return preprocess_fields_v2.isValidPhrase(tokens) and len(tokens) == otc

if __name__ == '__main__':
	reload(sys)  
	sys.setdefaultencoding('utf8')
	parser = optparse.OptionParser()
	parser.add_option("-c", "--count", dest = "doNgrams", action = "store_true", default = False,
					  help = "collect ngrams")
	parser.add_option("-a", "--acronyms", dest = "doAcronyms", action = "store_true", default = False,
					  help = "collect acronym/expansion pairs")
	parser.add_option("-k", "--nMin", dest = "nMin", type="int",
					  help = "min value of n (ngram or acronym size in tokens)")
	parser.add_option("-n", "--nMax", dest = "nMax", type="int",
					  help = "max value of n (ngram or acronym size in tokens)")
	parser.add_option("-s", "--src", dest = "srcFileName",
					  help = "source file")
	(options, args) = parser.parse_args()
	nMin = options.nMin if options.nMin else 1
	nMax = options.nMax if options.nMax else 3
	fileName = options.srcFileName
	for line in preprocess_fields_v2.fileToList(fileName):
		if options.doNgrams:
			for k in range(nMin, nMax + 1):
				for ngram in ngrams(line, k):
					phrase = ' '.join(ngram)
					nvp = preprocess_fields_v2.normalizeAndValidatePhrase(phrase, phraseValidator = partial(noStopWordValidator, otc = k))
					if nvp is not None: print phrase
		elif options.doAcronyms:
			for (acro, tokens) in acronymizePhrase(line, nMin, nMax): 
				print '|'.join([acro, ' '.join(tokens)])
