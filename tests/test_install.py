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


if __name__=='__main__': unittest.main()
