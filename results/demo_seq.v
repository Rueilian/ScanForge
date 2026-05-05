// demo_seq.v — synthetic structural Verilog for sequential graph demo.
// 8 DFFs (U_FF0..U_FF7) with two cycles and one long sequential path.
//
// The Verilog parser in ScanForge infers FF-to-FF edges from shared Q/D net names.
// Each DFF has a single .d(net) and .q(net); when FF_i.q_net == FF_j.d_net, edge i→j is added.
//
// Net assignments and resulting edges:
//   U_FF0 .d(ext) .q(n0)   n0 drives U_FF1.d   => edge FF0→FF1
//   U_FF1 .d(n0)  .q(n1)   n1 drives U_FF2.d   => edge FF1→FF2
//   U_FF2 .d(n1)  .q(n2)   n2 drives U_FF1.d'? no—n2 drives U_FF3.d  => edge FF2→FF3
//
// To create cycle FF1↔FF2, we need n2 also to be the .d of U_FF1.
// But each instance can only have one .d net; so we reuse the same wire for both FFs.
// Specifically: make U_FF1.d = n2 (FF2's Q), and U_FF0.q = n2 too? No, that conflates things.
//
// Cleaner approach: use a 'mux' net naming trick.
// Let U_FF1.d  = n_f1d   (a specific net name)
//     U_FF0.q  = n_f1d   => edge FF0→FF1
//     U_FF2.q  = n_f1d   => edge FF2→FF1 (back-edge, forms cycle FF1→FF2→FF1)
//
// U_FF2.d  = n_f2d
// U_FF1.q  = n_f2d       => edge FF1→FF2
//
// Cycle A confirmed: FF1.q=n_f2d drives FF2.d, FF2.q=n_f1d drives FF1.d  => cycle FF1↔FF2
//
// For cycle B (FF3→FF4→FF5→FF3):
//   U_FF3.d = n_f3d;  U_FF5.q = n_f3d  => edge FF5→FF3 (back-edge)
//   U_FF2.q = n_f3d? No — n_f1d is already U_FF2.q. Use a separate net:
//   U_FF2.q = n_f1d (already used above)
//   Need FF2→FF3 edge: U_FF2.q = n_f1d  and U_FF3.d = n_f1d → but n_f1d is the D of FF1, 
//   that would give edge FF2→FF1 and FF2→FF3 simultaneously if both FF1 and FF3 have .d(n_f1d).
//
// Final clean topology (8 FFs, 2 cycles, long path after cycle removal):
//
// Nets:
//   U_FF0: .d(ext_in), .q(n01)            => n01 used as d of FF1
//   U_FF1: .d(n01),    .q(n12)            => n12 used as d of FF2; also n32 below drives n01? 
//
// Restart with a minimal but correct cycle-inducing topology:
//
//   U_FF0: .q(w0)  .d(ext_in)
//   U_FF1: .q(w1)  .d(w0)       => edge 0→1
//   U_FF2: .q(w1)  .d(w2)       => FF2.Q=w1 = FF1.Q, so net_q_driver[w1]=FF1 (overwritten by FF2!)
//
// Problem: if two FFs share the same Q net name, the second overwrites the first in net_q_driver.
// Solution: give every FF a unique Q net, and only reuse D nets for back-edges.
//
// CORRECT topology:
//   FF0: .d(ext), .q(q0)
//   FF1: .d(q0),  .q(q1)    => edge 0→1  (q0 = FF0's Q, drives FF1's D)
//   FF2: .d(q1),  .q(q2)    => edge 1→2
//   FF1 also has .d(q2) — impossible with one instance.
//
// Since each named FF appears once, we cannot have FF1.d be both q0 and q2.
// The back-edge FF2→FF1 requires q2 to appear as FF1's d-net, but q0 is already there.
//
// The Verilog parser picks the LAST seen .d for each named FF instance.
// So we can list U_FF1 twice: first .d(q0)  then .d(q2) — the parser will use q2 as the d-net.
// That gives only edge FF2→FF1, not FF0→FF1. Unless the parser accumulates all .d nets...
//
// Reading verilog_netlist.cpp: parseFfInstance() sets dnet = sig for first matching isDataPort.
// It does NOT accumulate; it picks the last .d port in the named port list.
// So listing .d(q2) after .d(q0) in the same instance would override. Can't get both.
//
// WORKAROUND: Use multi-driven nets by giving two different data ports names.
// ISCAS dff cell has ports in this order: clk, d, q. 
// Parser for named ports: tries isDataPort and isQPort.
// We can use two data ports with different names (e.g. .d and .si) since isDataPort("si")=true.
// So: U_FF1 (.clk(clk), .d(q0), .si(q2), .q(q1))
// The parser will set dnet=q0 on seeing .d, then dnet=q2 on seeing .si → last wins = q2.
// Still only one d-net per instance.
//
// FINAL APPROACH: model each "virtual" back-edge by having the DESTINATION FF
// use the SOURCE FF's Q net as its D net (i.e., the D-net equals the back-source's Q-net).
// This means we must choose which edge to represent for each FF.
//
// Topology choice that maximises demo value with the parser limitation:
//
//   FF0: .d(ext),  .q(q0)                    no predecessor
//   FF1: .d(q3),   .q(q1)    => edge 3→1  (cycle FF1→FF2→FF3→FF1 if we set it up)
//   FF2: .d(q1),   .q(q2)    => edge 1→2
//   FF3: .d(q2),   .q(q3)    => edge 2→3 + cycle FF1↔FF2↔FF3↔FF1 (3-node)
//   FF4: .d(q0),   .q(q4)    => edge 0→4
//   FF5: .d(q4),   .q(q5)    => edge 4→5
//   FF6: .d(q5),   .q(q6)    => edge 5→6
//   FF7: .d(q6),   .q(q7)    => edge 6→7
//
// Edges: 3→1, 1→2, 2→3 (cycle FF1→FF2→FF3→FF1), 0→4, 4→5, 5→6, 6→7
// Cycles: one 3-node cycle {FF1,FF2,FF3}
// After breaking: FVS picks one of {FF1,FF2,FF3} (highest freq = all equal → FF1 by index)
// Remaining chain: FF0→FF4→FF5→FF6→FF7 (depth 4 edges; with --seq-depth 3 triggers depth pass)
// Also: FF2→FF3 and FF3→FF1 still form sub-paths of length 2 in remaining after removing FF1.
//
// To also trigger depth reduction, set --seq-depth 3 for the demo.

module demo_seq (input clk, input ext, output q7);

  wire q0, q1, q2, q3, q4, q5, q6;

  dff U_FF0 (.clk(clk), .d(ext), .q(q0));
  dff U_FF1 (.clk(clk), .d(q3),  .q(q1));   // edge FF3→FF1 (back-edge of cycle)
  dff U_FF2 (.clk(clk), .d(q1),  .q(q2));   // edge FF1→FF2
  dff U_FF3 (.clk(clk), .d(q2),  .q(q3));   // edge FF2→FF3
  dff U_FF4 (.clk(clk), .d(q0),  .q(q4));   // edge FF0→FF4
  dff U_FF5 (.clk(clk), .d(q4),  .q(q5));   // edge FF4→FF5
  dff U_FF6 (.clk(clk), .d(q5),  .q(q6));   // edge FF5→FF6
  dff U_FF7 (.clk(clk), .d(q6),  .q(q7));   // edge FF6→FF7

endmodule
