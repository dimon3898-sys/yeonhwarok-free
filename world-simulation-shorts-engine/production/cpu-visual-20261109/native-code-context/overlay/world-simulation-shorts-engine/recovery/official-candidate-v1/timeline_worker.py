"""Official sequential chunk transport and composition; never grants admission."""
import copy
import json
from pathlib import Path
import importlib.util
_candidate_spec=importlib.util.spec_from_file_location('_up2_timeline_candidate_contract',Path(__file__).with_name('candidate_activation_contract.py'))
_candidate_contract=importlib.util.module_from_spec(_candidate_spec)
_candidate_spec.loader.exec_module(_candidate_contract)
validate_candidate_activation=_candidate_contract.validate_candidate_activation
verify_candidate_receipt=_candidate_contract.verify_candidate_receipt
candidate_for_chunk=_candidate_contract.candidate_for_chunk


def chunk_capture_wire(pipeline, index, sha):
    """Preserve authoritative Node member ordering; never reserialize geometry."""
    admission=pipeline['sourceAdmission'];plan=admission['chunkPlan']
    rows=admission.get('chunkCaptureWires')
    if not isinstance(rows,list) or len(rows)!=len(plan['chunks']):
        raise RuntimeError('UP2_TIMELINE_CAPTURE_WIRES_REQUIRED')
    chunk=plan['chunks'][index];row=rows[index]
    if (not isinstance(row,dict) or set(row)!={'chunkRequestSHA256','wireJSON','wireSHA256'}
            or row['chunkRequestSHA256']!=chunk['requestSHA256'] or not isinstance(row['wireJSON'],str)):
        raise RuntimeError('UP2_TIMELINE_CAPTURE_WIRE_IDENTITY')
    raw=row['wireJSON'].encode('utf-8')
    if len(raw)>24*1024**2 or sha(raw)!=row['wireSHA256']:
        raise RuntimeError('UP2_TIMELINE_CAPTURE_WIRE_HASH')
    expected={'schema':'WORLD_ENGINE_OFFICIAL_SCENE_CHUNK_CAPTURE_V1','plan':plan,'chunk':chunk}
    if 'candidateActivation' in pipeline:
        expected.update(candidateActivation=pipeline['candidateActivation'],candidateActivationSHA256=pipeline['candidateActivationSHA256'])
    if json.loads(raw)!=expected:
        raise RuntimeError('UP2_TIMELINE_CAPTURE_WIRE_SEMANTICS')
    return raw


def validate_timeline(pipeline, sha, canonical):
    admission = pipeline['sourceAdmission']
    plan, qualification = admission.get('chunkPlan', {}), admission['sourceQualification']
    original = pipeline['runtimePayload']
    chunks, rows = plan.get('chunks'), qualification.get('chunks')
    if (pipeline.get('durationSeconds') != 10 or admission.get('candidateSourceAdmitted') is not False
            or plan.get('schema') != 'WORLD_ENGINE_SEALED_TIMELINE_V1'
            or plan.get('original') != original or original.get('durationSeconds') != 10
            or original.get('totalFrames') != 300 or plan.get('productionAdmitted') is not False
            or plan.get('originalSHA256') != sha(canonical(original))
            or qualification.get('originalSHA256') != plan['originalSHA256']
            or not isinstance(chunks, list) or not 2 <= len(chunks) <= 16
            or not isinstance(rows, list) or len(rows) != len(chunks)):
        raise RuntimeError('UP2_TIMELINE_PLAN_SEAL_INVALID')
    frame, segment = 0, 0
    for index, (chunk, row) in enumerate(zip(chunks, rows)):
        start, end = chunk.get('segmentRange', [None, None])
        first, last = chunk.get('globalRange', [None, None])
        if (type(start) is not int or type(end) is not int or start != segment
                or not start < end <= len(original['segments']) or first != frame
                or first != original['segments'][start]['startFrame']
                or last != original['segments'][end-1]['endFrame'] or not 2 <= last-first <= 240):
            raise RuntimeError('UP2_TIMELINE_CHUNK_RANGE_INVALID')
        expected = copy.deepcopy(original)
        expected.pop('durationSeconds', None)
        expected['segments'] = expected['segments'][start:end]
        for scene in expected['segments']:
            scene['startFrame'] -= first
            scene['endFrame'] -= first
        expected['totalFrames'] = last-first
        expected['transitions'] = [{'type':'CUT','frame':s['startFrame']} for s in expected['segments'][1:]]
        wire = row.get('sourceQualificationWireJSON')
        q = row.get('sourceQualification', {})
        if (chunk.get('schema') != 'WORLD_ENGINE_SEALED_SCENE_CHUNK_V1'
                or chunk.get('request') != expected or chunk.get('requestSHA256') != sha(canonical(expected))
                or chunk.get('originalSHA256') != plan['originalSHA256']
                or row.get('index') != index or row.get('globalRange') != [first,last]
                or row.get('requestSHA256') != chunk['requestSHA256']
                or not isinstance(wire, str) or sha(wire.encode()) != row.get('sourceQualificationSHA256')
                or json.loads(wire) != q or q.get('schema') != 'WORLD_ENGINE_PRESENTATION_SOURCES_V2'
                or q.get('totalFrames') != last-first):
            raise RuntimeError('UP2_TIMELINE_CHUNK_SEAL_INVALID')
        frame, segment = last, end
    if frame != 300 or segment != len(original['segments']):
        raise RuntimeError('UP2_TIMELINE_COVERAGE_INVALID')
    for index in range(len(chunks)):
        chunk_capture_wire(pipeline,index,sha)
    validate_candidate_activation(pipeline,sha,canonical)
    return plan


