#!/usr/bin/python
# coding=utf-8

import unittest, logging
import link_field, vocab_lookup
from collections import defaultdict

TEST_PAIRS = {

	'data/produit_phyto.acta.ref': [ # Corpus ACTA
		('furi', 'FURY 10 EW'),
		('CAREMBA', 'CARAMBA STAR'),
		('kart', 'KART'),
		# 'psychocelle', 'CYCOCEL C5 BASF'),
		('VACCI PLANT', 'VACCIPLANT GRANDES CULTURES'),
		('CHORTOLOURN', 'chlortoluron'),
		('VACCIPLANT', 'VACCIPLANT GRANDES CULTURES'),
		('vacciplante', 'VACCIPLANT GRANDES CULTURES')],

	'data/mention_licence.sise.ref': [ # Corpus APB
		('Métiers de la chimie', 
			'Chimie'),
		('Langues étrangères appliquées - Anglais - Allemand', 
			'Langues étrangères appliquées'),
		('Langues, littératures & civilisations étrangères et régionales -  Italien', 
			'Langues, littératures et civilisations étrangères et régionales'),
		('Conception et Réalisation de Systèmes Automatiques - en apprentissage', 
			'Electronique, énergie électrique, automatique'),
		('Contrôle industriel et régulation automatique', 
			'Electronique, énergie électrique, automatique'),
		('Contrôle industriel et régulation automatique - en apprentissage', 
			'Electronique, énergie électrique, automatique')],

	# The system was incorrectly returning: PORT D'ENVAUX|LES AUTHIEUX SUR LE PORT ST OUEN|4
	'data/commune.insee.ref': [ # Corpus INSEE
		('PORT D\'ENVAUX', 'PORT D ENVAUX')]

}

TEST_TRUTHS = {
	# 'data/produit_phyto.acta.ref': 'data/produit_phyto.acta.gold',
	'data/commune.insee.ref': 'data/commune.acta.gold'
	# 'data/titre_revue.scopus.ref': 'data/titre_revue.publis2011.gold'
}

class TestFieldLinkage(unittest.TestCase):

	def checkOneResult(self, ms, srcTerm, refTerm, referential, checkTerm = True, checkFirstRank = False):
		matchCount = len(ms)
		self.assertTrue(len(ms) >= 1, 'No match found for %s, expected %s' % (srcTerm, refTerm))
		foundTerm = ms[0][0]
		sortedTerms = sorted([(referential.termByUid[uid], s) for (uid, s) in ms], key = lambda p: p[1], reverse = True)
		foundTerms = list([p[0] for p in sortedTerms])
		if checkTerm:
			self.assertTrue(refTerm in foundTerms, 
				'Incorrect result for input %s: expected "%s", found "%s"' % (srcTerm, refTerm, '; '.join(foundTerms)))
		if checkFirstRank:
			self.assertTrue(refTerm == foundTerms[0],
				'Incorrect result for input %s: "%s" not ranked first, preceded by "%s"' % (srcTerm, refTerm, foundTerms[0]))

	def testNormalizeAndValidateTokens(self):
		pairs = [
			('Sciences de l’homme, anthropologie, ethnologie', ['sciences', 'homme', 'anthropologie', 'ethnologie'])
		]
		for (phrase, expected) in pairs:
			logging.debug('Checking normalization of phrase: %s' % phrase)
			found = vocab_lookup.normalizeAndValidateTokens(phrase)
			self.assertFalse(set(found) ^ set(expected), 'Invalid tokenization: %s --> %s' % (phrase, '|'.join(found))) 

	def testPairs(self):
		for refFileName, pairs in TEST_PAIRS.iteritems():
			logging.info('Testing %d dirty/clean pairs in %s' % (len(pairs), refFileName))
			referential = link_field.Referential(refFileName)
			for (term, ref) in pairs:
				ms = list(referential.matchScore(term))
				logging.debug('match scores for %s : %s' % (term, ' | '.join(['%s(%d)' % (s[0], s[1]) for s in ms])))
				self.checkOneResult(ms, term, ref, referential, checkTerm = True, checkFirstRank = False) # TODO check 1st rank!!!

	def testAcronymMatching(self):
		pairs = [('LEA Anglais, Chinois', 'Langues étrangères appliquées')]
		trainFileName = 'data/mention_licence.apb.src'
		refFileName = 'data/mention_licence.sise.ref'
		trainPhrases = list(link_field.fileValueiterator(trainFileName))
		referential = link_field.Referential(refFileName)
		acronyms = referential.findAcronyms(trainPhrases, refFileName)
		for (term, ref) in pairs:
			ms = list(referential.matchScore(term, acronyms))
			self.checkOneResult(ms, term, ref, referential, checkTerm = True, checkFirstRank = False)

	# @unittest.skip('TOO LONG')
	def testForGold(self):
		for (refFileName, goldFileName) in TEST_TRUTHS.iteritems():
			referential = link_field.Referential(refFileName, True)
			logging.info('Testing truth file %s against referential %s' % (goldFileName, refFileName))
			result = defaultdict(int)
			for r in link_field.fileRowIterator(goldFileName, sep = '\t'):
				if len(r) < 1 or not link_field.isValidValue(r[0]): continue
				term = r[0]
				result['total'] += 1
				if len(r) > 1 and link_field.isValidValue(r[1]):
					ref = r[1]
					result['truth'] += 1
					ms = list(referential.matchScore(term))
					matchCount = len(ms)
					try: 
						self.checkOneResult(ms, term, ref, referential, checkTerm = True, checkFirstRank = False)
						result['correct'] += 1
					except AssertionError, e:
						print str(e)
			link_field.dumpStats(result)
	
if __name__ == '__main__':
	logging.getLogger().level = logging.DEBUG
	# unittest.main()
	suite = unittest.TestSuite()
	suite.addTest(TestFieldLinkage("testAcronymMatching"))
	runner = unittest.TextTestRunner()
	runner.run(suite)
