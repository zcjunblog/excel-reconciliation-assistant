// M1合成输入构建器；不读取或生成expected.json，不执行核对。
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'outputs/m1-fixtures');
await fs.mkdir(output, { recursive: true });
const field = (id, lc, rc, lh, rh, type, extra={}) => ({id, left_column:lc, right_column:rc, left_header:lh, right_header:rh, type, ...extra});
const table = (id, source_id, sheet, data_range, exclusions=[]) => ({id, source_id, sheet, header_row:1, data_range, exclusions});
const task = (id, left_table, right_table, keys, fields, formula_policy='pending') => ({id,left_table,right_table,keys,fields,formula_policy});
const json = async (p,v) => fs.writeFile(p, JSON.stringify(v,null,2)+'\n');
async function rules(name, sources, tables, tasks) {
  const dir=path.join(root,'examples',name); await fs.mkdir(dir,{recursive:true});
  await json(path.join(dir,'rules.json'),{schema_version:'1.0',sources,tables,tasks});
}
async function csv(name, filename, values, bom=false) {
  const escape = v => '"'+String(v??'').replaceAll('"','""')+'"';
  await fs.writeFile(path.join(root,'examples',name,filename),(bom?'\uFEFF':'')+values.map(r=>r.map(escape).join(',')).join('\n')+'\n');
}
async function xlsx(name, filename, sheets) {
  const wb=Workbook.create();
  for (const {name:sheetName, values, formulas=[]} of sheets) {
    const sh=wb.worksheets.add(sheetName);
    sh.showGridLines=false;
    const cols=values[0].length, rows=values.length;
    sh.getRangeByIndexes(0,0,rows,cols).values=values;
    const all=sh.getRangeByIndexes(0,0,rows,cols);
    all.format.font={name:'Arial',size:11,color:'#243247'};
    all.format.columnWidth=20; all.format.rowHeight=27;
    sh.getRangeByIndexes(0,0,1,cols).format={fill:'#17365D',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:32};
    sh.getRangeByIndexes(0,0,1,cols).format.horizontalAlignment='center';
    // 数字形状的文本编号明确按文本显示，不能因渲染格式丢掉前导零。
    for(let r=1;r<rows;r++) for(let c=0;c<cols;c++) {
      const value=values[r][c];
      if(typeof value==='string') sh.getCell(r,c).setNumberFormat('@');
    }
    if(name==='commerce') {
      const centered=sheetName==='订单'?['B2:B9','D2:D9','F2:F9']:['C2:C8','D2:D8','E2:E8'];
      for(const address of centered) sh.getRange(address).format.horizontalAlignment='center';
    }
    sh.freezePanes.freezeRows(1);
    for (const [cell,formula] of formulas) sh.getRange(cell).formulas=[[formula]];
  }
  wb.recalculate();
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:10},maxChars:1200});
  await fs.writeFile(path.join(output,`${name}-inspect.ndjson`),errors.ndjson);
  for (const {name:sheetName,values} of sheets) {
    const range=`A1:${String.fromCharCode(64+values[0].length)}${values.length}`;
    const png=await wb.render({sheetName,range,scale:1.5,format:'png'});
    await fs.writeFile(path.join(output,`${name}-${sheetName}.png`),new Uint8Array(await png.arrayBuffer()));
  }
  const file=await SpreadsheetFile.exportXlsx(wb);
  await file.save(path.join(output,`${name}-${filename}`));
  await fs.copyFile(path.join(output,`${name}-${filename}`),path.join(root,'examples',name,filename));
}

await rules('commerce',[{id:'book',path:'inputs.xlsx',format:'xlsx'}],[
  table('orders','book','订单','A2:F9',[{rows:[9],reason:'显式排除合计行'}]),table('delivery','book','交付','A2:F8')
],[task('order_delivery','orders','delivery',['order','line'],[
  field('order','A','A','订单号','编号','identifier'),field('line','B','C','行号','行号','identifier'),
  field('item','C','F','品名','品名','text'),field('quantity','D','E','数量','数量','decimal'),
  field('amount','E','B','金额','金额','decimal',{tolerance:'0.01',context:{currency:{left:{column:'F'},right:{column:'D'}}}})
])]);
await xlsx('commerce','inputs.xlsx',[
  {name:'订单',values:[['订单号','行号','品名','数量','金额','币种'],['O001','01','Desk',2,100,'CNY'],['O001','02','Chair',1,50,'CNY'],['O002','01','Lamp',0,10,'USD'],['O003','01','Cable',4,20,'CNY'],['O003','01','Cable',1,5,'CNY'],[null,'01','Unknown',1,1,'CNY'],['O004','01','Adapter',3,30,'CNY'],['合计',null,null,12,216,null]]},
  {name:'交付',values:[['编号','金额','行号','币种','数量','品名'],['O001',100.01,'01','CNY',2,'Desk'],['O002',10,'01','CNY',0,'Lamp'],['O001',50.02,'02','CNY',2,'Chair'],['O003',25,'01','CNY',5,'Cable'],['O005',40,'01','CNY',4,'New'],[null,1,'01','CNY',1,'Unknown'],['O006',60,'01','CNY',6,'Other']]}
]);

