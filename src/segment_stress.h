#pragma once
// ScanForge — segment_stress.h
// Sliding-window segment stress (hotspot) profiling along the scan chain.

#include "scan_chain.h"

#include <string>
#include <vector>

namespace ScanForge {

// `perFF_chainOrder` must match simulate() output: length K, index i = chain position i.
std::vector<SegmentStress> computeSegmentStress(
    const std::vector<FFStress> &perFF_chainOrder,
    int                          window_size);

// Sets is_hotspot: avg > mean(all avgs) + 1.0 * stddev(all avgs). Fills summary.
void markHotspotsAndSummarize(std::vector<SegmentStress> &segments,
                              SegmentSummary             *summary_out);

SegmentSummary profileSegments(const std::vector<FFStress> &perFF_chainOrder,
                               int                          window_size,
                               std::vector<SegmentStress>  *segments_out);

bool writeSegmentCsv(const std::vector<SegmentStress> &segments,
                     const std::string                &path);

} // namespace ScanForge
