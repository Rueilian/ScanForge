// ScanForge — two_phase_justification_prototype.cpp
// C++ prototype implementation for Two-Phase State Justification in FAN_ATPG.

#include "atpg.h"
#include <map>
#include <vector>
#include <iostream>

namespace CoreNs {

/**
 * Perform backward sequential justification on the combinational circuit representation.
 * Virtual time frames: step = maxDepth-1 down to 0.
 *
 * @param requiredState The partial target state required at the observation frame.
 *                      Maps gateID (PPO/PPI slot) to required Value (L or H).
 * @param maxDepth The maximum unrolled time-frame depth (e.g., T=4).
 * @param prefixPatterns Out-parameter. If successful, appends the sequence of PI patterns.
 * @return True if a valid sequence of state justification transitions is found; false otherwise.
 */
bool Atpg::justifyStateSequentially(const std::map<int, Value>& requiredState,
                                    int maxDepth,
                                    std::vector<Pattern>& prefixPatterns)
{
    std::map<int, Value> currentState = requiredState;
    std::vector<Pattern> tempPatterns;

    // Save current circuit ATPG state to restore later in case of conflict
    std::vector<Value> savedValues(pCircuit_->circuitGates_.size());
    for (size_t g = 0; g < pCircuit_->circuitGates_.size(); ++g) {
        savedValues[g] = pCircuit_->circuitGates_[g].atpgVal_;
    }

    bool success = true;

    // Justify backward step-by-step
    for (int step = maxDepth - 1; step >= 0; --step)
    {
        // 1. Reset all gate ATPG values in the combinational circuit
        for (Gate& gate : pCircuit_->circuitGates_) {
            gate.atpgVal_ = X;
        }

        // 2. Apply target state assignments to the PPI gates (inputs of the non-scan FFs)
        for (const auto& assign : currentState) {
            int gateId = assign.first;
            Value val = assign.second;
            
            // Set the PPI value
            pCircuit_->circuitGates_[gateId].atpgVal_ = val;
        }

        // 3. Run combinational implication to propagate assignments
        if (pSimulator_->goodSim() == CONFLICT) {
            success = false;
            break;
        }

        // 4. Solve remaining objectives to justify the PPI values back to PIs and previous-state PPIs
        // We use FAN's findFinalObjective/implication loop.
        bool justified = true;
        int backtrackCount = 0;
        const int BACKTRACK_LIMIT = 500;

        while (true)
        {
            Gate* pObjectiveGate = nullptr;
            Value objectiveVal = X;
            
            // Find an unjustified objective feeding the PPI assignments
            findFinalObjective(&pObjectiveGate, objectiveVal);
            if (!pObjectiveGate) {
                // All objectives justified successfully
                break;
            }

            // Perform backtrack-based search step
            if (backtrackCount++ > BACKTRACK_LIMIT) {
                justified = false;
                break;
            }

            // Decide and imply
            Gate* pDecisionGate = nullptr;
            Value decisionVal = X;
            multipleBacktrace(pObjectiveGate, objectiveVal, &pDecisionGate, decisionVal);
            
            if (!pDecisionGate) {
                justified = false;
                break;
            }

            if (setGateAtpgValAndRunImplication(*pDecisionGate, decisionVal) == CONFLICT) {
                // Backtrack on decision
                if (setGateAtpgValAndRunImplication(*pDecisionGate, (decisionVal == H) ? L : H) == CONFLICT) {
                    justified = false;
                    break;
                }
            }
        }

        if (!justified) {
            success = false;
            break;
        }

        // 5. Success for this step! Extract the PI values and the previous-state requirements.
        Pattern stepPattern(pCircuit_);
        
        // Read Primary Inputs (PIs) for this step's pattern
        for (int j = 0; j < pCircuit_->numPI_; ++j) {
            stepPattern.PI1_[j] = pCircuit_->circuitGates_[j].atpgVal_;
        }

        // The previous-state requirement (at step-1) is defined by the values 
        // justified at the non-scan FF data inputs (PPOs) in this step.
        std::map<int, Value> previousState;
        for (int j = 0; j < pCircuit_->numPPI_; ++j) {
            if (pCircuit_->isPpiNonscan_[j]) {
                // Find the corresponding PPO driving this PPI
                int ppoGateId = pCircuit_->numGate_ - pCircuit_->numPPI_ + j;
                Value ppoVal = pCircuit_->circuitGates_[ppoGateId].atpgVal_;
                
                if (ppoVal != X) {
                    // Non-X value must be justified in the previous time step
                    // We map it to the corresponding PPI gate ID for the previous step
                    int ppiGateId = pCircuit_->numPI_ + j;
                    previousState[ppiGateId] = ppoVal;
                }
            }
        }

        tempPatterns.push_back(stepPattern);
        currentState = previousState;

        // If no requirements are left for the previous state, we are done early!
        if (currentState.empty()) {
            break;
        }
    }

    // Restore original ATPG circuit values
    for (size_t g = 0; g < pCircuit_->circuitGates_.size(); ++g) {
        pCircuit_->circuitGates_[g].atpgVal_ = savedValues[g];
    }

    if (success) {
        // Reverse the patterns since we justified backward
        std::reverse(tempPatterns.begin(), tempPatterns.end());
        prefixPatterns.insert(prefixPatterns.end(), tempPatterns.begin(), tempPatterns.end());
        return true;
    }

    return false;
}

} // namespace CoreNs
