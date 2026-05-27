#pragma once

#include "scan_chain.h"

#include <string>
#include <vector>

namespace ScanForge {

struct TimingRankingEntry {
    int         ff_index = -1;
    std::string ff_name;
    double      score = 0.0;
};

struct TimingRanking {
    std::vector<double>            score_by_ff;
    std::vector<TimingRankingEntry> entries_desc;
};

// Load a timing-criticality ranking CSV and align it to ScanData FF names.
// Supported rows:
//   ff_name,score
//   score,ff_name
// A header row is optional.
bool loadTimingRankingCsv(const std::string &path,
                          const ScanData &data,
                          TimingRanking &out);

// Select top round(ratio * N) FFs as non-scan based on descending timing score.
std::vector<int> selectNonScanFFs(const TimingRanking &ranking,
                                  int num_ff,
                                  double exclusion_ratio);

// Build the default single scan chain from all FFs not marked non-scan.
std::vector<int> buildScanChainFromNonScan(const std::vector<int> &non_scan,
                                           int num_ff);

bool writeNonScanCsv(const std::string &path,
                     const ScanData &data,
                     const TimingRanking &ranking,
                     const std::vector<int> &non_scan);

} // namespace ScanForge
