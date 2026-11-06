// 只读渲染最终缓存夹具，不导出或回写输入，不调用recalculate。
import fs from 'node:fs/promises';
import { Workbook, FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const root=new URL('../',import.meta.url);
for(const [caseName,filename] of [['commerce','inputs.xlsx'],['administration','inputs.xlsx']]) {
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(new URL(`examples/${caseName}/${filename}`,root).pathname));
  const names=caseName==='commerce'?['订单','交付']:['资产台账','领用核对','修订核对'];
  for(const sheetName of names) {
    const png=await wb.render({sheetName,range:caseName==='commerce'?`A1:F${sheetName==='订单'?9:8}`:'A1:C4',scale:1.5,format:'png'});
    await fs.writeFile(new URL(`outputs/m1-fixtures/final-${caseName}-${sheetName}.png`,root),new Uint8Array(await png.arrayBuffer()));
  }
}
// CSV同样只读预览，所有单元格按源文本显示，不推导业务结论。
for(const [caseName,filename] of [['inventory','ledger.csv'],['inventory','count.csv'],['training','registration.csv'],['training','attendance.csv']]) {
  const wb=await Workbook.fromCSV(await fs.readFile(new URL(`examples/${caseName}/${filename}`,root),'utf8'),{sheetName:'Source'});
  const sh=wb.worksheets.getItem('Source');
  sh.getRange('A1:D6').setNumberFormat('@');
  sh.getRange('A1:D6').format.columnWidth=23;
  sh.getRange('A1:D6').format.rowHeight=28;
  sh.getRange('A1:D1').format={fill:'#17365D',font:{name:'Arial',bold:true,color:'#FFFFFF'}};
  const png=await wb.render({sheetName:'Source',range:'A1:D6',scale:1.5,format:'png'});
  await fs.writeFile(new URL(`outputs/m1-fixtures/final-${caseName}-${filename}.png`,root),new Uint8Array(await png.arrayBuffer()));
}
console.log('Read-only previews saved; source XLSX/CSV files not exported or modified.');
