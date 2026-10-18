import de.neemann.digital.cli.CircuitLoader;
import de.neemann.digital.core.Model;
import de.neemann.digital.core.ObservableValue;
import de.neemann.digital.core.Signal;
import de.neemann.digital.core.wiring.Clock;
import de.neemann.digital.draw.elements.Circuit;
import de.neemann.digital.draw.elements.Pin;
import de.neemann.digital.draw.elements.VisualElement;
import de.neemann.digital.draw.model.ModelCreator;
import de.neemann.digital.draw.model.Net;
import de.neemann.digital.draw.model.NetList;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * DigSim - headless simulator for Digital .dig circuits (tested with Digital 0.31).
 *
 * Actions are executed in command line order, so a whole scenario can be run in
 * one invocation, e.g. the Output Register module:
 *
 *   tools/digsim --dig "digital/Output Register.dig" --list
 *   tools/digsim --dig "digital/Output Register.dig" \
 *       --set 'CLR\_hat=1' --set 'OI=1' --set 'BUS\_1=1' --set 'BUS\_5=1' \
 *       --edge CLK --toggle 'MUX\_CLK:8' --render
 *
 * Note that Digital stores labels containing an underscore with a backslash
 * escape (e.g. "BUS\_1"); --set/--edge/--toggle accept both the escaped form
 * and the plain one.
 *
 * Options:
 *   --dig FILE         circuit file (required)
 *   --list             list the input signal names and exit
 *   --set NAME=VALUE   set an input signal; VALUE may be 0x.., 0b.. or decimal.
 *                      Propagation steps run after each --set.
 *   --edge NAME        pulse a signal 0->1->0 (a full clock cycle)
 *   --toggle NAME=N    toggle a signal N half-cycles, stepping after each;
 *                      with --render, the display state is printed per half-cycle
 *   --steps N          run N propagation steps
 *   --render           with --toggle: print the Seven-Seg display state after
 *                      each half-cycle. Displays are printed left-to-right;
 *                      '.' marks a disabled display, ' ' an enabled blank one.
 *   --watch SPEC       print the current value of a pin, given either as
 *                      "LABEL.pinName" (e.g. "U37.1~Q") or as a pin position
 *                      "x,y" (e.g. "1800,-280")
 *   --dump [FILTER]    print all pin values, optionally only for elements whose
 *                      Label or element name contains FILTER
 *
 * Implementation notes (version specific):
 *  - Pin values are read through the model's net list, reached via reflection
 *    on ModelCreator.netList. VisualElement.getPins() returns fresh Pin copies
 *    without values, so values are looked up by pin position.
 *  - Only wires sharing endpoints are one net (Digital semantics); the
 *    reflection uses the same NetList Digital itself builds, so this matches
 *    the simulator exactly.
 */
public class DigSim {

    private final Circuit circuit;
    private final Model model;
    private final Map<String, ObservableValue> inputs = new LinkedHashMap<>();
    private final Map<String, ObservableValue> posMap = new HashMap<>();
    private final List<Net> nets = new ArrayList<>();
    private final List<VisualElement> elements;
    private boolean render = false;

    public DigSim(String file) throws Exception {
        CircuitLoader cl = new CircuitLoader(file, false);
        circuit = cl.getCircuit();
        ModelCreator mc = new ModelCreator(circuit, cl.getLibrary());
        model = mc.createModel(true);

        for (Signal s : model.getInputs())
            inputs.put(s.getName(), s.getValue());
        for (Clock c : model.getClocks())
            inputs.put(c.getLabel(), c.getClockOutput());

        Field f = ModelCreator.class.getDeclaredField("netList");
        f.setAccessible(true);
        NetList nl = (NetList) f.get(mc);
        for (Net n : nl) {
            nets.add(n);
            for (Pin p : n.getPins())
                posMap.put(p.getPos().x + "," + p.getPos().y, p.getValue());
        }

        elements = new ArrayList<>(circuit.getElements());
        model.init();
    }

    // ---------------- actions ----------------

    void setInput(String name, long value) {
        ObservableValue v = inputs.get(name);
        if (v == null)
            v = inputs.get(name.replace("\\_", "_"));
        if (v == null)
            throw new RuntimeException("input not found: " + name + " (use --list; have " + inputs.keySet() + ")");
        v.setValue(value);
    }

    static long parseValue(String s) {
        if (s.startsWith("0x") || s.startsWith("0X")) return Long.parseLong(s.substring(2), 16);
        if (s.startsWith("0b") || s.startsWith("0B")) return Long.parseLong(s.substring(2), 2);
        return Long.parseLong(s);
    }

    void step() throws Exception {
        model.doStep();
    }

    void edge(String name) throws Exception {
        setInput(name, 1);
        step();
        setInput(name, 0);
        step();
    }

