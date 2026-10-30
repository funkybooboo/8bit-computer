// panel.js - the machine's parts as DOM: the modules, the lamps, the
// switches, the keys. Structure only - main.js owns the machine and
// decides what is lit; the looks live in css/style.css. Every part here
// corresponds to something on the real machine (docs/hardware.md,
// "The front panel" and the module sections); nothing else is drawn.

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** A module card: the caption strip (title + chip annotation, e.g.
 *  "U8 U9 - 74173") + content. */
export function moduleCard(title, sub) {
  const m = el("section", "module");
  const cap = el("div", "cap");
  cap.append(el("span", "cap-t", title));
  if (sub) cap.append(el("span", "cap-s", sub));
  m.append(cap);
  return m;
}

/** A labeled bank of `bits` lamps (MSB on the left), like a row of
 *  LEDs on the machine. set(v) lights it. */
export function ledBank(label, bits, color) {
  const leds = [];
  const box = el("div", "leds");
  for (let i = bits - 1; i >= 0; i--) {
    const l = el("span", "led " + color);
    l.title = (label || "") + " bit " + i;
    box.append(l);
    leds[i] = l;
  }
  const row = el("div", "bank");
  if (label) row.append(el("span", "note", label));
  row.append(box);
  return {
    el: row,
    set(v) {
      for (let i = 0; i < bits; i++) {
        leds[i].classList.toggle("on", ((v >> i) & 1) === 1);
      }
    },
  };
}

/** A row of individually named lamps (the control lines, the
 *  microsteps, the flags): cells left to right in the order given.
 *  lsbFirst maps name i to bit i (when the natural display is LSB
 *  leftmost, like T0..T6); the default maps name i to bit (n-1-i)
 *  (MSB leftmost, like the control word tables in docs/microcode.md). */
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
  let value = 0;
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
      if (onChange) onChange(on);
    },
  };
}

/** A keycap button. */
export function keycap(label, onClick, cls) {
  const b = el("button", "key" + (cls ? " " + cls : ""), label);
  if (onClick) b.addEventListener("click", onClick);
  return b;
}
