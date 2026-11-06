// 非交付文件：为M1资源预算产生10万数据单元格的XLSX读取探测输入。
import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const dir=new URL('../tmp/m1-probe/',import.meta.url);
await fs.mkdir(dir,{recursive:true});
const wb=Workbook.create(), sheet=wb.worksheets.add('Probe');
const rows=Array.from({length:10000},(_,i)=>[`S${String(i).padStart(6,'0')}`,...Array.from({length:9},(_,j)=>(i+j)%1000)]);
sheet.getRange('A1:J1').values=[['ID',...Array.from({length:9},(_,j)=>`V${j+1}`)]];
sheet.getRange('A2:J10001').values=rows;
wb.recalculate();
const file=await SpreadsheetFile.exportXlsx(wb);
await file.save(new URL('probe.xlsx',dir).pathname);
console.log('Prepared synthetic 10000 x 10 XLSX probe. No performance claim from authoring.');
