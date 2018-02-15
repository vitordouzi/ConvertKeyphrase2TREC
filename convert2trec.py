import os, string, glob
from segtok.tokenizer import web_tokenizer, split_contractions

class Convert(object):
	def __init__(self, datasetdir, listoffilters=['simple'], matcher='exact'):
		self.datasetdir = datasetdir
		self.listoffilters = self.build_list_of_filters(listoffilters)
		self.datasetid = self.get_datasetid()
		self.matcher = self.getMatcher(matcher)
	def build_ground_truth(self):
	    keysfiles = glob.glob(os.path.join(self.datasetdir, 'keys','*'))
	    self.qrels = {}
	    for i, keyfile in enumerate(keysfiles):
	        docid = self.get_docid(keyfile)
	        gt = {}
	        keysunfiltered = self.readfile(keyfile).split('\n')
	        for goldkey in keysunfiltered:
	            for termfilter in self.listoffilters:
	                goldkey = termfilter(goldkey)
	            if goldkey not in gt and len(goldkey) > 0:
	                gt[goldkey] = ('k%d' % len(gt), True)
	        self.qrels[docid] = gt
	        print('\rBuilding Ground Truth (%s): %.2f' % (self.datasetid, 100.*i/len(keysfiles)), end='% ')
	    print('\rBuilding Ground Truth (%s): 100.00%%' % self.datasetid)
	    return self.qrels
	def build_result(self, resultdir):
	    appname = self.get_appname(resultdir)
	    conversor = self.getconversor(appname)

	    listofresults = glob.glob(os.path.join(resultdir, self.datasetid, '*'))
	    toreturn = []
	    
	    for i, resultdoc in enumerate(sorted(listofresults)):
	        docid = self.get_docid(resultdoc)
	        gt = self.qrels[docid]
	        seen = set()
	        result=[]
	        keyphrases = self.readfile(resultdoc).split('\n')
	        if len(keyphrases) == 0:
	        	idkw = 'uk00'
	        	gt['--'] = (idkw, False)
	        else:
		        for weight, kw in conversor(keyphrases):
		            for termfilter in self.listoffilters:
		                kw = termfilter(kw)
		            if len(kw) == 0:
		                continue
		            if kw not in gt:
		                isrel = self.matcher(kw, gt)
		                idkw = ('%sk%d' % ('' if isrel else 'u', len(gt))) #uK%d if unrel key or K%d to rel new keys
		                gt[kw] = (idkw, isrel)
		            idkw, isrel = gt[kw]
		            if idkw not in seen:
		                seen.add(idkw)
		                result.append( idkw )
	        self.qrels[docid] = gt
	        toreturn.append( (docid, result) )
	        print('\r%s: %.2f' % (appname, 100.*i/len(listofresults)), end='% ')
	    print('\r%s: 100.00%%' % appname)
	    return ( appname, toreturn )
	def save_in_trec_format(self, outputpath, appname, results):
		output_file = os.path.join(outputpath, "%s_%s.out" % (self.datasetid, appname))
		with open(output_file, 'w') as outfile:
			for (docid, result) in results:
				for i, instance in enumerate(result):
					outfile.write("%s Q0 %s %d %d %s\n" % ( docid, instance, (i+1), (len(result)-i), appname ) )
	def save_qrel(self, outputpath):
		output_file = os.path.join(outputpath, "%s.qrel" % self.datasetid)
		with open(output_file, 'w') as outfile:
			for docid in self.qrels:
				for (idkw, isrel) in [(idkw, isrel) for (idkw, isrel) in self.qrels[docid].values() if isrel]:
					outfile.write("%s\t0\t%s\t1\n" % ( docid, idkw ) )

	def build_list_of_filters(self, listoffilters):
		list_of_filter = []
		for filter_name in listoffilters:
			if filter_name == 'simple':
				list_of_filter.append(self.simple_filter)
		return list_of_filter
	def simple_filter(self, word):
	    term = word.lower()
	    for p in string.punctuation:
	        term = term.replace(p, ' ')
	    term = ' '.join([ w for w in split_contractions(web_tokenizer(term)) ])
	    return term.strip()

	# Type of input results
	def getconversor(self, method):
	    if method.startswith('Rake') or method.startswith('Yake') or method.startswith('IBM'):
	        return self.sortedNumericList	
	    return self.nonNumericList
	def nonNumericList(self, listofkeys):
		# Only ordered keyphrases
	    return [ (100./(1.+i), kw) for i, kw in enumerate(listofkeys) if len(kw) > 0 ]
	def sortedNumericList(self, listofkeys):
	    toreturn = []
	    for key in listofkeys:
	        parts = key.rsplit(' ', 1)
	        if len(key) > 0 and len(parts) > 1:
	            kw, weight = parts
	            try:
	            	weight = float(weight)
	            except:
	            	weight = 0.
	            toreturn.append( (weight, kw) )
	    return toreturn
	def resortedNumericList(self, listofkeys):
	    toreturn = []
	    for key in listofkeys:
	        if len(key) > 0:
	            kw, weight = key.rsplit(' ', 1)
	            toreturn.append( (10./(1.+float(weight)), kw) )
	    return toreturn

	# Matchers: define the type of match to use
	def getMatcher(self, name):
		if name == 'exact':
			return self.exactmatch
		return None
	def exactmatch(self, kw, gt):
	    # Exact match
	    return kw in gt
	def ingroundtruth(self, kw, gt):
	    # Considering if the candidate keyphrase is inside some gold keyphrase
	    for goldkey in gt:
	        if kw in goldkey:
	            return True
	    return False
	def inkeyphrase(self, kw, gt):
	    # Considering if some gold keyphrase is inside the candidate keyphrase  
	    for goldkey in gt:
	        if goldkey in kw:
	            return True
	    return False
	def inoutgroundtruth(self, kw, gt):
		# Considering if some gold keyphrase is inside the candidate keyphrase
		# OR
	    # Considering if the candidate keyphrase is inside some gold keyphrase
	    return self.inkeyphrase(kw, gt) or self.ingroundtruth(kw, gt)


	# Auxiliar methods
	def readfile(self, filepath):
	    with open(filepath, encoding='utf8') as infile:
	        content = infile.read()
	    return content
	def get_datasetid(self):
	    return self.datasetdir.rsplit(os.path.sep,2)[1]
	def get_appname(self, resultdir):
	    return '_'.join([ config for config in os.path.dirname(resultdir).split(os.path.sep)[-2:] if config != 'None'])
	def get_docid(self, dockeypath):
	    return os.path.basename(dockeypath).replace('.txt','').replace('.key','').replace('.out','').replace('.phrases','')

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-d','--datasetdir', type=str, nargs=1, help='')
parser.add_argument('-r','--results', type=str, nargs='+', help='')
parser.add_argument('-m','--matcher', type=str, nargs='?', help='Type of match to use (Default: exact).', default='exact')
parser.add_argument('-o','--output', type=str, nargs='?', help='Output path.', default='./output/')
parser.add_argument('-f','--filter', type=str, nargs='+', help='Filter method.', default=['simple'])

