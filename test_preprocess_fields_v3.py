#!/usr/bin/env python3
# coding=utf-8

import unittest, logging, functools, sys, re
from collections import defaultdict
from preprocess_fields_v3 import *

class TestCustomDateMatcher(CustomDateMatcher):
	def __init__(self):
		super(TestCustomDateMatcher, self).__init__()
		self.matches = defaultdict(set)
	def match(self, v):
		self.matches.clear()
		super(TestCustomDateMatcher, self).match(Cell(v, self.t))
	def registerFullMatch(self, c, t, ms, hit = None): 
		m = hit if hit else c.value
		print('Full match on "{}": "{}" ({})'.format(c.value, m, ms))
		self.matches[t].add(stripped(m))
	def registerPartialMatch(self, c, t, ms, hit, span): 
		print('Partial match on "{}": "{}" [{}, {}] ({})'.format(c.value, hit, span[0], span[1], ms))
		self.matches[t].add(stripped(hit))

class TestRegexMatcher(RegexMatcher):
	def __init__(self, t, p, g = 0, ignoreCase = False, partial = False, validator = None, neg = False, wordBoundary = True):
		super(TestRegexMatcher, self).__init__(t, p, g, ignoreCase, partial, validator, neg, wordBoundary)
		self.matches = defaultdict(set)
	def match(self, v):
		self.matches.clear()
		super(TestRegexMatcher, self).match(Cell(v, self.t))
	def registerFullMatch(self, c, t, ms, hit = None): 
		if not self.validateHit(hit): return
		m = hit if hit else c.value
		print('Full match on "{}": "{}" ({})'.format(c.value, m, ms))
		self.matches[t].add(stripped(m))
	def registerPartialMatch(self, c, t, ms, hit, span): 
		if not self.validateHit(hit): return
		print('Partial match on "{}": "{}" [{}, {}] ({})'.format(c.value, hit, span[0], span[1], ms))
		self.matches[t].add(stripped(hit))

class TestLabelMatcher(LabelMatcher):
	def __init__(self, t, lexicon, mm):
		super(TestLabelMatcher, self).__init__(t, lexicon, mm)
		self.matches = defaultdict(set)
	def match(self, v):
		self.matches.clear()
		super(TestLabelMatcher, self).match(Cell(v, self.t))
	def registerFullMatch(self, c, t, ms, hit = None): 
		m = hit if hit else c.value
		print('Full match on "{}": "{}" ({})'.format(c.value, m, ms))
		self.matches[t].add(stripped(m))
	def registerPartialMatch(self, c, t, ms, hit, span): 
		print('Partial match on "{}": "{}" [{}, {}] ({})'.format(c.value, hit, span[0], span[1], ms))
		self.matches[t].add(stripped(hit))

class TestTokenizedMatcher(TokenizedMatcher):
	def __init__(self, t, lexicon, maxTokens = 0, scorer = tokenScorer):
		super(TestTokenizedMatcher, self).__init__(t, lexicon, maxTokens, scorer)
		self.matches = defaultdict(set)
	def match(self, v):
		self.matches.clear()
		super(TestTokenizedMatcher, self).match(Cell(v, self.t))
	def registerFullMatch(self, c, t, ms, hit = None): 
		m = hit if hit else c.value
		print('Full match on "{}": "{}" ({})'.format(c.value, m, ms))
		self.matches[t].add(stripped(m))
	def registerPartialMatch(self, c, t, ms, hit, span): 
		print('Partial match on "{}": "{}" [{}, {}] ({})'.format(c.value, hit, span[0], span[1], ms))
		self.matches[t].add(stripped(hit))

class TestCustomAddressMatcher(CustomAddressMatcher):
	def __init__(self):
		super(TestCustomAddressMatcher, self).__init__()
		self.matches = defaultdict(set)
	def match(self, v):
		self.matches.clear()
		super(TestCustomAddressMatcher, self).match(Cell(v, self.t))
	def registerFullMatch(self, c, t, ms, hit = None): 
		m = hit if hit else c.value
		print('Full match on "{}": "{}" ({})'.format(c.value, m, ms))
		self.matches[t].add(stripped(m))
	def registerPartialMatch(self, c, t, ms, hit, span): 
		print('Partial match on "{}": "{}" [{}, {}] ({})'.format(c.value, hit, span[0], span[1], ms))
		self.matches[t].add(stripped(hit))

