"""Detector regressions use explicit synthetic rasters, never authored map geometry."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TerrainPixelMetricsV024(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = r"""
import {terrainRegionPixels,boundaryPixelMetrics,haloPixelMetrics,outlineContrastPixels,
containmentPixelMetrics,imageDifference,evaluateTerrainPixels,existingLandMaskPixels,interiorCoveragePixels,nativeGeometryContains,sourceGeometryMask,sourceGeometryCoveragePixels,annotationContrastPixels} from './tools/terrain_pixel_metrics_v024.mjs';
import fs from 'node:fs';
const w=120,h=120,base=new Uint8ClampedArray(w*h*4),pm=new Uint8ClampedArray(base.length),sm=pm.slice();
for(let y=0;y<h;y++)for(let x=0;x<w;x++){const i=(y*w+x)*4,v=70+(x*7+y*3)%60;
base.set([v,v+10,v+20,255],i);if(x>=8&&x<53&&y>=8&&y<112)pm[i+3]=255;if(x>=67&&x<112&&y>=8&&y<112)sm[i+3]=255;}
const colorize=()=>{const out=base.slice();for(let i=0;i<out.length;i+=4){const r=pm[i+3]?40:sm[i+3]?14:0;out[i]+=r;out[i+1]-=r*30/59;}return out;};
const painted=colorize(),primary=terrainRegionPixels(base,painted,pm,w,h),secondary=terrainRegionPixels(base,painted,sm,w,h);
const raster=(lineWidth,alpha=255)=>{const out=new Uint8ClampedArray(base.length),top=Math.floor(60-lineWidth/2);for(let y=top;y<top+lineWidth;y++)for(let x=5;x<115;x++)out.set([255,255,255,alpha],(y*w+x)*4);return out;};
const segments=[[{x:5,y:60},{x:115,y:60}]],core=boundaryPixelMetrics(raster(8),w,h,segments,{brightCore:true}),secondaryCore=boundaryPixelMetrics(raster(3),w,h,segments,{brightCore:true}),halo=haloPixelMetrics(raster(12,30),w,h,segments);
const boundary=base.slice(),coreRaster=raster(8);for(let i=0;i<boundary.length;i+=4)if(coreRaster[i+3])boundary.set([255,255,255,255],i);
const edgeContrast=outlineContrastPixels(base,boundary,w,h,segments),containment=containmentPixelMetrics(pm,pm,w,h),off=imageDifference(base,base.slice(),w,h);
const healthy={primary,secondary,core,secondaryCore,halo,edgeContrast,containment,off};
const missing=terrainRegionPixels(base,base,pm,w,h),opaque=base.slice(),dim=painted.slice();
for(let i=0;i<opaque.length;i+=4)if(pm[i+3]){opaque.set([120,130,140,255],i);for(let c=0;c<3;c++)dim[i+c]*=.5;}
const fullGlow=new Uint8ClampedArray(base.length);for(let i=0;i<fullGlow.length;i+=4)fullGlow.set([255,190,40,70],i);
const leaked=pm.slice();leaked[(2*w+2)*4+3]=255;const changed=base.slice();changed[17]++;
const localTone=base.slice();for(let i=0;i<localTone.length;i+=4)if(pm[i+3]){
for(let c=0;c<3;c++)localTone[i+c]=base[i+c]*.86;localTone[i]+=40;localTone[i+1]-=40*30/59;}
const toneMetrics=terrainRegionPixels(base,localTone,pm,w,h,{expectedLuminanceScale:.86});
const toneBad=terrainRegionPixels(base,dim,pm,w,h,{expectedLuminanceScale:.86});
const secondaryOpaque=painted.slice();for(let i=0;i<secondaryOpaque.length;i+=4)if(sm[i+3])secondaryOpaque.set([130,100,90,255],i);
const adjacent=raster(12,30),edgeMask=raster(1);for(let x=5;x<115;x++){
edgeMask[(80*w+x)*4+3]=255;for(let y=74;y<86;y++)adjacent.set([255,255,255,30],(y*w+x)*4);}
const receipt={healthy:evaluateTerrainPixels(healthy),primary,secondary,core,secondaryCore,halo,
 localTone:toneMetrics,localToneQC:evaluateTerrainPixels({...healthy,primary:toneMetrics}),
 excessiveToneQC:evaluateTerrainPixels({...healthy,primary:toneBad}),
 secondaryErased:evaluateTerrainPixels({...healthy,secondary:terrainRegionPixels(base,secondaryOpaque,sm,w,h,{expectedLuminanceScale:.88})}),
 adjacentHalo:haloPixelMetrics(adjacent,w,h,segments,{nativeEdgeMask:edgeMask}),
 fullGlowNearest:evaluateTerrainPixels({...healthy,halo:haloPixelMetrics(fullGlow,w,h,segments,{nativeEdgeMask:edgeMask})}),
 missing:evaluateTerrainPixels({...healthy,primary:missing}),
 opaque:evaluateTerrainPixels({...healthy,primary:terrainRegionPixels(base,opaque,pm,w,h)}),
 dim:evaluateTerrainPixels({...healthy,primary:terrainRegionPixels(base,dim,pm,w,h)}),
 unbounded:evaluateTerrainPixels({...healthy,halo:haloPixelMetrics(fullGlow,w,h,segments)}),
 hierarchy:evaluateTerrainPixels({...healthy,secondary:{...secondary,median_rgb_contrast:primary.median_rgb_contrast*2}}),
 coast:evaluateTerrainPixels({...healthy,containment:containmentPixelMetrics(leaked,pm,w,h)}),
 off:evaluateTerrainPixels({...healthy,off:imageDifference(base,changed,w,h)})};
