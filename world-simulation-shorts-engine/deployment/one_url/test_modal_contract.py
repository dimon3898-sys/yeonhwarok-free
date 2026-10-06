"""Offline SDK construction only; not a Modal build or provider acceptance."""
import importlib.util
import unittest
from unittest.mock import patch
import warnings

from deployment.one_url.budget import validate_budget_config
from deployment.one_url.test_budget import NOW, fixture
from deployment.one_url.modal_candidate import build_app


class ModalContractTests(unittest.TestCase):
    def test_missing_budget_blocks_before_sdk_is_loaded(self):
        with self.assertRaisesRegex(ValueError, 'BUDGET_UNVERIFIED'):
            build_app('/tmp/nonexistent-world-budget-fixture-20261006.json')

    @unittest.skipUnless(importlib.util.find_spec('modal'), 'Optional isolated provider SDK not installed')
    def test_real_sdk_can_construct_lazy_app_without_network(self):
        import modal
        budget = validate_budget_config(fixture(), now=NOW)
        with patch('deployment.one_url.modal_candidate.load_verified_budget', return_value=budget):
            # Any accidental lookup/deploy in the constructor fails this test.
            with patch.object(modal.Sandbox, 'create', side_effect=AssertionError('Remote call forbidden')):
                app = build_app('synthetic-config-path')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.assertIn('portal', app.registered_functions)
            function = app.registered_functions['portal']
        self.assertFalse(function._is_hydrated)
        self.assertEqual(app.name, 'world-engine-mobile')

    @unittest.skipUnless(importlib.util.find_spec('modal'), 'Optional isolated provider SDK not installed')
    def test_serialized_broker_captures_only_explicitly_resolved_sdk_handles(self):
        import modal
        from modal._utils.async_utils import synchronizer
        from modal_proto import api_pb2
        budget = validate_budget_config(fixture(), now=NOW)
        with patch('deployment.one_url.modal_candidate.load_verified_budget', return_value=budget):
            app = build_app('synthetic-config-path')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            function = app.registered_functions['portal']
        # Model the SDK's deployment dependency traversal without a build, RPC
        # or credentials. Only declared dependencies and the precreated function
        # receive synthetic IDs. Its real serializer must reject any additional
        # lazy handle captured solely through the broker's closure.
        resolved = set()
        metadata_types = {
            'fu': api_pb2.FunctionHandleMetadata, 'mo': api_pb2.MountHandleMetadata,
            'im': api_pb2.ImageMetadata, 'st': api_pb2.SecretMetadata,
            'vo': api_pb2.VolumeMetadata,
        }
        def hydrate_declared(obj):
            if id(obj) in resolved:
                return
            resolved.add(id(obj))
            for dependency in obj._deps_():
                hydrate_declared(dependency)
            metadata = metadata_types[obj._type_prefix]()
            if obj._type_prefix == 'fu':
                metadata.function_name = 'portal'
            obj._hydrate(obj._type_prefix + '-synthetic' + str(len(resolved)), None, metadata)
        internal_function = synchronizer._translate_in(function)
        hydrate_declared(internal_function)
        data = internal_function._source_info_.serialized_function()
        self.assertGreater(len(data), 0)


if __name__ == '__main__':
    unittest.main()
