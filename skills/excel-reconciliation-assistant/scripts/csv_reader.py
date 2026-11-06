"""Strict streaming CSV reader retaining logical and physical record positions."""
from __future__ import annotations
import codecs
import csv
import io
from common import BudgetExceeded, IntakeError
from table_data import Grid, RawCell, wanted


class _Lines:
    def __init__(self, raw, encoding, budget):
        self.text=io.TextIOWrapper(io.BytesIO(raw),encoding=encoding,errors='strict',newline='')
        self.encoder=codecs.getincrementalencoder(encoding)()
        self.budget=budget; self.line=0; self.record_bytes=0

    def __iter__(self): return self

    def __next__(self):
        self.budget.check()
        line=self.text.readline(self.budget.max_record_bytes+1)
        if not line: raise StopIteration
        self.record_bytes+=len(self.encoder.encode(line))
        self.budget.enforce('max_record_bytes',self.record_bytes)
        self.line+=1
        return line


def read_csv(snapshot, source, tables, budget):
    encoding=source.get('encoding','utf-8-sig')
    lines=_Lines(snapshot.data,encoding,budget)
    reader=csv.reader(lines,delimiter=',',strict=True)
    cells={}; rows=0; width=None; scanned_cells=0
    original_limit=csv.field_size_limit()
    try:
        csv.field_size_limit(max(budget.max_record_bytes,budget.max_text_chars))
        while True:
            lines.record_bytes=0; start=lines.line+1
            try: values=next(reader)
            except StopIteration: break
            rows+=1; budget.enforce('max_scan_rows',rows)
            if width is None:
                width=len(values)
            elif not values:
                values=['']*width
            if len(values)!=width: raise IntakeError('csv_width_mismatch','CSV记录列数与首条记录不一致',{'source_id':snapshot.id,'row':rows,'physical_lines':(start,lines.line)})
            scanned_cells+=len(values); budget.enforce('max_scan_cells',scanned_cells)
            for c,value in enumerate(values,1):
                budget.enforce('max_text_chars',len(value))
                if wanted(rows,c,tables): cells[(rows,c)]=RawCell(value,'string',physical_lines=(start,lines.line))
        return Grid(cells,rows,width or 0,{'format':'csv','encoding':encoding,'scanned_rows':rows,'scanned_cells':scanned_cells,'physical_lines':lines.line,'hidden_rows':[],'auto_filter':None})
    except UnicodeError as e:
        raise IntakeError('invalid_encoding','CSV无法按指定编码严格解码',{'source_id':snapshot.id,'encoding':encoding}) from e
    except csv.Error as e:
        if 'field larger than field limit' in str(e): raise BudgetExceeded('max_text_chars') from e
        raise IntakeError('invalid_csv','CSV引号或记录结构无效',{'source_id':snapshot.id,'physical_line':lines.line}) from e
    finally:
        csv.field_size_limit(original_limit)
        lines.text.close()