args = parser.parse_args()

# Convert(datasetdir, listoffilters=['simple'], matcher='exact')
conv = Convert(args.datasetdir[0], listoffilters=args.filter, matcher=args.matcher)
conv.build_ground_truth()
print()
for results in args.results:
	( appname, results ) = conv.build_result(results)

	# save_in_trec_format(self, outputpath, appname, results):
	conv.save_in_trec_format(args.output, appname, results)
conv.save_qrel(args.output)
"""
parser.add_argument('-m','--measure', type=str, nargs='+', help='Evaluation method.', default=['P.10', 'recall.10'])
parser.add_argument('-t','--trec_eval', type=str, nargs='?', help='The trec_eval executor path (Default: %s).' % dir_trec_, metavar='TREC_EVAL_PATH', default=dir_trec_)
parser.add_argument('-sum','--summary', type=str, nargs='*', help='Summary each approach results using Over-sampling methods (Default: None).', default=['None'], choices=['ros','smote'])
parser.add_argument('-s','--statistical_test', type=str, nargs='*', help='Statistical test (Default: student).', default=['student'], choices=['None','student','wilcoxon','welcht'])
parser.add_argument('-f','--format', type=str, nargs='?', help='Output format.', default='string', choices=['csv', 'html', 'json', 'latex', 'sql', 'string'])
parser.add_argument('-cv','--cross-validation', type=int, nargs='?', help='Cross-Validation.', default=1)
parser.add_argument('-r','--round', type=int, nargs='?', help='Round the result.', default=4)
"""