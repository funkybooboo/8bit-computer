// hex.js - memory-image parsing.
//
// The same three formats machine.py reads (logisim .hex, Intel HEX, raw
// binary), sniffed the same way, so this build loads exactly the images
// every other implementation burns:
//   - logisim: "v2.0 raw" header + hex words - what Digital's ROM editor
//     and roms/*.hex use
//   - intel:   Intel HEX records - what EEPROM burners take
//   - raw:     bare binary
//
// parseImage(bytes, size) -> Uint8Array of exactly `size` bytes (padded or
// truncated), or, with size === null, exactly the image's own content.
// Bytes come from fetch().arrayBuffer() in the browser or fs.readFileSync()
// under node.

function padOrTruncate(u8, size) {
  if (size === null || size === undefined) {
    return new Uint8Array(u8);
  }
  const out = new Uint8Array(size);
  out.set(u8.subarray(0, Math.min(u8.length, size)));
  return out;
}

function parseLogisim(text, size) {
  // drop the "v2.0 raw" header line; words are whitespace- or comma-separated
  const body = text.includes("\n") ? text.slice(text.indexOf("\n") + 1) : "";
  const vals = [];
  for (const t of body.replace(/,/g, " ").split(/\s+/)) {
    if (t) vals.push(parseInt(t, 16));
  }
  return padOrTruncate(Uint8Array.from(vals), size);
}

function parseIntel(u8, size) {
  const text = new TextDecoder("utf-8", { fatal: false }).decode(u8);
  const vals = [];  // [addr, byte] pairs
  for (let line of text.split(/\r?\n/)) {
    line = line.trim();
    if (!line) continue;
    if (line[0] !== ":") {
      throw new Error("bad Intel HEX line: " + line);
    }
    const rec = [];
    for (let i = 1; i + 1 < line.length; i += 2) {
      rec.push(parseInt(line.slice(i, i + 2), 16));
    }
    const count = rec[0];
    const addr = (rec[1] << 8) | rec[2];
    const rectype = rec[3];
    if (rectype === 0x00) {
      for (let i = 0; i < count; i++) vals.push([addr + i, rec[4 + i]]);
    } else if (rectype === 0x01) {
      break;  // end of file record
    } else {
      throw new Error("unsupported Intel HEX record type " + rectype);
    }
  }
  if (!vals.length) throw new Error("no data records in Intel HEX image");
  const len = size !== null && size !== undefined
    ? size : vals[vals.length - 1][0] + 1;
  const mem = new Uint8Array(len);
  for (const [a, v] of vals) {
    if (a < len) mem[a] = v;
  }
  return mem;
}

export function parseImage(bytes, size) {
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  // sniff: skip leading whitespace, a ':' means Intel HEX (like read_image)
  let i = 0;
  while (i < u8.length && (u8[i] === 0x20 || u8[i] === 0x09 || u8[i] === 0x0a || u8[i] === 0x0d)) i++;
  if (u8[i] === 0x3a) return parseIntel(u8, size);
  const text = new TextDecoder("utf-8", { fatal: false }).decode(u8);
  if (/^\s*v2\.0/.test(text)) return parseLogisim(text, size);
  return padOrTruncate(u8, size);  // raw binary
}
