// demo_seq_cycles.v — 10-FF demo with multiple cycles and a long sequential path.
//
// Sequential edges (from shared Q/D net names):
//   FF0.q=n0  → FF1.d=n0        edge 0→1
//   FF1.q=n1  → FF2.d=n1        edge 1→2
//   FF2.q=n2  → FF1.d=n2 (!)    edge 2→1  [back-edge: cycle FF1↔FF2]
//   FF2.q=n2  → FF3.d=n2        edge 2→3
//   FF3.q=n3  → FF4.d=n3        edge 3→4
//   FF4.q=n4  → FF5.d=n4        edge 4→5
//   FF5.q=n5  → FF3.d=n5 (!)    edge 5→3  [back-edge: cycle FF3→FF4→FF5→FF3]
//   FF5.q=n5  → FF6.d=n5        edge 5→6
//   FF6.q=n6  → FF7.d=n6        edge 6→7
//   FF7.q=n7  → FF8.d=n7        edge 7→8
//   FF8.q=n8  → FF6.d=n8 (!)    edge 8→6  [back-edge: cycle FF6→FF7→FF8→FF6]
//   FF8.q=n8  → FF9.d=n8        edge 8→9
//
// Cycles (3 total):
//   Cycle A: FF1↔FF2  (2-node)
//   Cycle B: FF3→FF4→FF5→FF3  (3-node)
//   Cycle C: FF6→FF7→FF8→FF6  (3-node)
//
// Heuristic FVS picks one FF per cycle to break all 3 cycles.
// After cycle-breaking, the longest acyclic path from FF0 can be up to depth 5+.
// With --seq-depth 3, the depth-reduction pass further reduces sequential depth.

module demo_seq_cycles (input clk, input ext, output q9);

  wire n0, n1, n2, n3, n4, n5, n6, n7, n8;

  dff FF0 (.clk(clk), .d(ext), .q(n0));
  dff FF1 (.clk(clk), .d(n2),  .q(n1));   // d=n2 => edge FF2→FF1 (back-edge for cycle A)
  dff FF2 (.clk(clk), .d(n1),  .q(n2));   // d=n1 => edge FF1→FF2; q=n2 drives FF1.d and FF3.d
  dff FF3 (.clk(clk), .d(n5),  .q(n3));   // d=n5 => edge FF5→FF3 (back-edge for cycle B)
  dff FF4 (.clk(clk), .d(n3),  .q(n4));   // d=n3 => edge FF3→FF4
  dff FF5 (.clk(clk), .d(n4),  .q(n5));   // d=n4 => edge FF4→FF5; q=n5 drives FF3.d and FF6.d
  dff FF6 (.clk(clk), .d(n8),  .q(n6));   // d=n8 => edge FF8→FF6 (back-edge for cycle C)
  dff FF7 (.clk(clk), .d(n6),  .q(n7));   // d=n6 => edge FF6→FF7
  dff FF8 (.clk(clk), .d(n7),  .q(n8));   // d=n7 => edge FF7→FF8; q=n8 drives FF6.d and FF9.d
  dff FF9 (.clk(clk), .d(n8),  .q(q9));   // d=n8 => edge FF8→FF9

endmodule
