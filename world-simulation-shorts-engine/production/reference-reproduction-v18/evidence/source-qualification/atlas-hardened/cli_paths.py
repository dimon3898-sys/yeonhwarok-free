"""Portable builder options; parsing does not create or modify any directory."""
import argparse,pathlib,os

def parse_paths(argv=None,code_root=None):
 code=pathlib.Path(code_root or __file__).resolve()
 if code_root is None:code=code.parent
 p=argparse.ArgumentParser(description='Build an isolated candidate atlas generation, never runtime admission.')
 p.add_argument('--source-root',type=pathlib.Path,default=pathlib.Path(os.environ.get('WORLD_ENGINE_SOURCE_ROOT',code.parent)))
 p.add_argument('--output-root',type=pathlib.Path,default=pathlib.Path(os.environ.get('WORLD_ENGINE_OUTPUT_ROOT',code/'generation1')))
 p.add_argument('--baseline-receipt',type=pathlib.Path,default=None)
 p.add_argument('--check-paths',action='store_true',help='Print resolved paths without reading sources or creating output.')
 a=p.parse_args(argv);a.source_root=a.source_root.resolve();a.output_root=a.output_root.resolve()
 a.baseline_receipt=(a.baseline_receipt or a.source_root/'BASELINE_MATERIALIZATION_RECEIPT.json').resolve()
 return a
