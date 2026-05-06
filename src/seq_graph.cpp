// ScanForge — seq_graph.cpp
// Sequential FF graph analysis: elementary cycles, FVS heuristic, depth reduction.

#include "seq_graph.h"

#include <algorithm>
#include <functional>
#include <iostream>
#include <queue>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace ScanForge {

namespace {

// Iterative Tarjan's SCC.  Returns one vector<int> per SCC (any order, any size).
// O(V+E), no recursion (safe for large graphs).
std::vector<std::vector<int>> tarjanSCC(int n,
                                         const std::vector<std::vector<int>> &adj)
{
    std::vector<int>  disc(n, -1), low(n, 0);
    std::vector<bool> onStack(n, false);
    std::vector<int>  stk;
    std::vector<std::vector<int>> sccs;
    int timer = 0;

    // Explicit stack frame for iterative DFS.
    struct Frame {
        int v;
        int ei; // index into adj[v]
    };
    std::vector<Frame> dfsStack;

    for (int root = 0; root < n; ++root) {
        if (disc[root] != -1) continue;
        dfsStack.push_back({root, 0});
        disc[root] = low[root] = timer++;
        stk.push_back(root);
        onStack[root] = true;

        while (!dfsStack.empty()) {
            Frame &f = dfsStack.back();
            int v = f.v;
            if (f.ei < (int)adj[v].size()) {
                int w = adj[v][f.ei++];
                if (disc[w] == -1) {
                    disc[w] = low[w] = timer++;
                    stk.push_back(w);
                    onStack[w] = true;
                    dfsStack.push_back({w, 0});
                } else if (onStack[w]) {
                    low[v] = std::min(low[v], disc[w]);
                }
            } else {
                // Done with v — propagate low upward.
                dfsStack.pop_back();
                if (!dfsStack.empty())
                    low[dfsStack.back().v] = std::min(low[dfsStack.back().v], low[v]);
                // SCC root?
                if (low[v] == disc[v]) {
                    std::vector<int> scc;
                    while (true) {
                        int u = stk.back(); stk.pop_back();
                        onStack[u] = false;
                        scc.push_back(u);
                        if (u == v) break;
                    }
                    sccs.push_back(std::move(scc));
                }
            }
        }
    }
    return sccs;
}

// Count non-trivial (size > 1) SCCs in the subgraph induced by vertices not in `removed`.
// Returns the SCCs themselves (each sorted ascending).
std::vector<std::vector<int>> nonTrivialSCCs(int n,
                                              const std::vector<std::vector<int>> &adj,
                                              const std::unordered_set<int> &removed)
{
    // Build compact adjacency for live vertices.
    std::vector<int> live;
    live.reserve(n);
    for (int i = 0; i < n; ++i)
        if (!removed.count(i)) live.push_back(i);

    const int m = (int)live.size();
    std::unordered_map<int,int> id;
    id.reserve(static_cast<std::size_t>(m) * 2);
    for (int i = 0; i < m; ++i) id[live[i]] = i;

    std::vector<std::vector<int>> sub(m);
    for (int i = 0; i < m; ++i) {
        int v = live[i];
        for (int w : adj[v]) {
            if (removed.count(w)) continue;
            sub[i].push_back(id[w]);
        }
    }

    auto sccs = tarjanSCC(m, sub);

    std::vector<std::vector<int>> result;
    for (auto &scc : sccs) {
        if (scc.size() < 2) continue;
        std::vector<int> orig;
        orig.reserve(scc.size());
        for (int i : scc) orig.push_back(live[i]);
        std::sort(orig.begin(), orig.end());
        result.push_back(std::move(orig));
    }
    return result;
}

// Greedy SCC-based FVS: at each step pick the vertex with the highest combined
// (in + out) degree *within the current cyclic SCCs*, remove it, recompute SCCs.
// O(#removed × (V+E)) — practical for V ≤ ~2000.
std::vector<int> fvsFromSCCs(int n,
                              const std::vector<std::vector<int>> &adj,
                              std::unordered_set<int> removed)
{
    std::vector<int> selected;

    while (true) {
        auto sccs = nonTrivialSCCs(n, adj, removed);
        if (sccs.empty()) break;

        // Collect all vertices in cyclic SCCs and count intra-SCC degree.
        std::unordered_map<int, int> inDeg, outDeg;
        for (const auto &scc : sccs) {
            std::unordered_set<int> sccSet(scc.begin(), scc.end());
            for (int v : scc) {
                if (!inDeg.count(v)) inDeg[v] = 0;
                if (!outDeg.count(v)) outDeg[v] = 0;
                for (int w : adj[v]) {
                    if (removed.count(w) || !sccSet.count(w)) continue;
                    outDeg[v]++;
                    inDeg[w]++;
                }
            }
        }

        int best = -1;
        int bestScore = -1;
        for (const auto &kv : outDeg) {
            int v = kv.first;
            int score = outDeg[v] + inDeg[v];
            if (score > bestScore) { bestScore = score; best = v; }
        }
        if (best < 0) break;

        selected.push_back(best);
        removed.insert(best);
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

    // Count non-trivial SCCs (size > 1) before FVS.
    {
        std::unordered_set<int> noRemoved;
        auto sccs = nonTrivialSCCs(n, adj, noRemoved);
        out.cycle_count_raw = (int)sccs.size();   // repurposed: number of cyclic SCCs
        out.cycle_count_minimal = out.cycle_count_raw;
    }

    out.cycle_break_ffs = fvsFromSCCs(n, adj, {});

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
    std::cout << "Sequential FF graph analysis (edges: combinational reachability from each "
                 "FF's Q to another's D; no F0→F2 shortcut across intermediate FFs)\n";
    if (sel.edges_missing) {
        if (!data.seq_netlist_loaded) {
            std::cout << "  No sequential edges — --seq-netlist <circuit.v> is required (FF "
                         "instance names should match FF_NAMES when possible).\n";
        } else {
            std::cout << "  No sequential edges after parsing the netlist — see stderr hints "
                         "above.\n";
        }
        return;
    }

    std::cout << "  Cyclic SCCs (non-trivial strongly-connected components): "
              << sel.cycle_count_raw << "\n";
    std::cout << "  Cycle-breaking FFs (heuristic FVS via SCC greedy): "
              << sel.cycle_break_ffs.size() << "\n";
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
