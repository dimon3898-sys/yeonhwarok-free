"""Measured-pixel QC regressions; synthetic rasters only test detector semantics."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BoldPixelMetricsV023(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = r"""
import {imageDifference,regionPixelMetrics,boundaryPixelMetrics,containmentPixelMetrics,evaluateBoldPixels} from './tools/bold_pixel_metrics_v023.mjs';
const w=120,h=120,base=new Uint8ClampedArray(w*h*4),primaryMask=new Uint8ClampedArray(base.length),secondaryMask=new Uint8ClampedArray(base.length);
for(let y=0;y<h;y++)for(let x=0;x<w;x++){const i=(y*w+x)*4,v=70+(x*7+y*3)%80;base.set([v,v+10,v+20,255],i);if(x>=8&&x<53&&y>=8&&y<112)primaryMask[i+3]=255;if(x>=67&&x<112&&y>=8&&y<112)secondaryMask[i+3]=255;}
const paint=(opacity)=>{const out=base.slice();for(let i=0;i<out.length;i+=4)if(primaryMask[i+3]||secondaryMask[i+3]){const a=primaryMask[i+3]?opacity:.18,color=primaryMask[i+3]?[210,40,180]:[160,110,40];for(let c=0;c<3;c++)out[i+c]=base[i+c]*(1-a)+color[c]*a;}return out;};
const painted=paint(.55),primary=regionPixelMetrics(base,painted,primaryMask,w,h),secondary=regionPixelMetrics(base,painted,secondaryMask,w,h);
const raster=(width)=>{const out=new Uint8ClampedArray(base.length);for(let y=60-width/2;y<60+width/2;y++)for(let x=5;x<115;x++)out[(y*w+x)*4+3]=255;return out;};
const segments=[[{x:5,y:60},{x:115,y:60}]],primaryBoundary=boundaryPixelMetrics(raster(8),w,h,segments),secondaryBoundary=boundaryPixelMetrics(raster(4),w,h,segments);
const containment=containmentPixelMetrics(primaryMask,primaryMask,w,h),off=imageDifference(base,base.slice(),w,h);
const healthy={primary,secondary,primaryBoundary,secondaryBoundary,containment,off},result={healthy:evaluateBoldPixels(healthy),primary,secondary,primaryBoundary,secondaryBoundary};
result.missing=evaluateBoldPixels({...healthy,primary:regionPixelMetrics(base,base,primaryMask,w,h)});
result.opaque=evaluateBoldPixels({...healthy,primary:regionPixelMetrics(base,paint(1),primaryMask,w,h)});
result.hierarchy=evaluateBoldPixels({...healthy,secondary:{...secondary,median_rgb_contrast:primary.median_rgb_contrast*2}});
result.lineMissing=evaluateBoldPixels({...healthy,primaryBoundary:boundaryPixelMetrics(new Uint8ClampedArray(base.length),w,h,segments)});
const contaminated=primaryMask.slice();contaminated[(2*w+2)*4+3]=255;
result.coastLeak=evaluateBoldPixels({...healthy,containment:containmentPixelMetrics(contaminated,primaryMask,w,h)});
const changed=base.slice();changed[17]++;
result.changedOff=evaluateBoldPixels({...healthy,off:imageDifference(base,changed,w,h)});
result.thin=evaluateBoldPixels({...healthy,primaryBoundary:boundaryPixelMetrics(raster(2),w,h,segments)});
const hiddenPrimary=new Uint8ClampedArray(base.length);
result.hidden=evaluateBoldPixels({...healthy,primary:regionPixelMetrics(base,painted,hiddenPrimary,w,h)});
console.log(JSON.stringify(result));
"""
        run = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                             check=True, text=True, capture_output=True, timeout=60)
        cls.receipt = json.loads(run.stdout)

    def test_actual_raster_width_is_measured_from_pixels(self):
        self.assertEqual(self.receipt['primaryBoundary']['width_px_median'], 8)
        self.assertEqual(self.receipt['secondaryBoundary']['width_px_median'], 4)

    def test_valid_terrain_preserving_hierarchy_is_admitted(self):
        self.assertTrue(self.receipt['healthy']['passed'], self.receipt['healthy'])
        self.assertGreater(self.receipt['primary']['median_rgb_contrast'],
                           self.receipt['secondary']['median_rgb_contrast'])
        self.assertGreater(self.receipt['primary']['terrain_edge_correlation'], .99)
        self.assertGreater(self.receipt['primary']['terrain_edge_retention'], .4)

    def test_missing_fill_is_not_accepted_as_a_present_flag(self):
        self.assertIn('PRIMARY_FILL_LOW_CONTRAST', self.receipt['missing']['failures'])

    def test_opaque_fill_that_erases_texture_is_rejected(self):
        self.assertIn('PRIMARY_TERRAIN_LOST', self.receipt['opaque']['failures'])

    def test_secondary_stronger_than_primary_is_rejected(self):
        self.assertIn('FILL_HIERARCHY_REVERSED', self.receipt['hierarchy']['failures'])

    def test_absent_boundary_is_rejected(self):
        self.assertIn('PRIMARY_BOUNDARY_NOT_BOLD', self.receipt['lineMissing']['failures'])

    def test_ocean_or_hole_fill_leak_is_rejected(self):
        self.assertIn('COASTLINE_OR_HOLE_LEAK', self.receipt['coastLeak']['failures'])

    def test_off_checks_exact_raster_channels(self):
        self.assertIn('OFF_BASELINE_CHANGED', self.receipt['changedOff']['failures'])

    def test_thin_line_fails_even_if_requested_style_says_bold(self):
        self.assertIn('PRIMARY_BOUNDARY_NOT_BOLD', self.receipt['thin']['failures'])

    def test_invisible_projected_primary_is_not_false_pass(self):
        self.assertIn('PRIMARY_FILL_NOT_MEASURABLE', self.receipt['hidden']['failures'])

    def test_cpu_detector_never_claims_gpu_quality_acceptance(self):
        self.assertEqual(self.receipt['healthy']['GPU'], 'NOT_RUN')
        self.assertEqual(self.receipt['healthy']['visual_quality_acceptance'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
