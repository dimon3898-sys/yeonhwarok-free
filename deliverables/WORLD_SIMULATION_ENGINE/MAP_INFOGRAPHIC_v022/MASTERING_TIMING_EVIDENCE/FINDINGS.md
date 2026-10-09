# Independent v022 measured audio duration diagnosis

Protected engine/audio.py remains unchanged. All experiments use temporary files only. The truncation experiments below used development-host FFmpeg 7.1.5. Repeating the measured fixture with the exact pinned-base FFmpeg 5.1.9 shows that its legacy output already retains the full sample count. This is not evidence of an audio failure in a published image.

The cross-version proof is [FFMPEG_VERSION_COMPARISON.json](FFMPEG_VERSION_COMPARISON.json). All counts are decoded PCM samples at 48,000 Hz.

| Environment | FFmpeg | Legacy output `-t` | Natural EOF | Scoped v022 wrapper |
| --- | --- | ---: | ---: | ---: |
| Development host | 7.1.5 | 401,600 | 404,800 | 404,800 |
| Pinned v021 base | 5.1.9 | 404,800 | 404,800 | 404,800 |

On both versions, the scoped wrapper is bit-identical to natural EOF, and the legacy output's overlapping samples remain bit-identical. The portable regression classifies the measured BEFORE result while requiring the exact full sample count, natural-EOF equality, retained speech tail, checkpoint reuse and tamper rejection after the fix.

Development-host raw/voice fixture: 404800 decoded PCM samples at 48000 Hz, 8.433333333333334 s. On FFmpeg 7.1.5, the existing normalization second pass with output -t emits only 401600 samples, 8.366666666666667 s. Its report describes raw mix length as final WAV duration rather than measuring the physical output.

Exact same measured loudnorm filter without output -t emits 404800 samples. The first 401600 samples are bit-identical to the existing output. Appending aresample=48000,atrim=end_sample=404800 also preserves all samples and is bit-identical. Output -t ends transcode before the filter tail is fully drained at EOF. A separate nonzero terminal-tone fixture reproduces the same 3200-sample loss, proving that post-padding a truncated output could hide real content loss.

Prepending silence before loudnorm preserves duration but changes normalization of the overlap; it is not the minimal behavior-preserving correction. Scoped new v022 FunctionType _run interception can remove output -t and append sample-domain resample/trim only for the measured mastering pass, then read and record actual output PCM length/hash.

AAC evidence: exact 404800-sample WAV encoded with unchanged AAC pipeline has stream duration_ts=404784 / 48000 (8.433000 s) due default MP4 movie timescale 1000; decoding emits 405504 samples (8.448 s), including codec frame padding. These are separate measured presentation and decoded clocks. Specifying movie_timescale 48000 or 90000 gives exact presentation duration_ts=404800 / 48000 (8.433333 s), without changing AAC decoded frame padding. No global/protected audio changes recommended.

Artifacts: counts.json, pcm_comparison.json, nonzero-tail.json, tail_preservation.json, AAC probe JSON, independent WAV outputs/logs. No GPU executed.
