# Original reference access

The target is the complete approximately 31.8-second 65379.mp4. The 14-second Korean
War Candidate is a comparison input only and must never replace that target.
No video implementation, reference segment selection or rendering may proceed
without access to the actual complete target.

The current Sediment download tool accepts files of at most 32MiB. Repeating the
same oversized upload cannot remove that deterministic limit. No supported
alternate attachment endpoint or byte-range tool is available in this session.

Preferred recovery: supply a directly downloadable HTTPS URL for the original
reference MP4. Keep original bytes; do not reencode or crop it to 5 seconds. The
source must permit downloading the complete body. Access and TLS verification
will be checked through the configured network path before analysis.

Alternative recovery: split the original file into raw 20MiB parts and upload all
parts together with PARTS_MANIFEST.json. This splits the original bytes without media
conversion. The included transfer_parts.py uses only the Python standard library
and works wherever Python 3 is installed:

```sh
python3 transfer_parts.py split "Screen_Recording_20261013_223349_YouTube.mp4" reference_parts
```

On Windows with the Python launcher, replace python3 with py -3. The destination
folder must not already exist. Retain the original and upload every
reference.part.0000, reference.part.0001, etc. plus PARTS_MANIFEST.json. Parts are
each no larger than 20MiB, below the tool's 32MiB limit. Preserve names and order.

After all parts have arrived and been copied into the same directory:

```sh
python3 transfer_parts.py join reference_parts/PARTS_MANIFEST.json RESTORED_REFERENCE.mp4
```

Reassembly verifies each part's size/SHA-256 and the complete original size/SHA-256.
Existing outputs and originals are never overwritten. Corrupt parts are rejected
before creating an output. The method was tested with 33MiB of synthetic bytes;
round-trip byte identity, overwrite rejection and corruption rejection passed.
This test is not access to or analysis of the actual reference.

After access succeeds: verify the target's identity and actual duration, audit
the complete video in chronological order, then select a contiguous 5-second
segment exhibiting territory-color expansion and camera tracking. Resume the
MASTER at PHASE 1 while retaining all previous completed work and FINAL baselines.