class TestFrenchAddressMatcher(FrenchAddressMatcher):
	def __init__(self):
		super(TestFrenchAddressMatcher, self).__init__()
		self.matches = defaultdict(set)
	def match(self, v):
		self.matches.clear()
		super(TestFrenchAddressMatcher, self).match(Cell(v, self.t))
	def registerFullMatch(self, c, t, ms, hit = None): 
		m = hit if hit else c.value
		print('Full match on "{}": "{}" ({})'.format(c.value, m, ms))
		self.matches[t].add(stripped(m))
	def registerPartialMatch(self, c, t, ms, hit, span): 
		print('Partial match on "{}": "{}" [{}, {}] ({})'.format(c.value, hit, span[0], span[1], ms))
		self.matches[t].add(stripped(hit))

class ParseValuesTestCase(unittest.TestCase):

	def checkMatcher(self, tm, pairs):
		for (value, ref) in pairs:
			tm.match(value)
			if ref:
				self.assertTrue(tm.t in tm.matches, '{} missed a match of type {} for input "{}"'.format(tm, tm.t, value))
				self.assertTrue(stripped(ref) in tm.matches[tm.t], '{} missed "{}" match for input "{}"'.format(tm, ref, value))
			else:
				self.assertTrue(len(tm.matches) < 1, '{} produced false positive for input "{}": {}'.format(tm, value, tm.matches))

	def testSIRENMatcher(self):
		self.checkMatcher(TestRegexMatcher(F_SIREN, "[0-9]{9}", validator = validateLuhn), [
			('542065479', '542065479'),
			('780129987', '780129987'),
			('130015332', '130015332'),
			('130015334', None),
			('267500452', '267500452'),
			('775664113', '775664113')])
		self.checkMatcher(TestRegexMatcher(F_SIREN, "[0-9]{9}", partial = True, validator = validateLuhn), [
			('this... 542065479 and after', '542065479'),
			('some stuff before 780129987 "(sur Matriel d?Injection Standard"', '780129987'),
			('blabla 130015332 ou alors 130152 ...', '130015332')])
	
	def testSIRETMatcher(self):
		self.checkMatcher(TestRegexMatcher(F_SIRET, "[0-9]{14}", validator = validateLuhn), [
			('58201495700259', '58201495700259'),
			('40986970800019', '40986970800019'),
			# ('49859345800025', '49859345800025'),
			('49859345800026', None)])

	def testVariantExpansion(self):
		self.checkMatcher(VariantExpander(fileToVariantMap('resource/etab_enssup.syn'), F_MESR, False, targetType = F_ETAB_ENSSUP), [
			('ESPCI, 10 rue Vauquelin, 75231 Paris cedex 05', 'Ecole Superieure de Physique et Chimie Industrielles [ESPCI]'),
			('Espace de sciences Pierre-Gilles de Gennes - ESPCI Paristech', 'Ecole Superieure de Physique et Chimie Industrielles [ESPCI]')
			])
		self.checkMatcher(VariantExpander(fileToVariantMap('resource/org_societe.syn'), F_ENTREPRISE, True), [
			('Nanovation SARL', 'Nanovation Société à responsabilité limitée')
			])


	def testPhytoMatcher(self):
		lm = TestLabelMatcher(F_PHYTO, fileToSet('resource/phyto'), MATCH_MODE_CLOSE)
		self.checkMatcher(lm, [
			('fury 10 EW', 'FURY 10 EW'),
			('kart', 'KART'),
			('CAREMBA star', 'CARAMBA STAR')
			# ('CHORTOLOURN', 'chlortoluron')
		])
		tm = TestTokenizedMatcher(F_PHYTO, fileToSet('resource/phyto'))
		self.checkMatcher(tm, [
			('furi', 'FURY 10 EW'),
			# ('CAREMBA', 'CARAMBA STAR'),
			('VACCI PLANT', 'VACCIPLANT GRANDES CULTURES'),
			('VACCIPLANT', 'VACCIPLANT GRANDES CULTURES'),
			('vacciplant', 'VACCIPLANT GRANDES CULTURES')
			# ('vacciplante', 'VACCIPLANT GRANDES CULTURES')
			# ('psychocelle', 'CYCOCEL C5 BASF')
		])

	def testAPBMatcher(self):
		am = TestTokenizedMatcher(F_APB_MENTION, fileToSet('resource/mention_licence_apb2017.col'), 
		maxTokens = 5)
		self.checkMatcher(am, [
		('Métiers de la chimie', 
			'Chimie'),
		('Langues étrangères appliquées - Anglais - Allemand', 
			'Langues étrangères appliquées'),
		('Langues, littératures & civilisations étrangères et régionales -  Italien', 
			'Langues, littératures et civilisations étrangères et régionales'),
		('Conception et Réalisation de Systèmes Automatiques - en apprentissage', 
			'Electronique, énergie électrique, automatique'),
		# ('Contrôle industriel et régulation automatique - en apprentissage', 
		# 	'Electronique, énergie électrique, automatique').
		('Contrôle industriel et régulation automatique', 
			'Electronique, énergie électrique, automatique')
		])

	def testCustomPersonNameParsing(self):
		for (src, refs) in [('Alain Schnapp', [('Alain', 'Schnapp')]),
									('Schnapp Alain', [('Alain', 'Schnapp')]),
									('BADIE Bertrand', [('Bertrand', 'BADIE')]),
									('BAKHOUCHE Béatrice', [('Béatrice', 'BAKHOUCHE')]),
									('Emmanuel WALLON (sous la direction de)', [('Emmanuel', 'WALLON')]),
									('Charles-Edmond BICHOT', [('Charles-Edmond', 'BICHOT')]),
									('Abdellah Bounfour, Kamal Naït-Zerrad et Abdallah Boumalk', [('Abdellah', 'Bounfour'), ('Kamal', 'Naït-Zerrad'), ('Abdallah', 'Boumalk')]),
									('Sylvie Neyertz et David Brown', [('Sylvie', 'Neyertz'), ('David', 'Brown')]),
									('Anne-Dominique Merville & Antoine COPPOLANI', [('Anne-Dominique', 'Merville'), ('Antoine', 'COPPOLANI')]),
									('Justine, J.-L.', [('Justine', 'J.-L.')]),
									('J.P. Poly', [('J.P.', 'Poly')]),
									('Dominique Kalifa', [('Dominique', 'Kalifa')]),
									('S. CHAKER (Dir.)', [('S.', 'CHAKER')]),
									('Schreck E., Gontier L. and Treilhou M.', [('E.', 'Schreck'), ('L.', 'Gontier'), ('M.', 'Treilhou')]),
									]:
			parsedList = customParsePersonNames(src)
			print(parsedList)

	def testPersonNameParsing(self):
		for (src, refs) in [('Alain Schnapp', [('Alain', 'Schnapp')]),
									('Schnapp Alain', [('Alain', 'Schnapp')]),
									('BADIE Bertrand', [('Bertrand', 'BADIE')]),
									('BAKHOUCHE Béatrice', [('Béatrice', 'BAKHOUCHE')]),
									# ('Emmanuel WALLON (sous la direction de)', [('Emmanuel', 'WALLON')]),
									('Charles-Edmond BICHOT', [('Charles-Edmond', 'BICHOT')]),
									('Abdellah Bounfour, Kamal Naït-Zerrad et Abdallah Boumalk', [('Abdellah', 'Bounfour'), ('Kamal', 'Naït-Zerrad'), ('Abdallah', 'Boumalk')]),
									('Sylvie Neyertz et David Brown', [('Sylvie', 'Neyertz'), ('David', 'Brown')]),
									('Anne-Dominique Merville & Antoine COPPOLANI', [('Anne-Dominique', 'Merville'), ('Antoine', 'COPPOLANI')]),
									('Justine, J.-L.', [('Justine', 'J.-L.')]),
									('J.P. Poly', [('J.P.', 'Poly')]),
									('Dominique Kalifa', [('Dominique', 'Kalifa')]),
									('S. CHAKER (Dir.)', [('S.', 'CHAKER')]),
									('Schreck E., Gontier L. and Treilhou M.', [('E.', 'Schreck'), ('L.', 'Gontier'), ('M.', 'Treilhou')]),
									]:
			parsedList = parsePersonNames(src)
			self.assertTrue(len(parsedList) == len(refs), 'Could not parse exactly {} person names from {}'.format(len(refs), src))
			foundList = sorted(list([(justCase(i[0][F_FIRST]), justCase(i[0][F_LAST])) for i in parsedList])) # A list of (first name, surname) pairs
			expectedList = sorted(list([(justCase(ref[0]), justCase(ref[1])) for ref in refs]))
			for i, found in enumerate(foundList):
				self.assertEqual(found, expectedList[i], 'Name mismatch: expected {}, found {}'.format(expectedList[i], found))
			self.assertEqual(foundList, expectedList,'Name list mismatch')

	def testCustomDateMatcher(self):
		self.checkMatcher(TestCustomDateMatcher(), [
			('20/03/1954', '20/03/1954'),
			('26/10/1945', '26/10/1945'),
			('01-06-1967', '01/06/1967'),
			('06/01/1967', '06/01/1967'),
			('Lyon', None)
		])

	def testEmailRegex(self):
		for v in ['HERBIERS@univ-bpclermont.fr',
			'ddp15@ac-clermont.fr',
			'Hubert.Heckmann@univ-rouen.fr',
			'Library@obs.univ-lyon1.fr',
			#	'Renseignements auprès du peb sciences : PEB.sciences@clermont-universite.fr'
			]:
			m = re.search(EMAIL_PATTERN + '$', v, 0)
			self.assertTrue(m, 'Could not match email %s' % v)

	def testAddressMatchers(self):
		matcherLibparse = TestCustomAddressMatcher()
		matcherBAN = TestFrenchAddressMatcher()
		# addrList = fileToList('test_data/addresses.to_normalize')
		addrLists = { 
			'fr' : ([matcherLibparse, matcherBAN], [
					'1 avenue Bourgelat, 69280 Marcy l Etoile',
					'149 rue de Bercy, F-75595 Paris',
					'UFR STAPS 118 route de Narbonne 31062 Toulouse Cedex',
					'P. Grousset Allée P. Grousset Pôle Campus Universitaire - Le Bailly Bâtiment UFR des Sciences du Sports AMIENS CEDEX 1 80025',
					'Inria Bordeaux',
					'Site Schuman - 3 avenue Robert Schuman 13628 Aix-en-Provence Cedex 01Site Canebière - 110-114 La Canebière 13001 MarseilleSite d’Arles - Espace Van Gogh 13200 Arles',
					'Messimy sur Saône',
					'75019;PARIS',
					'18 rue des Pins, 11570 Cazilhac, France',
					'Campus de Beaulieu 35042 Rennes cedex'
			]),
			'row': ([matcherLibparse], [
					'3Department of Atmospheric and Oceanic Sciences, University of California, Los Angeles, CA 90095-1565, USA'
			])
		}
		for (matchers, addrList) in addrLists.values():
			for addr in addrList:
				for matcher in matchers:
					ms = matcher.match(addr)
					# self.assertTrue(ms is not None, '{}: could not parse address: {}'.format(matcher, addr))
					print('{}: parse of "{}"'.format(matcher, addr))
					if ms is None:
						print('Failed!')
					else: 
						for (k, v) in ms.iteritems(): print(k.rjust(20), v.ljust(40))

if __name__ == '__main__':
	logging.basicConfig(filename = 'log/test_preprocess_fields_v3.log', level = logging.DEBUG)
	# unittest.main()
	suite = unittest.TestSuite()
	suite.addTest(ParseValuesTestCase("testAddressMatchers"))
	runner = unittest.TextTestRunner()
	runner.run(suite)
