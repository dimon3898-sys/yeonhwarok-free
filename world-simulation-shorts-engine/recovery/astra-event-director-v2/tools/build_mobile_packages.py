"""Allowlisted review ZIPs, each below the 32 MiB attachment transfer ceiling."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'public-review'
MAX=32*1024*1024
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
media=json.loads((ROOT/'reports/MEDIA_VALIDATION.json').read_bytes())
visual=json.loads((ROOT/'reports/VISUAL_INSPECTION.json').read_bytes())
if media['technicalMediaValidation']!='PASS' or media['visualQualityApproved']:
    raise ValueError('ACTUAL_VALIDATED_SOURCE_REVIEW_ONLY_REQUIRED')
stills=sorted(PUBLIC.glob('FRAME_*.png'))
if len(stills)!=16:
    raise ValueError('ACTUAL_SIXTEEN_STILLS_REQUIRED')
groups={
 'ASTRA_V2_PNG_01_08.zip':stills[:8]+[PUBLIC/'CONTACT_SHEET_16.png',PUBLIC/'PRIOR_VS_NEW_4_TIMES.png'],
 'ASTRA_V2_PNG_09_16.zip':stills[8:],
 'ASTRA_V2_MOTION_AND_REPORTS.zip':sorted(PUBLIC.glob('*.mp4'))+sorted(PUBLIC.glob('M*_FRAMES.json'))+
   [PUBLIC/'MOTION_FILMSTRIP.png',ROOT/'RESULT.md',ROOT/'REPRODUCTION.md']+
   sorted((ROOT/'docs').glob('*.md'))+
   [ROOT/'reports'/n for n in ['ACTUAL_ANALYSIS.json','MEDIA_VALIDATION.json','VISUAL_INSPECTION.json',
    'FRAME_REVIEW_16.csv','FEATURE_STATUS_151.csv','FEATURE_STATUS_SUMMARY.json','PRESERVATION.json',
    'FOCUSED_TESTS.json','P0_HISTORY_MAPPING.json','P0_SOURCE_ACQUISITION.json','P0_SOURCE_SECOND_REVIEW_R2.json',
    'DERIVATION.json','SECRET_SCAN_FINAL.json','SOURCE_FILES.json']]+
   [ROOT/'fixtures'/n for n in ['EVENT_DIRECTOR_SOURCE_REVIEW_REQUEST.json','HISTORY_EVENT_PROFILE_V2.json',
    'HISTORY_SOURCE_CATALOG.json','CONTROL_TIMELINE.json','CAMERA_REVIEW_PROFILE.json','CAMERA_ADMISSION.json',
    'MARKER_EVIDENCE.json','AUDIO_CUE_MANIFEST.json','DERIVED_SCENE.json']]+
   [ROOT/'source-review/CMH_APPLEMAN_1950_06_28_PARTIAL_FRONT.geojson']+
   [p for p in sorted(ROOT.rglob('*')) if p.is_file() and p.suffix in {'.mjs','.py'} and '.private' not in p.parts and '__pycache__' not in p.parts]
}
receipt=[]
for name,files in groups.items():
    target=PUBLIC/name
    if target.exists():
        raise ValueError('REFUSE_EXISTING_REVIEW_PACKAGE_OVERWRITE')
    if len(files)!=len(set(files)) or any(not p.is_file() or p.is_symlink() for p in files):
        raise ValueError('REVIEW_ALLOWLIST_REGULAR_FILES_REQUIRED')
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        manifest=[]
        for p in files:
            relative=p.relative_to(ROOT).as_posix()
            if '.private' in p.parts or p.suffix.lower() in {'.pdf','.pem','.key'}:
                raise ValueError('REVIEW_PRIVATE_SOURCE_EXCLUDED')
            archive.write(p,relative)
            manifest.append({'file':relative,'sha256':sha(p),'bytes':p.stat().st_size})
        archive.writestr('PACKAGE_MANIFEST.json',json.dumps({'schema':'WORLD_ENGINE_ASTRA_V2_SAFE_REVIEW_PACKAGE_V1',
            'files':manifest,'visualQualityApproved':False,'decision':'NEEDS_REWORK','next':'USER_REVIEW_REQUIRED'},
            ensure_ascii=False,indent=2)+'\n')
    if target.stat().st_size>=MAX:
        raise ValueError('REVIEW_PACKAGE_EXCEEDS_ATTACHMENT_LIMIT')
    receipt.append({'file':name,'sha256':sha(target),'bytes':target.stat().st_size,'entries':len(files),
        'lessThan32MiB':True})
download_files=sorted(p for p in PUBLIC.iterdir() if p.is_file() and p.name!='SHA256SUMS')
(PUBLIC/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n'for p in download_files))
(ROOT/'reports/MOBILE_PACKAGES.json').write_text(json.dumps({'packages':receipt,
    'publicReviewFileCount':len(download_files),'rawPDFsOrSecretsIncluded':False,
    'allFilesRequireActualExternalDownloadVerification':True},indent=2)+'\n')
print(json.dumps(receipt))