    void toggle(String name, int halfCycles) throws Exception {
        Map<Integer, Character> seen = new HashMap<>();
        for (int i = 0; i < halfCycles; i++) {
            setInput(name, i % 2);
            step();
            String r = renderDisplays();
            if (render)
                System.out.println("  display: [" + r + "]");
            for (int d = 0; d < r.length(); d++)
                if (r.charAt(d) != '.')
                    seen.putIfAbsent(d, r.charAt(d));
        }
        StringBuilder sb = new StringBuilder();
        int n = 0;
        for (int d : seen.keySet()) n = Math.max(n, d + 1);
        for (int d = 0; d < n; d++)
            sb.append(seen.getOrDefault(d, '?'));
        System.out.println("  display(mux full cycle): [" + sb + "]");
    }

    long readPos(int x, int y) {
        ObservableValue v = posMap.get(x + "," + y);
        return v == null ? -1 : v.getValueHighZIsZero();
    }

    // ---------------- watch / dump / render ----------------

    /**
     * Watch spec: "x,y" position, or "LABEL.pinName" / "ELEMENTNAME.pinName".
     */
    void watch(String spec) {
        long val;
        if (spec.matches("-?\\d+,-?\\d+")) {
            String[] xy = spec.split(",", 2);
            val = readPos(Integer.parseInt(xy[0]), Integer.parseInt(xy[1]));
        } else {
            int dot = spec.lastIndexOf('.');
            if (dot < 0)
                throw new RuntimeException("bad --watch spec (need 'LABEL.pin' or 'x,y'): " + spec);
            String el = spec.substring(0, dot);
            String pin = spec.substring(dot + 1);
            val = readByElement(el, pin);
        }
        System.out.println("watch " + spec + " = " + val);
    }

    long readByElement(String el, String pin) {
        for (VisualElement ve : elements) {
            String label = ve.getElementAttributes().getLabel();
            if (!el.equals(label) && !el.equals(ve.getElementName()))
                continue;
            for (Pin p : ve.getPins())
                if (p.getName().equals(pin)) {
                    ObservableValue v = posMap.get(p.getPos().x + "," + p.getPos().y);
                    return v == null ? -1 : v.getValueHighZIsZero();
                }
        }
        throw new RuntimeException("pin not found: " + el + "." + pin);
    }

    /** Prints Digital's own nets (from ModelCreator.netList) with pin names, positions, directions and values. */
    void dumpNets() {
        for (Net n : nets) {
            StringBuilder sb = new StringBuilder("net [");
            boolean first = true;
            for (Pin p : n.getPins()) {
                if (!first) sb.append("; ");
                first = false;
                ObservableValue v = p.getValue();
                sb.append(p.getName()).append('@').append(p.getPos().x).append(',').append(p.getPos().y)
                        .append('/').append(p.getDirection())
                        .append('=').append(v == null ? "-" : Long.toString(v.getValueHighZIsZero()))
                        .append(v != null && v.isHighZ() ? "Z" : "");
            }
            sb.append(']');
            System.out.println(sb);
        }
    }

    void dump(String filter) {
        for (VisualElement ve : elements) {
            String label = ve.getElementAttributes().getLabel();
            String name = label.isEmpty() ? ve.getElementName() : label + " (" + ve.getElementName() + ")";
            if (filter != null && !name.toLowerCase().contains(filter.toLowerCase()))
                continue;
            StringBuilder sb = new StringBuilder(String.format("%-16s", name));
            for (Pin p : ve.getPins()) {
                ObservableValue v = posMap.get(p.getPos().x + "," + p.getPos().y);
                sb.append(' ').append(p.getName()).append('=')
                        .append(v == null ? "-" : v.getValueHighZIsZero());
            }
            System.out.println(sb);
        }
    }

    /** Prints each element's pins with their real positions (and value if a net is attached). */
    void pins(String filter) {
        for (VisualElement ve : elements) {
            String label = ve.getElementAttributes().getLabel();
            String name = label.isEmpty() ? ve.getElementName() : label + " (" + ve.getElementName() + ")";
            if (filter != null && !name.toLowerCase().contains(filter.toLowerCase()))
                continue;
            StringBuilder sb = new StringBuilder(String.format("%-16s", name));
            for (Pin p : ve.getPins()) {
                ObservableValue v = posMap.get(p.getPos().x + "," + p.getPos().y);
                sb.append(' ').append(p.getName()).append('@')
                        .append(p.getPos().x).append(',').append(p.getPos().y)
                        .append('=').append(v == null ? "-" : v.getValueHighZIsZero());
            }
            System.out.println(sb);
        }
    }

