"""Authorized, bounded, immutable source snapshots and XLSX container guards."""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import stat
import zipfile
import zlib
from common import Budget, IntakeError, SourceSnapshot


def snapshot_file(source_id: str, path: Path, authorized: set[Path], budget: Budget) -> SourceSnapshot:
    try:
        real=path.resolve(strict=True)
        # Canonical target must itself be authorized; authorizing an alias does not grant its target.
        if real not in authorized:
            raise IntakeError('source_not_authorized','来源文件未获得明确授权',{'source_id':source_id})
        mode=os.O_RDONLY | getattr(os,'O_NONBLOCK',0) | getattr(os,'O_NOFOLLOW',0)
        fd=os.open(real,mode)
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            os.close(fd)
            raise IntakeError('source_not_regular','来源必须是常规文件',{'source_id':source_id})
        with os.fdopen(fd,'rb') as f:
            budget.enforce('max_file_bytes',info.st_size)
            chunks=[]; size=0
            while True:
                budget.check(); chunk=f.read(65536)
                if not chunk: break
                size+=len(chunk); budget.enforce('max_file_bytes',size); chunks.append(chunk)
            after=os.fstat(f.fileno())
            if (info.st_size,info.st_mtime_ns,info.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise IntakeError('source_changed','读取时来源发生变化',{'source_id':source_id},fatal=True)
        raw=b''.join(chunks)
        return SourceSnapshot(source_id,real,hashlib.sha256(raw).hexdigest(),size,(info.st_dev,info.st_ino),raw)
    except IntakeError:
        raise
    except (OSError,RuntimeError) as e:
        # Avoid leaking unrelated absolute paths in end-user error text.
        raise IntakeError('source_unavailable','来源不存在或无法只读访问',{'source_id':source_id}) from e


def inspect_zip(data: bytes, budget: Budget) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries=archive.infolist(); budget.enforce('max_zip_members',len(entries))
            names=[i.filename for i in entries]
            if len(set(names))!=len(names): raise IntakeError('invalid_zip','工作簿包含重复ZIP成员名')
            expected=0
            for entry in entries:
                name=entry.filename; parts=PurePosixPath(name).parts; lower=name.lower()
                if (name.startswith('/') or '\\' in name or '..' in parts or ':' in name or entry.flag_bits & 1
                        or 'vbaproject' in lower or lower.startswith('xl/externallinks/')):
                    raise IntakeError('unsafe_workbook','拒绝加密、宏、外部工作簿链接或异常成员路径')
                budget.enforce('max_member_bytes',entry.file_size)
                expected+=entry.file_size; budget.enforce('max_zip_bytes',expected)
            if '[Content_Types].xml' not in names or 'xl/workbook.xml' not in names:
                raise IntakeError('invalid_zip','不是受支持的XLSX工作簿结构')
            actual=0
            for entry in entries:
                size=0; tail=b''; is_xml=entry.filename.lower().endswith(('.xml','.rels'))
                with archive.open(entry) as stream:
                    while True:
                        budget.check(); chunk=stream.read(65536)
                        if not chunk: break
                        size+=len(chunk); actual+=len(chunk)
                        budget.enforce('max_member_bytes',size); budget.enforce('max_zip_bytes',actual)
                        budget.charge('expanded_bytes',len(chunk),'max_total_zip_bytes')
                        if is_xml:
                            text=(tail+chunk).lower()
                            if b'<!doctype' in text or b'<!entity' in text or b'\x00' in text:
                                raise IntakeError('unsafe_workbook','XML声明包含不支持的实体或编码')
                            if entry.filename=='[Content_Types].xml' or entry.filename.lower().endswith('.rels'):
                                if any(word in text for word in (b'macroenabled',b'vbaproject',b'externallink')):
                                    raise IntakeError('unsafe_workbook','工作簿包含宏或外部工作簿关联')
                            tail=text[-64:]
                if size!=entry.file_size: raise IntakeError('invalid_zip','ZIP声明与实际解压长度不一致')
            return {'zip_members':len(entries),'expanded_bytes':actual}
    except IntakeError:
        raise
    except (zipfile.BadZipFile, OSError, ValueError, RuntimeError, NotImplementedError, zlib.error) as e:
        raise IntakeError('invalid_zip','工作簿压缩结构损坏或不受支持') from e