def execute_timeline(*, pipeline, job, output_root, here, supervisor, sha, canonical,
                     validate_capture, atomic, state, state_file):
    plan = validate_timeline(pipeline, sha, canonical)
    output_root.mkdir(mode=0o700)  # Exclusive job output; no stale outputs accepted.
    validations, videos, credits, candidate_credits = [], [], [], []
    for index, chunk in enumerate(plan['chunks']):
        supervisor.check()
        raw = chunk_capture_wire(pipeline,index,sha)
        package_file, directory = job / ('chunk-%03d.json' % index), output_root / ('chunk-%03d' % index)
        with package_file.open('xb') as file:
            file.write(raw)
        package_file.chmod(0o600)
        pin = pipeline['sourceAdmission']['sourceQualification']['chunks'][index]
        capture = supervisor.run(['node', str(here/'capture_scene_chunk.mjs'), '--package='+str(package_file),
            '--expected-sha256='+sha(raw), '--expected-original-sha256='+plan['originalSHA256'],
            '--expected-source-qualification-sha256='+pin['sourceQualificationSHA256'], '--output-root='+str(directory)], text=True)
        count = 0
        for line in capture.stdout.splitlines():
            if len(line) > 16384:
                raise RuntimeError('UP2_CAPTURE_PROGRESS_INVALID')
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('stage') != 'ACTUAL_FRAME_DRAW':
                continue
            count += 1
            if row.get('renderedFrames') != count or row.get('frame') != count-1 or row.get('totalFrames') != chunk['request']['totalFrames']:
                raise RuntimeError('UP2_CAPTURE_PROGRESS_INVALID')
        if count != chunk['request']['totalFrames']:
            raise RuntimeError('UP2_CAPTURE_ACTUAL_FRAME_PROGRESS_INCOMPLETE')
        runtime_file = Path(str(package_file)+'.runtime.json')
        if runtime_file.is_symlink() or not runtime_file.is_file():
            raise RuntimeError('UP2_TIMELINE_RUNTIME_FILE_INVALID')
        runtime_wire = runtime_file.read_bytes()
        if json.loads(runtime_wire) != chunk['request']:
            raise RuntimeError('UP2_TIMELINE_RUNTIME_WIRE_CHANGED')
        child_pipeline = dict(pipeline, totalFrames=count, runtimeWireSHA256=sha(runtime_wire),
                              runtimeSemanticSHA256=chunk['requestSHA256'], sourceAdmission=pin,candidateChunkRequestSHA256=chunk['requestSHA256'])
        validations.append(validate_capture(directory, child_pipeline, runner=supervisor.run))
        child_receipt = json.loads((directory/'CAPTURE_RECEIPT.json').read_bytes())
        candidate = verify_candidate_receipt(pipeline,child_receipt,chunk['requestSHA256'],sha,canonical)
        if candidate is not None:
            for credit in candidate['credits']:
                if credit not in candidate_credits:
                    candidate_credits.append(credit)
        child_credits = child_receipt.get('sourceCredits')
        if not isinstance(child_credits, list) or len(child_credits) != chunk['segmentRange'][1]-chunk['segmentRange'][0]:
            raise RuntimeError('UP2_TIMELINE_CREDITS_MISSING')
        for local_index, credit in enumerate(child_credits):
            if (credit.get('segmentIndex') != local_index or not credit.get('attribution')
                    or not credit.get('license') or not credit.get('sourceURL')):
                raise RuntimeError('UP2_TIMELINE_CREDITS_INVALID')
            credits.append(dict(credit, segmentIndex=chunk['segmentRange'][0]+local_index))
        videos.append(directory/'VIDEO.mp4')
        state.update(processedFrames=chunk['globalRange'][1],completedScenes=chunk['segmentRange'][1],phase='SCENE_CHUNK_VERIFIED')
        atomic(state_file,state)
    supervisor.check()
    # Relative generated names only; no user-controlled concat syntax or URLs.
    concat = output_root/'chunks.concat'
    with concat.open('x') as file:
        file.write(''.join("file 'chunk-%03d/VIDEO.mp4'\n" % i for i in range(len(videos))))
    credit_parts = []
    for credit in credits:
        license_text = credit['license'] if isinstance(credit['license'], str) else json.dumps(credit['license'],ensure_ascii=False,separators=(',',':'))
        text = credit['attribution']+'; license='+license_text+'; source='+credit['sourceURL']
        if text not in credit_parts:
            credit_parts.append(text)
    credit_text = ' | '.join(credit_parts)+' | Modifications: native-pixel crop, geographic map rendering and supplied event graphics.'
    if candidate_credits:
        credit_text += ' | '+' | '.join(_candidate_contract.candidate_credit_text(row) for row in candidate_credits)
    supervisor.run(['ffmpeg','-v','error','-nostdin','-f','concat','-safe','1','-i',str(concat),'-map','0:v:0','-an','-c','copy','-metadata','comment='+credit_text,'-metadata','copyright='+credit_text,'-n',str(output_root/'VIDEO.mp4')])
    media = supervisor.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(output_root/'VIDEO.mp4')],timeout=60)
    metadata = json.loads(media.stdout)
    streams = metadata.get('streams',[])
    if (len(streams)!=1 or streams[0].get('codec_type')!='video' or streams[0].get('codec_name')!='h264'
            or streams[0].get('width')!=1080 or streams[0].get('height')!=1920
            or streams[0].get('r_frame_rate')!='30/1' or int(streams[0].get('nb_read_frames',-1))!=300
            or abs(float(metadata.get('format',{}).get('duration',-1))-10)>.001):
        raise RuntimeError('UP2_TIMELINE_MEDIA_CONTRACT_INVALID')
    tags = metadata.get('format',{}).get('tags',{})
    if tags.get('comment') != credit_text or tags.get('copyright') != credit_text:
        raise RuntimeError('UP2_TIMELINE_EMBEDDED_CREDITS_MISSING')
    decoded = supervisor.run(['ffmpeg','-v','error','-nostdin','-i',str(output_root/'VIDEO.mp4'),'-f','null','-'],timeout=60)
    if decoded.stderr:
        raise RuntimeError('UP2_TIMELINE_FULL_DECODE_FAILED')
    cleanup = supervisor.assert_complete()
    data = (output_root/'VIDEO.mp4').read_bytes()
    receipt = {'schema':'WORLD_ENGINE_PRESENTATION_TIMELINE_CAPTURE_V1','status':'TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED',
        'originalSHA256':plan['originalSHA256'],'sourceQualificationSHA256':pipeline['sourceAdmission']['sourceQualificationSHA256'],
        'totalFrames':300,'renderedFrames':300,'durationSeconds':10,'softwareOnly':True,'gpuRenderingVerified':False,
        'visualQualityApproved':False,'paidExecuted':False,'sourceCredits':credits,'embeddedSourceCredits':{'text':credit_text},'children':validations,'cleanup':cleanup,
        'video':{'sha256':sha(data),'bytes':len(data),'fullDecode':'PASS'}}
    if 'candidateActivation' in pipeline:
        sidecar_bytes = (credit_text+'\n').encode('utf-8')
        with (output_root/'SOURCE_CREDITS.txt').open('xb') as file:
            file.write(sidecar_bytes)
        receipt['sourceCreditSidecar'] = {'file':'SOURCE_CREDITS.txt','sha256':sha(sidecar_bytes),
            'bytes':len(sidecar_bytes),'encoding':'UTF-8','contains':'EXACT_NATIVE_AND_CANDIDATE_ATTRIBUTION_TEXT'}
        receipt.update(candidateActivation=pipeline['candidateActivation'],candidateActivationSHA256=pipeline['candidateActivationSHA256'],candidateRegistrySHA256=pipeline['candidateActivation']['registrySHA256'],candidateCredits=candidate_credits,candidateCreditsSHA256=sha(canonical(candidate_credits)))
    supervisor.check()
    atomic(output_root/'CAPTURE_RECEIPT.json',receipt)
    with (output_root/'SHA256SUMS').open('x') as file:
        file.write(sha(data)+'  VIDEO.mp4\n')
    supervisor.check()
    return receipt
