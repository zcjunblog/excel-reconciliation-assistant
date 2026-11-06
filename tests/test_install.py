import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from distribution_helpers import SOURCE,NAME,tool


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.dir=Path(self.temp.name).resolve()

    def test_documented_client_paths_and_dry_run_do_not_write(self):
        installer=tool(self,'install'); project=self.dir/'project'; user=self.dir/'home'
        paths={'codex':('.agents/skills','.agents/skills'),'claude':('.claude/skills','.claude/skills'),
               'cursor':('.cursor/skills','.cursor/skills'),'copilot':('.github/skills','.copilot/skills'),
               'gemini':('.gemini/skills','.gemini/skills'),'opencode':('.opencode/skills','.config/opencode/skills')}
        for client,(p,u) in paths.items():
            self.assertEqual(installer.destination(client,'project',project,user),project/p/NAME)
            self.assertEqual(installer.destination(client,'user',project,user),user/u/NAME)
        target=project/'.agents/skills'/NAME; result=installer.install(target,dry_run=True)
        self.assertTrue(result['dry_run']); self.assertFalse(project.exists())

    def test_complete_install_is_a_byte_identical_self_contained_skill(self):
        installer=tool(self,'install'); target=self.dir/'工作 项目/.agents/skills'/NAME
        result=installer.install(target); self.assertEqual(result['version'],'0.1.0')
        self.assertEqual((target/'SKILL.md').read_bytes(),(SOURCE/'SKILL.md').read_bytes())
        self.assertEqual((target/'scripts/checks.py').read_bytes(),(SOURCE/'scripts/checks.py').read_bytes())
        self.assertEqual((target/'references/examples/inventory/ledger.csv').read_bytes(),(SOURCE/'references/examples/inventory/ledger.csv').read_bytes())
        self.assertEqual(list(target.parent.glob('.skill-install-*')),[])
        self.assertTrue(result['hashes_verified'])

    def test_existing_directory_and_destination_links_are_preserved(self):
        installer=tool(self,'install'); target=self.dir/NAME; target.mkdir(); (target/'keep').write_text('foreign')
        with self.assertRaises(ValueError): installer.install(target)
        self.assertEqual((target/'keep').read_text(),'foreign')
        external=self.dir/'other'; external.mkdir(); alias=self.dir/'alias'; alias.symlink_to(external,target_is_directory=True)
        with self.assertRaises(ValueError): installer.install(alias)
        self.assertEqual(list(external.iterdir()),[])

    def test_interrupted_entry_publication_keeps_concurrent_foreign_files(self):
        installer=tool(self,'install'); target=self.dir/'skills'/NAME
        def interrupted(*args,**kwargs):
            self.assertFalse((target/'SKILL.md').exists())
            (target/'foreign.txt').write_text('foreign'); (target/'foreign-dir').mkdir()
            raise OSError('entry publication interrupted')
        with patch('os.link',side_effect=interrupted):
            with self.assertRaises(OSError): installer.install(target)
        self.assertFalse((target/'SKILL.md').exists()); self.assertFalse((target/'scripts/checks.py').exists())
        self.assertEqual((target/'foreign.txt').read_text(),'foreign'); self.assertTrue((target/'foreign-dir').is_dir())

    def test_replaced_entry_is_never_claimed_or_removed_as_our_inode(self):
        from delivery_guard import DeliveryGuard
        from common import IntakeError
        import os
        out=self.dir/'target'; stage=self.dir/'stage'; stage.mkdir(); guard=DeliveryGuard(out,stage,'run')
        link=os.link
        def replace(src,dst):
            link(src,dst); Path(dst).unlink(); Path(dst).write_bytes(b'foreign replacement')
        with patch('os.link',side_effect=replace):
            with self.assertRaises(IntakeError): guard.publish_entry('SKILL.md',b'our entry')
        guard.cleanup(); self.assertEqual((out/'SKILL.md').read_bytes(),b'foreign replacement')

    def test_modified_resource_blocks_entry_before_a_loader_can_discover_it(self):
        installer=tool(self,'install'); from delivery_guard import DeliveryGuard
        original=DeliveryGuard.open; target=self.dir/'skills'/NAME
        def mutate(guard,name):
            stream=original(guard,name)
            if name=='templates/workbook-style.json': (guard.root/'scripts/checks.py').write_bytes(b'changed')
            return stream
        def publish(*args,**kwargs): raise AssertionError('Entry published with an already-corrupt resource')
        with patch.object(DeliveryGuard,'open',mutate),patch.object(DeliveryGuard,'publish_entry',side_effect=publish):
            with self.assertRaises(ValueError): installer.install(target)
        self.assertFalse((target/'SKILL.md').exists())

    def test_deep_ancestor_symlinks_are_rejected_before_dest_or_project_resolution(self):
        installer=tool(self,'install'); outside=self.dir/'outside'; outside.mkdir()
        alias=self.dir/'alias'; alias.symlink_to(outside,target_is_directory=True)
        for mode in ('dest','project'):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    target=alias/'project/skills'/NAME if mode=='dest' else installer.destination('codex','project',project=alias/'project')
                    installer.install(target)
                self.assertEqual(list(outside.iterdir()),[])

    def test_cli_rejects_aliased_project_with_structured_error(self):
        import json,subprocess,sys
        tool(self,'install'); outside=self.dir/'outside'; outside.mkdir()
        alias=self.dir/'alias'; alias.symlink_to(outside,target_is_directory=True)
        cli=SOURCE.parents[1]/'tools/install.py'
        process=subprocess.run([sys.executable,str(cli),'--client','codex','--project',str(alias/'project')],capture_output=True)
        self.assertEqual(process.returncode,1)
        self.assertTrue(process.stdout,process.stderr)
        self.assertEqual(json.loads(process.stdout)['status'],'blocked')
        self.assertEqual(list(outside.iterdir()),[])

    def test_foreign_file_directory_or_link_blocks_complete_install_and_survives_cleanup(self):
        installer=tool(self,'install'); from delivery_guard import DeliveryGuard
        original_open=DeliveryGuard.open; original_entry=DeliveryGuard.publish_entry
        for phase in ('before','after'):
            for kind in ('file','directory','link'):
                with self.subTest(phase=phase,kind=kind):
                    target=self.dir/(phase+kind)/NAME; foreign=target/'scripts/foreign'
                    def add():
                        if kind=='file': foreign.write_text('foreign')
                        elif kind=='directory': foreign.mkdir()
                        else: foreign.symlink_to(self.dir,target_is_directory=True)
                    def opening(guard,name):
                        stream=original_open(guard,name)
                        if phase=='before' and name=='templates/workbook-style.json': add()
                        return stream
                    def entry(guard,name,data):
                        if phase=='before': raise AssertionError('Foreign resource reached entry publication')
                        original_entry(guard,name,data); add()
                    with patch.object(DeliveryGuard,'open',opening),patch.object(DeliveryGuard,'publish_entry',entry):
                        with self.assertRaises(ValueError): installer.install(target)
                    self.assertTrue(foreign.exists()); self.assertFalse((target/'SKILL.md').exists())


if __name__=='__main__': unittest.main()
