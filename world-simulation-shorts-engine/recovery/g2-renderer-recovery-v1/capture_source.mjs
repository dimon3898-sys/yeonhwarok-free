/** Compatibility entrypoint selected by the unchanged detached worker contract. */
import {capture,parseCaptureArguments} from './capture_recovery.mjs';
await capture(parseCaptureArguments(process.argv.slice(2)));
