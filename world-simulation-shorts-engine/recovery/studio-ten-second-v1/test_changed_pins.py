"""New changed-row pin chain only; never rehash the inherited runtime closure."""
from pathlib import Path
import hashlib
import json
import re
import unittest

HERE=Path(__file__).resolve().parent
RECOVERY=HERE.parent
REPO=HERE.parents[2]
HANDOFF=RECOVERY/'codex-to-gcube-handoff-v1'
def sha(value): return hashlib.sha256(value).hexdigest()

class ChangedPinTests(unittest.TestCase):
    def test_new_source_and_startup_links(self):
        receipt=json.loads((HERE/'evidence/PIN_UPDATE_RECEIPT.json').read_text())
        runtime_raw=(HANDOFF/'RUNTIME_SOURCE_MANIFEST.json').read_bytes()
        runtime=json.loads(runtime_raw)
        self.assertEqual(len(runtime['files']),353)
        changed=set(receipt['updatedRows']+receipt['existingG2DependenciesAdded'])
        for row in runtime['files']:
            if row['path'] in changed:
                raw=(REPO/row['path']).read_bytes()
                self.assertEqual(row['sha256'],sha(raw))
                self.assertEqual(row['bytes'],len(raw))
        # Check inherited JSON row identity, without reading inherited source files.
        reused=[r for r in runtime['files'] if r['path'] not in changed]
        self.assertEqual(len(reused),receipt['reusedRowCount'])
        self.assertEqual(sha(json.dumps(reused,sort_keys=True,separators=(',',':')).encode()),receipt['reusedManifestRowsBindingSHA256'])
        variants=json.loads((HANDOFF/'backend/GENERATED_SOURCE_MANIFEST.json').read_text())
        capture=next(r for r in variants['variants'] if r['variant']=='capture_vulkan.generated.mjs')
        self.assertEqual(capture['variantSHA256'],sha((HANDOFF/capture['variant']).read_bytes()))
        startup=RECOVERY/'studio-cold-start-v2'
        boot=(startup/'bootstrap.py').read_bytes()
        source_pin=re.search(rb"^SOURCE_SHA = '([0-9a-f]{64})'",boot,re.M).group(1).decode()
        self.assertEqual(source_pin,sha(runtime_raw))
        manifest=json.loads((startup/'STARTUP_MANIFEST.json').read_text())
        self.assertEqual(manifest['runtimeManifestSHA256'],source_pin)
        self.assertEqual(manifest['files']['bootstrap.py'],{'sha256':sha(boot),'bytes':len(boot)})

if __name__=='__main__': unittest.main(verbosity=2)
