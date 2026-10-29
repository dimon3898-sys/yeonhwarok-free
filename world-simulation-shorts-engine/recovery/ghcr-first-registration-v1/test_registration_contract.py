"""Only new first-registration proof-state simulations; no external effects."""
import copy
import unittest

from registration_contract import (OWNER, BOOTSTRAP_REPOSITORY, ORIGINAL_REPOSITORY,
    SUCCESS_PACKAGE, SUCCESS_DIGEST, SOURCE_IMAGE, CANDIDATE_PACKAGE, bootstrap_tag,
    binding, validate_first_registration_plan, validate_created_seed,
    validate_normal_handoff)


def access():
    return {'schema':'WORLD_ENGINE_READ_ONLY_PACKAGE_ACCESS_SNAPSHOT_V1',
        'packageRepository':SUCCESS_PACKAGE,'subjectRepository':BOOTSTRAP_REPOSITORY,
        'source':'PACKAGE_SETTINGS_READ_ONLY','proofSHA256':'1'*64,
        'observedAtUnixMs':1800000000000,'linked':False,'permissionInheritance':False,
        'actionsRole':'NONE','canWrite':False,'canDelete':False,'mutationProbePerformed':False}


def plan():
    return {'schema':'WORLD_ENGINE_GHCR_FIRST_REGISTRATION_PLAN_V1',
        'status':'APPROVED_FOR_SEPARATE_REGISTRATION','separateRegistrationApprovalRecorded':True,
        'approval':'FIRST_REGISTER_CANDIDATE_PARENT_COPY_ONCE','namespaceOwner':OWNER,
        'namespaceType':'USER','bootstrapRepository':BOOTSTRAP_REPOSITORY,
        'workflowRepository':BOOTSTRAP_REPOSITORY,'githubContextRepository':BOOTSTRAP_REPOSITORY,
        'reusableWorkflowUsed':False,'credentialKind':'GITHUB_TOKEN',
        'credentialRepository':BOOTSTRAP_REPOSITORY,'packagesPermission':'write',
        'contentsPermission':'read','runId':'123','runAttempt':1,'reviewedHeadSHA':'a'*40,
        'trigger':'workflow_dispatch','runner':'github-hosted-standard-ubuntu-24.04',
        'repositoryPublic':True,'zeroCostConfirmed':True,'budgetStopConfirmed':True,
        'sourceImage':SOURCE_IMAGE,'candidateRepository':CANDIDATE_PACKAGE,
        'destination':CANDIDATE_PACKAGE+':'+bootstrap_tag('123'),
        'candidateAbsence':{'schema':'WORLD_ENGINE_PACKAGE_ABSENCE_PROOF_V1',
            'repository':CANDIDATE_PACKAGE,'status':'CONFIRMED_ABSENT','httpStatus':404,
            'authorizedMetadataRead':True,'readPrincipalRole':'NAMESPACE_OWNER',
            'source':'NAMESPACE_OWNER_API_READ_ONLY',
            'proofSHA256':'2'*64,'observedAtUnixMs':1800000000000},
        'successfulPackageAccessBefore':access(),'firstCreationAdminAcknowledged':True,
        'candidateDeleteCapabilityDeniedClaimed':False,'requestedVisibility':'private',
        'imageBuildAllowed':False,'sourceMutationAllowed':False,
        'destructiveOperationsAllowed':False,'gpuAllowed':False,
        'normalPublisherEnabled':False,'existingPassTestsRerun':False}


def seed(p):
    return {'schema':'WORLD_ENGINE_GHCR_CREATED_SEED_RECEIPT_V1',
        'status':'FIRST_REGISTRATION_COMPLETE_QUARANTINED','planBindingSHA256':binding(p),
        'packageId':42,'destination':p['destination'],'sourceRegistryDigest':SUCCESS_DIGEST,
        'destinationTagDigest':SUCCESS_DIGEST,'destinationAddressedDigest':SUCCESS_DIGEST,
        'successfulTagBeforeDigest':SUCCESS_DIGEST,'successfulTagAfterDigest':SUCCESS_DIGEST,
        'manifestBytesEqual':True,'configDigestPreserved':True,'imageBytesUnmodified':True,
        'configuredLabelsChanged':False,'packageAssociationRepository':BOOTSTRAP_REPOSITORY,
        'packageAssociationVerifiedReadOnly':True,'autoAssociationAssumed':False,
        'visibility':'private','visibilityObservedReadOnly':True,
        'bootstrapTokenNewPackageRole':'ADMIN','creatorAdminCapabilityAcknowledged':True,
        'bootstrapJobStatus':'COMPLETED','bootstrapTokenStatus':'EXPIRED_JOB_TOKEN',
        'bootstrapTokenExpiryEvidenceSHA256':'3'*64,'successfulPackageAccessAfter':access(),
        'logicalCopyAttempts':1,'retryCount':0,'deleteRequests':0,'gpuExecuted':False,
        'imageBuilt':False,'normalPublicationPerformed':False,'registrationEvidenceSHA256':'4'*64}