await rules('inventory',[{id:'ledger',path:'ledger.csv',format:'csv',encoding:'utf-8-sig'},{id:'count',path:'count.csv',format:'csv',encoding:'utf-8-sig'}],[table('ledger','ledger',null,'A2:D6'),table('count','count',null,'A2:D6')],[task('stock_check','ledger','count',['sku','location'],[
  field('sku','A','B','SKU','sku','identifier'),field('location','B','A','仓位','仓位','identifier'),field('unit','C','D','单位','单位','text'),
  field('quantity','D','C','账面数量','实盘','decimal',{parse_numeric_text:true,context:{unit:{left:{column:'C'},right:{column:'D'}}}})
])]);
await csv('inventory','ledger.csv',[['SKU','仓位','单位','账面数量'],['0007','A1','件','10'],['0007','B1','件','5'],['9','A1','箱','2'],['0010','A1','件','0'],['0011','A1','件','']],true);
await csv('inventory','count.csv',[['仓位','sku','实盘','单位'],['B1','0007','6','件'],['A1','0007','10','件'],['A1','9','20','件'],['A1','10','0','件'],['A1','0011','0','件']]);

await rules('training',[{id:'registration',path:'registration.csv',format:'csv'},{id:'attendance',path:'attendance.csv',format:'csv'}],[table('registration','registration',null,'A2:D6'),table('attendance','attendance',null,'A2:D6')],[task('roster_check','registration','attendance',['registration_id'],[
  field('registration_id','A','B','报名号','报名号','identifier'),field('name','B','D','姓名','姓名','text',{normalize:['trim']}),
  field('session','C','A','场次','场次','identifier'),field('date','D','C','日期','出席日期','date',{date_format:{left:'%Y-%m-%d',right:'%Y-%m-%d'}})
])]);
await csv('training','registration.csv',[['报名号','姓名','场次','日期'],['R001','王宁','S1','2026-11-01'],['R002','王宁','S1','2026-11-01'],['R003','李林','S2','2026-11-02'],['','陆鸣','S2','2026-11-02'],['R004','陈晓','S2','2026-11-02']]);
await csv('training','attendance.csv',[['场次','报名号','出席日期','姓名'],['S1','R002','2026-11-01','王宁'],['S1','R001','2026-11-01',' 王宁 '],['S2','R003','01/02/2026','李林'],['S2','R005','2026-11-02','赵易'],['S2','','2026-11-02','陆鸣']]);

const assetsFields=[field('asset_id','A','B','资产编号','编号','identifier'),field('owner','B','A','领用人','领用人','text'),field('value','C','C','登记值','登记值','decimal',{context:{currency:{left:{literal:'CNY'},right:{literal:'CNY'}}}})];
await rules('administration',[{id:'assets',path:'inputs.xlsx',format:'xlsx'}],[table('baseline','assets','资产台账','A2:C4'),table('handover','assets','领用核对','A2:C4'),table('revision','assets','修订核对','A2:C4')],[task('assets_default','baseline','handover',['asset_id'],assetsFields),task('assets_cached','baseline','revision',['asset_id'],assetsFields,'cached')]);
const assetValues=[['领用人','编号','登记值'],['甲组','A-002',200],['乙组','A-001',100],['丙组','A-003',300]];
await xlsx('administration','inputs.xlsx',[
  {name:'资产台账',values:[['资产编号','领用人','登记值'],['A-001','乙组',100],['A-002','甲组',200],['A-003','丙组',300]]},
  {name:'领用核对',values:assetValues,formulas:[['C2','=100+100'],['C3','=50+50'],['C4','=300']]},
  {name:'修订核对',values:assetValues,formulas:[['C2','=100+100'],['C3','=50+50'],['C4','=300']]}
]);
console.log('Prepared four synthetic cases. Run finalize_m1.py to set deliberate cache states and freeze hashes.');
