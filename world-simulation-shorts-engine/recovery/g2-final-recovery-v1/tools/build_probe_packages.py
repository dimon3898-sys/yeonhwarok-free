"""Hash-bound technical probes using the exact Studio-selected layout adapter."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parents[1]

def main(output_root):
    gates=json.loads((HERE/'reports/GATES.json').read_text())
    if not all(gates.get(k,{}).get('status')=='PASS' for k in ['phaseA','phaseB']):
        raise ValueError('G2_FINAL_PHASE_A_B_REQUIRED')
    spec=importlib.util.spec_from_file_location('_g2_final_probe_adapter',HERE/'source_contract.py')
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    prepared=json.loads((HERE/'reports/GENERIC_REGIONS_PREPARATION.json').read_text())
    output_root=output_root.resolve();output_root.mkdir(mode=0o700,exist_ok=False)
    rows=[]
    for case in prepared['cases']:
        original=Path(case['runtime']['path']);raw=original.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=case['runtime']['sha256']:
            raise ValueError('G2_FINAL_SOURCE_RUNTIME_CHANGED')
        runtime=json.loads(raw)
        receipt_file=HERE/case['receipt']['path'];receipt_raw=receipt_file.read_bytes()
        if hashlib.sha256(receipt_raw).hexdigest()!=case['receipt']['sha256']:
            raise ValueError('G2_FINAL_SOURCE_STYLE_RECEIPT_CHANGED')
        receipt=json.loads(receipt_raw)
        pipeline={'ready':True,'mode':'SYNTHETIC_TEST','totalFrames':len(runtime['frames']),
            'startFrame':0,'sourceStyle':receipt,'sourceStyleSHA256':case['receipt']['sha256'],
            'sourceStyleReceiptSHA256':case['receipt']['sha256']}
        pipeline.update(module.apply_layout_profile(runtime))
        data={'schema':module.SCHEMA,'sourcePipeline':pipeline,
              'classification':'SYNTHETIC_REGION_PROBE_NOT_STUDIO_VIDEO'}
        destination=output_root/(case['id'].upper()+'_PROBE_PACKAGE.json')
        content=module.adapter.canonical(data)
        with destination.open('xb') as f:f.write(content)
        destination.chmod(0o600)
        rows.append({'id':case['id'],'region':case['region'],'plan':str(destination),
            'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),
            'originalRuntimeSHA256':case['runtime']['sha256'],
            'layoutActivationReceipt':pipeline['layoutActivationReceipt'],
            'sourceStyleReceiptSHA256':case['receipt']['sha256'],
            'frames':[0,1,2,1],'outputRoot':str(HERE/'captures'/('region-'+case['id']))})
    report={'schema':'WORLD_ENGINE_G2_FINAL_PROBE_PACKAGES_V1','status':'PREPARED',
        'sameAdapterAsStudio':True,'paidGpuAllowed':False,'cases':rows}
    (HERE/'reports/PROBE_PACKAGES.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','cases':len(rows),'outputRoot':str(output_root)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-root',type=Path,required=True)
    main(p.parse_args().output_root)