let invalid=false;try{terrainRegionPixels(new Uint8Array(3),painted,pm,w,h);}catch{invalid=true;}receipt.invalid=invalid;
receipt.invalidScale=false;try{terrainRegionPixels(base,painted,pm,w,h,{expectedLuminanceScale:.79});}catch{receipt.invalidScale=true;}
const coverage=new Uint8Array(w*h).fill(1),rasterWaterLeak=base.slice();
for(let y=2;y<6;y++)for(let x=2;x<6;x++)rasterWaterLeak[(y*w+x)*4]+=20;
receipt.rasterWater=existingLandMaskPixels(base,rasterWaterLeak,pm,coverage,w,h);
receipt.cleanRasterWater=existingLandMaskPixels(base,base.slice(),pm,coverage,w,h);
const trueEdges=new Uint8ClampedArray(base.length);for(let x=8;x<53;x++){trueEdges[(8*w+x)*4+3]=255;trueEdges[(111*w+x)*4+3]=255;}
for(let y=8;y<112;y++){trueEdges[(y*w+8)*4+3]=255;trueEdges[(y*w+52)*4+3]=255;}
const internalSeam=pm.slice();for(let y=30;y<80;y++)internalSeam[(y*w+30)*4+3]=128;
receipt.cleanCoverage=interiorCoveragePixels(pm,trueEdges,w,h);receipt.seamCoverage=interiorCoveragePixels(internalSeam,trueEdges,w,h);
const registry=JSON.parse(fs.readFileSync('web/infographic/v022/registry.json','utf8'));const zaf=registry.geometries.find(r=>r.id==='COUNTRY_ZAF'),idn=registry.geometries.find(r=>r.id==='COUNTRY_IDN');
receipt.nativePIP={southAfrica:nativeGeometryContains(zaf,24,-30),lesothoHole:nativeGeometryContains(zaf,28.25,-29.5),java:nativeGeometryContains(idn,110,-7),oceanGap:nativeGeometryContains(idn,118.5,-6)};
const healedMask=pm.slice();receipt.healedSource=sourceGeometryCoveragePixels(internalSeam,healedMask,pm,trueEdges,w,h);
const falseSource=pm.slice();falseSource[(50*w+30)*4+3]=0;receipt.fakeHeal=sourceGeometryCoveragePixels(internalSeam,healedMask,falseSource,trueEdges,w,h);
const ink=base.slice();for(let y=30;y<42;y++)for(let x=30;x<42;x++)ink.set([255,255,255,255],(y*w+x)*4);
const inkBox={x:28,y:28,width:16,height:16};receipt.ink=annotationContrastPixels(base,ink,inkBox,w,h);receipt.noInk=annotationContrastPixels(base,base.slice(),inkBox,w,h);
console.log(JSON.stringify(receipt));
"""
        result = subprocess.run(['node', '--input-type=module', '-e', source], cwd=ROOT,
                                check=True, capture_output=True, text=True, timeout=60)
        cls.receipt = json.loads(result.stdout)

    def test_source_luminance_and_three_detail_scales_are_measured(self):
        primary = self.receipt['primary']
        self.assertLess(primary['luminance']['W3C']['mean_absolute_error'], .002)
        self.assertGreater(primary['luminance']['REC709']['mean_absolute_error'], .01)
        self.assertEqual([row['scale_px'] for row in primary['detail']], [1, 3, 7])
        for row in primary['detail']:
            self.assertAlmostEqual(row['W3C']['retention'], 1, delta=.01)
            self.assertGreater(row['W3C']['correlation'], .999)

    def test_measured_healthy_terrain_hierarchy_is_admitted(self):
        self.assertTrue(self.receipt['healthy']['passed'], self.receipt['healthy'])

    def test_missing_color_layer_is_rejected(self):
        self.assertIn('PRIMARY_COLOR_NOT_VISIBLE', self.receipt['missing']['failures'])

    def test_flat_fill_erasing_terrain_is_rejected(self):
        self.assertIn('TERRAIN_DETAIL_ATTENUATED', self.receipt['opaque']['failures'])

    def test_dimmed_source_lighting_is_rejected(self):
        self.assertIn('SOURCE_LUMINANCE_CHANGED', self.receipt['dim']['failures'])

    def test_full_frame_glow_is_rejected_by_actual_threshold_reach(self):
        self.assertIn('HALO_UNBOUNDED_OR_DOMINANT', self.receipt['unbounded']['failures'])

    def test_secondary_stronger_than_primary_is_rejected(self):
        self.assertIn('COLOR_HIERARCHY_REVERSED', self.receipt['hierarchy']['failures'])

    def test_coastline_or_hole_ink_is_rejected(self):
        self.assertIn('COASTLINE_OR_HOLE_LEAK', self.receipt['coast']['failures'])

    def test_off_uses_exact_v023_pixel_channels(self):
        self.assertIn('OFF_V023_BASELINE_CHANGED', self.receipt['off']['failures'])

    def test_invalid_pixels_are_not_silently_admitted(self):
        self.assertTrue(self.receipt['invalid'])

    def test_cpu_metrics_cannot_claim_gpu_or_target_visual_acceptance(self):
        self.assertEqual(self.receipt['healthy']['GPU'], 'NOT_RUN')
        self.assertEqual(self.receipt['healthy']['visual_quality_acceptance'], 'NOT_RUN')

    def test_existing_land_mask_reports_actual_changed_water_pixels(self):
        self.assertEqual(self.receipt['rasterWater']['changed_ocean_or_hole_pixels'], 16)
        self.assertFalse(self.receipt['rasterWater']['ocean_or_hole_exact_unchanged'])

    def test_existing_land_mask_keeps_unchanged_ocean_distinct_from_geometry_flags(self):
        self.assertEqual(self.receipt['cleanRasterWater']['changed_ocean_or_hole_pixels'], 0)
        self.assertTrue(self.receipt['cleanRasterWater']['ocean_or_hole_exact_unchanged'])

    def test_local_tone_retains_raw_loss_and_independent_absolute_detail_gate(self):
        measured = self.receipt['localTone']
        self.assertGreater(measured['luminance']['W3C']['mean_absolute_error'], .03)
        self.assertLess(measured['luminance']['W3C']['mean_absolute_error_against_scaled_source'], .003)
        for row in measured['detail']:
            self.assertAlmostEqual(row['W3C']['retention'], .86, delta=.01)
            self.assertAlmostEqual(row['W3C']['normalized_retention_against_expected_local_scale'], 1, delta=.01)
            self.assertGreaterEqual(row['W3C']['retention'], .80)
        self.assertTrue(self.receipt['localToneQC']['passed'], self.receipt['localToneQC'])

    def test_scale_normalization_cannot_admit_excessive_detail_loss(self):
        failures = self.receipt['excessiveToneQC']['failures']
        self.assertIn('SOURCE_LUMINANCE_CHANGED', failures)
        self.assertIn('TERRAIN_DETAIL_ATTENUATED', failures)

    def test_out_of_bounds_local_tone_factor_is_rejected(self):
        self.assertTrue(self.receipt['invalidScale'])

    def test_nearby_native_edges_do_not_look_like_remote_halo_growth(self):
        halo = self.receipt['adjacentHalo']
        self.assertGreater(halo['reach_from_native_edge_px_max'], 16)
        self.assertLessEqual(halo['nearest_native_edge']['distance_px_max'], 6)

    def test_nearest_native_edge_distance_still_rejects_full_frame_glow(self):
        self.assertIn('HALO_UNBOUNDED_OR_DOMINANT', self.receipt['fullGlowNearest']['failures'])

    def test_secondary_flat_fill_and_local_luminance_loss_are_independently_rejected(self):
        failures = self.receipt['secondaryErased']['failures']
        self.assertIn('SECONDARY_SOURCE_LUMINANCE_CHANGED', failures)
        self.assertIn('SECONDARY_TERRAIN_DETAIL_ATTENUATED', failures)

    def test_internal_antialias_seam_is_not_hidden_by_terrain_mask_erosion(self):
        measured = self.receipt['seamCoverage']
        self.assertEqual(measured['partial_coverage_away_from_native_boundary_pixels'],50)
        self.assertGreater(measured['maximum_distance_from_native_edge_px'],16)

    def test_opaque_native_interior_has_no_false_internal_seam(self):
        self.assertEqual(self.receipt['cleanCoverage']['partial_coverage_away_from_native_boundary_pixels'],0)

    def test_source_gis_oracle_respects_real_native_holes_and_ocean_gaps(self):
        self.assertEqual(self.receipt['nativePIP'],{'southAfrica':True,'lesothoHole':False,'java':True,'oceanGap':False})

    def test_healed_mesh_gap_requires_independent_source_polygon_membership(self):
        self.assertEqual(self.receipt['healedSource']['healed_interior_pixels'],50)
        self.assertEqual(self.receipt['healedSource']['healed_interior_outside_source_geometry_pixels'],0)
        self.assertEqual(self.receipt['fakeHeal']['healed_interior_outside_source_geometry_pixels'],1)

    def test_annotation_pixel_control_detects_real_ink_and_missing_marker_or_text(self):
        self.assertEqual(self.receipt['ink']['measured_ink_pixels'],144)
        self.assertGreater(self.receipt['ink']['p90_rgb_contrast'],.3)
        self.assertEqual(self.receipt['noInk']['measured_ink_pixels'],0)


if __name__ == '__main__':
    unittest.main()