def handoff(s):
    return {'schema':'WORLD_ENGINE_GHCR_POST_REGISTRATION_ACL_V1','status':'VERIFIED_READ_ONLY',
        'candidateRepository':CANDIDATE_PACKAGE,'packageId':42,'seedBindingSHA256':binding(s),
        'inheritanceEnabled':False,'bootstrapActionsRole':'NONE',
        'bootstrapActionsAccessRemoved':True,'bootstrapWorkflowDisabled':True,
        'normalPublisherIdentity':'candidate-only-publisher','normalPublisherIsNamespaceOwner':False,
        'normalPublisherCandidateRole':'WRITE','normalPublisherHasDeleteScope':False,
        'normalPublisherCanAdminCandidate':False,'normalPublisherCanWriteSuccessful':False,
        'normalPublisherCanDeleteSuccessful':False,
        'normalPublisherSuccessfulAccessEvidenceSHA256':'5'*64,
        'automatedWriterIdentities':['candidate-only-publisher'],'onlyAutomatedWriterVerified':True,
        'ownerAdminsAcknowledged':True,'ownerAdminExceptionApproved':True,'aclEvidenceSHA256':'6'*64,
        'separateNormalPublicationApprovalRequired':True,'normalPolicyAutomaticallyActivated':False,
        'newSecretCreatedByContract':False,'packageSettingsChangedByContract':False}