    /**
     * Renders all Seven-Seg elements left-to-right. '.' = display disabled,
     * a letter/digit = enabled pattern, ' ' = enabled but blank.
     */
    String renderDisplays() {
        ArrayList<VisualElement> segs = new ArrayList<>();
        for (VisualElement ve : elements)
            if (ve.getElementName().equals("Seven-Seg"))
                segs.add(ve);
        segs.sort(Comparator.comparingInt(v -> v.getPos().x));
        StringBuilder sb = new StringBuilder();
        for (VisualElement ve : segs) {
            Map<String, ObservableValue> pins = new HashMap<>();
            boolean hasCa = false, hasCc = false;
            for (Pin p : ve.getPins()) {
                pins.put(p.getName(), posMap.get(p.getPos().x + "," + p.getPos().y));
                if ("ca".equals(p.getName())) hasCa = true;
                if ("cc".equals(p.getName())) hasCc = true;
            }
            String common = hasCa ? "ca" : "cc";
            ObservableValue cv = pins.get(common);
            boolean enabled = cv == null || (hasCa ? cv.getBool() : !cv.getBool());
            boolean anode = hasCa;
            if (!enabled) {
                sb.append('.');
                continue;
            }
            boolean a = bit(pins, "a", anode), b = bit(pins, "b", anode), c = bit(pins, "c", anode);
            boolean d = bit(pins, "d", anode), e = bit(pins, "e", anode), f = bit(pins, "f", anode);
            boolean g = bit(pins, "g", anode);
            sb.append(decode(a, b, c, d, e, f, g));
        }
        return sb.toString();
    }

    private static boolean bit(Map<String, ObservableValue> pins, String name, boolean anode) {
        ObservableValue v = pins.get(name);
        if (v == null) return false;
        return anode ? !v.getBool() : v.getBool();
    }

    static char decode(boolean a, boolean b, boolean c, boolean d, boolean e, boolean f, boolean g) {
        String key = (a ? "a" : "") + (b ? "b" : "") + (c ? "c" : "") + (d ? "d" : "")
                + (e ? "e" : "") + (f ? "f" : "") + (g ? "g" : "");
        switch (key) {
            case "": return ' ';
            case "abcdef": return '0';
            case "bc": return '1';
            case "abdeg": return '2';
            case "abcdg": return '3';
            case "bcfg": return '4';
            case "acdfg": return '5';
            case "acdefg": return '6';
            case "abc": return '7';
            case "abcdefg": return '8';
            case "abcdfg": return '9';
            case "abcefg": return 'A';
            case "cdefg": return 'b';
            case "adef": return 'C';
            case "bcdeg": return 'd';
            case "adefg": return 'E';
            case "aefg": return 'F';
            default: return '?';
        }
    }

    // ---------------- CLI ----------------

    public static void main(String[] args) throws Exception {
        String dig = null;
        boolean list = false;
        DigSim sim = null;

        // --render is position independent: apply to every --toggle
        boolean render = false;
        for (String a : args) if (a.equals("--render")) render = true;

        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            if (sim == null && !a.equals("--dig") && !a.equals("--list")) {
                // create lazily so --list does not need the rest
                if (dig == null)
                    throw new RuntimeException("--dig FILE is required");
                sim = new DigSim(dig);
                sim.render = render;
            }
            switch (a) {
                case "--dig":
                    dig = args[++i];
                    sim = new DigSim(dig);
                    sim.render = render;
                    break;
                case "--list":
                    if (sim == null)
                        sim = new DigSim(dig);
                    System.out.println("inputs: " + sim.inputs.keySet());
                    return;
                case "--set": {
                    String[] kv = args[++i].split("=", 2);
                    if (kv.length != 2) throw new RuntimeException("bad --set (need NAME=VALUE)");
                    sim.setInput(kv[0], parseValue(kv[1]));
                    sim.step();
                    break;
                }
                case "--edge":
                    sim.edge(args[++i]);
                    break;
                case "--toggle": {
                    String[] kv = args[++i].split(":", 2);
                    int n = kv.length == 2 ? Integer.parseInt(kv[1]) : 1;
                    sim.toggle(kv[0], n);
                    break;
                }
                case "--steps":
                    for (int n = Integer.parseInt(args[++i]); n > 0; n--) sim.step();
                    break;
                case "--render":
                    sim.render = true;
                    break;
                case "--nets":
                    sim.dumpNets();
                    break;
                case "--watch":
                    sim.watch(args[++i]);
                    break;
                case "--dump": {
                    String filter = null;
                    if (i + 1 < args.length && !args[i + 1].startsWith("--"))
                        filter = args[++i];
                    sim.dump(filter);
                    break;
                }
                case "--pins": {
                    String filter = null;
                    if (i + 1 < args.length && !args[i + 1].startsWith("--"))
                        filter = args[++i];
                    if (sim == null)
                        sim = new DigSim(dig);
                    sim.pins(filter);
                    break;
                }
                default:
                    throw new RuntimeException("unknown option: " + a);
            }
        }
        if (sim != null)
            sim.model.close();
    }
}
