// docs.js - the in-app documentation reader: the markdown under
// ../docs/ rendered in the page, with the cross-references between the
// documents working inside the reader (a .md link loads that document;
// a link to a file shows that file's source; an http link opens a tab).
//
// The renderer covers what the docs actually use - headings, tables,
// indented and fenced code, blockquotes, lists (one nesting level),
// inline code, bold and links - and nothing more. No dependencies, no
// network: the files are fetched from the repo the app is served from.

// the documents, in the order of docs/README.md's table
export const DOCS = [
  { file: "README.md", title: "docs/ - the documentation index" },
  { file: "architecture.md", title: "Architecture - how the parts make a computer" },
  { file: "hardware.md", title: "Hardware - every part and every wire" },
  { file: "instruction-set.md", title: "Instruction set - the machine language" },
  { file: "language.md", title: "The .hl language" },
  { file: "microcode.md", title: "Microcode - the control signals and ROMs" },
  { file: "assembly-language.md", title: "Assembly language - the assembler" },
  { file: "programs.md", title: "Programs - the gallery and the limits" },
  { file: "tools.md", title: "Tools - the toolchain" },
  { file: "additions.md", title: "Additions - made and possible" },
  { file: "getting-to-c.md", title: "Getting to C" },
  { file: "getting-to-os.md", title: "Getting to an OS" },
];

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** inline markdown (code spans first, so links/bold stay literal
 *  inside them). Input is RAW markdown; output is HTML. */
function inline(raw) {
  const parts = raw.split(/`([^`]+)`/);  // even: text, odd: code
  return parts.map((part, i) => {
    if (i % 2 === 1) return "<code>" + esc(part) + "</code>";
    let t = esc(part);
    t = t.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g,
      '<a href="$2" class="mdlink">$1</a>');
    return t;
  }).join("");
}

function renderTable(lines) {
  const rows = lines.map((l) => {
    const cells = l.replace(/^\|/, "").replace(/\|$/, "").split("|");
    return cells.map((c) => c.trim());
  });
  let html = "<table><thead><tr>";
  for (const c of rows[0]) html += "<th>" + inline(c) + "</th>";
  html += "</tr></thead><tbody>";
  for (let i = 2; i < rows.length; i++) {  // row 1 is the |---| rule
    html += "<tr>";
    for (const c of rows[i]) html += "<td>" + inline(c) + "</td>";
    html += "</tr>";
  }
  return html + "</tbody></table>";
}

function renderList(lines) {
  // items: [indent, text]; one nesting level (2-space indented items
  // nest under the previous item)
  let html = "<ul>";
  let open = false;
  for (const [ind, text] of lines) {
    if (ind > 0 && open) {
      html += "<li class='nest'>" + inline(text) + "</li>";
    } else {
      if (open) html += "</ul></li>";
      html += "<li>" + inline(text);
      html += "<ul class='sub'>";
      open = true;
    }
  }
  if (open) html += "</ul></li>";
  return html + "</ul>";
}

/** markdown text -> HTML string (the constructs the docs use). */
export function renderMarkdown(text) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;
  let para = [];
  const flushPara = () => {
    if (para.length) {
      out.push("<p>" + para.map(inline).join("\n") + "</p>");
      para = [];
    }
  };
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {  // fenced code block
      flushPara();
      const code = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++;
      out.push("<pre>" + esc(code.join("\n")) + "</pre>");
      continue;
    }
    const h = /^(#{1,4}) +(.*)$/.exec(line);
    if (h) {
      flushPara();
      const level = h[1].length;
      out.push("<h" + level + ">" + inline(h[2]) + "</h" + level + ">");
      i++;
      continue;
    }
    if (/^\|/.test(line) && i + 1 < lines.length && /^\|[-| ]+\|?\s*$/.test(lines[i + 1])) {
      flushPara();
      const table = [];
      while (i < lines.length && /^\|/.test(lines[i])) table.push(lines[i++]);
      out.push(renderTable(table));
      continue;
    }
    if (/^> ?/.test(line)) {
      flushPara();
      const quote = [];
      while (i < lines.length && /^> ?/.test(lines[i])) {
        quote.push(lines[i].replace(/^> ?/, ""));
        i++;
      }
      out.push("<blockquote>" + quote.map(inline).join("\n") + "</blockquote>");
      continue;
    }
    if (/^(\s*)[-*] +/.test(line)) {
      flushPara();
      const items = [];
      while (i < lines.length && /^(\s*)([-*] |$)/.test(lines[i]) &&
             (lines[i].trim() === "" || /^(\s*)[-*] +/.test(lines[i]))) {
        if (lines[i].trim() !== "") {
          const m = /^(\s*)[-*] +(.*)$/.exec(lines[i]);
          items.push([m[1].length, m[2]]);
        }
        i++;
      }
      out.push(renderList(items));
      continue;
    }
    if (/^ {4,}\S/.test(line)) {  // indented code block
      flushPara();
      const code = [];
      while (i < lines.length && (/^ {4,}\S/.test(lines[i]) || lines[i] === "")) {
        if (lines[i] === "" && !(i + 1 < lines.length && /^ {4,}\S/.test(lines[i + 1]))) break;
        code.push(lines[i].slice(4));
        i++;
      }
      out.push("<pre>" + esc(code.join("\n")) + "</pre>");
      continue;
    }
    if (line.trim() === "") {
      flushPara();
      i++;
      continue;
    }
    para.push(line);
    i++;
  }
  flushPara();
  return out.join("\n");
}

/** Build the reader into `container`: a document picker and the
 *  rendered page, with .md links navigating inside the reader. */
export function makeDocsViewer(container, baseDir) {
  container.replaceChildren();
  const bar = document.createElement("div");
  bar.className = "docbar";
  const select = document.createElement("select");
  for (const d of DOCS) {
    const opt = document.createElement("option");
    opt.value = d.file;
    opt.textContent = d.title;
    select.append(opt);
  }
  bar.append(select);
  const page = document.createElement("div");
  page.className = "md";
  container.append(bar, page);

  let current = DOCS[0].file;

  select.addEventListener("change", () => show(select.value));

  async function show(file) {
    current = file;
    select.value = DOCS.some((d) => d.file === file) ? file : select.value;
    page.replaceChildren();
    try {
      const r = await fetch(baseDir + file);
      if (!r.ok) throw new Error(r.status);
      const text = await r.text();
      if (/\.md$/.test(file)) {
        page.innerHTML = renderMarkdown(text);
      } else {  // a linked source file: show it as text
        page.innerHTML = "<h3>" + esc(file) + "</h3><pre>" + esc(text) + "</pre>";
      }
      page.scrollTop = 0;
    } catch (e) {
      page.innerHTML = "<p class='err'>could not load " + esc(file) +
        " (" + e + ") - serve the repo root with an HTTP server" +
        " (see web/README.md)</p>";
      return;
    }
  }

  // navigate cross-references inside the reader
  page.addEventListener("click", (ev) => {
    const a = ev.target.closest("a");
    if (!a || !a.getAttribute("href")) return;
    const href = a.getAttribute("href");
    ev.preventDefault();
    if (/^https?:/.test(href)) {
      window.open(href, "_blank", "noopener");
      return;
    }
    // resolve relative to the current document
    const parts = (baseDir + current).split("/");
    parts.pop();
    for (const seg of href.split("/")) {
      if (seg === "..") parts.pop();
      else if (seg !== "." && seg !== "") parts.push(seg);
    }
    const target = parts.join("/");
    show(target);
  });

  show(DOCS[0].file);
  return { show };
}
