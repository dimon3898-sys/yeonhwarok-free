/** Exact compatibility CLI for the reused Studio detached worker. */
import {capture,parseCaptureArguments} from './capture_recovery.mjs';
await capture(parseCaptureArguments(process.argv.slice(2)));
