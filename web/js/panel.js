// panel.js - the front panel's parts: the LEDs, the switches and the
// tables, built as DOM and updated per frame. Structure only - main.js
// owns the machine and decides what is lit; the looks live in
// css/style.css. The panel follows docs/hardware.md, "The front
// panel": which LEDs exist, which switches, and the program-entry
// procedure.
//
// Builders return small { el, ... } objects; `el` goes into the
// document, the rest is the update surface.

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** A module card on the faceplate: the caption strip + content.
 *  `sub` is the chip annotation (e.g. "U8 U9 - 74173"). A `web`
 *  module is one of this app's conveniences - not on the machine -
 *  and is drawn dashed with a caption that says so (the convention is
 *  the legend above the panel). */
export function moduleCard(title, sub, web) {
  const m = el("section", "module" + (web ? " web" : ""));
  const cap = el("div", "cap");
  cap.append(el("span", "cap-t", title));
  if (web && !sub) sub = "not on the machine";
  if (sub) cap.append(el("span", "cap-s", sub));
  m.append(cap);
  return m;
}

/** A labeled bank of `bits` LEDs (MSB on the left) with a hex readout
 *  and an optional trailing note (the BUS driver). set(v) lights it.
 *  The label may be empty (the module caption already names it). */
export function ledBank(label, bits, color, note) {
  const leds = [];
  const box = el("div", "leds");
  for (let i = bits - 1; i >= 0; i--) {
    const l = el("span", "led " + color);
    l.title = (label || "") + " bit " + i;
    box.append(l);
    leds[i] = l;
  }
  const row = el("div", "bank");
  const read = el("span", "read");
  const trail = note ? el("span", "note") : null;
  if (label) row.append(el("span", "note", label));
  row.append(box, read, trail);
  return {
    el: row,
    read,
    note: trail,
    set(v) {
      for (let i = 0; i < bits; i++) leds[i].classList.toggle("on", ((v >> i) & 1) === 1);
      read.textContent = "0x" + v.toString(16).padStart(bits / 4, "0");
    },
  };
}

/** A row of individually named LEDs (control lines, microsteps, flags):
 *  cells left to right in the order given. lsbFirst maps name i to
 *  bit i (used when the natural display is LSB leftmost, like T0..T6);
 *  the default maps name i to bit (n-1-i) (MSB leftmost, like the
 *  control word tables in docs/microcode.md). */
export function namedLeds(names, color, lsbFirst) {
  const cells = [];
  const box = el("div", "cells");
  const n = names.length;
  names.forEach((name, i) => {
    const cell = el("span", "cell");
    const led = el("span", "led " + color);
    const bit = lsbFirst ? i : n - 1 - i;
    cell.append(led, el("span", "cl", name));
    led.title = name;
    box.append(cell);
    cells[bit] = led;
  });
  return {
    el: box,
    set(mask) {
      for (let i = 0; i < n; i++) {
        cells[i].classList.toggle("on", ((mask >> i) & 1) === 1);
      }
    },
  };
}

/** A bank of dipswitch levers (MSB on the left), clickable to flip.
 *  get()/set() read and load the switch byte. */
export function dipRow(label, bits, onChange) {
  const levers = [];
  const row = el("div", "dips");
  for (let i = bits - 1; i >= 0; i--) {
    const lever = el("span", "lever");
    lever.append(el("i"));
    lever.title = "bit " + i;
    lever.addEventListener("click", () => {
      value ^= 1 << i;
      lever.classList.toggle("on", ((value >> i) & 1) === 1);
      if (onChange) onChange(value);
    });
    row.append(lever);
    levers[i] = lever;
  }
  const wrap = el("div", "bank");
  wrap.append(el("span", "note", label), row);
  let value = 0;
  return {
    el: wrap,
    get: () => value,
    set(v) {
      value = v;
      for (let i = 0; i < bits; i++) {
        levers[i].classList.toggle("on", ((v >> i) & 1) === 1);
      }
      if (onChange) onChange(v);  // a programmatic set behaves like a flip
    },
  };
}

/** A slide switch with a caption on each side; on = right side.
 *  `label` (optional) names the panel net it drives (PROG_ADDR,
 *  STEP_MODE, DEC_HEX...), like the hardware doc does. */
export function toggleSwitch(left, right, onChange, label) {
  const wrap = el("div", "bank");
  const tg = el("span", "tg");
  const knobWrap = el("span", "slot");
  knobWrap.append(el("span", "knob"));
  tg.append(el("span", "tlabel", left), knobWrap, el("span", "tlabel", right));
  if (label) wrap.append(el("span", "note", label));
  wrap.append(tg);
  let on = false;
  tg.addEventListener("click", () => {
    on = !on;
    tg.classList.toggle("on", on);
    if (onChange) onChange(on);
  });
  return {
    el: wrap,
    get: () => on,
    set(v) {
      on = !!v;
      tg.classList.toggle("on", on);
      if (onChange) onChange(on);  // a programmatic set behaves like a flip
    },
  };
}

