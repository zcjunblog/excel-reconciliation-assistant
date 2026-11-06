"""Small source-shaped fixtures for M3; expected outcomes stay literal in tests."""
from pathlib import Path
import sys
from fixture_helpers import ROOT, authorize
from common import Budget, CellRef, CellValue, RowData, TableData
from rules import load_rules
from intake import inspect_sources, read_tables


def read_case(name):
    rules=load_rules(ROOT/'examples'/name/'rules.json'); budget=Budget()
    intake=inspect_sources(rules,authorize(rules),budget)
    tables=read_tables(intake,rules,budget)
    assert intake.status=='ready',intake.issues
    return rules,tables,budget


def cell(value, table='left', row=2, column='B', kind=None, lexeme=None, **extra):
    if kind is None:
        kind='missing' if value is None else 'boolean' if type(value) is bool else 'number' if isinstance(value,(int,float)) else 'string'
    if kind=='number' and type(value) is int and lexeme is None: lexeme=str(value)
    return CellValue(CellRef(table,table,None,row,column),value,kind,lexeme,**extra)


def table(side, values):
    rows=[]
    for i,values_row in enumerate(values,2):
        cells={}
        for j,value in enumerate(values_row):
            col=chr(65+j)
            cells[col]=value if isinstance(value,CellValue) else cell(value,side,i,col)
        rows.append(RowData(i,cells))
    return TableData(side,{'A':'id','B':'value','C':'context'},rows,list(range(2,len(rows)+2)),{}, {'format':'synthetic','date_system':'1900'})


def task(kind='text', **extra):
    return {'id':'check','left_table':'left','right_table':'right','keys':['id'],'formula_policy':'pending','fields':[
        {'id':'id','left_column':'A','right_column':'A','left_header':'id','right_header':'id','type':'identifier'},
        {'id':'value','left_column':'B','right_column':'B','left_header':'value','right_header':'value','type':kind,**extra}]}
