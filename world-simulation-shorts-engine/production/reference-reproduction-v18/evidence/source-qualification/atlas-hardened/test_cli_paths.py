import json,pathlib,subprocess,tempfile,unittest
from cli_paths import parse_paths
class Checks(unittest.TestCase):
 def test_builder_explicit_paths_do_not_create_output(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);a=parse_paths(['--source-root',str(p/'input'),'--output-root',str(p/'output'),'--baseline-receipt',str(p/'receipt.json')]);self.assertEqual(a.source_root,p/'input');self.assertEqual(a.output_root,p/'output');self.assertFalse(a.output_root.exists())
 def test_builder_cli_dry_path(self):
  with tempfile.TemporaryDirectory() as t:
   r=subprocess.run(['python','build_atlases.py','--source-root',t,'--output-root',t+'/out','--check-paths'],capture_output=True,text=True,check=True);self.assertEqual(json.loads(r.stdout)['sourceRoot'],t);self.assertFalse(pathlib.Path(t,'out').exists())
 def test_verifier_override_without_import_or_io(self):
  with tempfile.TemporaryDirectory() as t:
   r=subprocess.run(['node','verify_generation.mjs','--output-root',t+'/gen','--validator',t+'/missing.mjs','--check-paths'],capture_output=True,text=True,check=True);d=json.loads(r.stdout);self.assertEqual(d['validator'],t+'/missing.mjs');self.assertFalse(pathlib.Path(t,'gen').exists())
 def test_verifier_default_is_repo_relative_candidate_contract(self):
  r=subprocess.run(['node','verify_generation.mjs','--check-paths'],capture_output=True,text=True,check=True);self.assertTrue(json.loads(r.stdout)['validator'].endswith('/source-candidate-contract/derived_source_manifest.mjs'))
 def test_verifier_rejects_report_inside_generation(self):
  r=subprocess.run(['node','verify_generation.mjs','--output-root','/tmp/candidate-test','--report','/tmp/candidate-test/report.json','--check-paths'],capture_output=True,text=True);self.assertNotEqual(r.returncode,0)
if __name__=='__main__':unittest.main(verbosity=2)
