"""Pure CPU checks for server-sealed candidate identity. No registry lookup."""
import re

def _hex(value):
    return isinstance(value,str) and re.fullmatch(r'[a-f0-9]{64}',value) is not None

def capture_identity(pipeline):
    identity={'requestSHA256':pipeline['requestSHA256'],'runtimeSemanticSHA256':pipeline['runtimeSemanticSHA256'],
        'runtimeWireSHA256':pipeline['runtimeWireSHA256'],'sourceAdmission':pipeline['sourceAdmission'],
        'sourceBindings':pipeline['sourceBindings'],'sourceRegistrySHA256':pipeline['sourceRegistrySHA256']}
    if 'candidateActivation' in pipeline:
        identity['candidateActivation']=pipeline['candidateActivation']
        identity['candidateActivationSHA256']=pipeline['candidateActivationSHA256']
    return identity

def validate_candidate_activation(pipeline,sha,canonical):
    active='candidateActivation' in pipeline
    if active != ('candidateActivationSHA256' in pipeline):
        raise RuntimeError('UP2_CANDIDATE_ACTIVATION_PAIR_REQUIRED')
    if not active:return None
    activation=pipeline['candidateActivation'];admission=pipeline['sourceAdmission']
    if (not isinstance(activation,dict) or activation.get('schema')!='WORLD_ENGINE_OFFICIAL_CANDIDATE_ACTIVATION_V1'
            or activation.get('mode')!='CPU_QUALIFIED_GPU_PENDING' or activation.get('productionAdmitted') is not False
            or not _hex(activation.get('registrySHA256')) or pipeline.get('totalFrames')!=300
            or activation.get('originalSemanticSHA256')!=pipeline.get('runtimeSemanticSHA256')
            or activation.get('aggregateQualificationSHA256')!=admission.get('sourceQualificationSHA256')
            or sha(canonical(activation))!=pipeline['candidateActivationSHA256']):
        raise RuntimeError('UP2_CANDIDATE_ACTIVATION_SEAL_INVALID')
    chunks=activation.get('chunks');planned=admission['chunkPlan']['chunks'];qualified=admission['sourceQualification']['chunks']
    if not isinstance(chunks,list) or len(chunks)!=len(planned):raise RuntimeError('UP2_CANDIDATE_ACTIVATION_COVERAGE')
    ids=set()
    for row,chunk,pin in zip(chunks,planned,qualified):
        registration=row.get('registrationId');scene=row.get('sceneKey')
        if (row.get('chunkRequestSHA256')!=chunk['requestSHA256'] or row.get('nativeSourceQualificationSHA256')!=pin['sourceQualificationSHA256']
                or not isinstance(registration,str) or not registration or registration in ids
                or not isinstance(scene,str) or not scene.startswith(activation['originalSemanticSHA256']+':'+chunk['requestSHA256']+':')
                or row.get('materialPolicy')!='MODERN_UNFILLED_SOURCE_V1'
                or row.get('lightingPolicy') not in ('DISABLED','MASKED_HEIGHT_NORMALIZED_V1')
                or not _hex(row.get('shaderSha256')) or not isinstance(row.get('credits'),list) or not row['credits']
                or sha(canonical(row['credits']))!=row.get('creditsSHA256')):
            raise RuntimeError('UP2_CANDIDATE_ACTIVATION_CHUNK_INVALID')
        for credit in row['credits']:
            if (not isinstance(credit,dict) or set(credit)!={'sourceId','license','attribution','sourceURL','transformations','evidenceSHA256'}
                    or any(not isinstance(credit[k],str) or not credit[k] for k in ('sourceId','license','attribution','sourceURL','transformations'))
                    or not _hex(credit['evidenceSHA256'])):
                raise RuntimeError('UP2_CANDIDATE_CREDITS_INVALID')
        ids.add(registration)
    if sha(canonical(capture_identity(pipeline)))!=pipeline.get('captureSignature'):
        raise RuntimeError('UP2_CANDIDATE_CAPTURE_SIGNATURE_INVALID')
    return activation

def candidate_for_chunk(pipeline,chunk_sha):
    activation=pipeline.get('candidateActivation')
    if activation is None:return None
    matches=[row for row in activation['chunks'] if row['chunkRequestSHA256']==chunk_sha]
    if len(matches)!=1:raise RuntimeError('UP2_CANDIDATE_CHUNK_IDENTITY_INVALID')
    return matches[0]

def verify_candidate_receipt(pipeline,receipt,chunk_sha,sha,canonical):
    fields=('candidateActivationSHA256','candidateRegistrySHA256','candidateRegistrationId','candidateSceneKey','candidateCredits','candidateCreditsSHA256')
    row=candidate_for_chunk(pipeline,chunk_sha)
    if row is None:
        if any(key in receipt for key in fields):raise RuntimeError('UP2_UNSEALED_CANDIDATE_RECEIPT')
        return None
    expected=dict(zip(fields,(pipeline['candidateActivationSHA256'],pipeline['candidateActivation']['registrySHA256'],row['registrationId'],row['sceneKey'],row['credits'],row['creditsSHA256'])))
    if any(receipt.get(key)!=value for key,value in expected.items()) or sha(canonical(receipt['candidateCredits']))!=row['creditsSHA256']:
        raise RuntimeError('UP2_CANDIDATE_RECEIPT_IDENTITY_MISMATCH')
    return row


def candidate_credit_text(credit):
    return (credit['attribution']+'; license='+credit['license']+'; source='+credit['sourceURL']
        +'; modifications='+credit['transformations']+'; evidence='+credit['evidenceSHA256'])


def expected_child_credit_text(receipt, candidate):
    parts=[]
    import json
    for credit in receipt['sourceCredits']:
        license_text=credit['license'] if isinstance(credit['license'],str) else json.dumps(credit['license'],ensure_ascii=False,separators=(',',':'))
        text=credit['attribution']+'; license='+license_text+'; source='+credit['sourceURL']
        if text not in parts:parts.append(text)
    base=' | '.join(parts)+' | Modifications: native-pixel crop, geographic map rendering and supplied event graphics.'
    return base+' | '+' | '.join(candidate_credit_text(credit) for credit in candidate['credits'])


def verify_candidate_result(pipeline,result,sha,canonical):
    activation=pipeline.get('candidateActivation')
    if activation is None:
        if any(key in result for key in ('candidateActivation','candidateActivationSHA256','candidateRegistrySHA256','candidateCredits','candidateCreditsSHA256')):
            raise RuntimeError('UP2_UNSEALED_CANDIDATE_RESULT')
        return
    credits=[]
    for chunk in activation['chunks']:
        for credit in chunk['credits']:
            if credit not in credits:credits.append(credit)
    expected={'candidateActivation':activation,'candidateActivationSHA256':pipeline['candidateActivationSHA256'],
        'candidateRegistrySHA256':activation['registrySHA256'],'candidateCredits':credits,'candidateCreditsSHA256':sha(canonical(credits))}
    if any(result.get(key)!=value for key,value in expected.items()):
        raise RuntimeError('UP2_CANDIDATE_RESULT_IDENTITY_MISMATCH')
