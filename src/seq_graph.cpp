// ScanForge — seq_graph.cpp
// Sequential FF graph analysis: elementary cycles, FVS heuristic, depth reduction.

#include "seq_graph.h"

#include <algorithm>
#include <functional>
#include <iostream>
#include <queue>
#include <set>
#include <unordered_set>
#include <vector>

namespace ScanForge {

namespace {

using VertexSet = std::vector<int>; // sorted unique vertex ids

bool isStrictSubset(const VertexSet &small, const VertexSet &big)
{
    if (small.size() >= big.size()) return false;
    std::size_t i = 0, j = 0;
    while (i < small.size() && j < big.size()) {
        if (small[i] == big[j]) {
            ++i;
            ++j;
        } else if (small[i] > big[j]) {
            ++j;
        } else {
            return false;
        }
    }
    return i == small.size();
}

VertexSet sortedUnique(const std::vector<int> &cyc)
{
    VertexSet v = cyc;
    std::sort(v.begin(), v.end());
    v.erase(std::unique(v.begin(), v.end()), v.end());
    return v;
}

// Enumerate simple directed cycles where the smallest vertex index equals `start`,
// using only vertices with index >= `start` (standard uniqueness trick).
void enumerateCyclesFrom(int start, int n,
                         const std::vector<std::vector<int>> &adj,
                         std::vector<std::vector<int>> &out,
                         int cap)
{
    if ((int)out.size() >= cap) return;

    std::vector<int> path;
    std::vector<char> onPath(n, 0);

    std::function<void(int)> dfs = [&](int v) {
        if ((int)out.size() >= cap) return;
        for (int w : adj[v]) {
            if (w < start) continue;
            if (w == start) {
                if (path.size() >= 2) {
                    std::vector<int> cyc = path;
                    cyc.push_back(start);
                    out.push_back(std::move(cyc));
                    if ((int)out.size() >= cap) return;
                }
            } else if (!onPath[w]) {
                onPath[w] = 1;
                path.push_back(w);
                dfs(w);
                path.pop_back();
                onPath[w] = 0;
                if ((int)out.size() >= cap) return;
            }
        }
    };

    onPath[start] = 1;
    path.push_back(start);
    dfs(start);
    path.pop_back();
    onPath[start] = 0;
}

std::vector<std::vector<int>> enumerateElementaryCycles(
    int n, const std::vector<std::vector<int>> &adj, int cap)
{
    std::vector<std::vector<int>> cycles;
    for (int s = 0; s < n && (int)cycles.size() < cap; ++s)
        enumerateCyclesFrom(s, n, adj, cycles, cap);
    return cycles;
}

// Drop cycle A if ∃ B with V(B) ⊂ V(A) (inclusion-minimal vertex sets kept).
std::vector<std::vector<int>> minimalCyclesByVertexInclusion(
    std::vector<std::vector<int>> cycles)
{
    std::vector<VertexSet> verts;
    verts.reserve(cycles.size());
    for (const auto &c : cycles)
        verts.push_back(sortedUnique(c));

    std::vector<char> drop(verts.size(), 0);
    for (std::size_t i = 0; i < verts.size(); ++i) {
        if (drop[i]) continue;
        for (std::size_t j = 0; j < verts.size(); ++j) {
            if (i == j || drop[j]) continue;
            if (isStrictSubset(verts[j], verts[i]))
                drop[i] = 1;
        }
    }

    std::vector<std::vector<int>> kept;
    for (std::size_t i = 0; i < cycles.size(); ++i)
        if (!drop[i]) kept.push_back(std::move(cycles[i]));
    return kept;
}

bool cycleContainsVertex(const std::vector<int> &cyc, int v)
{
    return std::find(cyc.begin(), cyc.end(), v) != cyc.end();
}

std::vector<int> fvsFromMinimalCycles(std::vector<std::vector<int>> cycles)
{
    std::vector<int> selected;
    while (!cycles.empty()) {
        int maxv = 0;
        for (const auto &c : cycles)
            for (int v : c)
                maxv = std::max(maxv, v);

        std::vector<int> freq(maxv + 1, 0);
        for (const auto &c : cycles) {
            VertexSet su = sortedUnique(c);
            for (int v : su)
                ++freq[v];
        }
        int best = -1;
        int bestCnt = -1;
        for (int v = 0; v <= maxv; ++v) {
            if (freq[v] > bestCnt) {
                bestCnt = freq[v];
                best = v;
            }
        }
        if (best < 0) break;
        selected.push_back(best);

        std::vector<std::vector<int>> next;
        next.reserve(cycles.size());
        for (auto &c : cycles) {
            if (!cycleContainsVertex(c, best))
                next.push_back(std::move(c));
        }
        cycles.swap(next);
    }
    std::sort(selected.begin(), selected.end());
    selected.erase(std::unique(selected.begin(), selected.end()), selected.end());
    return selected;
}

std::vector<std::vector<int>> buildAdj(int n, const std::vector<SeqEdge> &edges)
{
    std::vector<std::vector<int>> adj(n);
    for (const auto &e : edges) {
        if (e.from == e.to) continue; // drop self-loops
        if (e.from < 0 || e.from >= n || e.to < 0 || e.to >= n) continue;
        adj[e.from].push_back(e.to);
    }
    for (auto &row : adj) {
        std::sort(row.begin(), row.end());
        row.erase(std::unique(row.begin(), row.end()), row.end());
    }
    return adj;
}

bool graphIsDAG(int n, const std::vector<std::vector<int>> &adj,
                const std::unordered_set<int> &removed)
{
    std::vector<int> indeg(n, 0);
    for (int u = 0; u < n; ++u) {
        if (removed.count(u)) continue;
        for (int v : adj[u]) {
            if (!removed.count(v))
                ++indeg[v];
        }
    }
    std::queue<int> q;
    for (int i = 0; i < n; ++i)
        if (!removed.count(i) && indeg[i] == 0) q.push(i);

    int seen = 0;
    while (!q.empty()) {
        int u = q.front();
        q.pop();
        ++seen;
        for (int v : adj[u]) {
            if (removed.count(v)) continue;
            if (--indeg[v] == 0)
                q.push(v);
        }
    }
    int alive = 0;
    for (int i = 0; i < n; ++i)
        if (!removed.count(i)) ++alive;
    return seen == alive;
}

// Enumerate simple paths (vertex lists); edge count = vertices - 1.
// Records paths with strictly more than depthThreshold edges.
void enumerateLongPaths(int n, const std::vector<std::vector<int>> &adj,
                        const std::unordered_set<int> &removed,
                        int depthThreshold, std::size_t cap,
                        std::vector<std::vector<int>> &pathsOut)
{
    pathsOut.clear();
    std::vector<int> path;
    std::vector<char> onStack(n, 0);

    std::function<void(int)> dfs = [&](int u) {
        if (pathsOut.size() >= cap) return;
        for (int v : adj[u]) {
            if (removed.count(v)) continue;
            if (onStack[v]) continue;
            path.push_back(v);
            onStack[v] = 1;
            int edges = (int)path.size() - 1;
            if (edges > depthThreshold) {
                pathsOut.push_back(path);
                if (pathsOut.size() >= cap) return;
            }
            dfs(v);
            onStack[v] = 0;
            path.pop_back();
            if (pathsOut.size() >= cap) return;
        }
    };

    for (int s = 0; s < n && pathsOut.size() < cap; ++s) {
        if (removed.count(s)) continue;
        path.clear();
        path.push_back(s);
        dfs(s);
    }
}

double centerWeight(int pos, int numVertices)
{
    int distEnd = std::min(pos, numVertices - 1 - pos);
    return static_cast<double>(distEnd + 1);
}

std::vector<int> depthReductionGreedy(const std::vector<std::vector<int>> &adj,
                                      int n,
                                      std::unordered_set<int> removed,
                                      int depthThreshold,
                                      std::size_t pathCap)
{
    std::vector<int> picked;

    while (true) {
        std::vector<std::vector<int>> longPaths;
        enumerateLongPaths(n, adj, removed, depthThreshold, pathCap, longPaths);
        if (longPaths.empty()) break;

        std::vector<double> score(n, 0.0);
        for (const auto &p : longPaths) {
            int L = (int)p.size();
            for (int i = 0; i < L; ++i) {
                int v = p[i];
                if (removed.count(v)) continue;
                score[v] += centerWeight(i, L);
            }
        }
        int best = -1;
        double bestSc = -1.0;
        for (int v = 0; v < n; ++v) {
            if (removed.count(v)) continue;
            if (score[v] > bestSc) {
                bestSc = score[v];
                best = v;
            }
        }
        if (best < 0 || bestSc <= 0.0) break;

        picked.push_back(best);
        removed.insert(best);
    }

    std::sort(picked.begin(), picked.end());
    picked.erase(std::unique(picked.begin(), picked.end()), picked.end());
    return picked;
}

} // namespace

SeqGraphSelection selectSequentialGraphFFs(const ScanData &data,
                                             int depth_threshold,
                                             std::size_t path_enum_cap)
{
    SeqGraphSelection out;
    const int n = data.numFF;
    if (n <= 0) return out;

    if (data.seq_edges.empty()) {
        out.edges_missing = true;
        return out;
    }

    auto adj = buildAdj(n, data.seq_edges);

    const int cycleCap = 100000;
    auto rawCycles = enumerateElementaryCycles(n, adj, cycleCap);
    out.cycle_count_raw = (int)rawCycles.size();

    auto minimal = minimalCyclesByVertexInclusion(std::move(rawCycles));
    out.cycle_count_minimal = (int)minimal.size();

    out.cycle_break_ffs = fvsFromMinimalCycles(std::move(minimal));

    std::unordered_set<int> removed;
    for (int v : out.cycle_break_ffs)
        removed.insert(v);

    if (!graphIsDAG(n, adj, removed)) {
        std::cerr << "Warning: sequential graph still has directed cycles after cycle-breaking "
                     "heuristic; depth reduction uses bounded path enumeration anyway.\n";
    }

    std::vector<std::vector<int>> longPaths;
    out.path_enum_cap_used = path_enum_cap;
    enumerateLongPaths(n, adj, removed, depth_threshold, path_enum_cap, longPaths);
    out.paths_long_recorded = (int)longPaths.size();

    out.depth_reduction_ffs =
        depthReductionGreedy(adj, n, std::move(removed), depth_threshold, path_enum_cap);

    std::set<int> uni(out.cycle_break_ffs.begin(), out.cycle_break_ffs.end());
    for (int v : out.depth_reduction_ffs)
        uni.insert(v);
    out.all_selected_ffs.assign(uni.begin(), uni.end());
    return out;
}

void printSeqGraphReport(const ScanData &data, const SeqGraphSelection &sel)
{
    std::cout << "Sequential FF graph analysis (reachability graph: F1→F2 if F2 is reachable "
                 "from F1 along one or more direct Q→D links)\n";
    if (sel.edges_missing) {
        if (!data.seq_netlist_loaded) {
            std::cout << "  No sequential edges — --seq-netlist <circuit.v> is required (FF "
                         "instance names should match FF_NAMES when possible).\n";
        } else {
            std::cout << "  No sequential edges after parsing the netlist — see stderr hints "
                         "above (direct Q→D nets only).\n";
        }
        return;
    }

    std::cout << "  Elementary cycles (enumerated): " << sel.cycle_count_raw << "\n";
    std::cout << "  Minimal cycles (non-embedded vertex sets): " << sel.cycle_count_minimal
              << "\n";
    std::cout << "  Cycle-breaking FFs (heuristic FVS): " << sel.cycle_break_ffs.size()
              << "\n";
    if (!sel.cycle_break_ffs.empty()) {
        std::cout << "    Indices:";
        for (int i : sel.cycle_break_ffs)
            std::cout << " " << i;
        std::cout << "\n";
        std::cout << "    Names:";
        for (int i : sel.cycle_break_ffs)
            std::cout << " " << data.ffs[i].name;
        std::cout << "\n";
    }

    std::cout << "  Depth-reduction FFs: " << sel.depth_reduction_ffs.size() << "\n";
    if (!sel.depth_reduction_ffs.empty()) {
        std::cout << "    Indices:";
        for (int i : sel.depth_reduction_ffs)
            std::cout << " " << i;
        std::cout << "\n";
        std::cout << "    Names:";
        for (int i : sel.depth_reduction_ffs)
            std::cout << " " << data.ffs[i].name;
        std::cout << "\n";
    }

    std::cout << "  Combined selected FFs: " << sel.all_selected_ffs.size() << "\n";
    if (!sel.all_selected_ffs.empty()) {
        std::cout << "    Indices:";
        for (int i : sel.all_selected_ffs)
            std::cout << " " << i;
        std::cout << "\n";
        std::cout << "    Names:";
        for (int i : sel.all_selected_ffs)
            std::cout << " " << data.ffs[i].name;
        std::cout << "\n";
    }
    std::cout << "  Long paths enumerated for depth pass (≤ cap): "
              << sel.paths_long_recorded << " / cap " << sel.path_enum_cap_used << "\n";
}

} // namespace ScanForge
