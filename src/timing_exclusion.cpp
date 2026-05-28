#include "timing_exclusion.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <unordered_map>

namespace ScanForge {

namespace {

std::string trim(const std::string &s)
{
    std::size_t begin = 0;
    while (begin < s.size() && std::isspace(static_cast<unsigned char>(s[begin])))
        ++begin;
    std::size_t end = s.size();
    while (end > begin && std::isspace(static_cast<unsigned char>(s[end - 1])))
        --end;
    return s.substr(begin, end - begin);
}

std::vector<std::string> splitCsvLine(const std::string &line)
{
    std::vector<std::string> out;
    std::string cur;
    bool in_quote = false;
    for (char ch : line) {
        if (ch == '"') {
            in_quote = !in_quote;
        } else if (ch == ',' && !in_quote) {
            out.push_back(trim(cur));
            cur.clear();
        } else {
            cur.push_back(ch);
        }
    }
    out.push_back(trim(cur));
    return out;
}

bool parseDouble(const std::string &s, double &out)
{
    char *end = nullptr;
    out = std::strtod(s.c_str(), &end);
    return end && *end == '\0';
}

} // namespace

bool loadTimingRankingCsv(const std::string &path,
                          const ScanData &data,
                          TimingRanking &out)
{
    std::ifstream in(path);
    if (!in) {
        std::cerr << "Error: cannot open timing ranking CSV: " << path << "\n";
        return false;
    }

    std::unordered_map<std::string, int> index_by_name;
    for (int i = 0; i < data.numFF; ++i)
        index_by_name[data.ffs[i].name] = i;

    out.score_by_ff.assign(data.numFF, 0.0);
    out.entries_desc.clear();

    std::string line;
    int line_no = 0;
    std::vector<char> seen(data.numFF, 0);
    while (std::getline(in, line)) {
        ++line_no;
        std::string t = trim(line);
        if (t.empty())
            continue;

        auto cols = splitCsvLine(t);
        if (cols.size() < 2)
            continue;

        double a = 0.0;
        double b = 0.0;
        bool a_num = parseDouble(cols[0], a);
        bool b_num = parseDouble(cols[1], b);

        std::string ff_name;
        double score = 0.0;
        if (!a_num && b_num) {
            ff_name = cols[0];
            score = b;
        } else if (a_num && !b_num) {
            ff_name = cols[1];
            score = a;
        } else if (line_no == 1) {
            continue;
        } else {
            std::cerr << "Error: malformed timing ranking row at line "
                      << line_no << " in " << path << "\n";
            return false;
        }

        auto it = index_by_name.find(ff_name);
        if (it == index_by_name.end()) {
            std::cerr << "Error: FF \"" << ff_name
                      << "\" from timing ranking not found in .sf data\n";
            return false;
        }

        int idx = it->second;
        out.score_by_ff[idx] = score;
        if (!seen[idx]) {
            seen[idx] = 1;
            out.entries_desc.push_back({idx, ff_name, score});
        } else {
            for (auto &entry : out.entries_desc) {
                if (entry.ff_index == idx) {
                    entry.score = score;
                    break;
                }
            }
        }
    }

    if ((int)out.entries_desc.size() != data.numFF) {
        std::cerr << "Error: timing ranking CSV covers " << out.entries_desc.size()
                  << " FFs, but .sf data contains " << data.numFF << "\n";
        return false;
    }

    std::sort(out.entries_desc.begin(), out.entries_desc.end(),
              [](const TimingRankingEntry &a, const TimingRankingEntry &b) {
                  if (a.score != b.score)
                      return a.score > b.score;
                  return a.ff_index < b.ff_index;
              });
    return true;
}

std::vector<int> selectNonScanFFs(const TimingRanking &ranking,
                                  int num_ff,
                                  double exclusion_ratio)
{
    if (num_ff <= 0)
        return {};
    int k = (int)std::round(exclusion_ratio * num_ff);
    if (k <= 0)
        k = 1;
    k = std::min(k, num_ff);

    std::vector<int> out;
    out.reserve(k);
    for (int i = 0; i < k && i < (int)ranking.entries_desc.size(); ++i)
        out.push_back(ranking.entries_desc[i].ff_index);
    std::sort(out.begin(), out.end());
    return out;
}

std::vector<int> buildScanChainFromNonScan(const std::vector<int> &non_scan,
                                           int num_ff)
{
    std::vector<char> excluded(num_ff, 0);
    for (int idx : non_scan) {
        if (idx >= 0 && idx < num_ff)
            excluded[idx] = 1;
    }

    std::vector<int> chain;
    chain.reserve(num_ff - (int)non_scan.size());
    for (int i = 0; i < num_ff; ++i) {
        if (!excluded[i])
            chain.push_back(i);
    }
    return chain;
}

bool writeNonScanCsv(const std::string &path,
                     const ScanData &data,
                     const TimingRanking &ranking,
                     const std::vector<int> &non_scan)
{
    std::vector<char> excluded(data.numFF, 0);
    for (int idx : non_scan) {
        if (idx >= 0 && idx < data.numFF)
            excluded[idx] = 1;
    }

    std::ofstream out(path);
    if (!out)
        return false;

    out << "ff_index,ff_name,timing_score,is_non_scan\n";
    for (int i = 0; i < data.numFF; ++i) {
        out << i << ','
            << data.ffs[i].name << ','
            << ranking.score_by_ff[i] << ','
            << (excluded[i] ? 1 : 0) << '\n';
    }
    return true;
}

} // namespace ScanForge
