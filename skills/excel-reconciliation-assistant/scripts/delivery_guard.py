"""Exclusive publication and identity-based cleanup, with a private ownership journal."""
from __future__ import annotations
import json
import os
from pathlib import Path
import stat
from common import IntakeError

JOURNAL='.delivery-ownership.json'


def identity(path):
    try:
        info=path.lstat()
        if stat.S_ISLNK(info.st_mode): return None
        return [info.st_dev,info.st_ino]
    except OSError: return None


def _within_owned_parents(root,relative,owned_dirs):
    current=root
    if identity(current)!=owned_dirs.get('.'): return False
    for part in relative.parent.parts:
        current=current/part
        if identity(current)!=owned_dirs.get(current.relative_to(root).as_posix()): return False
    return True


def cleanup_owned(data):
    """A planned name is never proof of ownership. Replaced or foreign objects survive."""
    root=Path(data['destination']); directories=data['directories']
    if identity(root)!=directories.get('.'): return
    for entry in reversed(data['files']):
        relative=Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts: continue
        path=root/relative
        if _within_owned_parents(root,relative,directories) and identity(path)==entry['identity']:
            path.unlink(missing_ok=True)
    for relative,expected in sorted(directories.items(),key=lambda item:len(Path(item[0]).parts),reverse=True):
        if relative=='.': continue
        path=root/relative
        if _within_owned_parents(root,Path(relative),directories) and identity(path)==expected:
            try: path.rmdir()
            except OSError: pass
    if identity(root)==directories.get('.'):
        try: root.rmdir()
        except OSError: pass


class DeliveryGuard:
    def __init__(self,destination,staging_dir,run_id):
        original=Path(destination).absolute()
        if original.exists() or original.is_symlink(): raise IntakeError('output_exists','交付版本目录已存在，拒绝覆盖')
        self.root=original.parent.resolve()/original.name
        self.stage=Path(staging_dir).resolve()
        if self.root==self.stage or self.root in self.stage.parents or self.stage in self.root.parents:
            raise IntakeError('unsafe_output','交付目录不能与暂存目录重叠')
        self.root.mkdir()
        self.data={'run_id':run_id,'destination':str(self.root),'directories':{'.':identity(self.root)},'files':[]}
        try: self._persist()
        except BaseException:
            self.cleanup(); raise

    def _persist(self):
        # Journal stays in the parent's private stage, never in user-controlled output.
        temporary=self.stage/(JOURNAL+'.new')
        with temporary.open('w',encoding='utf-8') as stream:
            json.dump(self.data,stream,ensure_ascii=True)
            stream.flush()
        os.replace(temporary,self.stage/JOURNAL)

    def open(self,name):
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts: raise IntakeError('unsafe_output','交付文件路径越界')
        current=self.root
        if identity(current)!=self.data['directories']['.']: raise IntakeError('unsafe_output','交付根目录已被替换')
        for part in relative.parent.parts:
            current=current/part; key=current.relative_to(self.root).as_posix()
            if key not in self.data['directories']:
                try: current.mkdir()
                except FileExistsError as error: raise IntakeError('unsafe_output','交付子目录已由其他写入者创建或为链接') from error
                self.data['directories'][key]=identity(current); self._persist()
            if identity(current)!=self.data['directories'][key]: raise IntakeError('unsafe_output','交付子目录已被替换或为链接')
        target=self.root/relative; handle=target.open('xb')
        try:
            info=os.fstat(handle.fileno()); owned=[info.st_dev,info.st_ino]
            self.data['files'].append({'path':relative.as_posix(),'identity':owned}); self._persist()
            if not _within_owned_parents(self.root,relative,self.data['directories']) or identity(target)!=owned:
                raise IntakeError('unsafe_output','创建文件期间交付路径被替换')
        except BaseException:
            handle.close(); raise
        return handle

    def unlink(self,name):
        relative=Path(name); entry=next(e for e in self.data['files'] if e['path']==relative.as_posix())
        if not _within_owned_parents(self.root,relative,self.data['directories']) or identity(self.root/relative)!=entry['identity']:
            raise IntakeError('unsafe_output','交付标记已被其他写入者替换')
        (self.root/relative).unlink()

    def validate(self,name):
        relative=Path(name); entry=next(e for e in self.data['files'] if e['path']==relative.as_posix())
        if not _within_owned_parents(self.root,relative,self.data['directories']) or identity(self.root/relative)!=entry['identity']:
            raise IntakeError('unsafe_output','已复制的交付文件或其父目录被替换')

    def cleanup(self): cleanup_owned(self.data)


def cleanup_interrupted(output,run_id,staging_dir):
    if staging_dir is None: return
    journal=Path(staging_dir)/JOURNAL
    try:
        data=json.loads(journal.read_text(encoding='utf-8'))
        requested=Path(output).absolute()
        canonical=requested.parent.resolve()/requested.name
        if data['run_id']!=run_id or Path(data['destination'])!=canonical: return
        cleanup_owned(data)
    except (OSError,ValueError,KeyError,TypeError): return
