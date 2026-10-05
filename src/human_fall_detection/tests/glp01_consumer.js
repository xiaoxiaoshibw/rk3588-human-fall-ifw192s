/* GL-P01 R2 cross-language consumer check (Node only).
 *
 * Reads a strictly serialized production snapshot on stdin and runs it through
 * the REAL preview parser (webui/human_fall_preview/human_fall_lib.js), then
 * prints "GLP01_CONSUMER_OK <json>". Exits non-zero unless the parser returns
 * the expected status, so the Python tests prove the actual wire chain.
 *
 * stdin may be a bare snapshot (expects "ready", the R1 positive) or an
 * envelope {"snapshot": ..., "expect": "ready"|"unqualified"|"unavailable"}.
 */
"use strict";

const path = require("path");
const HF = require(path.resolve(
  __dirname, "../../../webui/human_fall_preview/human_fall_lib.js"));

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  try {
    const payload = JSON.parse(raw);
    const expect = payload && payload.expect ? payload.expect : "ready";
    const snapshot = payload && payload.snapshot ? payload.snapshot : payload;
    const parsed = HF.parseGroundRender(snapshot);
    const out = {
      parse_status: parsed.status,
      parse_reason: parsed.reason || null,
      support_status: parsed.support ? parsed.support.status : null,
      ground_R: parsed.R || null,
      ground_t: parsed.t || null,
      ground_derived_id: parsed.ground_derived_id || null
    };
    if (parsed.status !== expect) {
      process.stderr.write("expected " + expect + " got " + parsed.status +
        ": " + JSON.stringify(out) + "\n");
      process.exit(3);
    }
    process.stdout.write("GLP01_CONSUMER_OK " + JSON.stringify(out) + "\n");
  } catch (error) {
    process.stderr.write(String((error && error.stack) || error) + "\n");
    process.exit(2);
  }
});
