# digital/repro - the upstream reproduction circuits

The four tiny circuits that reproduce the Digital 0.31 Driver bug for
[hneemann/Digital PR 1541](https://github.com/hneemann/Digital/pull/1541)
("Driver: propagate a high-Z input to the output"). Each one uses only
standard library elements, opens in the Digital GUI, and needs a single
input toggle to show the difference between stock 0.31 and the patched
Driver ([../Driver.java](../Driver.java), built by [../gui](../gui))).

| File | Circuit | stock 0.31 | with the Driver fix |
|---|---|---|---|
| [dig245.dig](dig245.dig) | one library 74245, A side unwired, B1 driven by input T | short-circuit error on every run | no error; RESULT = T |
| [driver_pullup.dig](driver_pullup.dig) | 4-bit enabled Driver reading a floating net, output net with only a pull-up | no error, RESULT is a random 0-15 every run | RESULT = 15 every run |
| [driver_z2.dig](driver_z2.dig) | the Driver repro plus a Not gate reading the same floating net | burns about half the runs | no error; the gate output is still random (the noise model is untouched) |
| [twodrivers.dig](twodrivers.dig) | control: two defined drivers on one net | short-circuit error | short-circuit error, unchanged |

To run one: open it in Digital, start the simulation, and toggle the
input named in the circuit's description field (DIR for dig245, S for
the two Driver circuits, A and B for the control). Restart the
simulation a few times - stock 0.31 gives a different outcome on
almost every start, the patched build does not.

Measured with 30 runs per version: dig245 30/30 vs 0/30 errors,
driver_pullup 30/30 random vs 30/30 = 15, driver_z2 16/30 vs 0/30
errors, twodrivers identical on both.
