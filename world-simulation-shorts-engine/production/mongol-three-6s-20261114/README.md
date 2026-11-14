# Mongol three six-second inputs

The common V2 source contract and three inputs have passed changed-scope free checks. Source windows are [0,180), [180,360), [360,540); original600 design remains unchanged. Download the three MONGOL_6S_PART_0*.json files together with the approved external data package if preparing deployment.

These inputs require WORLD_ENGINE_AUTHORED_HISTORY_INPUT_V2. Do not upload them to an older success/history20 image: those images lack this contract. Actual-image validation and node GPU readiness are separate gates; inspect CHECKPOINT.json. No GPU render is authorized or claimed.

Previous success/image-block evidence is preserved in baseline-66e94bb/ and original git history. Current common-engine evidence is in ../../recovery/universal-input-contract-v2/.
