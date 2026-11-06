import importlib
import shutil
import sys
from fixture_helpers import ROOT

NAME='excel-reconciliation-assistant'
SOURCE=ROOT/'skills'/NAME
sys.path.insert(0,str(ROOT/'tools'))


def tool(test,name):
    test.assertTrue((ROOT/'tools'/(name+'.py')).is_file(),'Missing distribution tool: '+name)
    return importlib.import_module(name)


def source_copy(directory):
    dest=directory/NAME
    shutil.copytree(SOURCE,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    return dest