/** A keycap button. */
export function keycap(label, onClick, cls) {
  const b = el("button", "key" + (cls ? " " + cls : ""), label);
  if (onClick) b.addEventListener("click", onClick);
  return b;
}

/** The RAM monitor: 16 rows of address / byte / decimal / mnemonic,
 *  with the PC row marked and the addressed row shaded. Clicking a row
 *  loads its address and byte into the panel dipswitches. */
export function ramMonitor(decode, onRow) {
  const table = el("table", "ram");
  const head = el("tr");
  for (const h of ["", "ADDR", "BYTE", "DEC", "OP"]) {
    head.append(el("th", null, h));
  }
  table.append(el("thead"), el("tbody"));
  table.firstChild.append(head);
  const body = table.lastChild;
  const rows = [];
  for (let i = 0; i < 16; i++) {
    const tr = el("tr");
    const cells = [el("td", "mark"), el("td"), el("td"), el("td"), el("td")];
    tr.append(...cells);
    tr.addEventListener("click", () => onRow(i));
    body.append(tr);
    rows.push({ tr, cells });
  }
  return {
    el: table,
    update(ram, pc, effAddr) {
      for (let i = 0; i < 16; i++) {
        const { tr, cells } = rows[i];
        const b = ram[i];
        cells[0].textContent = i === pc ? ">" : (i === effAddr ? "*" : "");
        cells[1].textContent = i.toString(16).padStart(2, "0");
        cells[2].textContent = b.toString(16).padStart(2, "0");
        cells[3].textContent = String(b).padStart(3, " ");
        cells[4].textContent = decode(b);
        tr.classList.toggle("cur", i === pc);
        tr.classList.toggle("mar", i === effAddr && i !== pc);
      }
    },
  };
}

/** The listing pane: the program's entry table - one line per RAM
 *  address with the three dipswitch groups. Lines that carry a byte
 *  are clickable: onLine(addr, byte) puts them on the panel switches,
 *  which is what the table is FOR - entering the program by hand.
 *  The current PC line is highlighted. */
export function listingPane(onLine) {
  const wrap = el("div");
  const body = el("div", "listing");
  wrap.append(body);
  const intro = el("p", "lstnote",
    "the bytes in RAM, however they got there - picked from the gallery," +
    " compiled below, or entered by hand. A line's bits column is its" +
    " dipswitch settings; click a line to put them on the switches.");
  let byAddr = new Map();
  let current = null;
  let lastAddr = -1, lastScroll = 0;
  return {
    el: wrap,
    /** Show listing text (or a plain note when there is none). */
    set(text) {
      byAddr = new Map();
      current = null;
      body.replaceChildren();
      if (!text) {
        body.append(el("pre", null, "(no listing - load a program from the gallery,\n" +
          "or compile one of your own below)"));
        return;
      }
      const pre = el("pre");
      for (const line of text.replace(/\n$/, "").split("\n")) {
        const span = el("span", "lst-line", line + "\n");
        pre.append(span);
        const m = /^([0-9a-f]{2})\s+([0-9a-f]{2}|--)/.exec(line);
        if (m) {
          const a = parseInt(m[1], 16);
          if (!byAddr.has(a)) byAddr.set(a, []);
          byAddr.get(a).push(span);
          if (m[2] !== "--" && onLine) {
            // a real byte: the line IS a dipswitch setting - click to load
            span.classList.add("pick");
            span.addEventListener("click", () =>
              onLine(a, parseInt(m[2], 16)));
          }
        }
      }
      body.append(intro, pre);
    },
    /** Highlight the row for `addr` (label rows too); while the
     *  machine runs, keep the current line in view - scrolling the
     *  listing only, never the page. */
    mark(addr) {
      if (current) current.forEach((s) => s.classList.remove("cur"));
      current = byAddr.get(addr) || null;
      if (!current) return;
      current.forEach((s) => s.classList.add("cur"));
      if (addr === lastAddr && performance.now() - lastScroll < 500) return;
      lastAddr = addr;
      lastScroll = performance.now();
      const span = current[0];
      const pre = span.parentElement;
      const pr = pre.getBoundingClientRect(), sr = span.getBoundingClientRect();
      if (sr.top < pr.top + 4 || sr.bottom > pr.bottom - 4) {
        pre.scrollTop += sr.top - pr.top - pr.height / 3;
      }
    },
  };
}
