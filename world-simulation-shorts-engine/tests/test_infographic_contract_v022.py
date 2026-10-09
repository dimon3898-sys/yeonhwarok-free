"""Actual GIS provenance risks at the new version boundary, without GPU claims."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from engine.infographic_contract import (canonical_sha, load_registry,
    validate_geometry, validate_registry, profile)


class NativeGISContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=load_registry()
        cls.records={record['id']:record for record in cls.registry['geometries']}

    def test_native_registry_and_original_country_holes_are_preserved(self):
        checked=validate_registry(self.registry)
        self.assertTrue(checked['passed'],checked)
        countries=[r for r in self.records.values()if r['geometry_role']=='country'and r['geometry_type']in {'Polygon','MultiPolygon'}]
        self.assertEqual(len(countries),242)
        holes=[r for r in countries if r['geometry_qa']['hole_count']]
        self.assertTrue(holes)
        self.assertTrue(all(r['geometry_qa']['coordinates_changed']is False for r in countries))
        self.assertEqual(checked['physical_gpu'],'NOT_RUN')

    def test_canal_native_gaps_remain_disconnected(self):
        north=self.records['CANAL_SUEZ_RIVER_NE10M']
        lake=self.records['CANAL_SUEZ_LAKE_NE10M']
        self.assertEqual(north['geometry_type'],'MultiLineString')
        self.assertEqual([len(part)for part in north['coordinates']],[13,2])
        self.assertEqual([len(part)for part in lake['coordinates']],[11])
        self.assertNotEqual(north['coordinates'][0][-1],lake['coordinates'][0][0])
        self.assertEqual(north['scale']['denominator'],10000000)

    def test_representative_point_never_becomes_canal_line(self):
        point=self.records['LOCATION_SUEZ_CANAL']
        self.assertEqual(point['geometry_type'],'Point')
        self.assertNotEqual(point['geometry_role'],'canal_centerline')
        changed=deepcopy(point);changed['geometry_type']='LineString'
        changed['sha256']=canonical_sha(dict(type='LineString',coordinates=changed['coordinates']))
        with self.assertRaises(ValueError):validate_geometry(changed)

    def test_native_geometry_mutation_even_with_recomputed_hash_is_rejected(self):
        changed=deepcopy(self.registry)
        record=next(r for r in changed['geometries']if r['id']=='CANAL_SUEZ_RIVER_NE10M')
        record['coordinates'][0][0][0]+=.01
        record['sha256']=canonical_sha(dict(type=record['geometry_type'],coordinates=record['coordinates']))
        self.assertFalse(validate_registry(changed)['passed'])

    def test_feature_or_license_forgery_is_rejected(self):
        for key,value in [('source_feature_id','fictional-canal'),('source_id','UNKNOWN_SOURCE'),('source_version','fictional'),('license',{'spdx':'CC0'})]:
            changed=deepcopy(self.registry)
            record=next(r for r in changed['geometries']if r['id']=='CANAL_SUEZ_RIVER_NE10M')
            record[key]=value
            with self.subTest(key=key):self.assertFalse(validate_registry(changed)['passed'])

    def test_bool_nonfinite_and_range_invalid_coordinates_fail(self):
        for coordinate in ([True,30.318359],[float('nan'),30.318359],[32.38,float('inf')],[181,0],[0,-91]):
            record=deepcopy(self.records['LOCATION_SUEZ_CANAL']);record['coordinates']=coordinate
            with self.subTest(coordinate=coordinate):
                with self.assertRaises(ValueError):validate_geometry(record)

    def test_unclosed_source_polygon_ring_fails(self):
        record=deepcopy(self.records['COUNTRY_EGY'])
        rings=record['coordinates'][0]if record['geometry_type']=='MultiPolygon'else record['coordinates']
        rings[0][-1]=[rings[0][-1][0]+.001,rings[0][-1][1]]
        with self.assertRaises(ValueError):validate_geometry(record)

    def test_wrong_bbox_or_crs_is_rejected(self):
        for key,value in [('bbox',[0,0,0,0]),('crs','EPSG:3857')]:
            record=deepcopy(self.records['LOCATION_SINGAPORE']);record[key]=value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):validate_geometry(record)

    def test_profile_rejects_noninteger_frame_policy_and_unknown_effect(self):
        original=profile()
        for mutate in (lambda p:p['marker'].__setitem__('pop_frames',9.0),
                       lambda p:p['marker'].__setitem__('pop_frames',True),
                       lambda p:p.__setitem__('arbitrary_flash',True)):
            changed=deepcopy(original);mutate(changed)
            with patch('engine.infographic_contract._read_pair',return_value=changed):
                with self.assertRaises(ValueError):profile()


if __name__=='__main__':unittest.main()
