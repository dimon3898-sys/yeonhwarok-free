"""Only new label asset coverage and changed pin links; no old PASS suite."""
from pathlib import Path
import hashlib
import json
import re
import unittest
from fontTools.ttLib import TTFont

HERE=Path(__file__).resolve().parent
RECOVERY=HERE.parent
REPO=HERE.parents[2]
HANDOFF=RECOVERY/'codex-to-gcube-handoff-v1'
def sha(raw):return hashlib.sha256(raw).hexdigest()

class NewLabelPinAndFontTests(unittest.TestCase):
    def test_supported_text_range_has_real_pinned_font_glyphs(self):
        file=REPO/'world-simulation-shorts-engine/web/fonts/NotoSansCJKkr-Bold.otf'
        self.assertEqual(sha(file.read_bytes()),'da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0')
        font=TTFont(file)
        cmap=font.getBestCmap()
        supported=set(range(0xAC00,0xD7A4))|set(map(ord,"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,:;!?%+-/()[]{}=_'\"#&@$"))
        self.assertFalse(supported-set(cmap))
        font.close()

    def test_new_modules_and_changed_source_pin_chain(self):
        receipt=json.loads((HERE/'evidence/PIN_UPDATE_RECEIPT.json').read_text())
        raw=(HANDOFF/'RUNTIME_SOURCE_MANIFEST.json').read_bytes()
        value=json.loads(raw);self.assertEqual(len(value['files']),355)
        changed=set(receipt['changedRows']+receipt['newModules'])
        for row in value['files']:
            if row['path'] in changed:
                data=(REPO/row['path']).read_bytes()
                self.assertEqual(row['sha256'],sha(data));self.assertEqual(row['bytes'],len(data))
        # Reused row metadata only: never read the inherited source closure.
        inherited=[r for r in value['files'] if r['path'] not in changed]
        self.assertEqual(len(inherited),receipt['reusedRows'])
        self.assertEqual(sha(json.dumps(inherited,sort_keys=True,separators=(',',':')).encode()),receipt['reusedRowsBindingSHA256'])
        variants=json.loads((HANDOFF/'backend/GENERATED_SOURCE_MANIFEST.json').read_text())
        row=next(r for r in variants['variants'] if r['variant']=='presentation_runtime_vulkan.generated.mjs')
        self.assertEqual(row['originalSHA256'],sha((REPO/row['original']).read_bytes()))
        self.assertEqual(row['variantSHA256'],sha((HANDOFF/row['variant']).read_bytes()))
        startup=RECOVERY/'studio-cold-start-v2'
        boot=(startup/'bootstrap.py').read_bytes()
        self.assertEqual(re.search(rb"^SOURCE_SHA = '([a-f0-9]{64})'",boot,re.M).group(1).decode(),sha(raw))
        manifest=json.loads((startup/'STARTUP_MANIFEST.json').read_text())
        self.assertEqual(manifest['runtimeManifestSHA256'],sha(raw))
        self.assertEqual(manifest['files']['bootstrap.py'],{'bytes':len(boot),'sha256':sha(boot)})

if __name__=='__main__':unittest.main(verbosity=2)
