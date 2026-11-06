"""Read-only capability check; no dependency installation or account access."""
import argparse
import importlib
import json
from pathlib import Path
import re
import sys
RUNTIME_MODULES=('checks common compare csv_reader delivery_guard doctor export export_rows intake matching normalization presentation '
                 'reconcile_tool report rules runner runtime_info source_guard table_data typed_values xlsx_reader').split()


def diagnose(require_xlsx=False):
    root=Path(__file__).resolve().parents[1]; issues=[]
    python_ok=sys.version_info>=(3,9)
    if not python_ok: issues.append({'code':'unsupported_python','message':'Python 3.9+ required'})
    try:
        from runtime_info import skill_version
        version=skill_version(root)
    except (ImportError,ValueError):
        version=None; issues.append({'code':'invalid_version','message':'Skill VERSION missing or invalid'})
    required=['SKILL.md','references/reconciliation-rules.schema.json','references/rules.md','references/runtime.md',
              'references/delivery.md','templates/workbook-style.json']+['scripts/'+name+'.py' for name in RUNTIME_MODULES]
    for path in required:
        if not (root/path).is_file(): issues.append({'code':'missing_resource','path':path,'message':'Installed skill is incomplete'})
    xlsx=False; dependency=None
    try:
        module=importlib.import_module('openpyxl'); dependency=module.__version__
        match=re.match(r'^(\d+)\.(\d+)',dependency)
        xlsx=bool(match and (3,1)<=(int(match[1]),int(match[2]))<(4,0))
    except (ImportError,AttributeError): pass
    if require_xlsx and not xlsx: issues.append({'code':'missing_dependency','message':'This interpreter needs openpyxl>=3.1,<4 for XLSX'})
    usable=python_ok and version is not None and not any(i['code']=='missing_resource' for i in issues)
    return {'status':'ready' if usable and (not require_xlsx or xlsx) else 'blocked','skill_version':version,
            'python':sys.version.split()[0],'interpreter':sys.executable,
            'capabilities':{'csv':usable,'xlsx':usable and xlsx},'openpyxl_version':dependency,'issues':issues}


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--require-xlsx',action='store_true')
    result=diagnose(parser.parse_args().require_xlsx)
    print(json.dumps(result,ensure_ascii=True,allow_nan=False)); return 0 if result['status']=='ready' else 1


if __name__=='__main__': raise SystemExit(main())