class FirstRegistrationTests(unittest.TestCase):
    def test_01_valid_plan_is_copy_seed_not_vulkan_candidate(self):
        result=validate_first_registration_plan(plan())
        self.assertEqual(result['status'],'FIRST_REGISTRATION_PLAN_VALID_NOT_EXECUTED')
        self.assertFalse(result['seedIsVulkanCandidate']);self.assertFalse(result['normalPublicationReady'])
        self.assertIn('bootstrap-parent-',result['destination'])
    def test_02_owner_pat_original_repo_and_reusable_caller_rejected(self):
        for key,value in [('credentialKind','OWNER_PAT'),('credentialRepository',ORIGINAL_REPOSITORY),
            ('githubContextRepository',ORIGINAL_REPOSITORY),('workflowRepository',ORIGINAL_REPOSITORY),
            ('reusableWorkflowUsed',True)]:
            p=plan();p[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_first_registration_plan(p)
    def test_03_unauthorized_or_ambiguous_404_is_not_absence(self):
        for key,value in [('httpStatus',403),('authorizedMetadataRead',False),('readPrincipalRole','COLLABORATOR'),
            ('source','ANONYMOUS_404'),('proofSHA256',None)]:
            p=plan();p['candidateAbsence'][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_first_registration_plan(p)
    def test_04_any_old_success_write_admin_or_mutation_probe_blocks(self):
        for key,value in [('linked',True),('permissionInheritance',True),('actionsRole','ADMIN'),
            ('canWrite',True),('canDelete',True),('mutationProbePerformed',True)]:
            p=plan();p['successfulPackageAccessBefore'][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_first_registration_plan(p)
    def test_05_manual_free_single_attempt_and_explicit_approval_required(self):
        for key,value in [('status','DRAFT_NOT_AUTHORIZED'),('separateRegistrationApprovalRecorded',False),
            ('runAttempt',2),('runAttempt',True),('reviewedHeadSHA','invalid'),('trigger','push'),
            ('zeroCostConfirmed',False),('repositoryPublic',False),('budgetStopConfirmed',False)]:
            p=plan();p[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_first_registration_plan(p)
    def test_06_first_creator_admin_private_and_no_build_must_be_explicit(self):
        for key,value in [('firstCreationAdminAcknowledged',False),
            ('candidateDeleteCapabilityDeniedClaimed',True),('requestedVisibility','public'),
            ('imageBuildAllowed',True),('normalPublisherEnabled',True),('gpuAllowed',True)]:
            p=plan();p[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_first_registration_plan(p)
    def test_07_no_relabel_rebuild_or_digest_substitution(self):
        p=plan()
        for key,value in [('destinationTagDigest','sha256:'+'0'*64),('manifestBytesEqual',False),
            ('configDigestPreserved',False),('configuredLabelsChanged',True),('imageBuilt',True),
            ('successfulTagAfterDigest','sha256:'+'1'*64)]:
            s=seed(p);s[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_created_seed(p,s)
    def test_08_created_package_association_visibility_expiry_not_assumed(self):
        p=plan()
        for key,value in [('packageAssociationRepository',ORIGINAL_REPOSITORY),
            ('packageAssociationVerifiedReadOnly',False),('autoAssociationAssumed',True),
            ('visibility','public'),('bootstrapTokenStatus','STILL_ACTIVE'),
            ('bootstrapJobStatus','RUNNING'),('bootstrapTokenNewPackageRole','WRITE')]:
            s=seed(p);s[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_created_seed(p,s)
    def test_09_valid_seed_is_quarantined_and_never_normal_publish_ready(self):
        p=plan();s=seed(p);result=validate_created_seed(p,s)
        self.assertEqual(result['status'],'SEED_QUARANTINED_NOT_NORMAL_PUBLISH_READY')
        self.assertFalse(result['normalPublicationReady'])
        self.assertFalse(result['actualPackageCreationPerformedByModule'])
    def test_10_copy_retry_delete_and_old_permission_gain_rejected(self):
        p=plan()
        for key,value in [('logicalCopyAttempts',2),('retryCount',1),('deleteRequests',1),
            ('normalPublicationPerformed',True),('gpuExecuted',True)]:
            s=seed(p);s[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_created_seed(p,s)
        s=seed(p);s['successfulPackageAccessAfter']['canWrite']=True
        with self.assertRaises(RuntimeError):validate_created_seed(p,s)
    def test_11_normal_handoff_needs_removed_bootstrap_and_granular_acl(self):
        p=plan();s=seed(p)
        for key,value in [('inheritanceEnabled',True),('bootstrapActionsRole','ADMIN'),
            ('bootstrapActionsAccessRemoved',False),('bootstrapWorkflowDisabled',False)]:
            a=handoff(s);a[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_normal_handoff(p,s,a)
    def test_12_normal_writer_cannot_be_owner_admin_or_success_package_writer(self):
        p=plan();s=seed(p)
        for key,value in [('normalPublisherIdentity',OWNER),('normalPublisherCandidateRole','ADMIN'),
            ('normalPublisherIsNamespaceOwner',True),
            ('normalPublisherHasDeleteScope',True),('normalPublisherCanAdminCandidate',True),
            ('normalPublisherCanWriteSuccessful',True),('normalPublisherCanDeleteSuccessful',True),
            ('ownerAdminsAcknowledged',False),('ownerAdminExceptionApproved',False),
            ('automatedWriterIdentities',['candidate-only-publisher','other-writer'])]:
            a=handoff(s);a[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_normal_handoff(p,s,a)
    def test_13_valid_handoff_only_eligible_for_separate_normal_approval(self):
        p=plan();s=seed(p);a=handoff(s);result=validate_normal_handoff(p,s,a)
        self.assertEqual(result['status'],'NORMAL_POLICY_ELIGIBLE_FOR_SEPARATE_APPROVAL_NOT_ACTIVATED')
        self.assertFalse(result['normalPolicyActivated']);self.assertFalse(result['existingPublisherCodeModified'])
    def test_14_receipt_binding_extra_fields_and_automatic_activation_rejected(self):
        p=plan();p['token']='NON_SECRET_TEST_SENTINEL'
        with self.assertRaises(RuntimeError):validate_first_registration_plan(p)
        p=plan();s=seed(p);s['planBindingSHA256']='0'*64
        with self.assertRaises(RuntimeError):validate_created_seed(p,s)
        s=seed(p);a=handoff(s);a['normalPolicyAutomaticallyActivated']=True
        with self.assertRaises(RuntimeError):validate_normal_handoff(p,s,a)
        s=seed(p);s['successfulPackageAccessAfter']['observedAtUnixMs']=1
        with self.assertRaises(RuntimeError):validate_created_seed(p,s)
        s=seed(p);s['packageId']=1;a=handoff(s);a['packageId']=True
        with self.assertRaises(RuntimeError):validate_normal_handoff(p,s,a)


if __name__=='__main__':unittest.main(verbosity=2)
