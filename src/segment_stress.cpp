// ScanForge — segment_stress.cpp
// Sliding-window segment stress along the simulated scan chain order.

#include "segment_stress.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>

namespace ScanForge {

namespace {

double meanOfAvgs(const std::vector<SegmentStress> &segs)
{
    if (segs.empty()) return 0.0;
    double s = 0.0;
    for (const auto &g : segs) s += g.avg_stress;
    return s / (double)segs.size();
}

double stddevPopAvgs(const std::vector<SegmentStress> &segs, double mean)
{
    if (segs.empty()) return 0.0;
    double acc = 0.0;
    for (const auto &g : segs) {
        double d = g.avg_stress - mean;
        acc += d * d;
    }
    return std::sqrt(acc / (double)segs.size());
}

double variancePopAvgs(const std::vector<SegmentStress> &segs, double mean)
{
    if (segs.empty()) return 0.0;
    double acc = 0.0;
    for (const auto &g : segs) {
        double d = g.avg_stress - mean;
        acc += d * d;
    }
    return acc / (double)segs.size();
}

} // namespace

std::vector<SegmentStress> computeSegmentStress(
    const std::vector<FFStress> &perFF_chainOrder,
    int                          window_size)
{
    std::vector<SegmentStress> segments;
    int K = (int)perFF_chainOrder.size();
    if (K <= 0 || window_size <= 0) return segments;

    int W = std::min(window_size, K);
    segments.reserve(K - W + 1);

    for (int start = 0; start + W <= K; ++start) {
        SegmentStress seg;
        seg.segment_id = start;
        seg.start_idx  = start;
        seg.end_idx    = start + W - 1;

        double sum    = 0.0;
        double maxVal = 0.0;
        for (int pos = start; pos < start + W; ++pos) {
            double s = perFF_chainOrder[pos].stress_score;
            sum += s;
            maxVal = std::max(maxVal, s);
        }
        seg.sum_stress = sum;
        seg.avg_stress = sum / (double)W;
        seg.max_stress = maxVal;
        segments.push_back(seg);
    }
    return segments;
}

void markHotspotsAndSummarize(std::vector<SegmentStress> &segments,
                              SegmentSummary             *summary_out)
{
    if (summary_out) {
        summary_out->max_segment_stress  = 0.0;
        summary_out->mean_segment_stress = 0.0;
        summary_out->segment_variance    = 0.0;
        summary_out->hotspot_count       = 0;
    }
    if (segments.empty()) return;

    double meanSeg = meanOfAvgs(segments);
    double stdSeg  = stddevPopAvgs(segments, meanSeg);
    double thr     = meanSeg + 1.0 * stdSeg;

    double maxAvg = 0.0;
    for (auto &g : segments) {
        g.is_hotspot = (g.avg_stress > thr);
        maxAvg = std::max(maxAvg, g.avg_stress);
    }

    int hot = 0;
    for (const auto &g : segments)
        if (g.is_hotspot) ++hot;

    if (summary_out) {
        summary_out->max_segment_stress  = maxAvg;
        summary_out->mean_segment_stress = meanSeg;
        summary_out->segment_variance    = variancePopAvgs(segments, meanSeg);
        summary_out->hotspot_count       = hot;
    }
}

SegmentSummary profileSegments(const std::vector<FFStress> &perFF_chainOrder,
                               int                          window_size,
                               std::vector<SegmentStress>  *segments_out)
{
    SegmentSummary sum;
    std::vector<SegmentStress> segs =
        computeSegmentStress(perFF_chainOrder, window_size);
    markHotspotsAndSummarize(segs, &sum);
    if (segments_out) *segments_out = std::move(segs);
    return sum;
}

bool writeSegmentCsv(const std::vector<SegmentStress> &segments,
                     const std::string                &path)
{
    std::ofstream out(path);
    if (!out) return false;
    out << "segment_id,start_idx,end_idx,sum_stress,avg_stress,max_stress,hotspot\n";
    out << std::fixed << std::setprecision(6);
    for (const auto &g : segments) {
        out << g.segment_id << ',' << g.start_idx << ',' << g.end_idx << ','
            << g.sum_stress << ',' << g.avg_stress << ',' << g.max_stress << ','
            << (g.is_hotspot ? 1 : 0) << '\n';
    }
    return (bool)out;
}

void applySegmentProfile(ScanResult &r, int window)
{
    r.segments.clear();
    r.max_segment_stress  = 0.0;
    r.segment_variance    = 0.0;
    r.hotspot_count       = 0;
    r.segment_window_used = 0;
    if (window <= 0 || r.numFF <= 0) return;

    SegmentSummary s = profileSegments(r.perFF, window, &r.segments);
    r.max_segment_stress  = s.max_segment_stress;
    r.segment_variance    = s.segment_variance;
    r.hotspot_count       = s.hotspot_count;
    r.segment_window_used = std::min(window, r.numFF);
}

} // namespace ScanForge
