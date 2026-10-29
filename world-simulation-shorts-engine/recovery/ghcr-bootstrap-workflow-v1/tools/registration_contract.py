"""Pure GHCR first-registration proof contract; performs no external effects.

The first package can be created only by a separately approved future image copy.
This module validates declared proof metadata; it does not query GitHub or grant
permissions. It never enables the existing normal publication policy.
"""
from __future__ import annotations

import hashlib
import json
import re

OWNER = 'dimon3898-sys'
BOOTSTRAP_REPOSITORY = OWNER + '/world-engine-ghcr-candidate-bootstrap'
ORIGINAL_REPOSITORY = OWNER + '/yeonhwarok-free'
SUCCESS_PACKAGE = 'ghcr.io/' + OWNER + '/world-simulation-shorts-engine'
SUCCESS_DIGEST = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
SOURCE_IMAGE = SUCCESS_PACKAGE + '@' + SUCCESS_DIGEST
CANDIDATE_PACKAGE = 'ghcr.io/' + OWNER + '/world-engine-vulkan-surface-candidates'


def require(value, code):
    if not value:
        raise RuntimeError(code)


def binding(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _sha(value):
    return type(value) is str and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def _object(value, keys, code):
    require(isinstance(value, dict) and set(value) == set(keys), code)


def _positive_time(value):
    return type(value) is int and 0 < value <= 9007199254740991


def bootstrap_tag(run_id):
    require(type(run_id) is str and re.fullmatch(r'[1-9][0-9]{0,19}', run_id),
            'FIRST_RUN_ID_INVALID')
    return 'bootstrap-parent-9378a86d8134-' + run_id + '-a1'


def _old_package_access(snapshot):
    _object(snapshot, ('schema', 'packageRepository', 'subjectRepository', 'source',
        'proofSHA256', 'observedAtUnixMs', 'linked', 'permissionInheritance',
        'actionsRole', 'canWrite', 'canDelete', 'mutationProbePerformed'),
        'FIRST_OLD_PACKAGE_ACCESS_SCHEMA_INVALID')
    require(snapshot['schema'] == 'WORLD_ENGINE_READ_ONLY_PACKAGE_ACCESS_SNAPSHOT_V1'
        and snapshot['packageRepository'] == SUCCESS_PACKAGE
        and snapshot['subjectRepository'] == BOOTSTRAP_REPOSITORY,
        'FIRST_OLD_PACKAGE_ACCESS_SUBJECT_INVALID')
    require(snapshot['source'] in ('PACKAGE_SETTINGS_READ_ONLY', 'ADMIN_EXPORT_READ_ONLY')
        and _sha(snapshot['proofSHA256']) and _positive_time(snapshot['observedAtUnixMs'])
        and snapshot['mutationProbePerformed'] is False,
        'FIRST_READ_ONLY_ACL_PROVENANCE_REQUIRED')
    require(snapshot['linked'] is False and snapshot['permissionInheritance'] is False
        and snapshot['actionsRole'] in ('NONE', 'READ')
        and snapshot['canWrite'] is False and snapshot['canDelete'] is False,
        'FIRST_SUCCESSFUL_PACKAGE_WRITE_OR_ADMIN_ACCESS_FORBIDDEN')


PLAN_KEYS = ('schema', 'status', 'separateRegistrationApprovalRecorded', 'approval',
    'namespaceOwner', 'namespaceType', 'bootstrapRepository', 'workflowRepository',
    'githubContextRepository', 'reusableWorkflowUsed', 'credentialKind',
    'credentialRepository', 'packagesPermission', 'contentsPermission',
    'runId', 'runAttempt', 'reviewedHeadSHA', 'trigger', 'runner',
    'repositoryPublic', 'zeroCostConfirmed', 'budgetStopConfirmed',
    'sourceImage', 'candidateRepository', 'destination', 'candidateAbsence',
    'successfulPackageAccessBefore', 'firstCreationAdminAcknowledged',
    'candidateDeleteCapabilityDeniedClaimed', 'requestedVisibility',
    'imageBuildAllowed', 'sourceMutationAllowed', 'destructiveOperationsAllowed',
    'gpuAllowed', 'normalPublisherEnabled', 'existingPassTestsRerun')


def validate_first_registration_plan(plan):
    _object(plan, PLAN_KEYS, 'FIRST_PLAN_SCHEMA_OR_EXTRA_FIELDS_INVALID')
    require(plan['schema'] == 'WORLD_ENGINE_GHCR_FIRST_REGISTRATION_PLAN_V1'
        and plan['status'] == 'APPROVED_FOR_SEPARATE_REGISTRATION'
        and plan['separateRegistrationApprovalRecorded'] is True
        and plan['approval'] == 'FIRST_REGISTER_CANDIDATE_PARENT_COPY_ONCE',
        'FIRST_SEPARATE_APPROVAL_REQUIRED')
    require(plan['namespaceOwner'] == OWNER and plan['namespaceType'] == 'USER'
        and plan['bootstrapRepository'] == BOOTSTRAP_REPOSITORY
        and plan['workflowRepository'] == BOOTSTRAP_REPOSITORY
        and plan['githubContextRepository'] == BOOTSTRAP_REPOSITORY
        and plan['credentialRepository'] == BOOTSTRAP_REPOSITORY
        and plan['reusableWorkflowUsed'] is False,
        'FIRST_SEPARATE_REPOSITORY_TOKEN_CONTEXT_REQUIRED')
    require(plan['credentialKind'] == 'GITHUB_TOKEN'
        and plan['packagesPermission'] == 'write'
        and plan['contentsPermission'] == 'read',
        'FIRST_OWNER_PAT_OR_BROAD_CREDENTIAL_FORBIDDEN')
    require(type(plan['runAttempt']) is int and plan['runAttempt'] == 1
        and type(plan['reviewedHeadSHA']) is str
        and re.fullmatch('[a-f0-9]{40}', plan['reviewedHeadSHA'])
        and plan['trigger'] == 'workflow_dispatch'
        and plan['runner'] == 'github-hosted-standard-ubuntu-24.04'
        and plan['repositoryPublic'] is True
        and plan['zeroCostConfirmed'] is True and plan['budgetStopConfirmed'] is True,
        'FIRST_MANUAL_COST_AND_SINGLE_ATTEMPT_GATES_REQUIRED')
    tag = bootstrap_tag(plan['runId'])
    require(plan['sourceImage'] == SOURCE_IMAGE
        and plan['candidateRepository'] == CANDIDATE_PACKAGE
        and plan['destination'] == CANDIDATE_PACKAGE + ':' + tag,
        'FIRST_FIXED_PARENT_COPY_DESTINATION_REQUIRED')
    absence = plan['candidateAbsence']
    _object(absence, ('schema', 'repository', 'status', 'httpStatus',
        'authorizedMetadataRead', 'readPrincipalRole', 'source', 'proofSHA256', 'observedAtUnixMs'),
        'FIRST_ABSENCE_SCHEMA_INVALID')
    require(absence['schema'] == 'WORLD_ENGINE_PACKAGE_ABSENCE_PROOF_V1'
        and absence['repository'] == CANDIDATE_PACKAGE
        and absence['status'] == 'CONFIRMED_ABSENT'
        and type(absence['httpStatus']) is int and absence['httpStatus'] == 404
        and absence['authorizedMetadataRead'] is True
        and absence['readPrincipalRole'] == 'NAMESPACE_OWNER'
        and absence['source'] in ('NAMESPACE_OWNER_UI_READ_ONLY', 'NAMESPACE_OWNER_API_READ_ONLY')
        and _sha(absence['proofSHA256']) and _positive_time(absence['observedAtUnixMs']),
        'FIRST_AUTHORIZED_ABSENCE_PROOF_REQUIRED')
    _old_package_access(plan['successfulPackageAccessBefore'])
    require(plan['firstCreationAdminAcknowledged'] is True
        and plan['candidateDeleteCapabilityDeniedClaimed'] is False
        and plan['requestedVisibility'] == 'private',
        'FIRST_CREATOR_ADMIN_AND_PRIVATE_VISIBILITY_MUST_BE_ACKNOWLEDGED')
    require(all(plan[key] is False for key in ('imageBuildAllowed',
        'sourceMutationAllowed', 'destructiveOperationsAllowed', 'gpuAllowed',
        'normalPublisherEnabled', 'existingPassTestsRerun')),
        'FIRST_FORBIDDEN_OPERATION_OR_NORMAL_PUBLISH_ENABLED')
    return {'status': 'FIRST_REGISTRATION_PLAN_VALID_NOT_EXECUTED',
        'planBindingSHA256': binding(plan), 'destination': plan['destination'],
        'sourceRegistryDigest': SUCCESS_DIGEST, 'seedIsVulkanCandidate': False,
        'normalPublicationReady': False, 'livePermissionsVerifiedByModule': False,
        'actualPackageCreationPerformed': False}


SEED_KEYS = ('schema', 'status', 'planBindingSHA256', 'packageId', 'destination',
    'sourceRegistryDigest', 'destinationTagDigest', 'destinationAddressedDigest',
    'successfulTagBeforeDigest', 'successfulTagAfterDigest', 'manifestBytesEqual',
    'configDigestPreserved', 'imageBytesUnmodified', 'configuredLabelsChanged',
    'packageAssociationRepository', 'packageAssociationVerifiedReadOnly',
    'autoAssociationAssumed', 'visibility', 'visibilityObservedReadOnly',
    'bootstrapTokenNewPackageRole', 'creatorAdminCapabilityAcknowledged',
    'bootstrapJobStatus', 'bootstrapTokenStatus', 'bootstrapTokenExpiryEvidenceSHA256',
    'successfulPackageAccessAfter', 'logicalCopyAttempts', 'retryCount',
    'deleteRequests', 'gpuExecuted', 'imageBuilt', 'normalPublicationPerformed',
    'registrationEvidenceSHA256')


def validate_created_seed(plan, receipt):
    checked = validate_first_registration_plan(plan)
    _object(receipt, SEED_KEYS, 'FIRST_SEED_RECEIPT_SCHEMA_INVALID')
    require(receipt['schema'] == 'WORLD_ENGINE_GHCR_CREATED_SEED_RECEIPT_V1'
        and receipt['status'] == 'FIRST_REGISTRATION_COMPLETE_QUARANTINED'
        and receipt['planBindingSHA256'] == checked['planBindingSHA256']
        and receipt['destination'] == checked['destination']
        and type(receipt['packageId']) is int and receipt['packageId'] > 0,
        'FIRST_SEED_IDENTITY_BINDING_INVALID')
    require(all(receipt[key] == SUCCESS_DIGEST for key in ('sourceRegistryDigest',
        'destinationTagDigest', 'destinationAddressedDigest',
        'successfulTagBeforeDigest', 'successfulTagAfterDigest'))
        and receipt['manifestBytesEqual'] is True
        and receipt['configDigestPreserved'] is True
        and receipt['imageBytesUnmodified'] is True
        and receipt['configuredLabelsChanged'] is False,
        'FIRST_SEED_MUST_BE_UNMODIFIED_PARENT_NOT_VULKAN_CANDIDATE')
    require(receipt['packageAssociationRepository'] == BOOTSTRAP_REPOSITORY
        and receipt['packageAssociationVerifiedReadOnly'] is True
        and receipt['autoAssociationAssumed'] is False
        and receipt['visibility'] == 'private'
        and receipt['visibilityObservedReadOnly'] is True,
        'FIRST_CREATED_ASSOCIATION_AND_VISIBILITY_PROOF_REQUIRED')
    require(receipt['bootstrapTokenNewPackageRole'] == 'ADMIN'
        and receipt['creatorAdminCapabilityAcknowledged'] is True
        and receipt['bootstrapJobStatus'] == 'COMPLETED'
        and receipt['bootstrapTokenStatus'] == 'EXPIRED_JOB_TOKEN'
        and _sha(receipt['bootstrapTokenExpiryEvidenceSHA256']),
        'FIRST_BOOTSTRAP_ADMIN_AND_TOKEN_EXPIRY_PROOF_REQUIRED')
    _old_package_access(receipt['successfulPackageAccessAfter'])
    require(receipt['successfulPackageAccessAfter']['observedAtUnixMs']
            >= plan['successfulPackageAccessBefore']['observedAtUnixMs'],
            'FIRST_POST_ACCESS_PROOF_PREDATES_PLAN')
    require(type(receipt['logicalCopyAttempts']) is int and receipt['logicalCopyAttempts'] == 1
        and type(receipt['retryCount']) is int and receipt['retryCount'] == 0
        and type(receipt['deleteRequests']) is int and receipt['deleteRequests'] == 0
        and receipt['gpuExecuted'] is False and receipt['imageBuilt'] is False
        and receipt['normalPublicationPerformed'] is False
        and _sha(receipt['registrationEvidenceSHA256']),
        'FIRST_EXECUTION_OR_RETRY_RECEIPT_INVALID')
    return {'status': 'SEED_QUARANTINED_NOT_NORMAL_PUBLISH_READY',
        'seedBindingSHA256': binding(receipt), 'packageId': receipt['packageId'],
        'seedIsVulkanCandidate': False, 'normalPublicationReady': False,
        'newCandidateAdminCapabilityAcknowledged': True,
        'existingSuccessfulPackageWriteOrDeleteAllowed': False,
        'actualPackageCreationPerformedByModule': False}


HANDOFF_KEYS = ('schema', 'status', 'candidateRepository', 'packageId',
    'seedBindingSHA256', 'inheritanceEnabled', 'bootstrapActionsRole',
    'bootstrapActionsAccessRemoved', 'bootstrapWorkflowDisabled',
    'normalPublisherIdentity', 'normalPublisherIsNamespaceOwner',
    'normalPublisherCandidateRole', 'normalPublisherHasDeleteScope',
    'normalPublisherCanAdminCandidate', 'normalPublisherCanWriteSuccessful',
    'normalPublisherCanDeleteSuccessful', 'normalPublisherSuccessfulAccessEvidenceSHA256',
    'automatedWriterIdentities', 'onlyAutomatedWriterVerified',
    'ownerAdminsAcknowledged', 'ownerAdminExceptionApproved', 'aclEvidenceSHA256',
    'separateNormalPublicationApprovalRequired', 'normalPolicyAutomaticallyActivated',
    'newSecretCreatedByContract', 'packageSettingsChangedByContract')


def validate_normal_handoff(plan, seed_receipt, acl_receipt):
    seed = validate_created_seed(plan, seed_receipt)
    acl = acl_receipt
    _object(acl, HANDOFF_KEYS, 'FIRST_HANDOFF_SCHEMA_INVALID')
    require(acl['schema'] == 'WORLD_ENGINE_GHCR_POST_REGISTRATION_ACL_V1'
        and acl['status'] == 'VERIFIED_READ_ONLY'
        and acl['candidateRepository'] == CANDIDATE_PACKAGE
        and type(acl['packageId']) is int
        and acl['packageId'] == seed['packageId']
        and acl['seedBindingSHA256'] == seed['seedBindingSHA256'],
        'FIRST_HANDOFF_IDENTITY_BINDING_INVALID')
    require(acl['inheritanceEnabled'] is False
        and acl['bootstrapActionsRole'] == 'NONE'
        and acl['bootstrapActionsAccessRemoved'] is True
        and acl['bootstrapWorkflowDisabled'] is True,
        'FIRST_BOOTSTRAP_ACCESS_MUST_BE_REMOVED_BEFORE_HANDOFF')
    identity = acl['normalPublisherIdentity']
    require(type(identity) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', identity)
        and identity.lower() != OWNER.lower()
        and acl['normalPublisherIsNamespaceOwner'] is False
        and acl['normalPublisherCandidateRole'] == 'WRITE'
        and acl['normalPublisherHasDeleteScope'] is False
        and acl['normalPublisherCanAdminCandidate'] is False
        and acl['normalPublisherCanWriteSuccessful'] is False
        and acl['normalPublisherCanDeleteSuccessful'] is False
        and _sha(acl['normalPublisherSuccessfulAccessEvidenceSHA256']),
        'FIRST_NORMAL_PUBLISHER_MUST_BE_CANDIDATE_ONLY_WRITER')
    require(acl['automatedWriterIdentities'] == [identity]
        and acl['onlyAutomatedWriterVerified'] is True
        and acl['ownerAdminsAcknowledged'] is True
        and acl['ownerAdminExceptionApproved'] is True
        and _sha(acl['aclEvidenceSHA256']),
        'FIRST_EXCLUSIVE_AUTOMATED_WRITER_AND_OWNER_ADMIN_ACK_REQUIRED')
    require(acl['separateNormalPublicationApprovalRequired'] is True
        and acl['normalPolicyAutomaticallyActivated'] is False
        and acl['newSecretCreatedByContract'] is False
        and acl['packageSettingsChangedByContract'] is False,
        'FIRST_NO_AUTOMATIC_NORMAL_POLICY_OR_SETTINGS_CHANGE')
    return {'status': 'NORMAL_POLICY_ELIGIBLE_FOR_SEPARATE_APPROVAL_NOT_ACTIVATED',
        'handoffBindingSHA256': binding(acl), 'packageId': seed['packageId'],
        'normalPolicyActivated': False, 'existingPublisherCodeModified': False,
        'settingsOrSecretsChangedByModule': False, 'seedIsVulkanCandidate': False,
        'livePermissionsVerifiedByModule': False}
